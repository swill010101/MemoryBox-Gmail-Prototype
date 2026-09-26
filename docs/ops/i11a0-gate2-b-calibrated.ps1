$ErrorActionPreference = "Stop"
Set-Location C:\memorybox
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only
git log -1 --oneline
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
if ((hostname).Trim() -ne "FlightSim") { throw "controller is not FlightSim" }

$preserved = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-b\B\85644304f430bf48bb07b97e30cbb7336e6aa49fcc365228c064618970f3662b"
python -c "from pathlib import Path; from memorybox.ask.i11a.i11a0_smoke import write_qwen_b_initial_calibration; print(write_qwen_b_initial_calibration(Path(r'$preserved'))['legacy_execution_id'])"

$chunks = "C:\memorybox\docs\test-output\trusted-email-review\REVIEW_20260831T120929Z"
$bOut = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-b-calibrated"

python -m memorybox i11a0-benchmark --config "docs/ops/i11a0_smoke.gate2.b-calibrated.json" --stage smoke --confirm-benchmark --chunks-root $chunks --ollama-base-url "http://127.0.0.1:11434" --out $bOut
if ($LASTEXITCODE -ne 0) { throw "calibrated B smoke failed; review package was not assembled" }

$bRun = Get-ChildItem -LiteralPath (Join-Path $bOut "B") -Directory | Select-Object -First 1
if (-not $bRun) { throw "calibrated B artifact directory was not found" }

$aDir = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-a-calibrated\A\a1b6b4b2ce743fdb6836381e8b443a501439d80fcd0bc25f72ba827ee5a8c124"
$cDir = "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-flightsim\0717c7de073416f1200ce2047b39c961161d9ffe674f8374657700273117a24e"
$pkg = "C:\memorybox\docs\test-output\i11a0-benchmark\gate2-review-package"
if (Test-Path -LiteralPath $pkg) { throw "review package already exists: $pkg" }

python -m memorybox i11a0-gate2-review-package --a-dir $aDir --b-dir $bRun.FullName --c-dir $cDir --out $pkg
