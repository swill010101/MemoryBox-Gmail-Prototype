#Requires -Version 5.1
<#
.SYNOPSIS
  Run startmb or address-centric prove under a wall-clock watchdog.

.DESCRIPTION
  Nested powershell -Command one-liners inside gate.cmd are fragile on Windows
  (quote/caret escaping). This script is the durable watchdog: on timeout it
  taskkill /T the process tree and exits 98 (startmb) or 99 (prove) so gate.cmd
  can write a failure gate and force-push the results branch.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("startmb", "prove")]
  [string]$Target,

  [Parameter(Mandatory = $true)]
  [int]$TimeoutSec,

  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $RepoRoot = Split-Path -Parent $PSScriptRoot
}
Set-Location -LiteralPath $RepoRoot

if ($TimeoutSec -lt 30) {
  Write-Host "ERROR: TimeoutSec must be >= 30 (got $TimeoutSec)" -ForegroundColor Red
  exit 1
}
$timeoutMs = [Math]::Min([int64]$TimeoutSec * 1000, [int64][int]::MaxValue)

function Stop-ProcessTree([System.Diagnostics.Process]$Proc) {
  if ($null -eq $Proc) { return }
  $procId = $Proc.Id
  try {
    & cmd.exe /c "taskkill /F /T /PID $procId" 2>$null | Out-Null
  } catch {}
  try {
    if (-not $Proc.HasExited) { $Proc.Kill() }
  } catch {}
}

if ($Target -eq "startmb") {
  Write-Host "watchdog startmb timeout=${TimeoutSec}s cwd=$RepoRoot"
  $p = Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", ".\startmb.cmd -Restart") `
    -WorkingDirectory $RepoRoot `
    -NoNewWindow -PassThru
  if (-not $p.WaitForExit([int]$timeoutMs)) {
    Write-Host "ERROR: startmb watchdog timeout" -ForegroundColor Red
    Stop-ProcessTree $p
    exit 98
  }
  exit $p.ExitCode
}

# prove — always launch System32 Windows PowerShell. PATH "powershell.exe"
# can be a WindowsApps stub that exits 0 immediately (FlightSim then delivered
# gate_cmd_stub_missing_prove_artifacts / prove_exit=0 with no PROVE.log).
$provePs1 = Join-Path $PSScriptRoot "flightsim-address-centric-prove.ps1"
if (-not (Test-Path -LiteralPath $provePs1)) {
  Write-Host "ERROR: missing $provePs1" -ForegroundColor Red
  exit 1
}
$psReal = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path -LiteralPath $psReal)) { $psReal = "powershell.exe" }
Write-Host "watchdog prove timeout=${TimeoutSec}s file=$provePs1 ps=$psReal"
$p = Start-Process -FilePath $psReal `
  -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $provePs1
  ) `
  -WorkingDirectory $RepoRoot `
  -NoNewWindow -PassThru
if (-not $p.WaitForExit([int]$timeoutMs)) {
  Write-Host "ERROR: prove watchdog timeout" -ForegroundColor Red
  Stop-ProcessTree $p
  exit 99
}
exit $p.ExitCode
