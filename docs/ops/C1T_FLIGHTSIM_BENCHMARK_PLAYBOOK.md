# C1T FlightSim Gemma benchmark harness

Controlling requirement: `docs/MBPRD-P2-I11A-C1T_FlightSim_Gemma_Benchmark_PRD_v1.0_APPROVED.docx`.

This harness does not run a production Peggy job. Model execution is operator
invoked, sequential, and requires `--confirm-model-run`.

## T1 reconnaissance and preservation

Reuse points:

- `memorybox/ask/i11a/full_evidence_l1_chunker.py`: deterministic packing and
  completeness-proof conventions. C1T does not reuse its lossy email compaction.
- `memorybox/ask/i11a/full_evidence_benchmark.py`: immutable manifests, hashes,
  and JSON-first benchmark records.
- `memorybox/providers/llm/_ollama_http.py`: Ollama endpoint and usage-field
  conventions.
- `memorybox/__main__.py`: operator CLI surface.

The prior C1s FlightSim directory and any partial diagnostics remain historical.
C1T never overwrites it. Canonical generations, chunk parameter sets, and runs
each receive separate immutable directories. Runtime artifacts are gitignored.

## 1. Inventory only

```powershell
cd C:\memorybox
git fetch origin cursor/p2-i11a-c1t-benchmark-harness
git pull origin cursor/p2-i11a-c1t-benchmark-harness
.\tools\flightsim-c1t-inventory.ps1
```

Review `FLIGHTSIM_INVENTORY.json` and `FLIGHTSIM_INVENTORY.txt`. Missing
`psutil`, NVIDIA tooling, or unsupported metrics are represented as unavailable,
never as zero. Optional supporting evidence:

```powershell
.\tools\flightsim-c1t-inventory.ps1 -IncludeMsinfo32
```

## 2. Register one reviewed canonical generation

Run the corrected deterministic prepare path first. Then register its complete
artifact set without changing the reviewed paste:

```powershell
python -m memorybox c1t-register-canonical `
  --source-dir C:\memorybox\docs\test-output\trusted-email-review\REVIEW_<stamp> `
  --generations-dir C:\memorybox\docs\test-output\c1t-benchmark\generations
```

Registration fails if paste/sidecar hashes or `[email_N]` coverage disagree.
Existing generations are retained.

## 3. Build candidate chunks without a model

Select parameters only after reviewing inventory. Example for approved Case A:

```powershell
python -m memorybox c1t-prepare-chunks `
  --generation-dir C:\memorybox\docs\test-output\c1t-benchmark\generations\<generation_id> `
  --out-root C:\memorybox\docs\test-output\c1t-benchmark\chunks `
  --target-input-tokens 8000 `
  --hard-input-tokens 10240 `
  --reserved-output-tokens 4096 `
  --safety-margin-tokens 2048 `
  --num-ctx 16384 `
  --overlap-messages 3
```

Complete conversations are atomic. Only an individually oversized conversation
is split, only between complete emails, with the preceding three complete emails
declared as overlap.

## 4. Recommended first operator-invoked benchmark

Use the inventory and exact Chunk 1 hash from `CHUNK_MANIFEST.json`:

```powershell
$chunkDir = "<case-A chunk directory>"
$manifest = Get-Content "$chunkDir\CHUNK_MANIFEST.json" | ConvertFrom-Json
$chunkHash = $manifest.chunks[0].sha256

python -m memorybox c1t-run-benchmark `
  --chunk-dir $chunkDir `
  --chunk-index 1 `
  --require-chunk-hash $chunkHash `
  --inventory C:\memorybox\docs\test-output\c1t-benchmark\inventory\FLIGHTSIM_INVENTORY.json `
  --results-root C:\memorybox\docs\test-output\c1t-benchmark\results `
  --experiment-id A-cold `
  --repetition 1 `
  --model gemma4:26b `
  --num-ctx 16384 `
  --num-predict 4096 `
  --temperature 0.1 `
  --hard-timeout-seconds 1800 `
  --stall-warning-seconds 300 `
  --heartbeat-seconds 10 `
  --warm-or-cold cold `
  --confirm-model-run
```

Without `--confirm-model-run`, the command refuses before inference.
Without `--think true|false`, the command refuses during parameter validation.

Before quality-comparison runs, copy `C1T_QUALITY_CONTRACT_TEMPLATE.json`,
replace its synthetic expectation with reviewed Chunk 1 expectations, and add
`--quality-contract <reviewed-contract.json>`. Do not use the placeholder as a
real scoring contract.

## Diagnostics and recovery

The supervisor prints and records inventory/preflight, loading, awaiting-first-
token, generating, validation, saving, and terminal phases. Heartbeats report
elapsed time, time since output, streamed bytes, Python/Ollama process metrics,
RAM/pagefile, and NVIDIA metrics where available. Prompt-evaluation percent is
explicitly unavailable from Ollama.

At the stall threshold it warns but continues. At the hard timeout it terminates
only the worker, checks `/api/ps`, unloads the selected model if still active,
then verifies API readiness.

Each run stores `request.json`, `raw_api.jsonl`, `response.txt`, `console.log`,
`telemetry.jsonl`, `validation.json`, and `run_record.json`. `C1T_RESULTS.xlsx`
contains relative links and can move with the complete results directory.

## Ladder

`c1t-write-benchmark-matrix --out <path>` writes the approved A-F parameter
template. Map each case to chunks built for its approximate evidence target
after inventory. Execute selected cases with `c1t-run-matrix`; it is strictly
sequential, skips immutable completed repetitions, and stops on preflight,
runtime failure, timeout, or pressure gates.
