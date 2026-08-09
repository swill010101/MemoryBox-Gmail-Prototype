# Increment 4 final acceptance — run ON the P1 runtime host (FlightSim console).
# Do not run on the desktop as a substitute for final acceptance.
# Opaque metrics only — no family content printed.
#
# Usage (from repo root on the P1 runtime host):
#   powershell -ExecutionPolicy Bypass -File scripts\flightsim_accept_i4.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Require-Env([string]$Name) {
  $v = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($v)) {
    throw "Missing required environment variable: $Name"
  }
  return $v
}

if ($env:MEMORYBOX_ALLOW_DEV_DEFAULTS -eq "1") {
  Write-Warning "Unsetting MEMORYBOX_ALLOW_DEV_DEFAULTS for P1 runtime acceptance."
  Remove-Item Env:MEMORYBOX_ALLOW_DEV_DEFAULTS -ErrorAction SilentlyContinue
}

Require-Env "MEMORYBOX_DATABASE_URL" | Out-Null
Require-Env "MEMORYBOX_QDRANT_URL" | Out-Null
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
if (-not $env:MEMORYBOX_QDRANT_COLLECTION) {
  $env:MEMORYBOX_QDRANT_COLLECTION = "memorybox_evidence"
}
if (-not $env:MEMORYBOX_PHOTO_PROVIDER) {
  $env:MEMORYBOX_PHOTO_PROVIDER = "immich"
}

Write-Host "=== pip install ==="
python -m pip install -r memorybox\requirements.txt -q

Write-Host "=== migrate ==="
python -m memorybox migrate

Write-Host "=== health ==="
python -m memorybox health
if ($LASTEXITCODE -ne 0) { throw "health failed" }

Write-Host "=== prove-ask --flightsim (I4-A..K) ==="
python -m memorybox prove-ask --flightsim
if ($LASTEXITCODE -ne 0) { throw "prove-ask --flightsim failed" }

Write-Host "=== I4 acceptance PASS (opaque JSON above) ==="
Write-Host "Ask UI: python -m memorybox serve  then open /ask/ui"
