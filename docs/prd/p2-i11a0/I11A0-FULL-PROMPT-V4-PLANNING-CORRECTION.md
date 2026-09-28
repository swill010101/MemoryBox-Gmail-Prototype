# I11A.0 full-prompt v4 planning correction

**Status:** **RETIRED as a live preflight** after Diagnostic A2 (2026-09-28). A2 evaluated 24,174 tokens at `num_ctx=28416` with `truncate=false`/`shift=false`; Diagnostic B fail-closed overflow. Use v5: `I11A0-FULL-PROMPT-V5-PLAN.md`. This file remains as the historical v4 correction record.

**Planner:** `i14_cleaned_full_prompt_v4` (retired)  
**Does not rewrite** the reconstructed historical audit or prior run artifacts.

## Invalidation of v3

The reconstructed historical audit remains valid.

The proposed 18K starting point and `i14_cleaned_full_prompt_v3` ladder are **invalid**. No v3 inference occurred.

**Defect:** v3 preflight required only `predicted_complete_prompt_tokens + 2500 + 1500 <= num_ctx`. That is necessary but does not prevent Ollama 0.34.1 from truncating the input. For the tested Qwen B chat path:

`retention_limit = keep + (num_ctx - keep) // 2` with `keep = 4`.

A complete prompt must fit inside that retention window before it can be considered an untruncated run.

Example:

| Quantity | v3 18K proposal |
|----------|-----------------|
| Predicted complete prompt | ~24,109 |
| Planned `num_ctx` | 28,416 |
| Retention limit | `4 + (28416 - 4) // 2 = 14,210` |

The first proposed v3 run would have been truncated again.

Sidecar (gitignored audit tree, not a rewrite of CSV/JSONL/HASHES): `v3_plan_invalidation.json` / `V3-PLAN-INVALID.md`.

## Correct planning equations

```
keep = 4
retention_limit(num_ctx) = keep + (num_ctx - keep) // 2
minimum_num_ctx_for_retention = 2 * (predicted - keep) + keep
minimum_num_ctx_for_reserves = predicted + 2500 + 1500
planned_num_ctx = align_256(max(retention, reserves))
```

A run is eligible only when all of these pass:

1. `predicted <= retention_limit(planned_num_ctx)`
2. `predicted + 2500 + 1500 <= planned_num_ctx`
3. `planned_num_ctx <= 40960`
4. projected peak VRAM `< 22.5 GB` (historical peaks vs requested `num_ctx`; adjacent ≥22.5 GB is unsafe)
5. full GPU residency required (no CPU offload)

Do not cap an oversized predicted prompt and then run it. Reject or reduce the packet first.

At `num_ctx=40960`, retention is 20,482 (not 36,960). At `num_ctx=32768`, retention is 16,386. From `num_ctx=33024` upward, measured peaks include ≥22.5 GB.

## Corrected ladder

Config: `docs/ops/i11a0_gate3.b.full-prompt-v4.json`  
Packet table: `docs/prd/p2-i11a0/I11A0-FULL-PROMPT-V4-PACKET-PLAN.json`

- Start at the first conservative eligible nested complete-message packet (~8K estimated evidence; packed size overshoots to 8,665).
- Grow by ~1K estimated evidence on complete-message nested prefixes.
- Stop before submitting the 13K packet: planned `num_ctx=34048` projects to a VRAM ceiling (adjacent measured ≥22.5 GB). That is a capacity boundary, not a performance knee.
- Highest likely eligible coarse target: ~12K estimated evidence (packed 12,283; `num_ctx=32256`; interpolated peak ~22.20 GB).
- Refine at ~250 estimated evidence tokens inside the last eligible interval (12,283–12,533).
- Three repeats at the proposed operating point; three at the next larger eligible point only if it remains below every hard boundary.
- After every live run, require a unique Ollama log correlation. `truncating input prompt` → `invalid_truncated_prompt` and stop. Missing or ambiguous log match cannot pass.

No truncated run may become the proposed operating point.
