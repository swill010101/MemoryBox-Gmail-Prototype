# 27K Qwen B narration-quality review

**Bounded packet-narration review only.** This is not the Peggy narrative, not Words of a Life, and not an answer to “Tell me about Peggy George.” It evaluates four completed Qwen B outputs for one I14 household-email packet.

**Source limitation.** The packet contains **accepted I14 cleaned email only**. It does not contain SMS, photos, video, calendar, or later Peggy evidence.

**No inference in this review.** Ollama was not called. Existing COMPLETE run directories were not rewritten.

## Purpose and scope

Founder and Codex review of narration quality at the valid 27K rung of `gate3-b-i14-full-prompt-v5`, using only these executions:

| Blinded copy | Role | Execution ID |
| --- | --- | --- |
| Candidate A | Coarse (audit copy) | `d22f720fd063b6befe09fe02f5ca96f4a5f9693252b8868570f8ee310ec747d9` |
| Candidate B | Repeat 1 | `8e2c493bc89c96f1ad92fb97a87b471456e3660f213e36e0e3671ad761ab0960` |
| Candidate C | Repeat 2 | `ddaefaeb5da8826d79f732d49045085d3b7439eb8da7154561d84d30786e4f72` |
| Candidate D | Repeat 3 | `b65bf2af63a1b952721b9b484c41907851313187d93510e9da7a86c33077b55b` |

The four outputs are **not** all byte-identical. Candidate A is the sentence-level audit copy because it is the proposed-point coarse text and is byte-identical to Candidate B. Candidates C and D are retained for founder comparison. There is no four-way canonical identical narration.

## Model and configuration

| Item | Value |
| --- | --- |
| Tag | `qwen3:14b-q8_0` |
| Digest | `304bf7349c71ad37a07eec8be67212b3f05b0f243f4a6f7c98e90dd2f3009f48` |
| Prompt | `i11a0-narration-v0.2-draft` SHA-256 `c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b` |
| think | false |
| truncate / shift | false |
| temperature | 0.1 |
| seed | 42 |
| num_ctx | 39424 |

## Packet identity (all four)

Verified identical across the four COMPLETE runs:

| Field | Value |
| --- | --- |
| estimated evidence tokens (bytes÷4) | 27,054 |
| evidence bytes | 108,216 |
| messages | 62 |
| threads | 42 |
| actual complete prompt tokens | 34,806 |
| num_ctx | 39,424 |
| date range | 2005-12-10 through 2007-12-04 |
| packet / evidence_packet.txt SHA-256 | `ae0fcbb738dd956282aef23188fd53e703adefed7ba2ee1630a0a653b6ce20d7` |
| evidence IDs | 62 IDs; last included `93a44b2a-03c9-4f7c-8764-f9855d3b1ccb`; omitted split remainder `8c2b7377-b841-4be3-8b52-0a34a25a4d43` (thread T-0958) |

`prompt_sha256` and model digest match. `user_sha256` differs for Candidates C and D only because `packet_id` is `qwen3:14b-q8_0-27000-cold-1` / `cold-2` / `cold-3`. That is not a different evidence packet.

**Harness mismatch (not a different packet):** `packet_manifest.json` has `partial_context: true`. Every user wrapper says `partial_context: no` and `partial_boundary_note: none`. The prompt tells the model to add a missing-context close only when the user message says yes. The missing close is therefore expected given the wrapper, and is still a defect relative to the packed evidence.

## Special checks

| Check | Result |
| --- | --- |
| Four narrations byte-identical? | **No.** A = B. C and D each differ. |
| Cite only packet evidence IDs? | **No citations at all.** No invented IDs. Citation requirement failed. |
| Every factual sentence adequately evidenced? | **No.** See `claim_audit.csv`. |
| Invent feelings, motives, relationships, outcomes, significance? | **Yes**, throughout A/B and more strongly in C’s completed-holiday ending. Brother Tom is supportable. |
| Confuse Tom’s words with Peggy’s? | **A/B:** omitted Tom’s MS-150 letter rather than attributing it to Peg. **C:** frames the MS-150 thanks as Tom sharing the ride with Peg; the packet is Tom’s group letter (Peggy George on the To line) plus Sue Will’s reply. |
| Confuse forwarded/quoted material with the outer author? | **A/B:** did not unpack forwards. **C:** compresses the MS-150 thread without separating Sue’s reply from Tom’s letter. |
| Claim a discussed/planned event occurred? | **Yes.** A/B: “ensuring that each person received,” “everyone received something they would cherish.” C: “efforts paid off… everyone received the gifts they had hoped for.” DVD/VCR player for Dad is a planned Target run in the packet, not shown as completed. |
| Disclose partial context correctly? | **No** relative to the packet (T-0958 split). User wrapper incorrectly said `no`. |
| Omit material that distorts this bounded account? | **Yes.** A/B is a Christmas-2006 mood essay. It drops 2005-12-10, October 2006 MS-150, ice/power, car-repair outcome, 2007 tail, and almost all named gifts. |
| Output-limit termination? | **No.** `done_reason=stop`; eval_count 412–421 versus a 2500-token output budget. Natural stop. |

## Bundle files

- `README.md` — this file
- `repeatability.json`
- `canonical_narration.md` — Candidate A, unedited, with execution metadata outside the prose
- `evidence_packet.md` — exact I14 cleaned packet plus a short YAML header
- `claim_audit.csv` / `claim_audit.json`
- `narration_quality_assessment.md`
- `founder_score_sheet.md`
- `prompt_change_recommendations.md` — prompt not modified
- `candidates/candidate_A.txt` … `candidate_D.txt`
- `HASHES.txt`

## Stop

Stop for founder and Codex narration-quality review. Do not start Peggy narrative, Words of a Life, A/C testing, coexistence testing, prompt revision, or additional inference from this bundle.
