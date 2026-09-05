# Annotation sequence correction - 2026-09-05

Tom confirmed the selected 22 files and expects annotations inside MB, by highlighting text or face evidence and assigning a Person. MB must retain the evidence timestamps; manual video/time/name worksheets are not an admission prerequisite. This decision supersedes the initial Stage A truth-before-processing sequence at 686a11a.

## Confirmed implementation

- `memorybox/explore/static/explore.js` renders a synchronized transcript, captures highlighted words, provides Choose Person and Learn, and POSTs the selected span to `/speech/learn`. Face-box selection also exists. These are inspected source-code facts, not a new live UI acceptance result.
- `memorybox/speech/learn.py:owner_learn_voice` embeds source audio, persists a voice exemplar, assigns overlapping turns, recognizes the Person on the current source, and enqueues follow-on work. It is not an annotation-only save.
- `memorybox/speech/store.py:assign_turn_person` updates turn/moment identity fields. It does not by itself implement the required additive, auditable owner-overlay lifecycle.
- Full immutable transcript correction overlays and annotation-only persistence are not implemented by this correction. No new UI has been claimed or deployed.

## Corrected gates

1. Confirm exact source membership. Done for the 22-source proposal; source identities and hashes are unchanged.
2. Review a bounded evidence plan and budget. The concrete Stage A bootstrap is transcription-only, no Person targets. Preview needs confirmed membership, exact IDs/hashes/durations and cardinality limits, not owner truth. No new face-detection engine is introduced; anonymous face-evidence generation remains later scope.
3. Separately approve migration/locked deployment and then a bounded evidence start. Registration alone starts nothing. This task performs neither registration nor start.
4. Provide the annotation-only MB workflow in a later authorized stage: select existing timestamp-backed words/face evidence, assign Person, preserve machine output, write audited overlays. Saving an annotation must not automatically train, rescan or expand scope. Unknown/no-match evidence and coverage review must be supported before acceptance.
5. Export reviewed owner annotations/coverage for acceptance and separately authorized learning. The existing acceptance/learning plan validation retains truth/coverage requirements; later plans are immutable new admissions. Machine output is not owner truth. Archive acceptance/unlock/start remain separate.

The current evidence plan cannot call face/voice Learn or recognition, even after an explicit transcription start. This conservative boundary avoids treating today's combined Learn operation as the requested annotation-only workflow. Designing and implementing that workflow is a subsequent authorization, not silently added to this Stage A gate correction.

## Verification limits

Regression tests cover membership without truth, no implicit start, off-manifest denial, malformed sources/truth, preserved truth requirements for acceptance/learning, and rejection of face/voice/archive expansion from evidence generation. No runtime migrations or processing ran; no live annotation workflow was exercised. The earlier Chromium playback proof remains valid for unchanged playback code.
