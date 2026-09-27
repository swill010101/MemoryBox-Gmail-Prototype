$ErrorActionPreference = "Stop"
Set-Location C:\memorybox
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only
git log -1 --oneline
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
if ((hostname).Trim() -ne "FlightSim") { throw "controller is not FlightSim" }

# Phase 2 — I14 cleaned Qwen B ladder. Do not run until founder authorizes.
# Separate results directory from legacy gate3-b artifacts.
# Does not use REVIEW_20260831T120929Z seven chunks.
python -m memorybox i11a0-gate3 `
  --config "docs/ops/i11a0_gate3.b.i14.json" `
  --confirm-benchmark `
  --i14-export "C:\memorybox\docs\test-output\i11a0-benchmark\i14-cleaned-export" `
  --ollama-base-url "http://127.0.0.1:11434" `
  --out "C:\memorybox\docs\test-output\i11a0-benchmark\gate3-b-i14"
