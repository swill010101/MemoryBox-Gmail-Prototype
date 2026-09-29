# I11A.0 narration-quality v0.3 27K confirmation

**Not a capacity ladder.** The accepted 27K Qwen B hardware/context result stands. Prompt v0.2 is retained unchanged. This experiment does not start I11A.1, I11A.2, Peggy, A/C, or production narration.

## Disposition already taken

- Accept 27K as capacity/hardware.
- Reject v0.2 *output* as narration quality.
- Do not declare Qwen B unsuitable until one v0.3 confirmation is reviewed.

## Controller fixes

- `packet_from_saved_row` no longer forces `partial_context=false`.
- Gate 3 `RunRequest` now carries packet partial-context metadata.
- Model-visible `packet_id` is `i14pkt-{packet_sha256}` (no `cold-N`, phase, or repetition).
- `/api/chat` `_chat` uses those request fields; smoke without a stable id keeps the old tag-tokens-warm-rep formula.

## Prompt

- v0.2: `memorybox/ask/i11a/i11a0_prompt.py` (unchanged).
- v0.3 candidate: `memorybox/ask/i11a/i11a0_prompt_v03.py`.

## Inference

Ops default: `inference_authorized: false`. Offline prove and preflight planning do not call Ollama.

After founder authorization: set `inference_authorized` true in `docs/ops/i11a0.b.narration-quality-v03-27k.json`, then on FlightSim:

```powershell
cd <repo-root>
git fetch
git pull origin cursor/p2-i11a0-offline-harness
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox i11a0-narration-quality-v03-confirm --confirm-benchmark --config docs/ops/i11a0.b.narration-quality-v03-27k.json --out docs/test-output/i11a0-benchmark/gate3-b-i14-narration-quality-v03-27k-confirm
```

If the revised request cannot satisfy `estimated_complete + 2500 + 1500 <= num_ctx <= 40960`, inference must not start and the evidence packet must not be shrunk.
