#Requires -Version 5.1
<#
.SYNOPSIS
  FlightSim migrate + address-centric email e2e prove with startmb-equivalent env.

.DESCRIPTION
  startmb.cmd loads config\memorybox_app.env only inside its PowerShell process.
  Parent cmd.exe (and a bare `python -m memorybox ...`) does not inherit those vars,
  so prove can silently use MEMORYBOX_ALLOW_DEV_DEFAULTS localhost defaults and
  miss the Takeout archive. This script loads the same dotenv files as startmb,
  sets P1=1, waits for Postgres after startmb -Restart, then migrate + prove.
#>
[CmdletBinding()]
param(
  [int]$DbWaitSec = 90
)

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) {
  Split-Path -Parent $PSScriptRoot
} else {
  Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
Set-Location $Root

# Sentinel so gate.cmd can tell prove.ps1 actually started (vs watchdog stub exit 0).
$outDirEarly = Join-Path $Root "docs\test-output\historian-full-evidence\peggy-v2"
New-Item -ItemType Directory -Force -Path $outDirEarly | Out-Null
$startedPath = Join-Path $outDirEarly "ADDRESS_CENTRIC_PROVE_STARTED.txt"
$utf8s = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText(
  $startedPath,
  ("started={0} pid={1} root={2}`n" -f (Get-Date).ToUniversalTime().ToString("o"), $PID, $Root),
  $utf8s
)
Write-Host "PROVE_PS1_STARTED $startedPath"

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

function Write-AddressCentricGateFailure([string]$ErrorCode, [string]$Detail) {
  <#
  .SYNOPSIS
    Emit ADDRESS_CENTRIC_GATE.json even when prove never starts (env/DB/preflight).
    Without this, gate.cmd cannot push results and the cloud agent stays on waiting:true.
  #>
  $outDir = Join-Path $Root "docs\test-output\historian-full-evidence\peggy-v2"
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
  $gitHead = ""
  try { $gitHead = (& git rev-parse HEAD 2>$null) } catch {}
  $hostName = [System.Net.Dns]::GetHostName()
  $gate = @{
    gate = "address_centric_email_identity"
    ok = $false
    flightsim = $true
    waiting = $false
    error = $ErrorCode
    problems = @("$ErrorCode`: $Detail")
    runtime = @{
      git_head = "$gitHead"
      hostname = "$hostName"
      p1_runtime_host = $true
      database_url_set = [bool]$env:MEMORYBOX_DATABASE_URL
      allow_dev_defaults = [bool]$env:MEMORYBOX_ALLOW_DEV_DEFAULTS
      flightsim = $true
    }
  }
  $gatePath = Join-Path $outDir "ADDRESS_CENTRIC_GATE.json"
  $verdictPath = Join-Path $outDir "ADDRESS_CENTRIC_VERDICT.txt"
  $failPath = Join-Path $outDir "ADDRESS_CENTRIC_FAILURE_DIAG.json"
  # UTF-8 without BOM - Windows PS 5.1 Set-Content -Encoding UTF8 writes BOM,
  # which breaks strict json.loads on the results branch.
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($gatePath, (($gate | ConvertTo-Json -Depth 6) + "`n"), $utf8)
  [System.IO.File]::WriteAllText(
    $verdictPath,
    "VERDICT ok=False flightsim=True git_head=$gitHead hostname=$hostName error=$ErrorCode`n",
    $utf8
  )
  $failDoc = @{
    ok = $false
    problems = $gate.problems
    flightsim = $true
    waiting = $false
    error = $ErrorCode
    runtime = $gate.runtime
    hint = "Pre-prove failure on FlightSim - fix env/DB then re-run tools\flightsim-address-centric-gate.cmd"
  }
  [System.IO.File]::WriteAllText($failPath, (($failDoc | ConvertTo-Json -Depth 6) + "`n"), $utf8)
  Write-Host "Wrote failure gate: $gatePath" -ForegroundColor Yellow
}

$appEnv = Join-Path $Root "config\memorybox_app.env"
if (-not (Test-Path -LiteralPath $appEnv)) {
  Write-Host "ERROR: missing $appEnv - FlightSim prove needs the Takeout archive DSN." -ForegroundColor Red
  Write-Host "Create it from config\memorybox_app.env.example (do not commit secrets)."
  Write-AddressCentricGateFailure "missing_memorybox_app_env" $appEnv
  exit 1
}
Import-DotEnvFile $appEnv
Import-DotEnvFile (Join-Path $Root "config\memorybox_sources.env")
if (-not $env:MEMORYBOX_DATABASE_URL) {
  Write-Host "ERROR: MEMORYBOX_DATABASE_URL unset after loading $appEnv" -ForegroundColor Red
  Write-AddressCentricGateFailure "memorybox_database_url_unset" $appEnv
  exit 1
}
if (-not $env:MEMORYBOX_QDRANT_URL) {
  $env:MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"
}
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
# FlightSim must not fall back to empty ALLOW_DEV stores.
Remove-Item Env:MEMORYBOX_ALLOW_DEV_DEFAULTS -ErrorAction SilentlyContinue

function Get-DbEndpoint([string]$Url) {
  # postgresql://user:pass@host:5432/db  or  host without port -> 5432
  $hostName = "127.0.0.1"
  $port = 5432
  try {
    if ($Url -match '@([^/:]+)(?::(\d+))?') {
      $hostName = $Matches[1]
      if ($Matches[2]) { $port = [int]$Matches[2] }
    }
  } catch {}
  return @{ Host = $hostName; Port = $port }
}

function Get-RedactedDbHost([string]$Url) {
  return (Get-DbEndpoint $Url).Host
}

$DbEp = Get-DbEndpoint $env:MEMORYBOX_DATABASE_URL
Write-Host "hostname=$([System.Net.Dns]::GetHostName())"
Write-Host "MEMORYBOX_DATABASE_URL set: $([bool]$env:MEMORYBOX_DATABASE_URL) host=$($DbEp.Host) port=$($DbEp.Port)"
Write-Host "MEMORYBOX_P1_RUNTIME_HOST=$($env:MEMORYBOX_P1_RUNTIME_HOST)"
Write-Host "ALLOW_DEV_DEFAULTS=$($env:MEMORYBOX_ALLOW_DEV_DEFAULTS)"

# startmb -Restart can leave migrate racing Postgres/Docker bring-up.
Write-Host "==> waiting for Postgres $($DbEp.Host):$($DbEp.Port) (up to ${DbWaitSec}s)"
$deadline = (Get-Date).AddSeconds($DbWaitSec)
while ((Get-Date) -lt $deadline) {
  if (Test-TcpPort $DbEp.Host $DbEp.Port) { break }
  Start-Sleep -Seconds 2
}
if (-not (Test-TcpPort $DbEp.Host $DbEp.Port)) {
  Write-Host "ERROR: Postgres not reachable on $($DbEp.Host):$($DbEp.Port) after ${DbWaitSec}s" -ForegroundColor Red
  Write-Host "Start Docker / memorybox-pg (startmb.cmd), then re-run."
  Write-AddressCentricGateFailure "postgres_unreachable" "$($DbEp.Host):$($DbEp.Port)"
  exit 1
}

function Resolve-Python {
  foreach ($name in @("py", "python")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and ($cmd.Source -notmatch "WindowsApps")) {
      return $cmd.Source
    }
  }
  Write-Host "ERROR: python/py not found on PATH (or only WindowsApps stub)" -ForegroundColor Red
  Write-AddressCentricGateFailure "python_not_found" "PATH missing real python/py"
  exit 1
}

$Python = Resolve-Python
Write-Host "python=$Python"

$healthOk = $false
$healthDeadline = (Get-Date).AddSeconds([Math]::Min(60, $DbWaitSec))
while ((Get-Date) -lt $healthDeadline) {
  & $Python -m memorybox health 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    $healthOk = $true
    break
  }
  Start-Sleep -Seconds 2
}
if (-not $healthOk) {
  Write-Host "WARNING: memorybox health not green yet - continuing to migrate" -ForegroundColor Yellow
}

& $Python -m memorybox migrate
if ($LASTEXITCODE -ne 0) {
  Write-AddressCentricGateFailure "migrate_failed" "exit=$LASTEXITCODE"
  exit $LASTEXITCODE
}

# Advisory preflight - do NOT hard-exit here. prove-address-centric-email-e2e
# always writes ADDRESS_CENTRIC_GATE.json (incl. missing-structured failure),
# which gate.cmd force-pushes to the results branch for the cloud agent.
Write-Host "==> preflight probe peggo417@hotmail.com (advisory; prove owns gate artifacts)"
& $Python -m memorybox probe-email-address --address peggo417@hotmail.com --flightsim --require-structured-hits
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARNING: probe-email-address failed or structured occurrence_count=0 - continuing to prove for gate artifacts." -ForegroundColor Yellow
}

$outDir = Join-Path $Root "docs\test-output\historian-full-evidence\peggy-v2"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$gateJson = Join-Path $outDir "ADDRESS_CENTRIC_GATE.json"
$verdictPath = Join-Path $outDir "ADDRESS_CENTRIC_VERDICT.txt"
$auditPath = Join-Path $outDir "ADDRESS_CENTRIC_AUDIT.json"
$proveLog = Join-Path $outDir "ADDRESS_CENTRIC_PROVE.log"
$proveErr = Join-Path $outDir "ADDRESS_CENTRIC_PROVE.err.log"
$env:MEMORYBOX_ADDRESS_CENTRIC_OUT = $outDir

# Start-Process ExitCode is reliable on Windows PS 5.1. Native LASTEXITCODE
# can stay 0 from migrate/probe when the prove process never updates it.
# Tee-Object also clobbers LASTEXITCODE. That produced gate.cmd stub
# gate_cmd_stub_missing_prove_artifacts / prove_exit=0.
Write-Host "==> prove-address-centric-email-e2e --flightsim (cwd=$Root)"
if (Test-Path -LiteralPath $proveLog) { Remove-Item -LiteralPath $proveLog -Force }
if (Test-Path -LiteralPath $proveErr) { Remove-Item -LiteralPath $proveErr -Force }
$proveProc = Start-Process -FilePath $Python `
  -ArgumentList @("-u", "-m", "memorybox", "prove-address-centric-email-e2e", "--flightsim") `
  -WorkingDirectory $Root `
  -Wait -PassThru -NoNewWindow `
  -RedirectStandardOutput $proveLog `
  -RedirectStandardError $proveErr
$proveExit = $proveProc.ExitCode
Write-Host ("prove python ExitCode=" + $proveExit + " log=" + $proveLog)
if (Test-Path -LiteralPath $proveErr) {
  $errTail = Get-Content -LiteralPath $proveErr -Tail 40 -ErrorAction SilentlyContinue
  if ($errTail) { Write-Host ($errTail -join "`n") -ForegroundColor Yellow }
}

if (-not (Test-Path -LiteralPath $gateJson)) {
  $detail = "exit=$proveExit cwd=$Root python=$Python gate_missing_after_e2e"
  Write-AddressCentricGateFailure "prove_exit_ok_but_gate_missing" $detail
  if ($proveExit -eq 0) { $proveExit = 2 }
}

# Requirement audit - stamps goal_complete for the cloud agent / results branch.
$verifyPy = Join-Path $Root "tools\verify-address-centric-gate.py"
if ((Test-Path -LiteralPath $gateJson) -and (Test-Path -LiteralPath $verifyPy)) {
  Write-Host "==> verify-address-centric-gate (goal_complete requires ok+flightsim)"
  $auditJson = & $Python $verifyPy $gateJson 2>&1 | Out-String
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($auditPath, $auditJson, $utf8)
  $goalComplete = $false
  try {
    $auditObj = $auditJson | ConvertFrom-Json
    $goalComplete = [bool]$auditObj.goal_complete
  } catch {}
  if (Test-Path -LiteralPath $verdictPath) {
    Add-Content -LiteralPath $verdictPath -Value ("GOAL_COMPLETE=" + $goalComplete) -Encoding ascii
  }
  Write-Host ("GOAL_COMPLETE=" + $goalComplete)
}

exit $proveExit
