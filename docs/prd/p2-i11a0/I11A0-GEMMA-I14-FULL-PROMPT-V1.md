# I11A.0 Gemma 4 26B cleaned-I14 full-prompt ladder v1

Separate from every Qwen capacity, estimator, VRAM-fit, and quality experiment.

## Problem

Qwen B at 27K / `num_ctx=39424` exceeded the 22.5 GB FlightSim ceiling (peak 23.1377 GB) after a valid full prompt. Production operating headroom is insufficient. Do not generate Qwen again.

## Success

Offline controller, config, first-rung packet plan, and proofs exist. No model pull and no Gemma inference until founder authorization.

## In

- `gemma4:26b` digest `08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68` Q4_K_M
- Frozen accepted I14 cleaned-email messages, nested complete-message packets
- Prompt v0.3, thinking off, temperature 0.1, seed 42, `truncate=false`, `shift=false`
- Reserves 2500 + 1500; VRAM strictly below 22.5 GB at runtime
- Gemma-only conservative envelope: max(bytes÷4, bytes÷4+182 smoke error, rate-guarded bytes÷4) + 256
- Skip already-covered nominals; record complete-message overshoot; never shrink packets

## Out

- Qwen retry, Gemma pull, live inference, SMS, production narrator, Words of Life, Peggy scenario
- Qwen v5 estimator, Qwen VRAM curve, half-window rule, Qwen 40960 limit
- Quality judging during the ladder
