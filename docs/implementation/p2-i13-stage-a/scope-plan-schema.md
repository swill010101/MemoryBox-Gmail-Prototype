# Reviewed scope plan contract

The operator control commands accept a JSON plan. No committed example in this packet grants permission to process. Register requires a completed owner-reviewed plan and a review reference; processing additionally requires an explicit `start` transition. Archive plans require acceptance and unlock before start. Registration/start/unlock are operator CLI actions, not unauthenticated web mutations.

| Field | Required value |
|---|---|
| `scope_kind` | `bounded` or `archive`; `--full` requires archive. |
| `manifest.id`, `manifest.version` | Nonempty stable strings. A changed source/truth/config requires a new plan and review. |
| `manifest.sources` | Exactly 22 explicit entries for bounded scope; nonempty explicit archive inventory for archive scope. No wildcard, runtime-folder fallback or duplicate provider/source pair. |
| Per source: `provider_key`, `video_external_id` | Exact provider and stable ID, not display filename alone. Both participate in admission checks. |
| `source_sha256`, `duration_sec` | Full SHA-256 and finite positive duration. Source hashing/verification is a read-only pre-run operator gate; the admission service pins the plan digest but does not rehash media on every function call. |
| `owner_confirmed`, `owner_truth_ref` | Boolean true and explicit owner truth reference; machine suggestions cannot fill these. |
| `truth` | Nonempty list of modality (`face`, `voice`, `no_match`), canonical Person UUID for face/voice, and finite `start_sec < end_sec` within duration. No-match intervals need no Person. |
| `coverage_tags` | Bounded union covers face-only, off-camera voice, simultaneous modalities, multiple people, poor audio, occlusion, short/sustained appearance, no-match. Owner review validates tags, not a model. |
| `person_ids` | Explicit unique canonical MB Person UUID list. Face/voice requires at least one. No all-known-People discovery. |
| `lanes` | Unique nonempty subset of `face`, `voice`, `transcribe`. |
| `max_work_items` | Reviewed positive integer, hard ceiling 10,000. This ceiling is a Stage A safety choice for review, not measured hardware capacity or approval to schedule 10,000 items. |
| `max_attempts_per_item` | Reviewed integer 1?3; atomic reservation shared across queue/direct processing paths. |

Preview counts the entire plan conservatively: `sources ? (People ? enabled face/voice lanes + enabled transcription lane)`. Each logical queue unit has one enqueue reason per admission, preventing additional reasons from multiplying that unit. Attempts are reserved per admission/modality/Person/source; retries do not widen scope. Queue state transitions recheck persisted admission state and source membership. Old NULL-stamped rows are not eligible for I13 claims.

The new SQL state is additive and unapplied. The admission plan/hash/review reference are immutable via trigger. Stop changes admission state, preventing new work reservations/claims; it is not forced interruption of already executing code. A new review/admission is required after stop. There is no API for a browser to grant itself processing or archive authority.

## Stage A compatibility changes

- Existing Learn, direct processing, API/CLI archive pass, queues/retries and drains fail closed without a started admission. Missing migration/store also fails closed.
- Broad Immich seed/sync and legacy SQLite processing, upload/annotation/exemplar mutation, old pending-crop teaching and old live recognition prove commands are intentionally disabled until explicit source mapping and scoped equivalents are reviewed. These are not a fallback if native admission denies work.
- Native face/speech Learn use only the admitted source list for follow-on work. Voice's explicitly supplied other-source list is validated before audio/exemplar writes.
- Existing Gallery `openModal`/`closeModal` are unchanged. Source seek remains; relevance-end clamping/replay reset is removed. Opening video no longer auto-enqueues transcription or falsely indicates a newly started job.
- Source browser-proxy generation remains an existing distinct media-compatibility path; it is not recognition. This task did not invoke it. Do not generate proxies under the no-processing/no-derivative-change deployment hold.
- Immutable transcript overlays and retirement cascade are recorded founder decisions, not implemented in Stage A. I12 implementation and schema are unchanged.

## Evidence limits

Unit tests use actual pure admission logic, extracted full entry functions, and database doubles; they do not validate PostgreSQL DDL execution or real concurrent database sessions. Atomicity is implemented with database row locks/unique keys/conditional updates, but must be proven in a disposable migrated database after separate authorization. The browser proof uses a real Chromium media element and an in-memory synthetic canvas video; it is not full live Gallery/Immich acceptance.
