# Annotation-only implementation and deployment review

## Result

Implemented the slice approved after plan commit 25290136b60653c2423c37b21c5e4b38203b9b11. No runtime database, source media, recognition/transcription pipeline or I12 Capture was modified or executed. Application code, tests and an unapplied migration are delivered for review.

In Video Review, highlight timed words, expand Annotate transcript, choose a canonical MB Person or Unknown/No matching MB Person, optionally correct text, and Save assignment. History offers Review assignment for exact-span revision or withdrawal. A partially selected existing overlay expands to its exact saved word span. Neighboring words remain unchanged. Learn remains a separate processing-gated action. Current API save creates only an annotation record; no exemplar or job.

## Persistence and retrieval

031_p2_i13_transcript_annotations.sql creates immutable version snapshots and append-only annotations with actor, reason, time, source/version/word provenance, request digest and supersession. It snapshots existing surviving transcripts without altering the old tables. Historical text overwritten before this migration cannot be recovered: legacy snapshots are labeled legacy_surviving_state, not pristine machine output. The migration covers existing stored transcripts so non-corpus playback remains available; annotation writes remain limited to the exact reviewed 22-source manifest, pinned with a newline-normalized digest.

Future admitted transcription appends raw words/turns/moments and publishes a new immutable version in one transaction. No prior words are deleted. Repeated publication of the same run is rejected; it does not duplicate rows. Only the latest committed version is current, and prior annotations are marked stale rather than moved to new words. The database rejects modification/deletion of snapshots, annotation history and transcript words. Existing turn/moment attribution can still reflect independently produced machine recognition; the immutable snapshot preserves the source state before those updates.

Display and SQL speech search use the same effective word projection. Corrections replace selected display/search text while preserving each word's timing and original text; no blanket assignment of the surrounding turn occurs. Existing vector candidates are resolved through current effective moments before returning them, so old IDs do not restore a superseded version. New overlay text is searchable lexically; its new annotation IDs are not vector-indexed by saving. Full semantic retrieval coverage of novel correction text remains a later indexing design/proof, not an implicit job triggered by annotation.

Requests serialize per provider/source with a transaction advisory lock shared by version publication. Stale transcript/head, conflicting overlap, invalid Person, mismatched/noncontiguous words, out-of-duration selection and changed manifest are rejected. Identical request IDs/payloads replay the original result; reuse with different content fails. Withdrawal retains history and exposes underlying machine attribution again.

Owner boundary follows this local single-owner deployment: loopback client/host only, same-origin browser writes, required custom request header, canonical owner resolved server-side, and no caller-supplied actor. This is not multi-user authentication or authorization for remote clients. Contributor/remote requests are rejected. Runtime exposure must retain the locked launcher's loopback bind.

## Evidence

- 14 annotation tests pass: 3 offline contract tests and 11 real PostgreSQL integration tests, including concurrent conflicts, idempotency, exact-span revisions, withdrawal, stale versions, immutable guards, no-match isolation, API owner boundary, unchanged words, effective search, zero queue/exemplar/run writes on save, and read-only inventory.
- 33 Stage A, 18 Ask/context, 12 fragment correction and 4 trace tests pass: 81 tests total.
- Actual annotation form/selection browser proof passes using synthetic API responses; browser-annotation-proof.json/png. Screenshot visually inspected against the established dark player, transcript and right rail arrangement. Database persistence was tested separately, not through a running FlightSim browser.
- Existing synthetic source playback and moment selector proof passes; all 8 modal fit cases pass from 1208x832 down to 640x480. Annotation controls remain within the independently scrolling transcript; Save is reachable by scrolling.
- Python/JavaScript syntax and Git whitespace checks pass.
- Database tests use a new private loopback PostgreSQL 17 cluster, synthetic schemas and no runtime credentials/data. FlightSim PostgreSQL 16 migration/restore rehearsal is still required. Synthetic test storage is excluded from Git and retained; the cluster is stopped after validation.

## Read-only inventory and truth export

Before new transcription, inventory-transcript-coverage.py reads only exact-manifest source word counts, recorded-run counts and first/last word times in one repeatable-read/read-only transaction. It imports no MB application or processing modules and writes no files. It requires the operator's existing database environment, not supplied credentials. Counts do not prove identity or audio coverage.

After deployment, GET /annotations/transcript/coverage exports the exact manifest and current source/version-linked active owner truth with reviewed/unreviewed word counts. Missing transcripts and unreviewed words remain explicit. Scenario/audio/face coverage tags remain unreviewed rather than fabricated from text labels. Exports may contain private owner annotations; keep them outside Git unless separately reviewed for inclusion.

## Deployment sequence - Tom operates FlightSim

1. Keep current accepted locked release 33eff43d34ecf1d4314509519bd4549a66f1befe running. Review this report, code diff and migration; do not use the new helper with -Start yet.
2. Fetch codex/p2-i13-stage-a and create a new detached checkout at the exact delivered SHA, in a new explicit release directory. Preserve C:\MemoryBox and existing releases. The delivery will supply a complete block when preparing the reviewed release, not a pull into the dirty runtime checkout.
3. In the configured shell, run start-fragment-release.ps1 with -ExpectedSha and no -Start. It runs 70 offline tests and skips 11 explicitly opt-in database tests, then inspects paths/import origins without starting services. It clears the synthetic-test opt-in flag so no operator runtime environment can trigger these tests accidentally.
4. Run python -B docs/implementation/p2-i13-stage-a/inventory-transcript-coverage.py. Inspect aggregate output. Do not select Learn or enqueue missing transcripts.
5. Run python -B docs/implementation/p2-i13-stage-a/preflight-migrations.py. Expected pending list: only 031_p2_i13_transcript_annotations.sql. Migration 030 must already be recorded; historical 009/025 differences remain reported. Any new filename collision or other pending migration stops deployment. This helper is read-only.
6. Arrange a fresh consistent backup and restore to an isolated FlightSim PostgreSQL 16 test database under a separately reviewed operator procedure. On that clone only, rehearse 031 atomically; verify snapshots/guards, old row counts/content, new annotation lifecycle, I12 counts and normal read paths. Measure migration time/storage and transcript/Ask latency at realistic size: synthetic tests do not establish acceptable FlightSim performance. SQL effective views do not have the old materialized text index, so this measurement is a release gate.
7. Submit clone proof and backup evidence for founder review before runtime migration or service switch. No runtime migration command is authorized by implementation approval.
8. After the separate runtime deployment decision, stop existing app/worker consoles normally, apply only reviewed migration 031 using the approved transaction procedure, verify schema/history and unchanged old data, then run the new exact release helper with -Start. Launcher now requires both 030 and 031 and checks annotation relations before starting. Drains remain off and admission unset.
9. In MB, highlight existing words, save a Person assignment, reopen, revise text/Person, inspect history and withdraw. Confirm originals, unaffected neighboring words, search results, source jump/continuation, transcript scrolling, Gallery return and I12 access. Confirm queue/exemplar counts unchanged. Test Unknown and No matching MB Person. Do not run Learn as part of this proof.
10. Export owner truth/coverage read-only and review missing evidence before proposing any bounded run. Actual audio-based/off-camera voice recognition, exemplar lifecycle and full I13 acceptance remain separate.

Rollback: preserve all additive schema/history and keep drains disabled. Prefer fixing forward. Prior locked code can display legacy data but does not apply the new owner overlays, so reverting the code after annotations exist hides their effective display/search and requires an explicit reviewed decision. Never drop the new tables/guards or restore an old DB over owner annotations as a shortcut. No cleanup, derivative deletion or corpus processing is part of this deployment.


## FlightSim rehearsal and query correction

Tom's PostgreSQL 16 rollback rehearsal created 1,736 legacy snapshots, preserved 140,441 words with zero snapshot mismatches, and left all five reported counts unchanged. Zero annotations were created and rollback was confirmed. Two-source reads took 3.375s/3.324s. Follow-up single-source plans showed 4,087 scans of the same 177-moment JSON array, 183,915 buffer hits inside repeated expansion, and execution times of 2.652s/2.473s. The word sort spilled 4,728kB; repeated JSON expansion is the primary addressed issue, not a reason to increase global work_mem.

031 remains unapplied to runtime. Its effective-word view now materializes typed moment bounds once inside each selected source's correlated subquery. Containment, shortest-duration/text-ID tie-breaks, empty matches, live attribution, withdrawals and overlay precedence remain intact. No persistent cache or recognition run is added. Only the still-unapplied query definition changes; do not deploy the earlier 195725d migration.

Synthetic PostgreSQL 17 comparison (4,087 words, 177 moments and an unrelated source): old/new word reads 5017.62/843.32ms, moments 4012.58/593.30ms, with exactly equal result rows. Actual array scan loops are one per selected source. See annotation-query-performance-proof.json and benchmark_i13_annotation_queries.py. Fifteen annotation tests and 33 Stage A tests pass; the new case covers ties, gaps, withdrawn matches and overlay precedence. Unchanged suites retain earlier results; no FlightSim performance acceptance is claimed.

Next run rehearse-annotation-queries.ps1 from the exact corrected detached release with -ExpectedSha. It targets only the named restore clone, applies the migration inside a transaction, compares old/new rows in both directions for both pilot sources, prints optimized plans, and rolls back. It never starts services, changes the live database, stamps migration history or raises the 20-second query ceiling. Send output for review before runtime migration. The helper is PowerShell-parse validated; Docker execution awaits Tom on FlightSim.
