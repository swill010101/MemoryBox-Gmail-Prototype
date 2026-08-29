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

# prove - invoke IN-PROCESS. A nested Start-Process powershell -File still
# returned 0 on FlightSim (233fbba) without creating PROVE_STARTED.
$provePs1 = Join-Path $PSScriptRoot "flightsim-address-centric-prove.ps1"
if (-not (Test-Path -LiteralPath $provePs1)) {
  Write-Host "ERROR: missing $provePs1" -ForegroundColor Red
  exit 1
}
Write-Host "WATCHDOG_PROVE_ENTER in-process timeout=${TimeoutSec}s file=$provePs1 pid=$PID"
$killer = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" `
  -ArgumentList @("/c", "timeout /t $TimeoutSec /nobreak >nul && taskkill /F /T /PID $PID") `
  -WindowStyle Hidden -PassThru
try {
  # prove.ps1 uses `exit N` which ends this process (gate.cmd sees N).
  & $provePs1
  $code = 0
  if ($null -ne $LASTEXITCODE) { $code = [int]$LASTEXITCODE }
} catch {
  Write-Host ("ERROR: prove.ps1 threw: " + $_.Exception.Message) -ForegroundColor Red
  $code = 1
} finally {
  if ($killer -and -not $killer.HasExited) {
    try { & cmd.exe /c "taskkill /F /PID $($killer.Id)" 2>$null | Out-Null } catch {}
  }
}
exit $code
