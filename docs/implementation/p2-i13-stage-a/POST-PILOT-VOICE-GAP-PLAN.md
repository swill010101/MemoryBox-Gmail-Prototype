# Post-pilot voice gap plan

## What the completed bounded pilot established

The accepted run `1039c733-2149-40b2-b027-97058e032af3` used one Eugene Will training span (T1) and three held-out spans. It produced two Eugene matches and correctly rejected the off-camera Tom Will span as Eugene. It was stopped after one bounded run; legacy queues and transcript overlays were unchanged.

This is evidence for source-audio matching and a negative off-camera control. It is not a general accuracy claim.

## Remaining voice acceptance gaps

1. Positive recognition of Tom Will is unproven because no independently confirmed Tom training span was in the first run.
2. The selected clear U1 portion was not overlapping or poor-audio acceptance evidence. The unselected remainder remains unreviewed.
3. A confirmed no-match or background-audio case has not been measured.
4. Exemplar retirement, stale-result marking, and bounded affected reprocessing are implemented controls but have not been exercised against a separately approved voice reference.
5. Face/voice corroboration and the broader I13 scenario matrix remain separate acceptance work.

## Smallest owner-review queue before any second run

Use the deployed Review/Explore workflow. Select text, assign or mark Unknown, and save the annotation. Do not use Learn. These are candidates only until Tom confirms them locally.

| Key | Video and range | Owner decision needed | If confirmed |
|---|---|---|---|
| T2 candidate | `20111105_1530.MP4` / `vid-da41273dbd9ac4bb`, 00:37.120-00:42.400 | Is this clearly Tom Will, single-speaker, and adequate as a training reference? | Save a distinct Tom assignment marked `I13 TRAIN T2`. Do not use O1 for training. |
| O1 held-out | `20111105_1532.MP4` / `vid-c57dbd21f993f6d1`, 02:32.240-02:38.340 | Reconfirm the existing off-camera Tom assignment; no new annotation is required if it remains correct. | Reserve it as Tom held-out off-camera evidence. |
| N1 candidate | `second meals on wheels.mp4` / `vid-c015e0fe07414fcc`, 00:00.000-00:20.000 | Is this non-family/background speech or another known speaker? Is it single-speaker enough to label? | If it is not Tom or Eugene, save Unknown/no-match truth. Otherwise record the actual Person; do not invent a no-match case. |
| Q1 candidate | `20111105_1532.MP4` / `vid-c57dbd21f993f6d1`, 02:18.720-02:23.180 | Is the unreviewed portion actually poor audio, overlap, or merely Eugene speaking unclearly? | Save only the confirmed truth. Mark it unresolved if identity cannot be assigned; do not manufacture overlap. |

The smallest next recognition proposal is possible only if T2 and O1 are confirmed: one Tom training extraction, one held-out off-camera Tom comparison, and at most one separately confirmed N1 or Q1 evaluation span. Exact annotation/version IDs, source hashes, time bounds, model hash, thresholds, caps, and retirement behavior must be re-exported read-only and reviewed before another admission.

No recognition, Learn, migration, media conversion, archive unlock, or queue drain is authorized by this plan.

## Confirmed Tom evidence and second-pilot shape

Tom confirmed and saved T2 as a distinct owner-review annotation: `5e106e50-76ce-4fb2-8f62-0083119154cc`, on `vid-da41273dbd9ac4bb`, 00:37.120–00:42.400, 14 timed words. Its person is Tom Will (`33509a4c-0869-458a-b0b9-35a669aace16`). O1 remains a separate Tom annotation: `3fa1c4e1-d8a6-423f-9c9b-1a229d550945`, on `vid-c57dbd21f993f6d1`, 02:32.240–02:38.340, 22 timed words.

[`tom-bounded-voice-pilot-proposal.json`](tom-bounded-voice-pilot-proposal.json) is the smallest valid, design-only four-span shape: T2 trains Tom; O1 is the positive off-camera Tom hold-out; H1 and U1-clear are owner-confirmed Eugene passages used only as Tom negative controls. It selects 40.80 seconds total, preserves the fixed one-attempt/four-span limit, and creates no admission.

This is target-specific evidence, not a fresh general benchmark: H1 and U1-clear were already measured in the Eugene pilot. Background voices and low/mumbled Eugene speech are intentionally excluded until Tom saves a distinct, truthful annotation for a specific interval. No recognition, model invocation, Learn action, migration, archive unlock, media conversion, or queue drain is authorized by this proposal.