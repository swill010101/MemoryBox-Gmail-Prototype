$ErrorActionPreference = "Stop"
Set-Location C:\memorybox
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only
git log -1 --oneline
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
if ((hostname).Trim() -ne "FlightSim") { throw "controller is not FlightSim" }

# Resume cleaned-I14 Qwen B ladder with calibrated context planner v2.
# Does not rewrite existing gate3-b-i14 v1 run directories.
# Literal Ollama URL only. Do not start until founder authorizes new inference.
python -m memorybox i11a0-gate3 `
  --config "docs/ops/i11a0_gate3.b.i14.json" `
  --confirm-benchmark `
  --i14-export "C:\memorybox\docs\test-output\i11a0-benchmark\i14-cleaned-export" `
  --ollama-base-url "http://127.0.0.1:11434" `
  --out "C:\memorybox\docs\test-output\i11a0-benchmark\gate3-b-i14"
