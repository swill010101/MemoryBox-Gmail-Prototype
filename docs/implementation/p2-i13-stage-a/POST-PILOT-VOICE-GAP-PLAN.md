# Post-pilot voice gap plan

## What the completed bounded pilot established

The accepted run `1039c733-2149-40b2-b027-97058e032af3` used one Eugene Will training span (T1) and three held-out spans. It produced two Eugene matches and correctly rejected the off-camera Tom Will span as Eugene. It was stopped after one bounded run; legacy queues and transcript overlays were unchanged.

This is evidence for source-audio matching and a negative off-camera control. It is not a general accuracy claim.

## Remaining voice acceptance gaps

1. Positive recognition of Tom Will is now established only for the second pilot's exact T2 reference and O1 held-out passage; generalized accuracy remains unproven.
2. The selected clear U1 portion was not overlapping or poor-audio acceptance evidence. The unselected remainder remains unreviewed.
3. A confirmed background/no-match case is now measured by N1; it was correctly rejected as Tom. This is narrow evidence for the exact TV-announcer span, not a general background-audio claim.
4. Exemplar retirement, stale-result marking, and bounded affected reprocessing are implemented controls but have not been exercised against a separately approved voice reference.
5. Face/voice corroboration and the broader I13 scenario matrix remain separate acceptance work.

## Smallest owner-review queue before any second run

Use the deployed Review/Explore workflow. Select text, assign or mark Unknown, and save the annotation. Do not use Learn. These are candidates only until Tom confirms them locally.

| Key | Video and range | Owner decision needed | If confirmed |
|---|---|---|---|
| T2 completed | `20111105_1530.MP4` / `vid-da41273dbd9ac4bb`, 00:37.120-00:42.400 | Tom confirmed the saved assignment. | Used as the Tom training reference in the completed second pilot. |
| O1 completed | `20111105_1532.MP4` / `vid-c57dbd21f993f6d1`, 02:32.240-02:38.340 | Tom's existing off-camera assignment was used unchanged. | Held-out Tom result: match, 0.487. |
| N1 owner truth saved | `second meals on wheels.mp4` / `vid-c015e0fe07414fcc`, 00:00.000-00:06.740 | Tom identified the speech as a TV announcer and saved Unknown: annotation `74cc9646-82db-4899-960d-f795f691c524`, transcript version `8f879c74-ceb9-4f2c-b464-4f494ca66c25`, 31 timed words, no `person_id`. | Candidate held-out no-match evidence only. It must never train, create, or imply a family Person. |
| Q1 listening conclusion | `20111105_1532.MP4` / `vid-c57dbd21f993f6d1`, 02:18.720-02:23.180 | Tom heard TV/background audio and Eugene speaking together. This was listening only; no annotation was saved. | Excluded from training, hold-out, and recognition evidence until exact truthful sub-spans are saved. |

The T2/O1 second pilot is complete. N1 now has exact saved Unknown truth: TV announcer, annotation `74cc9646-82db-4899-960d-f795f691c524`, version `8f879c74-ceb9-4f2c-b464-4f494ca66c25`, 00:00.000-00:06.740, 31 timed words, and no person ID. The next proposal may use it only as explicit held-out no-match acceptance evidence after its source hash and current annotation are rechecked. Q1 remains excluded. A new readiness review is required before any admission.

No recognition, Learn, migration, media conversion, archive unlock, or queue drain is authorized by this plan.

## Confirmed Tom evidence and second-pilot shape

Tom confirmed and saved T2 as a distinct owner-review annotation: `5e106e50-76ce-4fb2-8f62-0083119154cc`, on `vid-da41273dbd9ac4bb`, 00:37.120–00:42.400, 14 timed words. Its person is Tom Will (`33509a4c-0869-458a-b0b9-35a669aace16`). O1 remains a separate Tom annotation: `3fa1c4e1-d8a6-423f-9c9b-1a229d550945`, on `vid-c57dbd21f993f6d1`, 02:32.240–02:38.340, 22 timed words.

[`tom-bounded-voice-pilot-proposal.json`](tom-bounded-voice-pilot-proposal.json) is the smallest valid, design-only four-span shape: T2 trains Tom; O1 is the positive off-camera Tom hold-out; H1 and U1-clear are owner-confirmed Eugene passages used only as Tom negative controls. It selects 40.80 seconds total, preserves the fixed one-attempt/four-span limit, and creates no admission.

This is target-specific evidence, not a fresh general benchmark: H1 and U1-clear were already measured in the Eugene pilot. Background voices and low/mumbled Eugene speech are intentionally excluded until Tom saves a distinct, truthful annotation for a specific interval. No recognition, model invocation, Learn action, migration, archive unlock, media conversion, or queue drain is authorized by this proposal.

## Completed Tom bounded pilot

FlightSim admission `9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea` completed on 2026-09-06 and is stopped, current, and visible through the deployed read-only results endpoint. T2 trained Tom Will against O1, an off-camera held-out Tom passage, which scored `match` at 0.4874674861. The two owner-confirmed Eugene controls were correctly `no_match`: H1 at 0.1216411184 and U1-clear at 0.0656342374.

A fresh 433 MB backup was hash-verified before registration at `C:\MemoryBox-backups\i13-final-pre-tom-547048044ed64ccb8b71b42baf16a6e9\memorybox.dump` (SHA-256 `8bf0912c631984e9902562105f5076947ab794218e5fc704c3301b8b4e77c9d0`). The guarded deployment reported unchanged legacy counts and no automatic retry.
## Completed N1 Unknown no-match pilot

FlightSim admission `46cb1d21-b464-4bc4-bf7c-7d0de0202ca6` completed once and stopped on 2026-09-07. It used Tom T2 as the reference, O1 as the Tom positive hold-out, H1 as the known-Eugene no-match control, and N1 as owner-confirmed Unknown TV-announcer evidence. Outcomes were O1 `match` at `0.4874674861`, H1 `no_match` at `0.1216411184`, and N1 `no_match` at `0.1115755753`. The N1 decision agrees with Tom?s saved `unknown` annotation and does not create or infer a Person.

The run used release `29e3f6fb6944adfcece404cb6c89ebb4180f6fe1` and reviewed plan `a9d2a32115db543c13381592bfed189c38c1ba5fb94f303e99f8df62986cf25d`. It created the fresh verified backup `C:\MemoryBox-backups\i13-final-pre-n1-unknown-f3b23c9c1a7645f69932bc9099c744a8\memorybox.dump` with SHA-256 `a89ce78d77cf0ac683b2b8ec143c264def1f2845f9677a77c5830401ee349162`; its E: copy remains a separate storage action until Tom supplies the copy/hash result. Legacy counts were unchanged and automatic retry was false.

The next remaining voice acceptance item is lifecycle proof: retire one separately selected reference, verify its dependent result becomes stale, and prepare a distinct bounded reprocessing proposal. This does not authorize changing the T2/O1/H1/N1 evidence or starting any reprocessing.
