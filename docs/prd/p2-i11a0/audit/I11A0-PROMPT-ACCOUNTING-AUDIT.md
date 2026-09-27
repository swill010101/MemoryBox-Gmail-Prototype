# I11A.0 cleaned-I14 prompt-accounting forensic audit

**Status:** `provisional_invalidated_pending_prompt_accounting_audit`  
**Models called:** `false`  
**Original Gate 3 B-I14 run artifacts rewritten:** `false`  
**HASHES.txt SHA-256 (unchanged after audit read):** `340002243c56d219a9eb22b91564a4af4841906b2bcad0892a6897c39717a57e`  
**Results root:** `//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark/gate3-b-i14`  
**COMPLETE markers hashed:** 43; byte-for-byte unchanged after this audit.

No Ollama generation, pull, Peggy narrative, coexistence, A/C, I11A.1, I11A.2, or SMS was run.

The 42K packet is **not** an accepted production operating point.

---

## 1. Ranked root-cause candidates

### 1 (leading): reported `prompt_eval_count` tracks configured `num_ctx`, not nested evidence size

On every inferred execution (42/42), the final raw stream `prompt_eval_count`, the token-accounting copy, and the CSV/JSONL `actual_prompt_tokens` are identical and equal

`configured_num_ctx // 2 + 2`

with **zero** transformation. Independent packets that share `num_ctx` share the same actual (18K and 31K both `num_ctx=24064` both actual `12034`; 33K and 34K both `25856` both `12930`).

That identity explains the non-monotonic “actuals”:

| Packet | Evidence bytes | `num_ctx` | `num_ctx/2+2` | Reported actual |
|--------|---------------:|----------:|--------------:|----------------:|
| 27K | 108,216 | 32,768 (v1) | 16,386 | 16,386 |
| 28K | 115,031 | 22,528 (v2) | 11,266 | 11,266 |
| 42K | 168,075 | 30,720 (v2) | 15,362 | 15,362 |
| 47K | 188,654 | 33,792 (v2) | 16,898 | 16,898 |

The 27K→42K drop of 1,024 reported tokens is the drop from v1 `32768` to v2 `30720`, not a loss of evidence. Nesting is an exact byte prefix (see §2).

Ollama 0.34.1 field semantics are therefore **not** established as “tokens in the complete rendered prompt.” The name `prompt_eval_count` was not treated as proof. A future cold-cache two-`num_ctx` proof is required; it is **not** authorized here.

### 2: v2 planner calibrated against the same identity

v2 predicted 26,617 complete-prompt tokens at 42K because it treated v1 `actual_prompt_tokens` (also `num_ctx/2+2`) as prompt size. Unused context `30720 − 15362 = 15358` is tautological. Do **not** recalibrate v2 against these actuals.

### 3 (rejected as packer defect): nested evidence was removed or reordered

Unique packets 18K→48K: 0 IDs removed, 0 reordered, exact prior-packet byte prefix at every rung.

### 4 (unproven): HTTP truncation or wrong packet submitted

Controller code path inserts `request.evidence_text` in full into `render_user_message` and JSON-encodes `/api/chat` with no `num_ctx`-tied string slice. Reconstructed user messages contain the saved packet (`evidence in user` is true for all 43 folders). **Historical request JSON was not persisted**, so byte-identical historical HTTP bodies cannot be proven.

### 5 (does not explain the identity): prefix cache / `keep_alive=2m`

Chat used `keep_alive="2m"` then unload `keep_alive: 0`. Cache reuse cannot produce `num_ctx/2+2` on every size, nor 18K=31K with different packets. Suffix growth of thousands of evidence bytes cannot map to a *smaller* reported count while still matching `num_ctx/2+2`.

### 6: series VRAM bleed (separate, confirmed)

`Gate3Progress.vram_history` was never reset between executions, and `finalize_hardware` mixed that series list into `vram_peak_gb`. The 48K peak 22.5449 GB was copied onto later rows (refinement 47164 and 45K repeat). Corrected per-execution peaks are in `I11A0-VRAM-PER-EXECUTION-SIDECAR.json`.

---

## 2. Packet-nesting audit

Unique inferred packets, ordered by estimated evidence. Full ordered evidence IDs are in `I11A0-PROMPT-ACCOUNTING-AUDIT.json` (`nesting_audit`). First ID is always `992d6453-3376-425c-a62b-fa05db1b4a3e`. Defects: **none**.

| Est. | Req. | Exec (12) | Planner | Bytes | Msgs | Threads | Last ID (12) | Prefix | Added | Removed | Reordered | `num_ctx` | Actual |
|-----:|-----:|-----------|---------|------:|-----:|--------:|--------------|--------|------:|--------:|-----------|----------:|-------:|
| 18516 | 18000 | 7247d899dcfd | v1 bytes÷4 | 74063 | 43 | 29 | f7b0b7bc-93c1 | first | — | 0 | no | 24064 | 12034 |
| 19386 | 19000 | 4fb582776ace | v1 | 77543 | 45 | 30 | 44202161-b153 | exact | >0 | 0 | no | 24832 | 12418 |
| 20008 | 20000 | c75adba4171e | v1 | 80029 | 47 | 30 | f15fe3e8-548a | exact | >0 | 0 | no | 25600 | 12802 |
| 21288 | 21000 | 533170f93d41 | v1 | 85152 | 49 | 32 | 4961c3bd-5792 | exact | >0 | 0 | no | 26880 | 13442 |
| 22547 | 22000 | a14fc5c430d3 | v1 | 90186 | 51 | 33 | 955f91b0-d4c3 | exact | >0 | 0 | no | 28160 | 14082 |
| 23491 | 23000 | 8dacd64c9f10 | v1 | 93964 | 52 | 34 | 9487a219-af7c | exact | >0 | 0 | no | 29184 | 14594 |
| 24522 | 24000 | 0b5bbbd3c962 | v1 | 98087 | 55 | 37 | df50ec2b-70f3 | exact | >0 | 0 | no | 30208 | 15106 |
| 25849 | 25000 | 12acde59a980 | v1 | 103395 | 58 | 38 | d3502ac2-2245 | exact | >0 | 0 | no | 31488 | 15746 |
| 26147 | 26000 | 2f36ab30da1d | v1 | 104587 | 60 | 40 | f412f34e-fdf3 | exact | >0 | 0 | no | 31744 | 15874 |
| 27054 | 27000 | 3bb1f765e92b | v1 | 108216 | 62 | 42 | 93a44b2a-03c9 | exact | >0 | 0 | no | 32768 | 16386 |
| 28758 | 28000 | 2e03b8c944d7 | v2 | 115031 | 63 | 42 | 8c2b7377-b841 | exact | >0 | 0 | no | 22528 | 11266 |
| 29512 | 29000 | 333421cd4401 | v2 | 118046 | 64 | 43 | 79e8022b-46cb | exact | >0 | 0 | no | 23040 | 11522 |
| 30463 | 30000 | 58a133c1dc29 | v2 | 121852 | 66 | 45 | 320549b9-96f9 | exact | >0 | 0 | no | 23552 | 11778 |
| 31154 | 31000 | e2a26994eb5d | v2 | 124616 | 67 | 46 | af0cfa07-53ef | exact | >0 | 0 | no | 24064 | 12034 |
| 32031 | 32000 | 7e58ae2ba5e9 | v2 | 128122 | 68 | 47 | 0c61d19a-222c | exact | >0 | 0 | no | 24576 | 12290 |
| 33901 | 33000 | 91c328075741 | v2 | 135604 | 69 | 47 | 1b8c14b5-f7c1 | exact | >0 | 0 | no | 25856 | 12930 |
| 34084 | 34000 | ab3dc452ff15 | v2 | 136333 | 70 | 48 | 244fa98d-9ff7 | exact | >0 | 0 | no | 25856 | 12930 |
| 36687 | 35000 | d5f26d05fc2c | v2 | 146748 | 71 | 48 | 33bb79e6-29e4 | exact | >0 | 0 | no | 27392 | 13698 |
| 37275 | 37000 | 0e61ac8cd6cd | v2 | 149099 | 72 | 49 | 98f1e0df-6d1d | exact | >0 | 0 | no | 27904 | 13954 |
| 38225 | 38000 | 6342b7ec749b | v2 | 152898 | 73 | 50 | 0fbe19d5-9a27 | exact | >0 | 0 | no | 28416 | 14210 |
| 39012 | 39000 | f80bd8c3fc33 | v2 | 156047 | 74 | 51 | 55ac0916-def8 | exact | >0 | 0 | no | 28928 | 14466 |
| 41500 | 40000 | 7a1d99e6dafd | v2 | 166000 | 76 | 52 | be069708-2a20 | exact | >0 | 0 | no | 30464 | 15234 |
| 42019 | 42000 | ee5a83c20cb3 | v2 | 168075 | 78 | 54 | 1863cc7d-fcb3 | exact | >0 | 0 | no | 30720 | 15362 |
| 43854 | 43000 | 49ff29a0eca0 | v2 | 175414 | 80 | 55 | 7462d86b-216e | exact | >0 | 0 | no | 31744 | 15874 |
| 44239 | 44000 | 55c07773ef18 | v2 | 176954 | 81 | 55 | 9db2dcc5-4405 | exact | >0 | 0 | no | 32000 | 16002 |
| 45754 | 45000 | 3e81b5099de6 | v2 | 183014 | 84 | 56 | 18868b6c-d020 | exact | >0 | 0 | no | 33024 | 16514 |
| 47164 | 46000 | 1f68131fde8f | v2 | 188654 | 85 | 56 | 3163a69b-a5b0 | exact | >0 | 0 | no | 33792 | 16898 |
| 48028 | 48000 | 849e150827fe | v2 | 192109 | 87 | 58 | 119e8289-14ab | exact | >0 | 0 | no | 34560 | 17282 |

27K packet SHA-256: `ae0fcbb738dd956282aef23188fd53e703adefed7ba2ee1630a0a653b6ce20d7`  
42K packet SHA-256: `9807caf061f57b4f949e837774a158f6dfbc142de2e88a252a62eba540d9f0b6`  
47,164 packet SHA-256: `29c9b427c5c897ea5bbac810965b47416131f677cc047b0792d8a812cf2bf848`

Partial-context flags and boundary IDs change at some rungs; that did **not** drop earlier evidence. Serialized evidence bytes and message counts never shrink.

---

## 3. Saved packet versus submitted request

| Layer | Historically persisted? | Audit finding |
|-------|-------------------------|---------------|
| 1 Saved packet text | Yes (`evidence_packet.txt`) | SHA-256 matches manifest `packet_sha256` |
| 2 Evidence in user template | Not as a separate file | Reconstructed `render_user_message(..., evidence_text=saved_packet)` contains the full saved packet for every run |
| 3 Complete user message | No | Reconstructable only from current template + saved packet |
| 4 System prompt | Implicit (frozen prompt hash on the run) | Current `SYSTEM_PROMPT` SHA recorded in the audit JSON |
| 5 Complete `/api/chat` JSON | **No** | Historical payload equality is **not** claimed |
| 6 Ollama-evaluated prompt | Only `prompt_eval_count` on the final stream event | No tokenizer count; no truncation field besides `done_reason` |

Code path (`NestedMessagePacker` → `RunRequest.evidence_text` → `_chat` payload `messages[1].content` → `json.dumps` → HTTP POST): no max-string slice, no `num_ctx`-tied truncation of the body, no partial file read. Packer stops adding messages after the target but never removes earlier complete messages.

**Future behavior now implemented:** `_chat` builds `request_capture` **before** POST: exact request JSON, system/user/evidence hashes and byte counts, `options`, model tag/digest, `num_ctx`, `num_predict`, `keep_alive`, execution/test-case IDs. `write_gate3_run_artifacts` writes `request_capture.json`. Sensitive family text stays under gitignored `docs/test-output/i11a0-benchmark/gate3-b-i14/`.

---

## 4. `prompt_eval_count` provenance

For every inferred run: `raw_api.jsonl` last event `prompt_eval_count` = `token_accounting.actual_prompt_eval_count` = CSV/JSONL `actual_prompt_tokens`. Transformation = 0.

Whether that value is the entire rendered prompt vs newly evaluated tokens after cache: **not proven from the field name.** Installed Ollama family is 0.34. Explicit unload (`keep_alive: 0`) was used after chat. That does **not** disprove the `num_ctx/2+2` identity, which holds across cold-looking load times and across different packets.

`done_reason` on the 48K final event is `stop`, not `length`. No separate truncated-token count was stored.

**Tokenizer:** none. No model or tokenizer was downloaded. No exact offline token count of persisted prompts was computed.

---

## 5. Why 16,386 at 27K fell to 15,362 at 42K

Evidence grew 108,216 → 168,075 bytes, +16 messages, exact byte prefix. Reported actual fell because `num_ctx` fell 32,768 → 30,720 and the reported count is `num_ctx/2+2` in both cases. This is **not** a 42K evidence-capacity result.

---

## 6. v2 planning-error table (selected)

`actual_required_context = prompt_eval_count + 2500 + 1500`. Unused here is `num_ctx − required`. Prediction error is actual − predicted (large negative because predicted used inflated v1 “actuals”).

| Req. | Exec (12) | Diagnostic | Predicted | Actual | Error | `num_ctx` | Required | Unused | Per-exec VRAM GB |
|-----:|-----------|-----------:|----------:|-------:|------:|----------:|---------:|-------:|-----------------:|
| 28000 | 2e03b8c944d7 | 30344 | 18471 | 11266 | −7205 | 22528 | 15266 | 7262 | 20.6992 |
| 31000 | e2a26994eb5d | 32778 | 19947 | 12034 | −7913 | 24064 | 16034 | 8030 | 20.9355 |
| 42000 | ee5a83c20cb3 | 43774 | 26617 | 15362 | −11255 | 30720 | 19362 | 11358 | 21.9590 |
| 46000 | 9142b07d5abe | 48958 | 29762 | 16898 | −12864 | 33792 | 20898 | 12894 | 22.4297 |
| 48000 | 849e150827fe | 49868 | 30314 | 17282 | −13032 | 34560 | 21282 | 13278 | 22.5449 |

42K unused versus prompt_eval only: `30720 − 15362 = 15358` (the figure in the original complaint). That is `num_ctx − (num_ctx/2+2)`, not leftover evidence context.

Full v2 rows: audit JSON `v2_planning_rows`.

---

## 7. Corrected per-execution VRAM

Series-wide maximum: **22.544921875 GB** (48K execution `849e150827fe…` own samples).

Contaminated recorded peaks (sidecar only; originals not rewritten):

| Exec | Role | Recorded peak | Corrected per-exec peak |
|------|------|--------------:|------------------------:|
| 1f68131fde8f… | refinement, 47,164 packet | 22.5449 | **22.4297** |
| 5f5f14eeae69… | repeat_proposed 45K | 22.5449 | **22.3154** |

48K itself is **not** contaminated: recorded = per-exec = 22.544921875.

Controller fix: `Gate3Progress.begin_execution()` clears per-run `vram_history` / `peak_vram_gb` and keeps `series_peak_vram_gb` separately. Future `vram_peak_gb` must use only the current execution’s samples plus that execution’s heartbeats.

---

## 8. All 47,164-packet executions

Packet hash `29c9b427c5c897ea5bbac810965b47416131f677cc047b0792d8a812cf2bf848`. Same evidence IDs. Same `num_ctx=33792`. Same actual `16898`.

| Exec | Requested target | Recorded phase | Corrected role | Per-exec VRAM | Safety | Placement |
|------|-----------------:|----------------|----------------|--------------:|--------|-----------|
| 9142b07d5abe… | 46000 | coarse | coarse (this size) | 22.4297 | passed | gpu_resident |
| ae771364baa0… | 46000 | coarse | confirm / same packet, not a new size | 22.4395 | passed | gpu_resident |
| 1f68131fde8f… | 46000 | refinement | refinement of the **same** packet; **not** next-larger | 22.4297 | passed | gpu_resident |

They share one packet because the packer already covered ~47,164 estimated evidence tokens at the 46,000 request; refinement at 46,000 cannot invent a larger nested set. A packet cannot be both the proposed point and a distinct next-larger point. Next distinct packet is 48,028 (`849e1508…`).

45K (`45754` estimated, hash `38b29de3…`) is a different packet (the proposed-repeat size in the ladder), not 47,164.

---

## 9. 48K ceiling event

Execution `849e150827fe99188ef5bfe3334bba6a3848173b5a3a1ce7c87504281465f4ad`:

- Requested 48,000; estimated 48,028; 192,109 evidence bytes.
- Per-execution (and recorded) peak **22.544921875 GB**, which is **≥ 22.5**.
- Final stream `done_reason=stop` (generation finished; not `length`).
- Recorded classification is `successful_stable` even though `hard_stop_reason` for peak ≥ 22.5 is `vram_ceiling`. Treat the VRAM sample as **observed hardware evidence**. Do **not** treat 48K as the true evidence ceiling until prompt completeness and token accounting are verified.

---

## 10. Historical evidence gaps

1. Historical `/api/chat` request JSON was never saved.
2. No local Qwen tokenizer was used.
3. `prompt_eval_count == num_ctx/2+2` is an exact empirical identity on this series; Ollama source/docs were not executed against, and a controlled two-`num_ctx` cold proof is not authorized.
4. Whether Ollama 0.34.1 truncates the prompt internally to something other than the HTTP body cannot be proven from persisted artifacts.

---

## 11. Code changes (future runs)

- `memorybox/ask/i11a/i11a0_prompt_accounting_audit.py` — offline audit + `request_capture_payload` + prove checks.
- `memorybox/ask/i11a/i11a0_smoke.py` — capture request JSON/hashes before POST; 4-tuple `_chat`.
- `memorybox/ask/i11a/i11a0_gate3.py` — persist `request_capture.json`; `begin_execution()`; invalidate recommendation when all inferred actuals match `num_ctx/2+2`; refuse duplicate packet as next-larger.
- `memorybox/ask/i11a/i11a0_gate3_progress.py` — per-execution VRAM reset; series peak retained.

---

## 12. Offline proof

`prove_gate3_offline`: `ok: true`, `models_called: false`, 110 checks including prompt-accounting proofs (nested IDs, submitted evidence vs packet, request hashes, non-monotonic invalidation, per-run VRAM reset, series peak separate, duplicate packet not a new size, ceiling peak does not replace own peak, audit does not rewrite COMPLETE, no Ollama in audit module).

---

## 13–15. Commit, artifacts, rerun

See the assistant reply for branch/SHA after commit.

**Minimum controlled rerun (do not execute until founder authorizes):** three cold loads only: 27,054 packet and 42,019 packet with `keep_alive: 0`, unload between, `request_capture.json` persisted, plus one extra 42,019 load at a *different* `num_ctx` to test the `num_ctx/2+2` identity. No ladder, no coexistence, no Peggy, no recalibration until that identity is confirmed or broken.
