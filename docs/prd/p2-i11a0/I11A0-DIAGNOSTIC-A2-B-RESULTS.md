# Diagnostic A2 and B results (read-only)

Original run files were not rewritten.

## A2 `292642bad1a27cb4bed1e9817ab8658640fc74adc2900a0db74976a935513cf9`

This is the first valid full-prompt hardware measurement. It is not a truncated historical rung and not a performance knee.

| Item | Value |
|------|------|
| Packet SHA | `51f891938ba3ab5910fb20ce8fe457dace74bfb5f9b5b380da28a52f24e73902` |
| Matches required 18K packet | **yes** |
| Packed evidence | 18,516 estimated tokens; 74,063 bytes; 43 messages; 29 threads; partial_context=true |
| Captured-request SHA | `e22c89fd72c3bc92c7ded43c7b51f08aaca56e27abd7bd87d3381ad344b7a747` (81,686 bytes) |
| Outgoing-request SHA | same (recomputed from captured JSON) |
| `num_ctx` | 28416 |
| `num_predict` | 256 |
| `think` | false |
| `truncate` | false (top-level) |
| `shift` | false (top-level) |
| `keep_alive` during chat | `"2m"` |
| Explicit unload | `keep_alive=0` |
| temperature / seed | 0.1 / 42 |
| Model | `qwen3:14b-q8_0` digest `304bf7349c71ad37a07eec8be67212b3f05b0f243f4a6f7c98e90dd2f3009f48` |
| HTTP | 200; fields accepted |
| Complete log prompt | **24,174** |
| `prompt_eval_count` | **24,174** |
| Diagnostic prediction used in A | 24,109 (historical 18K envelope) |
| Error vs that prediction | **+65 tokens (~0.27%)** |
| Frozen-rate formula on 74,063 bytes | 24,233 (did not underestimate A2) |
| Half-window | 14,210; prompt evaluated **above** half-window |
| Placement | **`gpu_resident`**, `cpu_offload=false` |
| `/api/ps` size | 19,885,845,380 bytes (~18.52 GB) |
| `/api/ps` `size_vram` | identical (~18.52 GB GPU-resident) |
| Processor field | not exposed (null) |
| Runner `context_length` | 28416 |
| GPU | NVIDIA GeForce RTX 4090 |
| VRAM baseline | 1.2607421875 GB |
| In-request peak | 20.2392578125 GB (`< 22.5`) |
| Pre-unload (last 1s sample, still loaded) | 20.2392578125 GB |
| Settled post-unload | 1.2607421875 GB |
| Unload | `clean_unload_settled_vram`; model absent immediately; VRAM returned to baseline |
| Host RAM baseline | 12.549 GB used / 18.608 GB available of 31.157 GB |
| In-request RAM peak used | 13.931 GB (available min 17.225 GB) |
| Settled RAM | not sampled after unload (VRAM/ps were) |
| Load | 3.406 s |
| Prompt eval | 6.061 s / 24,174 tokens = **3988.5 tok/s** (`prompt_eval_cached_count=0`) |
| Generation | 5.503 s / 256 tokens = **46.52 tok/s** |
| Total request | 14.993 s |
| Stream | 257 events persisted; only `message.content`; visible 1,317 chars; thinking 0; done event content empty; `eval_count=256`; `done_reason=length`; payload SHA `24a08d89f269706ec030c0d1e26476554b5af8ef75ff036b541fa154d641930d`; **`think=false` honored** |
| Log | appended segment: `task.n_tokens = 24174`; `prompt eval time = 6060.95 ms / 24174 tokens`; `truncated = 0`; no `truncating input prompt`; llama-server `-c 28416` **without `--context-shift`**; 41/41 layers on CUDA0 |

## Diagnostic B `4800ee4b3b4a6130fd9c75ccb4e72a301ae7ca4c5997d3985f6f25d57199d8d3`

Fail-closed overflow. No truncated HTTP 200.

| Item | Value |
|------|------|
| Synthetic user | 32,940 characters with begin/mid/end canaries |
| Request body | 36,869 bytes; SHA `eae60db96b0f34b645e3203f42b9307a67ed3d4f3eaf85a5b83474a2f9425f86` |
| `num_ctx` | 2048 |
| `num_predict` | 16 |
| `truncate` / `shift` | false / false |
| HTTP | **400** |
| Exception / body | `exceed_context_size_error`: request **12,008** tokens exceeds context **2048** |
| Prompt evaluation | none (`prompt_eval_count` null; log `n_tokens = 0` on release) |
| Generation | none |
| Log | `task.n_tokens = 12008` then `send_error`; `truncated = 0`; no `truncating input prompt`; no `--context-shift` |
| Classification | `fail_closed_overflow_rejected` (`fields_effective=true`) |
| Model did load | yes; GPU-resident; size=`size_vram`=15,538,711,428 (~14.47 GB) at this smaller ctx |
| Peak VRAM | 16.161 GB from 1.261 GB baseline |
| Unload | clean; VRAM returned to 1.261 GB |

The overflow log classifier also recorded `complete_log_tokens=12008` because the tokenizer counted the full prompt before rejecting it. That is not a successful truncated generation.
