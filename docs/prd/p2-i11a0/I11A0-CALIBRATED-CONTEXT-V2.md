# I11A.0 cleaned-I14 empirical context planner v2

**Status:** controller correction only. No new inference until founder authorization.  
**Planning segment:** `i14_cleaned_calibrated_context_v2`  
**Does not rewrite** existing files under `docs/test-output/i11a0-benchmark/gate3-b-i14/runs/`.

## Problem

The Phase 2 27K conclusion measured oversized `num_ctx` from the bytes÷4 complete-prompt diagnostic, not Qwen B’s actual evidence capacity.

| Quantity | 27K packet |
|----------|------------|
| Estimated evidence tokens | 27,054 |
| Actual `prompt_eval_count` | 16,386 |
| Required context (actual + 2500 + 1500) | 20,386 |
| Configured `num_ctx` | 32,768 |
| Excess allocated context | 12,382 |
| Peak VRAM | ~22.28 GB |

The 28K skip (`8603ae88…`) is a **planning-model stop**, not an observed Qwen B VRAM boundary. No performance knee was observed. The 27K packet remains a successful, repeatable v1 run and is **not** the accepted operating point.

## Planner

`predicted_prompt = ceil(diagnostic_bytes÷4 × max(actual/diagnostic) × 1.005 + max(0, residual vs that ratio) + 64)`  
`num_ctx = ceil((predicted_prompt + 2500 + 1500) / 256) × 256`  
Never exceed 40,960. Never reduce 2,500 / 1,500. Label **predicted**, not actual.

Calibration identity is invalidated by digest, prompt hash/version, I14 freeze hashes, chat-template family, thinking mode, or Ollama version family ≠ `0.34`.

VRAM projection uses only v2 inferred points. Resume starts at the skipped 28,758 estimated-evidence packet without rerunning 18K–27K.
