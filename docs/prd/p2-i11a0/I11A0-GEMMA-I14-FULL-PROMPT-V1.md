# I11A.0 Gemma 4 26B cleaned-I14 full-prompt ladder v1

Separate from every Qwen capacity, estimator, VRAM-fit, and quality experiment.

## Problem

Qwen B at 27K / `num_ctx=39424` exceeded the 22.5 GB FlightSim ceiling (peak 23.1377 GB) after a valid full prompt. Production operating headroom is insufficient. Do not generate Qwen again.

The first Gemma rung must not under-protect the complete prompt. The only valid Gemma smoke is +182 tokens / +9.6144% relative at `num_ctx=6144`. At the 8K complete-request diagnostic (10,439 tokens bytes÷4), the relative envelope is larger than +182 and must govern.

## Success

Offline controller, config, first-rung packet plan, and proofs exist. No model pull and no Gemma inference until founder authorization.

## In

- `gemma4:26b` digest `08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68` Q4_K_M
- Frozen accepted I14 cleaned-email messages, nested complete-message packets
- Prompt v0.3, thinking off, temperature 0.1, seed 42, `truncate=false`, `shift=false`
- Reserves: output 2,500 + safety 1,500; context aligned upward to 256
- Protected complete-prompt prediction is the **maximum** of:
  1. complete-request bytes÷4 (diagnostic)
  2. diagnostic + largest positive Gemma additive error (+182)
  3. diagnostic × largest positive Gemma relative-error envelope (×1.096144)
  4. any stronger documented model-specific envelope (none beyond the smoke pair)
- Then add documented planning guards: additional relative guard ≥0.5% and fixed +256 tokens
- Skip already-covered nominals; record complete-message overshoot; never shrink packets
- If actual complete-prompt tokens exceed the protected prediction, stop enlargement
- Safety-margin failure is a distinct class from truncation, VRAM boundary, and narration-quality failure
- Do not reduce `num_ctx` to stay under a projected VRAM number. Runtime VRAM remains strictly below 22.5 GB. If the required context reaches 22.5 GB, classify a valid Gemma VRAM boundary.

## Out

- Qwen retry, Gemma pull, live inference, SMS, production narrator, Words of Life, Peggy scenario
- Qwen v5 estimator, Qwen token-ratio calibration, Qwen VRAM curve, half-window rule, Qwen 40960 limit
- Quality judging during the ladder
- Shrinking `num_ctx` for an unmeasured VRAM projection

## Envelope formula

```
diagnostic = ceil(complete_request_bytes / 4)
governing  = max(diagnostic, diagnostic+182, ceil(diagnostic × 1.096144))
protected  = ceil(governing × 1.005 + 256)
planned_num_ctx = ceil_256(protected + 2500 + 1500)
```

Representative 8K diagnostic 10,439:

- additive envelope = 10,439 + 182 = 10,621
- relative envelope = ceil(10,439 × 1.096144) = 11,443
- governing = 11,443 (relative; +182 is smaller and must not replace this envelope)
- protected = ceil(11,443 × 1.005 + 256) = **11,757**
- multiplying without the inner relative ceil, `ceil(10439 × 1.096144 × 1.005 + 256)` = 11,756; the implemented max-then-guard path is one token higher because relative is ceiled first
- planned `num_ctx` = ceil_256(11,757 + 2,500 + 1,500) = ceil_256(15,757) = **15,872**

## First-rung planning table

| Field | Value |
| --- | --- |
| Nominal evidence | 8,000 estimated (bytes÷4); packet not shrunk |
| Diagnostic prompt estimate (complete-request bytes÷4) | 10,439 |
| Additive envelope | +182 → 10,621 |
| Relative envelope | +9.6144% → 11,443 |
| Additional relative guard | 0.5% |
| Fixed guard | 256 tokens |
| Protected complete-prompt prediction | **13,465 observed** (do not enlarge from 11,757) |
| Reserve equation | `actual + 2500 + 1500 ≤ num_ctx` → 17,465 required at the failed 15,872 ctx |
| Safety shortfall at 15,872 | **1,593** (not the −93 remainder after prompt+output) |
| Proposed same-packet `num_ctx` | **17,664** |
| Future-packet planner | `ceil(max(diag, diag+182, ceil(diag×1.096144), ceil(diag×13465/10439)) × 1.005 + 256)` then +4,000 aligned |
| Model context limit | 262,144 (advertised; not Qwen 40,960) |
| Expected VRAM status | measured 21.615 GB peak at 15,872; 17,664 projected below 22.5 GB with thin headroom |
| Prior Gemma smoke peak | ~21.65 GB at `num_ctx=6144` |
| Hardware risk | 15,872 ctx is larger than the smoke window; the 8K rung may already sit near the 22.5 GB FlightSim ceiling. If it reaches 22.5 GB, that is a valid Gemma VRAM boundary, not a reason to shrink context. |

## Authorization

Founder authorized **exactly one** first-rung execution (`first_rung_only`). Remaining ladder, 9K, refinement, repeats, Qwen, Words of Life, Peggy, and production narration remain unauthorized.

Docker Desktop and MemoryBox data-plane containers (Postgres, Qdrant) may stay running so the ladder is production-like. Do not treat Docker as a preflight failure.

Execution `a34465944adba324c6660a8c5a25f6f7a3dff067c845ce42582b9d85ee787cfc` is preserved unchanged. Classification: `full_prompt_evaluated_estimator_and_safety_margin_failed`. Not a stable rung. 9K is not authorized. `inference_authorized` and `calibrated_8k_rerun_authorized` are false until founder authorizes a 17,664 rerun.

Docker Desktop is recorded, not refused. Require RAM ≥12 GB free and page-file/commit available ≥8 GB.

