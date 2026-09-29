# Offline prove and preflight only. Do not pull. Do not generate until founder sets inference_authorized.
$ErrorActionPreference = "Stop"
if ($env:COMPUTERNAME -ne "FlightSim") { throw "run on FlightSim only" }
Set-Location C:\MemoryBox
if (-not (Test-Path "C:\MemoryBox")) { Set-Location "C:\memorybox" }
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only origin cursor/p2-i11a0-offline-harness
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
python -m memorybox i11a0-gemma-i14-full-prompt-v1 --config docs/ops/i11a0.c.gemma-i14-full-prompt-v1.json --out docs/test-output/i11a0-benchmark/gate3-c-gemma-i14-full-prompt-v1
