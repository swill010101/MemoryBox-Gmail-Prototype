# FlightSim I1–I3 deployment & real-data smoke checkpoint
# Run THIS SCRIPT ON THE P1 RUNTIME HOST (FlightSim), not on the dev box.
# Does not print family message/event content — counts/IDs/hashes only.
#
# Prerequisites (install once on host):
#   - Git clone of repo
#   - Python 3.11+
#   - PostgreSQL with memorybox db/role
#   - Qdrant listening (configure URL via env)
#   - Ollama with embed model (optional but preferred for real embeddings)
#   - Real mbox / ICS available locally on this host (archive or working smoke slices)
#
# Usage (from repo root on FlightSim):
#   powershell -ExecutionPolicy Bypass -File scripts\flightsim_checkpoint_i1_i3.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Require-Env([string]$Name) {
  $v = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($v)) {
    throw "Missing required environment variable: $Name"
  }
  return $v
}

# Fail closed: never use ALLOW_DEV_DEFAULTS on the P1 runtime host for this checkpoint.
if ($env:MEMORYBOX_ALLOW_DEV_DEFAULTS -eq "1") {
  Write-Warning "MEMORYBOX_ALLOW_DEV_DEFAULTS=1 is set — unset it for P1 runtime; using explicit URLs only."
  Remove-Item Env:MEMORYBOX_ALLOW_DEV_DEFAULTS -ErrorAction SilentlyContinue
}

Require-Env "MEMORYBOX_DATABASE_URL" | Out-Null
Require-Env "MEMORYBOX_QDRANT_URL" | Out-Null
# Ollama optional; rebuild falls back to Fake embedder if unset/unreachable
if (-not $env:MEMORYBOX_QDRANT_COLLECTION) {
  $env:MEMORYBOX_QDRANT_COLLECTION = "memorybox_evidence"
}
if (-not $env:MEMORYBOX_SMOKE_LIMIT) {
  $env:MEMORYBOX_SMOKE_LIMIT = "5"
}

Write-Host "=== pip install ==="
python -m pip install -r memorybox\requirements.txt -q

Write-Host "=== migrate ==="
python -m memorybox migrate

Write-Host "=== health ==="
python -m memorybox health
if ($LASTEXITCODE -ne 0) { throw "health failed" }

Write-Host "=== prove-synthetic (I1) ==="
python -m memorybox seed-synthetic
python -m memorybox prove-synthetic
if ($LASTEXITCODE -ne 0) { throw "prove-synthetic failed" }

Write-Host "=== prove-providers (I2) ==="
python -m memorybox prove-providers
if ($LASTEXITCODE -ne 0) { throw "prove-providers failed" }

# Real smoke gates
$missing = @()
if ([string]::IsNullOrWhiteSpace($env:MEMORYBOX_SMOKE_MBOX_URI)) {
  $missing += "MEMORYBOX_SMOKE_MBOX_URI (path to real mbox or working smoke slice on this host)"
}
elseif (-not (Test-Path -LiteralPath $env:MEMORYBOX_SMOKE_MBOX_URI)) {
  $missing += "MEMORYBOX_SMOKE_MBOX_URI path does not exist: $($env:MEMORYBOX_SMOKE_MBOX_URI)"
}
if ([string]::IsNullOrWhiteSpace($env:MEMORYBOX_SMOKE_ICS_URI)) {
  $missing += "MEMORYBOX_SMOKE_ICS_URI (path to real .ics on this host)"
}
elseif (-not (Test-Path -LiteralPath $env:MEMORYBOX_SMOKE_ICS_URI)) {
  $missing += "MEMORYBOX_SMOKE_ICS_URI path does not exist: $($env:MEMORYBOX_SMOKE_ICS_URI)"
}

if ($missing.Count -gt 0) {
  Write-Host "=== REAL-DATA SMOKE BLOCKED ==="
  $missing | ForEach-Object { Write-Host "MISSING: $_" }
  Write-Host "Synthetic I1–I3 proves may have passed above; real-data smoke is NOT complete."
  Write-Host "Prepare slices (on this host, originals untouched), e.g.:"
  Write-Host '  python scripts\prepare_smoke_slices.py --mbox "<archive-mbox>" --mbox-limit 5 --takeout-zip "<calendar-takeout-zip>"'
  Write-Host "Then set MEMORYBOX_SMOKE_MBOX_URI / MEMORYBOX_SMOKE_ICS_URI and re-run this script."
  exit 3
}

Write-Host "=== prove-ingest (I3 + real smoke) ==="
python -m memorybox prove-ingest
if ($LASTEXITCODE -ne 0) { throw "prove-ingest failed" }

Write-Host "=== checkpoint OK (safe report: see prove-ingest JSON; no family content logged here) ==="
exit 0
