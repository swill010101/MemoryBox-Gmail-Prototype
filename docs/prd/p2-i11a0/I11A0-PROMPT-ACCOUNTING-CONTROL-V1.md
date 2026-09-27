# I11A.0 prompt-accounting control v1

**Authorization:** founder 2026-09-27. This is the experiment PRD.  
**Experiment id:** `i11a0_prompt_accounting_control_v1`  
**Not** a ladder, capacity, narrative-quality, operating-point, or coexistence test.

## Problem

Completed cleaned-I14 Qwen B runs report `prompt_eval_count == num_ctx // 2 + 2` on every inferred execution. Nested packets are byte-prefix intact. The 42K recommendation is invalidated until this field’s meaning is measured.

## Success

Exactly three cold FlightSim loads (A, B, C) with captured HTTP bytes equal to the persisted request, and a founder-readable comparison:

- A vs B: evidence size changes, `num_ctx` fixed at 30,720.
- B vs C: packet/prompt bytes identical, `num_ctx` 30,720 vs 32,768.

No operating point is named.

## In

- Branch `cursor/p2-i11a0-offline-harness` descendant of `e5efa62a154377ea05c7f994724e56fe5af59f24`.
- FlightSim, RTX 4090, `http://127.0.0.1:11434`, Ollama 0.34.1, `qwen3:14b-q8_0` digest `304bf734…9f48`.
- Frozen I14 export and prompt hash unchanged.
- Existing 27,054 and 42,019 packets copied from `gate3-b-i14` by SHA-256, not rebuilt.
- Isolated output: `docs/test-output/i11a0-benchmark/prompt-accounting-proof`.
- `keep_alive: 0`, cold unload between runs, 22.5 GB hard stop.

## Out

Peggy, A/C, I11A.1/I11A.2, SMS, production narrator, model pull, ladder resume, v2 recalibration, coexistence.

## Constraints

- Toms-Desktop must not start inference.
- `gate3-b-i14` artifacts remain byte-for-byte unchanged.
- Fixed `num_ctx` values are not chosen by v1/v2 planners.
- Family text gitignored.
