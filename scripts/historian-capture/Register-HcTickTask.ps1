#Requires -Version 5.1
<#
.SYNOPSIS
  Create the Historian Capture tick scheduled task in the Disabled state.
.DESCRIPTION
  Does not enable the task. Founder authorization is required before Enable-ScheduledTask.
  Do not run this during development.
#>
[CmdletBinding()]
param(
  [string]$TaskName = "MemoryBox Historian Capture Tick",
  [string]$RepoRoot = "",
  [switch]$Enable
)

$ErrorActionPreference = "Stop"
if ($Enable) {
  Write-Error "Refusing to enable. Create the task disabled, then enable only after explicit founder authorization."
  exit 2
}
if (-not $RepoRoot) {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Launcher = Join-Path $RepoRoot "scripts\historian-capture\Invoke-HcTick.ps1"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Launcher)) { Write-Error "Missing launcher: $Launcher"; exit 3 }
if (-not (Test-Path -LiteralPath $Python)) { Write-Error "Missing venv Python: $Python"; exit 3 }

$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Disable-ScheduledTask -TaskName $TaskName | Out-Null
$stateDir = Join-Path $RepoRoot ".memorybox_hc_state"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
@{
  registered = $true
  enabled = $false
  task_name = $TaskName
  updated_at = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json | Set-Content -Encoding ascii (Join-Path $stateDir "tick_task_status.json")
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName, State, TaskPath
Write-Host "Registered disabled. Command: powershell.exe $arg"
Write-Host "WorkingDirectory: $RepoRoot"
Write-Host "Python: $Python"
Write-Host "Principal: $($env:USERNAME) Interactive Limited"
Write-Host "Do not enable until founder authorizes."
