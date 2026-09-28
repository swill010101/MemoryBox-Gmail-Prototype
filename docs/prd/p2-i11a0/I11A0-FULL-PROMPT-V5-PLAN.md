# I11A.0 full-prompt v5 — half-window retired

**Status:** planning and controller only. **No ladder execution.** Founder authorization required.

## Why the half-window preflight is retired

Diagnostic A2 (`292642bad1a27cb4…`) evaluated a **complete 24,174-token prompt at `num_ctx=28416`** with `truncate=false` and `shift=false`. The half-window at that context is 14,210. The prompt was larger than the half-window, was fully evaluated, and the appended Ollama log has no `truncating input prompt` line and `truncated = 0`.

Diagnostic B then overflowed a deliberately small `num_ctx=2048` with the same fields and received **HTTP 400** `exceed_context_size_error` (12,008 tokens vs 2048). No truncated HTTP 200 was accepted.

Therefore `keep + (num_ctx-keep)//2` is not the normal prompt admission limit. v4 half-window preflight is **retired**. v3 remains invalid for its original defect; do not revive it.

## Planning equation

```
predicted_complete_prompt_tokens + 2500 + 1500 <= num_ctx
num_ctx <= 40960
truncate = false
shift = false
```

Also required after every live rung (not run yet):

- appended-log proof of no truncation and no context shift
- `prompt_eval_count` agrees with complete log tokens
- complete tokens stay within calibrated estimator tolerance (A2 vs documented 24,109 was **+65 / ~0.27%**; live planner uses the frozen-rate formula, which predicted 24,233 for the A2 packet and did not underestimate)
- full GPU residency
- peak VRAM `< 22.5 GB`
- clean explicit unload before the next rung

Stop immediately on estimator underestimate, overflow rejection, truncation/shift evidence, CPU offload, unknown placement, VRAM ceiling, timeout, or unload failure.

Do not reuse truncated historical runs as rungs, narration comparisons, knees, or operating points. A2 is the first valid full-prompt hardware measurement.

VRAM projections still consult the historical **KV-vs-`num_ctx`** occupancy curve as a conservative ceiling check. Those points are occupancy measurements, not accepted ladder rungs. A2 measured **20.239 GB** peak at `num_ctx=28416` versus a 21.604 GB historical occupancy point at the same context.

Packet table: `I11A0-FULL-PROMPT-V5-PACKET-PLAN.json`  
Ops (not authorized): `docs/ops/i11a0_gate3.b.full-prompt-v5.json`
