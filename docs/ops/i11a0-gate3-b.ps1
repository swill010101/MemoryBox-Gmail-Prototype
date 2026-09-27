$ErrorActionPreference = "Stop"
Set-Location C:\memorybox
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only
git log -1 --oneline
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
if ((hostname).Trim() -ne "FlightSim") { throw "controller is not FlightSim" }

# Continues gate3-b from the 3,048-token GPU-resident baseline. Next coarse
# target is 4,000. Does not rerun the identical packet. Does not treat overshoot
# as evidence exhaustion.
python -m memorybox i11a0-gate3 --config "docs/ops/i11a0_gate3.b.json" --confirm-benchmark --chunks-root "C:\memorybox\docs\test-output\trusted-email-review\REVIEW_20260831T120929Z" --ollama-base-url "http://127.0.0.1:11434" --out "C:\memorybox\docs\test-output\i11a0-benchmark\gate3-b"
