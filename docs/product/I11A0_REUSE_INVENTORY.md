# P2-I11A.0 reuse inventory

**Date:** 2026-09-26  
**Status:** Gate 1 accepted. Offline harness only. No FlightSim inference.

## Reused

| Existing code | Use |
|---|---|
| `memorybox/ask/i11a/c1t_benchmark.py` `estimate_tokens` | Diagnostic bytes÷4 only. It cannot authorize an 8,000-token target. |
| `parse_conversations` | Read reviewed Peggy pastes into whole conversations and `[email_N]` turns. |
| C1T artifact idea: one folder per run, hashes, no overwrite | I11A.0 stores `run_record.json` and `narration.txt` under a schedule identity. |
| `openpyxl` workbook pattern from C1T | Four sheets: Runs, Quality Review, Configuration, Summary. Writes append. |
| Ollama `/api/tags`, `/api/show`, `/api/version` | Inventory only. No `/api/generate`, `/api/chat`, or `/api/pull`. |

## Not reused, and why

| Existing code | Reason |
|---|---|
| C1T A–F matrix and `c1t-run-matrix` | Fixed cases, pagefile stop, and per-case confirmation. I11A.0 steps by 1,000 tokens and stops on the VRAM and regression rules. |
| `historian-evidence-ledger-v1` | That prompt forbids the final narrative. |
| `memorybox/ask/narrative.py` `SYSTEM_PROMPT` | It expects a semantic episode outline. The benchmark input is an evidence packet. The draft prompt is not the production narrator. |
| Live Ask retrieve and hierarchical prep | Hierarchy and Peggy production narration are outside this increment. |
| Lossy email compaction | Benchmark evidence keeps thread boundaries. |
| `llama3.2` | Not one of the three approved configurations. |

## New offline modules

- `memorybox/ask/i11a/i11a0_prompt.py` — draft narration prompt and hash.
- `memorybox/ask/i11a/i11a0_benchmark.py` — config, token budget, packer, stop rules, resume, lifecycle double, read-only inventory.
- `memorybox/ask/i11a/i11a0_artifacts.py` — workbook and portable bundle.
- `memorybox/ask/i11a0_acceptance.py` — `python -m memorybox prove-i11a0-benchmark`.

Generation stays refused in `i11a0-benchmark` until Gate 2 is accepted.
