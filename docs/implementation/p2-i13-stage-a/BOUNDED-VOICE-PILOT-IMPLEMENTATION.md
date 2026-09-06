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

1. **Encoder updated and locally verified:** Tom approved TitaNet-Large. The pilot now restores the pinned official NGC v1 NeMo checkpoint, replacing the provisional TorchScript ECAPA contract. Actual offline model loading and generated-audio inference passed in an isolated Windows/Python 3.13 environment. See [TITANET-VALIDATION.md](TITANET-VALIDATION.md) and `titanet-smoke-proof.json`. FlightSim Python 3.12 compatibility and model-specific threshold selection remain unverified; no private recognition has run.
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

## FlightSim PostgreSQL 16 rehearsal and TitaNet threshold checkpoint

FlightSim clone `mb_i13_pre032_restore_b4d1c80b487e4d1383af6b80ed67be65` passed migration 032 rollback and commit rehearsal in 29.81 seconds. It came from the verified 433,074,031-byte backup at `C:\MemoryBox-backups\i13-pre032-b4d1c80b487e4d1383af6b80ed67be65\memorybox.dump` with SHA256 `31c3fb1c78cb4e2dd28876a13acfd6c0b85a62804a7d23c30c9a4e4d9e27ad4e`. Existing protected-table fingerprints were unchanged and live `memorybox` remained at 031 with no pilot tables.

TitaNet thresholds are frozen at 0.30 uncertain / 0.45 match using separate public LibriSpeech evidence. See [TITANET-THRESHOLD-CALIBRATION.md](TITANET-THRESHOLD-CALIBRATION.md). FlightSim still has no isolated TitaNet environment or checkpoint. Installing it, applying 032 to live `memorybox`, registering/starting the admission and extracting the four private spans remain part of the one consolidated production approval.
