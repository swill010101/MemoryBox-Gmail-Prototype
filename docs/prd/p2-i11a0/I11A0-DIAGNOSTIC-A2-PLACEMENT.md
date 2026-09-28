# Diagnostic A2 / B — placement-qualified retry

First Diagnostic A (`34a376c8`) remains the accepted token-accounting proof. Do not rewrite its `request_capture.json` or `run_record.json`.

A2 uses the same 18K packet, model digest, `num_ctx=28416`, `num_predict=256`, temperature 0.1, seed 42, `think=false`, `truncate=false`, `shift=false`. Measurement-only changes: `keep_alive=2m`, IndependentRequestSampler at 1s writing `in_request_telemetry.jsonl` incrementally, `/api/ps` after the last stream event and before `keep_alive=0` unload.

Diagnostic B runs only if A2 is `gpu_resident`, `cpu_offload=false`, peak VRAM `<22.5 GB`, complete prompt ~24,174, no truncation log, and clean unload. Overflow with `truncate=false`/`shift=false` must fail closed.

If A2 placement is unknown, stop. Do not run B. Do not resume the ladder.

18K estimator: predicted 24,109 vs observed 24,174 (**+65 tokens, ~0.27%**). Do not mix with the v4 8K +861 error.
