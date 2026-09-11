#Requires -Version 5.1
param(
  [string]$TaskName = "MemoryBox Historian Capture Tick"
)
$ErrorActionPreference = "Stop"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$stateDir = Join-Path $RepoRoot ".memorybox_hc_state"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
@{
  registered = $false
  enabled = $false
  task_name = $TaskName
  updated_at = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json | Set-Content -Encoding ascii (Join-Path $stateDir "tick_task_status.json")
Write-Host "Removed scheduled task '$TaskName'."
