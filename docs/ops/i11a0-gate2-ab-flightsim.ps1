$ErrorActionPreference = "Stop"
Set-Location C:\memorybox
git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only
git log -1 --oneline
git merge-base --is-ancestor fae684fc311a11ed923f7c4298110f6b8c0f177f HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD does not contain fae684f" }
python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed" }
hostname
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
ollama pull qwen3:30b-a3b-instruct-2507-q4_K_M
if ($LASTEXITCODE -ne 0) { throw "pull A failed" }
ollama pull qwen3:14b-q8_0
if ($LASTEXITCODE -ne 0) { throw "pull B failed" }
python -m memorybox i11a0-benchmark --config "docs/ops/i11a0_smoke.gate2.ab.json" --stage smoke --confirm-benchmark --chunks-root "C:\memorybox\docs\test-output\trusted-email-review\REVIEW_20260831T120929Z" --ollama-base-url "http://127.0.0.1:11434" --out "C:\memorybox\docs\test-output\i11a0-benchmark\smoke-ab"
