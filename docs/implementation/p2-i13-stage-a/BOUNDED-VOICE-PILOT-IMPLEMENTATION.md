# Bounded voice pilot implementation and readiness

Status: development implementation tested; **NOT READY for FlightSim execution**.

## What changed

Added a separately typed four-span voice admission, strict parent membership/content hashes, pinned owner annotations and training/test roles, one-use run/attempt ledger, a dedicated offline encoder subprocess, and separate reference/results provenance. Legacy Learn, recognition queues, machine transcripts and owner assignments are not used as result destinations. Existing admission gates still reject this purpose at legacy entry points.

Migration 032 adds only pilot tables, immutable-event triggers and a stale-results view. Retirement preserves history, blocks reuse, marks dependent results stale and returns affected admissions without scheduling work. Annotation changes and stop/retirement are rechecked before work and publication. The approved selection remains one training reference and three held-out probes; no private-media pilot has run.

## Verified

- 15 pilot tests, including five PostgreSQL integration tests: exact admission limits, held-out exclusion, revision/retirement invalidation, concurrent stop locking, single use, source hashing and failure behavior.
- Real FFmpeg bounded extraction used generated test audio; original bytes remained identical.
- A real child process was killed on encoder startup timeout. Recognition vectors in scoring tests were synthetic; these tests do not prove voice recognition quality or compatibility with an actual encoder.
- 15 annotation regression tests and 33 Stage A tests passed.
- `voice-pilot-clone-proof.json` records a pg_dump/pg_restore synthetic clone rehearsal on local PostgreSQL 17.10. Migration applied and committed, existing annotation counts remained unchanged, and transaction rollback removed the new schema objects. No FlightSim database was migrated. This is not a PostgreSQL 16 production-backup rehearsal.

## Readiness gaps

1. **Encoder compatibility:** the current adapter requires a reviewed local TorchScript ECAPA artifact with a 192-dimensional output and `forward(waveform[B,T], relative_lengths[B])`. This is a new adapter contract, not verified compatibility with the existing SpeechBrain checkpoint. No artifact, revision, hash, synthetic-audio model smoke test or actual model load has been verified. Discover the existing artifact first; adapt or export locally under development authorization as appropriate, then freeze the exact tested model. Do not download or silently substitute a model.
2. **Target rehearsal:** FlightSim runs PostgreSQL 16.14. Recheck migration numbering/schema and rehearse 032 against an isolated PG16 restore of a fresh verified backup. The historical pre031 backup is not current pilot backup proof.
3. **Publication resolved:** Tom explicitly approved the metadata payload and GitHub destination. The four pending commits through `84140ac76a97f85b1c3b68a75a8e6c55cf52d491` were pushed and the remote SHA verified.
4. Source hashing checks the deadline between reads; an operating-system stalled file read can exceed the nominal overall budget. Extraction and embedding subprocess waits have enforced timeouts. A production hard-deadline supervisor remains to be validated if an absolute wall-clock bound is required.
5. Hash matching catches identical files, not edited duplicates or historical model exposure. Three probes cannot establish general accuracy. Uncertain/overlapping speech and positive off-camera Tom recognition remain outside this pilot.

## Consolidated deployment sequence to finalize

Target: FlightSim, database `memorybox` in `memorybox-pg`, an isolated exact-commit release. Keep current application/worker locked, both drains off and admission unset. Historian Capture and original media remain unchanged.

1. Verify feature publication, exact code SHA, clean release, Python/model/FFmpeg hashes and approved four-span plan SHA.
2. Record fresh backup path, byte count and SHA256; restore it to a separately named PG16 test database. Rehearse only migration 032 with version-collision checks, immutable history checks and rollback proof. Do not use automatic migrate.
3. Complete local model smoke testing with generated audio, record input/output contract and artifact provenance. Generate the exact pilot plan read-only with `voice_pilot_cli prepare`, then preview it with `processing.control preview`. Preparation creates only an operator plan file; it neither registers nor runs processing.
4. Present the final report with literal, ready-to-paste deployment commands and all hashes. Request one production approval for migration plus the single pilot run. No production commands are supplied as executable steps while model identity and target rehearsal are missing.
5. After approval, take/verify the agreed final backup, apply only 032 transactionally, verify all legacy baseline counts, register the reviewed plan, explicitly start that admission, run the dedicated CLI once. Never place its admission ID in the app/worker environment or unlock Learn. Any failure consumes this admission; no automatic retry.
6. Read the three auditable results, verify four attempt rows and preserved legacy data, confirm locked recognition/speech probes and Explore/Capture access. Report scores and abstentions against frozen thresholds without tuning on held-out results.

Downtime: no app/worker replacement is needed by this CLI-only change. Migration locking and the single CPU encoder may cause contention; exact maintenance duration must come from the PG16 rehearsal rather than an invented estimate. Schedule with Tom before production.

Rollback: stop the exact pilot admission and terminate its dedicated runner if necessary. Preserve pilot history/results and the additive schema; existing app code does not require it. Keep Learn/drains locked. Do not delete annotations, legacy records, media or derivative files. A full database restore would discard later writes and is a separate recovery decision, not routine rollback.

## Read-only prerequisite command

Once this file is available on FlightSim, run `python -B docs/implementation/p2-i13-stage-a/check-voice-prerequisites.py`. It reports package versions and candidate cache existence without importing MB, loading a model, opening the database or reading media. Supply the exact local voice-model location and revision as the remaining target fact; do not send model weights, private audio or credentials.


Model discovery follow-up: existing `speech/embeddings.py` uses `%TEMP%/mb-spkrec-ecapa-voxceleb` and SpeechBrain `spkrec-ecapa-voxceleb`, not the pilot TorchScript format. The read-only helper now checks that exact cache and up to 20 Hugging Face snapshot directories for known checkpoint filenames. It was executed successfully on the desktop; FlightSim results are still required. No model was loaded.
