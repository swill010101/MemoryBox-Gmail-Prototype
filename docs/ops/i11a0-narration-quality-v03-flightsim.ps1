$ErrorActionPreference = "Stop"
Set-Location C:\MemoryBox
if (-not (Test-Path "C:\MemoryBox")) { Set-Location "C:\memorybox" }
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only origin cursor/p2-i11a0-offline-harness
git log -1 --oneline
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed; inference not started" }
python -m memorybox i11a0-narration-quality-v03-confirm --confirm-benchmark --config docs/ops/i11a0.b.narration-quality-v03-27k.json --out docs/test-output/i11a0-benchmark/gate3-b-i14-narration-quality-v03-27k-confirm
