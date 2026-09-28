# I11A.0 v4 run 48d5421b classification (sidecar)

Original run files are unchanged. This is a classification sidecar.

**Classification:** `complete_prompt_evaluated_infrastructure_unload_or_log_verification_failure`  
**Not a stable ladder rung.**

## Log facts (FlightSim `server.log`, 2026-09-28 07:54–07:57 CDT)

Ollama tokenized and evaluated **12,201** tokens. There is **no** `truncating input prompt` line on 2026-09-28. The slot recorded `truncated = 0`. `prompt_eval_count=12201` is the complete evaluated prompt, greater than the half-window of 11,394.

Therefore the half-window is the **overflow fallback destination**, not the preflight admission threshold. Do not keep requiring `predicted <= keep + (num_ctx-keep)//2` as a hard admission rule until the no-truncation diagnostic is reviewed.

Runner: `-c 22784 -np 1 --context-shift --keep 4`, CUDA, GPU-resident, no CPU offload. High Windows RAM (~29.94/31.16 GB) is not offload.

## Why `truncation_log_unverified`

The v4 controller searched for a unique `llama_server.go:318` truncation WARN (and treated “no match” as failure). An untruncated run has no such WARN, so correlation failed even though complete-eval lines were present.

## Why VRAM did not return to baseline in the run record

Approved tolerance remains **2.0 GB**: `settled <= baseline + 2.0`. Baseline 2.625 GB, recorded final 20.75 GB. Unload HTTP took 2 ms (`POST /api/generate`); llama-server did not log a stop; `/api/ps` was not polled after unload; generate telemetry has no post-unload sample. Chat `keep_alive` was `2m`. Later progress VRAM 2.625 GB is consistent with **delayed release after the measurement window**, not a baseline math error. Treat as unload/telemetry failure, not CPU offload.

## Estimator

Predicted 11,340 vs complete 12,201: **+861 tokens (~7.6%)**. Record only. Do not enlarge the ladder. Do not calibrate from truncated historical `prompt_eval_count`. Envelope update waits for founder review.

## Host RAM (diagnostic)

~1.22 GB available at peak use. Diagnostic must stop if available RAM is still about 1–2 GB. Proposed diagnostic-only guard: **stop at ≤2.0 GB available; prefer ≥4.0 GB available** after MemoryBox and other apps are closed.
