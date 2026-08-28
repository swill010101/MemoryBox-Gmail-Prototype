# P2-I11A Historian — Full-Fidelity Benchmark + L1 Chunking

**Branch:** `cursor/p2-i11a-full-evidence-bench-49da`  
**Machine:** FlightSim (`C:\memorybox`)  
**Purpose:** Freeze the successful Peggy full-evidence experiment, measure the compression funnel, and produce Level-1 complete-coverage chunks. **No LLM. No production I11A changes.**

---

## Outputs

`docs/test-output/historian-full-evidence/peggy/`

| Artifact | Role |
|----------|------|
| `PEGGY_FULL_EVIDENCE.txt` | Frozen normalized evidence |
| `PEGGY_FULL_EVIDENCE_METRICS.json` | Counts / bytes / tokens |
| `CLOUDREQ_peggy_full_evidence_paste.txt` | Clean cloud paste that produced the strong GPT result |
| `BENCHMARK_MANIFEST.json` | Hashes + source Git commit |
| `GPT56SOL_peggy_full_evidence_response.txt` | Optional — only if `--gpt-response` provided |
| `PEGGY_COMPRESSION_FUNNEL.json` / `.txt` | full → units → obs → rollups → HO → narrator |
| `PEGGY_CHUNK_001.txt` … | Human/model-readable L1 chunks |
| `PEGGY_L1_CHUNK_MANIFEST.json` | Completeness proof + per-chunk IDs/tokens |
| `BENCHMARK_REPORT.json` | Summary for review |

---

## FlightSim

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-full-evidence-bench-49da
.\startmb.cmd -Restart

python -m memorybox prove-historian-full-evidence-benchmark

python -m memorybox historian-full-evidence-benchmark --flightsim --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

If you already exported full evidence:

```bat
python -m memorybox historian-full-evidence-benchmark --flightsim --from-dir docs\test-output\full-evidence --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Preserve the GPT-5.6 Sol answer (benchmark artifact only):

```bat
python -m memorybox historian-full-evidence-benchmark --flightsim --from-dir docs\test-output\full-evidence --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json --gpt-response path\to\GPT56SOL_response.txt
```

Optional narrator-input size from a prior HISTRUN:

```bat
python -m memorybox historian-full-evidence-benchmark --flightsim --from-dir docs\test-output\full-evidence --fixture ... --historian-run docs\test-output\historian-runs\HISTRUN_peggy_....json
```

---

## SMS episode rules (deterministic)

- Primary split: gap ≥ **4 hours** within the same SMS channel/thread
- Participant-set change → new episode
- Day boundary alone is **not** a split; only with gap ≥ 2 hours
- No LLM topic boundaries
- Every message remains represented (including short “love you” / “OK”)

## Chunk sizing

- Target **75K–125K** estimated tokens
- Modest overshoot up to **150K** to keep email threads / SMS episodes intact
- Oversized threads subdivide only at message boundaries (parent thread ID preserved)

## Completeness

Diagnostic **fails** unless `union(chunk evidence IDs) == all normalized eligible IDs` (multiset, no silent drop/dup).

Do **not** proceed to semantic chunk summarization until funnel + chunks are reviewed.
