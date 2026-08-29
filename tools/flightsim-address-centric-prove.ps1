#Requires -Version 5.1
<#
.SYNOPSIS
  FlightSim migrate + address-centric email e2e prove with startmb-equivalent env.

.DESCRIPTION
  startmb.cmd loads config\memorybox_app.env only inside its PowerShell process.
  Parent cmd.exe (and a bare `python -m memorybox …`) does not inherit those vars,
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

Import-DotEnvFile (Join-Path $Root "config\memorybox_app.env")
Import-DotEnvFile (Join-Path $Root "config\memorybox_sources.env")
if (-not $env:MEMORYBOX_DATABASE_URL) {
  $env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
}
if (-not $env:MEMORYBOX_QDRANT_URL) {
  $env:MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"
}
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"

Write-Host "MEMORYBOX_DATABASE_URL set: $([bool]$env:MEMORYBOX_DATABASE_URL)"
Write-Host "MEMORYBOX_P1_RUNTIME_HOST=$($env:MEMORYBOX_P1_RUNTIME_HOST)"
Write-Host "ALLOW_DEV_DEFAULTS=$($env:MEMORYBOX_ALLOW_DEV_DEFAULTS)"

# startmb -Restart can leave migrate racing Postgres/Docker bring-up.
Write-Host "==> waiting for Postgres :5432 (up to ${DbWaitSec}s)"
$deadline = (Get-Date).AddSeconds($DbWaitSec)
while ((Get-Date) -lt $deadline) {
  if (Test-TcpPort "127.0.0.1" 5432) { break }
  Start-Sleep -Seconds 2
}
if (-not (Test-TcpPort "127.0.0.1" 5432)) {
  Write-Host "ERROR: Postgres not reachable on 127.0.0.1:5432 after ${DbWaitSec}s" -ForegroundColor Red
  Write-Host "Start Docker / memorybox-pg (startmb.cmd), then re-run."
  exit 1
}

$healthOk = $false
$healthDeadline = (Get-Date).AddSeconds([Math]::Min(60, $DbWaitSec))
while ((Get-Date) -lt $healthDeadline) {
  python -m memorybox health 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    $healthOk = $true
    break
  }
  Start-Sleep -Seconds 2
}
if (-not $healthOk) {
  Write-Host "WARNING: memorybox health not green yet — continuing to migrate" -ForegroundColor Yellow
}

python -m memorybox migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m memorybox prove-address-centric-email-e2e --flightsim
exit $LASTEXITCODE
