#Requires -Version 5.1
<#
.SYNOPSIS
  FlightSim trusted-identity Phase 2/3 with startmb-equivalent env.

.DESCRIPTION
  startmb.cmd loads config\memorybox_app.env only inside PowerShell.
  Parent cmd.exe `python -m memorybox` can miss Takeout DATABASE_URL and
  MEMORYBOX_CLOUD_LLM_*. Address-centric prove.ps1 is the path that worked.
  Restricted policy blocks a double-clicked .ps1 — gate.cmd launches this
  with System32 powershell -ExecutionPolicy Bypass.
#>
[CmdletBinding()]
param(
  [ValidateSet("Migrate", "Phase1", "Preflight", "Freeze", "Pipeline", "Verify", "Chunks")]
  [string]$Step = "Freeze",
  [int]$DbWaitSec = 90
)

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) {
  Split-Path -Parent $PSScriptRoot
} else {
  Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
Set-Location $Root
$OutDir = Join-Path $Root "docs\test-output\trusted-full-evidence-v2"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

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
    if (-not $ok) { $client.Close(); return $false }
    $client.EndConnect($iar)
    $client.Close()
    return $true
  } catch {
    return $false
  }
}

function Resolve-Python {
  foreach ($name in @("py", "python")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and ($cmd.Source -notmatch "WindowsApps")) {
      return $cmd.Source
    }
  }
  Write-Host "ERROR: python/py not found (or only WindowsApps stub)" -ForegroundColor Red
  exit 1
}

Import-DotEnvFile (Join-Path $Root "config\memorybox_app.env")
Import-DotEnvFile (Join-Path $Root "config\video_worker.env")
Import-DotEnvFile (Join-Path $Root "config\memorybox_sources.env")
if (-not $env:MEMORYBOX_DATABASE_URL) {
  $env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
}
if (-not $env:MEMORYBOX_QDRANT_URL) {
  $env:MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"
}
if (-not $env:MEMORYBOX_OLLAMA_BASE_URL) {
  $env:MEMORYBOX_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
}
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
Remove-Item Env:MEMORYBOX_ALLOW_DEV_DEFAULTS -ErrorAction SilentlyContinue

$hostName = "127.0.0.1"
$port = 5432
if ($env:MEMORYBOX_DATABASE_URL -match '@([^/:]+)(?::(\d+))?') {
  $hostName = $Matches[1]
  if ($Matches[2]) { $port = [int]$Matches[2] }
}
Write-Host "hostname=$([System.Net.Dns]::GetHostName()) step=$Step"
Write-Host "MEMORYBOX_P1_RUNTIME_HOST=$($env:MEMORYBOX_P1_RUNTIME_HOST)"
Write-Host "ALLOW_DEV_DEFAULTS=$($env:MEMORYBOX_ALLOW_DEV_DEFAULTS)"
Write-Host "CLOUD_LLM_MODEL=$($env:MEMORYBOX_CLOUD_LLM_MODEL)"
Write-Host "CLOUD_LLM_KEY_SET=$([bool]$env:MEMORYBOX_CLOUD_LLM_API_KEY)"

$deadline = (Get-Date).AddSeconds($DbWaitSec)
while ((Get-Date) -lt $deadline) {
  if (Test-TcpPort $hostName $port) { break }
  Start-Sleep -Seconds 2
}
if (-not (Test-TcpPort $hostName $port)) {
  Write-Host "ERROR: Postgres not reachable on ${hostName}:${port}" -ForegroundColor Red
  exit 1
}

$Python = Resolve-Python
Write-Host "python=$Python"

function Invoke-Mb([string[]]$MbArgs) {
  Write-Host ("==> " + ($MbArgs -join " "))
  $p = Start-Process -FilePath $Python `
    -ArgumentList (@("-u") + $MbArgs) `
    -WorkingDirectory $Root `
    -Wait -PassThru -NoNewWindow
  if ($p.ExitCode -ne 0) { exit $p.ExitCode }
}

switch ($Step) {
  "Migrate" {
    Invoke-Mb @("-m", "memorybox", "migrate")
  }
  "Phase1" {
    Invoke-Mb @("-m", "memorybox", "prove-trusted-identity-retrieval", "--flightsim")
    $v = Start-Process -FilePath $Python `
      -ArgumentList @("-u", (Join-Path $Root "tools\verify-trusted-identity-gate.py")) `
      -WorkingDirectory $Root -Wait -PassThru -NoNewWindow
    if ($v.ExitCode -ne 0) { exit $v.ExitCode }
  }
  "Preflight" {
    Invoke-Mb @("-m", "memorybox", "fev2-preflight", "--out-dir", $OutDir)
  }
  "Freeze" {
    Invoke-Mb @(
      "-m", "memorybox", "freeze-trusted-full-evidence-v2",
      "--person", "Peggy George",
      "--out-dir", $OutDir,
      "--reuse-if-coverage-ok"
    )
  }
  "Pipeline" {
    Invoke-Mb @(
      "-m", "memorybox", "run-trusted-evidence-pipeline",
      "--person", "Peggy George",
      "--flightsim"
    )
  }
  "Verify" {
    $v = Start-Process -FilePath $Python `
      -ArgumentList @("-u", (Join-Path $Root "tools\verify-trusted-fev2-reports.py")) `
      -WorkingDirectory $Root -Wait -PassThru -NoNewWindow
    if ($v.ExitCode -ne 0) { exit $v.ExitCode }
  }
  "Chunks" {
    Invoke-Mb @(
      "-m", "memorybox", "run-trusted-fev2-chunked-models",
      "--from-dir", $OutDir
    )
  }
}

exit 0
