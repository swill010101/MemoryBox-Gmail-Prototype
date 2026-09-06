# Bounded voice pilot ? implementation preparation

## Concrete scope

Use bounded-voice-pilot-proposal.json as a design artifact, not an executable processing admission. The exact 22-source parent manifest remains intact. The pilot selects only two sources, one target Person (Eugene Will), one training annotation and three held-out annotations. Latest source/version/annotation IDs and actual owner-selected intervals were rechecked in a read-only repeatable-read transaction. All reasons currently say Owner review; do not rely on reason text to enforce training/held-out roles. Pin roles in the immutable pilot selection.

| Role | Source | Saved interval | Purpose |
|---|---|---|---|
| Training T1 | vid-da41273dbd9ac4bb | 02:18.720?02:24.660 | Sole Eugene reference, 5.94 seconds. Reject inadequate audio explicitly; do not widen or substitute automatically. |
| Held-out H1 | vid-c57dbd21f993f6d1 | 05:25.220?05:45.560 | Main positive Eugene test, using the actual 42-word saved annotation. |
| Held-out O1 | vid-c57dbd21f993f6d1 | 02:32.240?02:38.340 | Negative test against Eugene; owner identifies off-camera Tom. No Tom training sample exists in this reviewed set, so this cannot prove positive recognition of Tom. |
| Held-out U1-clear | vid-c57dbd21f993f6d1 | 02:09.640?02:18.720 | Additional Eugene positive on the clear selected portion. The mumbled remainder is not included; this is not an overlap or poor-audio acceptance case. |

Upper bound: four audio extractions, four embeddings, three comparisons, one attempt per span and no automatic retries; 41.46 seconds of selected source audio. Additional source hashing/probing is read-only validation, not an expansion of audio extraction. Proposed per-extraction timeout 120 seconds, per-embedding timeout 120 seconds, overall run timeout 20 minutes; these must be implemented and tested before a run. No source-wide turn sweep, queue drain, automatic transcript generation, model download or legacy-exemplar matching is permitted. No runtime write or execution is authorized by preparing this plan.

## Confirmed code gaps

- processing/scope.py preview requires all 22 sources with owner truth and full coverage for acceptance_learning; evidence_generation is transcription-only. A four-span voice pilot is not expressible today. Add a separately typed pilot purpose and explicit selected-span admission, retaining parent membership/hashes. Never fake all-source truth, downgrade coverage gates, or route it through evidence_generation.
- speech/learn.py owner_learn_voice combines exemplar creation, turn assignment, immediate recognition and queue writes. Do not invoke it for this pilot.
- speech/process.py recognize_person_on_video obtains probes only from the provider i9_voice_vec_for_turn hook. With no hook it skips turns. The inspected path has no real-audio fallback for probes. The existing embeddings module can extract/encode real source audio, but it must be invoked explicitly for pinned spans by the new runner.
- The encoder can load/download into a temporary model cache and broadly maps failures to unavailable. Pilot preparation must identify the local model revision/files and hashes, disallow network fetching, record structured failure, and load once. No package installation or model readiness is assumed from ffmpeg availability.
- Current recognition modifies turn identity fields. Pilot results must be separate auditable suggestions, never overwrite owner overlays or machine records. Only the pinned T1 reference may influence scoring; legacy exemplars and held-out annotations are excluded from the reference set.

## Implementation sequence under development authorization

1. Implement pure validation/preview for a voice-pilot child scope: parent manifest/version/hash, exact source/version/annotation/word IDs, active revision, target Person, ordered finite boundaries, disjoint training/test spans, explicit roles, caps and timeouts. Registration remains inert. A revision, withdrawal, source mismatch or unaccounted duplicate invalidates the plan. Confirm historical duplicate-source/model exposure limits rather than claiming a pristine benchmark.
2. Add a dedicated runner and local-model preflight. Real source audio supplies reference and probes. Synthetic injected vectors belong only in tests and must be rejected in production proof. Fail closed on missing model, bad audio, oversized input, off-manifest request or exhausted attempts. No fallback to transcription, full-video work or network downloads.
3. Design append-only run/reference/suggestion provenance with source/annotation/word IDs, model hash, preprocessing, thresholds, scores and errors. If additive migration is required, inspect current runtime numbering and rehearse on an isolated clone. Never reuse 031, automatically apply migrations or publish a runtime reference during preparation.
4. Enforce held-out exclusion and exemplar lifecycle. Retiring a reference must prevent reuse, preserve its history, mark dependent suggestions stale and propose only affected bounded reprocessing; retirement itself starts nothing. Recheck retirement at work reservation and result publication to avoid races.
5. Test rejection paths, budgets, exact media calls, independent face/voice evidence, owner-overlay preservation, no queue/transcript/exemplar side effects outside the new explicit run records, idempotency, retirement and stale results. Use synthetic fixtures/disposable DB; do not run the private-media pilot during development.
6. Submit one consolidated FlightSim readiness report with exact tested code, local model prerequisites, fresh backup, applicable clone migration proof, migration/run commands, write set, budgets, downtime, smoke checks and rollback. Request production approval once for that concrete plan. Current Learn remains locked.

## Pilot evidence and acceptance limits

Record scores for all three probes against the single T1 reference, errors and abstentions. Existing code constants 0.55 match / 0.40 uncertain are uncalibrated implementation defaults, not accepted accuracy guarantees. Freeze the pilot's proposed threshold before scoring and never tune it on these held-out results while still calling them held out. Report outcome by case (two Eugene positives, one non-Eugene negative), not a generalized accuracy claim from three trials.

A successful Eugene-only pilot would demonstrate real-audio matching and an off-camera negative control. Full I13 still needs positive off-camera recognition with an independently confirmed training sample for that Person, actual uncertain/overlap or poor-audio evidence, broader face/voice coverage and the required lifecycle proof. Owner must provide truth in MB; agent prepares exact candidate intervals if more evidence is needed. Do not ask the founder to search all videos or label every word.

## Current boundary

This plan is complete; implementation gaps above remain open. No pilot code, migration, runtime model import, recognition, Learn, audio upload, cleanup or original-file change was performed in this preparation. The editor usability issue remains explicitly deferred. Private-derived checklist/plan publication remains pending the earlier requested specific permission; keep this preparation local until that is resolved. General feature-branch authorization otherwise remains in force.


## Approved model decision

Tom selected NVIDIA TitaNet-Large. Replace the provisional TorchScript ECAPA contract with local NeMo checkpoint restoration. Development installation and synthetic/public-audio validation are authorized; FlightSim migration, model installation and private-media processing remain subject to consolidated production readiness. No ECAPA comparison or expanded corpus run is implied. The four selected spans and one-attempt limits remain unchanged. Freeze model-specific thresholds explicitly before a private run; the old ECAPA defaults are not calibrated for TitaNet.
