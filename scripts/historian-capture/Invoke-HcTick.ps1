#Requires -Version 5.1
<#
.SYNOPSIS
  Load MemoryBox env and run one Historian Capture tick (HC-2).
.DESCRIPTION
  Used by Task Scheduler. Secrets come from gitignored env files, never from task arguments.
#>
[CmdletBinding()]
param(
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "memorybox"))) {
  $RepoRoot = Split-Path -Parent $PSScriptRoot
}
Set-Location -LiteralPath $RepoRoot

function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
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

Import-DotEnvFile (Join-Path $RepoRoot "config\memorybox_app.env")
if (-not $env:MEMORYBOX_DATABASE_URL) {
  $env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
}
if (-not $env:MEMORYBOX_QDRANT_URL) {
  $env:MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"
}
if (-not $env:MEMORYBOX_QDRANT_COLLECTION) {
  $env:MEMORYBOX_QDRANT_COLLECTION = "memorybox_evidence"
}
if (-not $env:MEMORYBOX_P1_RUNTIME_HOST) { $env:MEMORYBOX_P1_RUNTIME_HOST = "1" }
if (-not $env:MEMORYBOX_HC_EMAIL_PROVIDER) { $env:MEMORYBOX_HC_EMAIL_PROVIDER = "privateemail" }
if (-not $env:MEMORYBOX_HC_USER_EMAIL) { $env:MEMORYBOX_HC_USER_EMAIL = "memorybox@marvinbot.net" }
if (-not $env:MEMORYBOX_HC_MAX_SENDS_PER_TICK) { $env:MEMORYBOX_HC_MAX_SENDS_PER_TICK = "5" }

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
  Write-Error "MemoryBox venv Python not found: $Python"
  exit 3
}

$tickArgs = @("-m", "memorybox", "hc-tick")
if ($DryRun) { $tickArgs += "--dry-run" }

& $Python @tickArgs
exit $LASTEXITCODE
