#Requires -Version 5.1
<#
.SYNOPSIS
  FlightSim cold-boot: Docker PG/Qdrant + video worker + MemoryBox serve + Chrome Explore.

.DESCRIPTION
  Run from \\flightsim\memorybox (or C:\memorybox) after login.
  Docker Desktop is expected to auto-start on login; this script waits for the
  engine, ensures memorybox-pg / memorybox-qdrant, starts worker (:8791) and
  serve (:8790) in separate windows, then opens Explore in Chrome.

.NOTES
  See startme.readme for the runbook.
#>
[CmdletBinding()]
param(
  [ValidateSet("all", "worker", "serve")]
  [string]$Role = "all",
  [string]$ExploreUrl = "http://127.0.0.1:8790/explore/ui",
  [string]$ServeHost = "127.0.0.1",
  [int]$ServePort = 8790,
  [int]$WorkerPort = 8791,
  [int]$DockerWaitSec = 180,
  [int]$HealthWaitSec = 120,
  [switch]$SkipChrome,
  [switch]$RecreateContainers,
  [switch]$Restart
)

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location $Root

function Write-Step([string]$Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-TcpPort([string]$TargetHost, [int]$Port, [int]$TimeoutMs = 800) {
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect($TargetHost, $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
    if (-not $ok) {
      $client.Close()
      return $false
    }
    $client.EndConnect($iar)
    $client.Close()
    return $true
  } catch {
    return $false
  }
}

function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
  Write-Host "  loading $Path"
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path "Env:$name" -Value $value
  }
}

function Load-MbEnv {
  Import-DotEnvFile (Join-Path $Root "config\memorybox_app.env")
  Import-DotEnvFile (Join-Path $Root "config\video_worker.env")
  Import-DotEnvFile (Join-Path $Root "config\memorybox_sources.env")
  if (-not $env:MEMORYBOX_DATABASE_URL) {
    $env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
  }
  if (-not $env:MEMORYBOX_QDRANT_URL) {
    $env:MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"
  }
  if (-not $env:MEMORYBOX_QDRANT_COLLECTION) {
    $env:MEMORYBOX_QDRANT_COLLECTION = "memorybox_evidence"
  }
  if (-not $env:MEMORYBOX_HOST) { $env:MEMORYBOX_HOST = "0.0.0.0" }
  if (-not $env:MEMORYBOX_PORT) { $env:MEMORYBOX_PORT = "$ServePort" }
  if (-not $env:MEMORYBOX_P1_RUNTIME_HOST) { $env:MEMORYBOX_P1_RUNTIME_HOST = "1" }
  if (-not $env:MEMORYBOX_PHOTO_PROVIDER) { $env:MEMORYBOX_PHOTO_PROVIDER = "immich" }
  if (-not $env:MEMORYBOX_VIDEO_PROVIDER) { $env:MEMORYBOX_VIDEO_PROVIDER = "hvrt" }
  if (-not $env:MEMORYBOX_VIDEO_WORKER_URL) {
    $env:MEMORYBOX_VIDEO_WORKER_URL = "http://127.0.0.1:$WorkerPort"
  }
  if (-not $env:MEMORYBOX_VIDEO_WORKER_HOST) { $env:MEMORYBOX_VIDEO_WORKER_HOST = "127.0.0.1" }
  if (-not $env:MEMORYBOX_VIDEO_WORKER_PORT) { $env:MEMORYBOX_VIDEO_WORKER_PORT = "$WorkerPort" }
  $flightsimHomeVideos = "P:\photos\home videos"
  if (-not $env:MEMORYBOX_VIDEO_MEDIA_ROOT) {
    $env:MEMORYBOX_VIDEO_MEDIA_ROOT = $flightsimHomeVideos
  }
  if ($env:MEMORYBOX_VIDEO_MEDIA_ROOT -and -not (Test-Path -LiteralPath $env:MEMORYBOX_VIDEO_MEDIA_ROOT)) {
    if (Test-Path -LiteralPath $flightsimHomeVideos) {
      Write-Host "  WARNING: MEMORYBOX_VIDEO_MEDIA_ROOT=$($env:MEMORYBOX_VIDEO_MEDIA_ROOT) is not a readable folder. Using $flightsimHomeVideos" -ForegroundColor Yellow
      $env:MEMORYBOX_VIDEO_MEDIA_ROOT = $flightsimHomeVideos
    }
  }
  $immichPath = Join-Path $Root "config\immich.env"
  if (-not $env:MEMORYBOX_IMMICH_ENV -and (Test-Path -LiteralPath $immichPath)) {
    $env:MEMORYBOX_IMMICH_ENV = $immichPath
  }
  if (Test-Path -LiteralPath $immichPath) {
    $immichText = Get-Content -LiteralPath $immichPath -Raw
    if ($immichText -match "(?i)media-server") {
      Write-Host "  WARNING: config\immich.env still mentions media-server. Immich is on FlightSim - see docs\ops\FLIGHTSIM_IMMICH_CUTOVER.md" -ForegroundColor Yellow
    }
  }
}

function Resolve-Python {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $cmd) { $cmd = Get-Command py -ErrorAction SilentlyContinue }
  if (-not $cmd) { throw "python not found on PATH" }
  return $cmd.Source
}

function Add-DirToUserPath([string]$Dir) {
  if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { return }
  $env:Path = "$Dir;" + $env:Path
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($null -eq $userPath) { $userPath = "" }
  $parts = @($userPath -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  $already = $false
  foreach ($p in $parts) {
    if ([string]::Equals($p, $Dir, [StringComparison]::OrdinalIgnoreCase)) { $already = $true; break }
  }
  if (-not $already) {
    $next = if ($userPath.Trim()) { "$Dir;$userPath" } else { $Dir }
    [Environment]::SetEnvironmentVariable("Path", $next, "User")
    Write-Host "  User PATH += $Dir (open a new PowerShell for psql)"
  }
}

function Ensure-PsqlOnPath {
  Write-Step "Ensuring psql is on PATH"
  $existing = Get-Command psql -ErrorAction SilentlyContinue
  if ($existing) {
    Write-Host "  psql already on PATH: $($existing.Source)"
    return
  }
  $nativeDir = $null
  $pgRoot = Join-Path ${env:ProgramFiles} "PostgreSQL"
  if (Test-Path -LiteralPath $pgRoot) {
    $hit = Get-ChildItem -LiteralPath $pgRoot -Directory -ErrorAction SilentlyContinue |
      ForEach-Object { Join-Path $_.FullName "bin\psql.exe" } |
      Where-Object { Test-Path -LiteralPath $_ } |
      Select-Object -First 1
    if ($hit) { $nativeDir = Split-Path -Parent $hit }
  }
  if ($nativeDir) {
    Add-DirToUserPath $nativeDir
    Write-Host "  using Windows PostgreSQL client: $nativeDir"
    return
  }
  $tools = Join-Path $Root "tools"
  if (-not (Test-Path -LiteralPath (Join-Path $tools "psql.cmd"))) {
    Write-Host "  WARNING: no Windows psql.exe and no $tools\psql.cmd. Use: docker exec -it memorybox-pg psql -U memorybox -d memorybox" -ForegroundColor Yellow
    return
  }
  Add-DirToUserPath $tools
  Write-Host "  FlightSim Postgres is Docker (memorybox-pg). tools\psql.cmd is now on PATH."
}

function Wait-DockerReady([int]$Seconds) {
  Write-Step "Waiting for Docker engine (up to ${Seconds}s)"
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      docker info 1>$null 2>$null
      if ($LASTEXITCODE -eq 0) {
        Write-Host "  Docker is ready."
        return
      }
    } catch { }
    Start-Sleep -Seconds 3
  }
  throw "Docker did not become ready within ${Seconds}s. Confirm Docker Desktop auto-start on login."
}

function Ensure-Container {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][scriptblock]$Create,
    [switch]$Recreate
  )
  $names = @(docker ps -a --format "{{.Names}}" 2>$null)
  $exists = $names -contains $Name
  if ($Recreate -and $exists) {
    Write-Host "  recreating $Name"
    docker rm -f $Name 1>$null
    $exists = $false
  }
  if (-not $exists) {
    Write-Host "  creating $Name"
    & $Create
    if ($LASTEXITCODE -ne 0) { throw "Failed to create container $Name" }
  } else {
    $running = @((docker ps --format "{{.Names}}" 2>$null)) -contains $Name
    if (-not $running) {
      Write-Host "  starting $Name"
      docker start $Name 1>$null
      if ($LASTEXITCODE -ne 0) { throw "Failed to start container $Name" }
    } else {
      Write-Host "  $Name already running"
    }
  }
}

function Stop-MbListenPort([int]$Port) {
  $procIds = @()
  try {
    $procIds = @(
      Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
        Select-Object -ExpandProperty OwningProcess -Unique
    )
  } catch {
    foreach ($line in (netstat -ano)) {
      if ($line -match (":$Port\s+.+LISTENING\s+(\d+)\s*$")) {
        $procIds += [int]$Matches[1]
      }
    }
  }
  foreach ($procId in ($procIds | Select-Object -Unique)) {
    if (-not $procId -or $procId -le 4) { continue }
    Write-Host "  stopping PID $procId on :$Port"
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
}

function Wait-Tcp([string]$Label, [string]$TargetHost, [int]$Port, [int]$Seconds) {
  Write-Host "  waiting for $Label ${TargetHost}:${Port} ..."
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-TcpPort $TargetHost $Port) {
      Write-Host "  $Label is listening."
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "$Label did not listen on ${TargetHost}:${Port} within ${Seconds}s"
}

function Wait-HttpOk([string]$Url, [int]$Seconds) {
  Write-Host "  waiting for $Url ..."
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        Write-Host "  HTTP $($resp.StatusCode) from $Url"
        return
      }
    } catch { }
    Start-Sleep -Seconds 2
  }
  throw "Timed out waiting for $Url"
}

function Start-MbRoleWindow([string]$Title, [string]$ChildRole) {
  $scriptPath = Join-Path $Root "startmb.ps1"
  Start-Process -FilePath "powershell.exe" -WorkingDirectory $Root -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $scriptPath,
    "-Role", $ChildRole
  ) | Out-Null
}

# Child windows: load env and run one process in the foreground
if ($Role -eq "worker" -or $Role -eq "serve") {
  $Host.UI.RawUI.WindowTitle = "MemoryBox $Role"
  Load-MbEnv
  $PythonExe = Resolve-Python
  if ($Role -eq "worker") {
    Write-Host "Starting video worker on :$($env:MEMORYBOX_VIDEO_WORKER_PORT)"
    Write-Host "  VIDEO_MEDIA_ROOT=$($env:MEMORYBOX_VIDEO_MEDIA_ROOT)"
    & $PythonExe -m memorybox.video_worker
    exit $LASTEXITCODE
  }
  Write-Host "Starting serve on :$($env:MEMORYBOX_PORT)"
  & $PythonExe -m memorybox serve
  exit $LASTEXITCODE
}

# --- orchestrator (Role=all) ---
Write-Host "startmb - MemoryBox FlightSim cold boot"
Write-Host "root: $Root"

Write-Step "Loading local env files (if present)"
Load-MbEnv
Write-Host "  DATABASE_URL set: $([bool]$env:MEMORYBOX_DATABASE_URL)"
Write-Host "  QDRANT_URL=$($env:MEMORYBOX_QDRANT_URL)"
Write-Host "  VIDEO_WORKER_URL=$($env:MEMORYBOX_VIDEO_WORKER_URL)"
Write-Host "  VIDEO_MEDIA_ROOT=$($env:MEMORYBOX_VIDEO_MEDIA_ROOT)"
Write-Host "  IMMICH_ENV=$($env:MEMORYBOX_IMMICH_ENV)"

Ensure-PsqlOnPath

Wait-DockerReady -Seconds $DockerWaitSec

Write-Step "Ensuring Postgres + Qdrant containers"
Ensure-Container -Name "memorybox-pg" -Recreate:$RecreateContainers -Create {
  docker run -d --name memorybox-pg `
    -e POSTGRES_USER=memorybox `
    -e POSTGRES_PASSWORD=memorybox `
    -e POSTGRES_DB=memorybox `
    -p 5432:5432 `
    -v memorybox_pg_data:/var/lib/postgresql/data `
    postgres:16-alpine
}
Ensure-Container -Name "memorybox-qdrant" -Recreate:$RecreateContainers -Create {
  docker run -d --name memorybox-qdrant `
    -p 6333:6333 `
    -v memorybox_qdrant_data:/qdrant/storage `
    qdrant/qdrant
}
Wait-Tcp "Postgres" "127.0.0.1" 5432 60
Wait-Tcp "Qdrant" "127.0.0.1" 6333 60

$null = Resolve-Python

if ($Restart) {
  Write-Step "Restart: stopping listeners on :$WorkerPort and :$ServePort"
  Stop-MbListenPort $WorkerPort
  Stop-MbListenPort $ServePort
  Start-Sleep -Seconds 1
}

Write-Step "Video worker (:$WorkerPort)"
if (Test-TcpPort "127.0.0.1" $WorkerPort) {
  Write-Host "  already listening - leaving existing worker alone"
} else {
  Start-MbRoleWindow -Title "MemoryBox video worker :$WorkerPort" -ChildRole "worker"
  Wait-Tcp "video worker" "127.0.0.1" $WorkerPort $HealthWaitSec
}

Write-Step "Ask / serve (:$ServePort)"
if (Test-TcpPort "127.0.0.1" $ServePort) {
  Write-Host "  already listening - leaving existing serve alone"
} else {
  Start-MbRoleWindow -Title "MemoryBox serve :$ServePort" -ChildRole "serve"
  Wait-HttpOk "http://${ServeHost}:${ServePort}/health" $HealthWaitSec
}

if (-not $SkipChrome) {
  Write-Step "Opening Chrome -> $ExploreUrl"
  $chromeCandidates = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  $chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if ($chrome) {
    Start-Process -FilePath $chrome -ArgumentList $ExploreUrl | Out-Null
  } else {
    Write-Host "  Chrome not found - opening default browser"
    Start-Process $ExploreUrl | Out-Null
  }
}

Write-Step "Done"
Write-Host "  Explore: $ExploreUrl"
Write-Host "  Health:  http://${ServeHost}:${ServePort}/health"
Write-Host "  Worker:  listening on :$WorkerPort"
Write-Host "  Leave the worker and serve PowerShell windows open."
