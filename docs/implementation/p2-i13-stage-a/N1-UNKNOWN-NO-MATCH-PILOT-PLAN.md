# N1 Unknown held-out no-match pilot plan

## Purpose

This design-only extension measures whether the bounded Tom voice reference rejects a saved, owner-confirmed Unknown TV-announcer span. It does not identify the announcer and does not train a family Person from the span.

## Exact four-span shape

| Role | Key | Evidence | Expected decision |
|---|---|---|---|
| Training | T2 | Tom Will, `vid-da41273dbd9ac4bb`, 00:37.120?00:42.400 | Reference only |
| Held-out | O1 | Tom Will, `vid-c57dbd21f993f6d1`, 02:32.240?02:38.340 | Match |
| Held-out | H1-as-Tom-negative | Eugene Will, `vid-c57dbd21f993f6d1`, 05:25.220?05:45.560 | No match |
| Held-out | N1-TV-announcer-unknown | Unknown TV announcer, `vid-c015e0fe07414fcc`, 00:00.000?00:06.740 | No match |

N1 is active annotation `74cc9646-82db-4899-960d-f795f691c524`, transcript version `8f879c74-ceb9-4f2c-b464-4f494ca66c25`, 31 timed words, `speaker_state=unknown`, and `person_id=NULL`. The source hash is `09e6dfb523724448888586183d9e265f3181f241ab37fa9d6d800ac1b6cf92b3`.

## Bounded implementation rule

The pilot format now permits `person_id: null` only for a `held_out` span whose `speaker_state` is `unknown` and whose explicit `expected_match` is `false`. Training still requires the one target MB Person. Known-person spans retain their existing inferred behavior if `expected_match` is absent, so completed pilots remain readable.

The complete machine-readable proposal is [`tom-n1-unknown-no-match-pilot-proposal.json`](tom-n1-unknown-no-match-pilot-proposal.json). No admission, media operation, recognition, queue drain, migration, Learn action, or archive work is authorized by this design document.
