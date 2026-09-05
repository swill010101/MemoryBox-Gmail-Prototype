# Single-source fragment lineage assessment - read-only

Tom approved a read-only trace after verifying that all 15 Gallery entries for source vid-c57dbd21f993f6d1 play successfully through the one published full-source copy. Scope is observations -> exemplars/appearances -> grouping -> Gallery membership for that source. No record mutation, Learn, recognition, transcription, additional conversion or remediation is authorized by this trace.

## Confirmed static-code findings and offline reproduction

- recognition/frames.py sample_times selects a 10-second interval for this 1,105.104-second source, starting at 0.5 seconds. The configured 80-sample cap stops at 790.5 seconds. This is a sampling-coverage limitation, not evidence of who appears after that time.
- recognition/constants.py sets RANGE_GAP_SEC=8.0. observations.py group_assigned_into_ranges merges only when the next assigned sample is at most 8 seconds away; an isolated point gets a 0.5-second range. scan.py calls this grouper directly on its observations.
- Running the actual pure sampler and grouper on synthetic all-positive observations produces 80 separate half-second ranges. Reproduction: fragment-cadence-proof.json and tests/test_i13_fragment_trace.py. No media/model was used. This establishes a cadence incompatibility, not that the current 15 Gallery rows came from this path.
- The worker /faces legacy path creates a new face candidate ID and one-second detection for a marked frame. providers/video/merge.py groups by candidate ID with a default 60-second gap. Fifteen nearby detections sharing one candidate merge into one span; fifteen distinct candidate IDs stay separate. A shared displayed Person name does not itself join them. Effective FlightSim overrides may differ from the default.
- Ask retrieval combines provider video segments and durable face_appearance_moments, deduplicating by source/start-time slots of 2.5 seconds. Distinct short observations separated by ten seconds can survive that filter. This is not proof of physical duplicate video files.

## Prepared FlightSim read-only export

trace-source-fragments.py imports psycopg and standard library only, not MB/provider/model modules. Its source is fixed. It opens a repeatable-read, read-only transaction with statement/lock/connect timeouts and reads schema metadata to tolerate missing optional columns. All data queries are restricted to this source, or runs referenced by this source's observations. It prints snapshot identity, exact source row counts, up to 200 rows per table with truncation flags, observation timestamps, range bounds, status/lineage, Person/candidate/exemplar/observation/run IDs and method metadata. No names, embeddings, crop bytes, transcripts, OAuth content or connection string are exported.

Tables: video_face_observations, face_appearance_moments, face_evidence, identity_withdrawals, recognition_queue_items and pending_review_face_crops. Processing-run counters may cover other sources; only linked run IDs are selected and their broader count scope is disclosed. The existing detections.json is inspected read-only only if present and at most 64 MiB; only target-source timing/candidate fields are printed. File metadata is checked before/after read, but this is not a joint database/filesystem atomic snapshot. No files are written by the exporter. Raw trace output remains with Tom pending review; do not commit it automatically.

Four offline tests pass: native cadence mismatch, candidate-key split behavior, source-only/redacted derived export and per-Person duration summary. The live exporter has not been run by the agent. Gallery response membership and the actual lineage of the 15 entries are still unconfirmed.

## Next analysis after operator output

Match the owner-observed 15 entries to persisted appearance IDs/starts and worker candidate spans. Distinguish exemplar-only records, native point ranges, legacy candidate fragmentation, actual identity gaps, and duplicate representation across provider/native paths. Correlate observation_ids and processing_run_id, status and accepted/withdrawn state. Check truncation and do not infer absence from capped exports. If needed, request one further scoped read-only snapshot or existing browser response; do not launch a fresh corpus scan to diagnose it.

Then prepare a bounded correction proposal preserving immutable evidence and showing the intended Gallery/presence presentation. Do not simply increase a gap globally or merge everything bearing the same name: genuine cuts/departures and ambiguous identity must remain distinct. The reported continuous shot is owner evidence to include in acceptance. A source-wide playable copy should continue to serve all its moments regardless of the presentation correction. Historical record changes and reprocessing require their own concrete reviewed scope.

## FlightSim result - 2026-09-05

Tom supplied a complete, untruncated read-only/repeatable-read snapshot captured at 17:46:51 UTC. Four exporter tests passed on FlightSim. The attachment SHA256 is 66c435f78d4d84cd9bb477b536725242c200c53398a2115c1a50d2c1b87767e7; raw runtime rows and Person identifiers are not committed.

The source has 79 assigned observations for one Person/run, from 0.5 to 790.5 seconds: 77 ten-second gaps and one twenty-second gap. All 79 native appearance moments last 0.5 seconds. Offline replay of the actual pure grouper against the supplied observations reproduced every stored start/end and observation_ids link exactly. This confirms the cadence/grouping defect affects these persisted records. All moments are accepted but ai_inferred/system_associated, not owner-confirmed.

The linked run is provider_seeded/newly_known_person, completed August 27; this does not establish that pressing Learn directly caused it. There are 132 completed source queue entries across 69 Person IDs, corroborating historical broad queue fan-out but not presence of those people or duplicate media files. No source-linked face_evidence, withdrawals or pending review crops were returned; the inspected detections.json is absent. Historical worker activity or exemplars elsewhere are not ruled out.

The exact mapping of the 15 displayed Gallery entries to the 79 persisted moments remains unconfirmed because Gallery response membership was not exported. Do not extrapolate presence beyond the final observation to the full 1,105.104-second source.

Recommended next step: prepare a bounded correction proposal for cadence-aware grouping and evidence-preserving Gallery presentation, then verify source-specific Gallery membership before publication. Preserve observations, lineage, genuine cuts/departures, ambiguous evidence, owner overlays, natural playback and Gallery return context. Do not simply increase a global gap or delete old rows. Implementation/runtime repair remains separate from this read-only authorization. No application/runtime/media changes or processing occurred.
