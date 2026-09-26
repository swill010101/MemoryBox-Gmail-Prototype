$ErrorActionPreference = "Stop"
Set-Location C:\memorybox
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only
git log -1 --oneline
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
if ((hostname).Trim() -ne "FlightSim") { throw "controller is not FlightSim" }

$preserved = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-ab\A\c1cd10594705ff1f1ac7f89bd8a4325c9a432017553b179abb5c2a2d7ff51b0f"
python -c "from pathlib import Path; from memorybox.ask.i11a.i11a0_smoke import write_qwen_a_initial_calibration; print(write_qwen_a_initial_calibration(Path(r'$preserved'))['legacy_execution_id'])"

$chunks = "C:\memorybox\docs\test-output\trusted-email-review\REVIEW_20260831T120929Z"
$aOut = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-a-calibrated"
$bOut = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-b"

python -m memorybox i11a0-benchmark --config "docs/ops/i11a0_smoke.gate2.a-calibrated.json" --stage smoke --confirm-benchmark --chunks-root $chunks --ollama-base-url "http://127.0.0.1:11434" --out $aOut
if ($LASTEXITCODE -ne 0) { throw "calibrated A smoke failed; B was not started" }

python -m memorybox i11a0-benchmark --config "docs/ops/i11a0_smoke.gate2.b.json" --stage smoke --confirm-benchmark --chunks-root $chunks --ollama-base-url "http://127.0.0.1:11434" --out $bOut

