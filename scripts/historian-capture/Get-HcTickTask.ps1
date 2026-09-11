#Requires -Version 5.1
param(
  [string]$TaskName = "MemoryBox Historian Capture Tick"
)
$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = $task | Get-ScheduledTaskInfo
$action = $task.Actions | Select-Object -First 1
[pscustomobject]@{
  TaskName = $task.TaskName
  State = [string]$task.State
  UserId = $task.Principal.UserId
  LogonType = [string]$task.Principal.LogonType
  RunLevel = [string]$task.Principal.RunLevel
  Execute = $action.Execute
  Arguments = $action.Arguments
  WorkingDirectory = $action.WorkingDirectory
  MultipleInstances = [string]$task.Settings.MultipleInstances
  LastRunTime = $info.LastRunTime
  LastTaskResult = $info.LastTaskResult
  NextRunTime = $info.NextRunTime
} | Format-List
