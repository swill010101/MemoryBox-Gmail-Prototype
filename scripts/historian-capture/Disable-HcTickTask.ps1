#Requires -Version 5.1
param(
  [string]$TaskName = "MemoryBox Historian Capture Tick"
)
$ErrorActionPreference = "Stop"
Disable-ScheduledTask -TaskName $TaskName | Out-Null
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$stateDir = Join-Path $RepoRoot ".memorybox_hc_state"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
@{
  registered = $true
  enabled = $false
  task_name = $TaskName
  updated_at = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json | Set-Content -Encoding ascii (Join-Path $stateDir "tick_task_status.json")
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
