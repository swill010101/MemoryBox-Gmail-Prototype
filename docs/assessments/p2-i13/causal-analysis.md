# Causal analysis and read-only runtime evidence

## Confirmed playback mechanism

`explore/find.py` emits source-linked `type=video` cards with `duration_sec=end_sec-start_sec`. `explore/static/explore.js:bindAppearanceView` seeks the original player to start, clamps seeking, pauses at end, and restarts from start on replay. `verification.json` records the actual binder called with a synthetic player: start=12, attempted time=15, observed time=14 and one pause. This reproduces the chopped experience without creating or decoding a physical video.

Historical `docs/product/MBACR-P2-001_PERSON_APPEARANCE_VIEW.md` explicitly required stop-at-end and excluded physical clips. Accepted I13 FR-005 requires continued playback. **Conflict recorded; no code or historical contract changed.** Founder review must confirm I13 supersedes that behavior before a build changes the shared binder. A two-second UI experience is not evidence of a two-second file.

Legacy `hvrt/hvrt/face_learn.py:_insert_appearance` writes a range from t-0.5 to t+0.5, explaining one-second database observations. Its near-duplicate check uses video/person/time within 1.5 seconds and may update confidence/pass. It does not establish model/version uniqueness and does not prove all existing records came through this function.

## Approximately 155,000 work items: founder history and confirmed expansion path

Tom clarified during assessment that Cursor initiated full face reconciliation of all known MB People against the video repository, creating the approximately 155K work expansion; face recognition subsequently worked those records through. This is founder-reported operational history. It changes the primary diagnosis from an assumed outstanding duplicate-record pile to **unbounded all-People-by-video work fan-out**. Exact historical operands, invocation, run ID, deployed revision and completed-result counts remain unverified.

Confirmed baseline path: `app.py:/recognition/archive-pass` accepts `full=true`, starts the drain, and calls `recognition/archive_pass.py:enqueue_known_people_archive`. That function ignores watermarks under full, loops scan-enabled People with exemplars, sets `to_run=videos`, and enqueues each Person against the combined video inventory. CLI `recognition-archive-pass` exposes the same path; `person/immich_sync.py` can also enqueue eligible videos when identities become known. Queue conflict handling prevents duplicate keys for the same reason, but does **not** prevent the initial People ? videos expansion and requeues completed/failed work for exemplar changes. No approved corpus, preflight cardinality budget or accepted archive gate intervenes.

An isolated execution of the actual enqueue planner with all external reads/writes replaced by in-memory stubs requests all 12 pairs for 3 synthetic People ? 4 already-queued videos under full=True. This reproduces the expansion mechanism without creating runtime work or invoking recognition. It does not claim historical counts were 3 and 4 or independently reproduce 155,000 rows.

Additional distinct mechanisms supported by code:

1. Recognition queues are Person ? source ? enqueue reason. Archive passes gather provider and owned-folder inventories, then enumerate people. Multiple reasons, repeated eligible sources/aliases, and large person counts can make a large queue without equivalent media duplicates.
2. Legacy fallback in `recognition/process.py:process_one` writes each returned hit through `upsert_appearance_moment`, which is an unconditional INSERT. Requeued legacy work can append equivalent moments. No semantic uniqueness constraint on those moments prevents this.
3. Native rescan uses delete-and-rebuild rather than immutable idempotent revisions; separate calls/transactions make interleaving and partial failure unsafe. Cleanup ignores provider identity and deletes unknown observations for the source across person passes. This is a different failure mechanism from append-only legacy duplication.
4. Per-frame observations, merged appearance ranges, speech words/turns, jobs, and processing runs are different counting units. They must not be summed and labeled videos or recognition events without a defined metric.

The full-reconciliation fan-out matches founder history and is structurally reproduced. The legacy duplicate and native rebuild risks are separate findings, not explanations asserted for the historical 155K. Do not propose deleting 155K records that the founder says have already been processed. Prevent recurrence through scoped admission and workload preview; reconcile resulting evidence separately.

## Observed runtime scope

Read-only probes on 2026-09-04:

| Store/view | Observation | Limitation |
|---|---|---|
| Documented localhost PostgreSQL `memorybox` | Connected with `default_transaction_read_only=on`; SHOW confirmed `on`; 33 public tables, zero matching recognition/face/speech table names | Actual I13 runtime DB not identified. No migrations executed. This is schema absence, not a zero-count recognition archive. |
| Local config | `config/memorybox_app.env`, `video_worker.env`, `memorybox_sources.env` absent; process has no DATABASE_URL | No credentials printed/read from Gmail files. No alternate DSN guessed beyond documented localhost default. |
| `C:/MemoryBox/hvrt/database/hvrt.sqlite` | Opened with SQLite `mode=ro&immutable=1` and query_only; 19 videos; 3,579 face rows; 94 analysis passes; 345 jobs; 19 transcripts; 1,148 segments; 6,253 words; 21 voice samples | **Checkpoint main file only; existing WAL excluded. Not a consistent current live-store snapshot.** No WAL checkpoint, journal write, database copy, or live app access. |
| Same checkpoint | 3,557 face ranges satisfy 0 <= end-start <= 2 seconds; zero face/video join orphans; 268 excess rows grouped by video_id/person_id/start_sec/end_sec | Coarse candidate duplication key excludes model, pass, box and unknown_id; not a deletion set or confirmed invalid share. Null identities may combine unrelated detections. |
| Local `hvrt/sample` | 19 files: 11 MP4, 8 MOV; 3,606,626,598 bytes | Directory membership is not an approved corpus; source status not determined by extension. |
| Local `hvrt/working/browser_proxies` | 4 MP4, 327,191,603 bytes | Code creates browser-compatible full-source proxies. Individual durations/lineage not verified; cannot rule out physical fragments elsewhere. |
| Local `hvrt/working/exemplars` | 14 JSON, 14 WAV, 6 JPG; 5,012,443 bytes | Derived evidence files exist; no bytes/content copied into artifacts. |
| Local `hvrt/gallery` | 15 JPG, 5 PNG; 449,505 bytes | Enrollment imagery; no identities, filenames or media included in this report. |

Counts were printed as aggregates only. No personal transcript, source identifier, credential or sample media was committed. Original worktree files were only inspected read-only where explicitly authorized.

## Fragment classification status

Database short observations are confirmed in the checkpoint. Physical derivatives (proxies/audio/crops) exist, but whether physical **1?2 second video fragments** exist remains Unknown. No complete authoritative inventory, source-reference migration, quarantine ledger, or deletion-eligibility proof exists. FR-021 is Partial; the Legacy Fragment Reconciliation acceptance gate is not passed.

After runtime location is resolved, obtain a transaction-consistent read-only inventory: group queues by status/reason/provider; observations by source/model/state; moments by lineage/method/range/status; runs by version; source count separately. Compute semantic duplicate candidates within the same version/config and provider/source, then reconcile all references before classifying validity. Inspect file metadata and source-link maps read-only; never infer originals from file length, directory, extension, or similarity alone.

## Recovery/remediation proposal ? not executed

Before later authorized remediation, record a consistent backup/recovery point across PostgreSQL, legacy SQLite including WAL-consistent state, vector index references, and derived-file mappings. Prove restore in a separate disposable environment. Maintain an immutable mapping ledger of each old ID to migrated moment, quarantined record with reason, or verified generated derivative eligible for controlled deletion. Preserve source media and original machine transcripts. Prefer quarantine/supersession first; no blind duplicate deletion. Physical deletion requires separate reviewed eligibility, all consumer references migrated, backup/restore proof, and explicit authorization. Roll back using ledger revisions and restored derived state, not by touching source/provider media.
