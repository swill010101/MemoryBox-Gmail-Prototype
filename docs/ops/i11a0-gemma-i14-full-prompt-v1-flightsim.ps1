# Offline prove only. Calibrated 8K rerun is not authorized.
$ErrorActionPreference = "Stop"
if ($env:COMPUTERNAME -ne "FlightSim") { throw "run on FlightSim only" }
Set-Location C:\MemoryBox
if (-not (Test-Path "C:\MemoryBox")) { Set-Location "C:\memorybox" }
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only origin cursor/p2-i11a0-offline-harness
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox prove-i11a0-benchmark
