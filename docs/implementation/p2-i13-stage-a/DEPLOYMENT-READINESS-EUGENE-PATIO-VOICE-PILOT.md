# FlightSim readiness: bounded Eugene Patio voice pilot

## Approval requested

Approve one bounded private-audio Eugene Will pilot using the exact four-span reviewed plan. The execution guard first verifies the release, model, plan digest, active annotations and source hashes, creates one hash-verified PostgreSQL backup on FlightSim `C:`, registers one admission, runs once, then stops it. It does not authorize Learn, drains, transcription, archive work, model download, migration, media conversion, or automatic retry.

## Exact scope

| Key | Role | Owner-confirmed evidence | Expected result |
|---|---|---|---|
| T3-patio | training | Eugene, Patio 003, 00:15.94–00:32.04 | reference only |
| E3-patio-held-out | held-out | Eugene, Patio 003, 02:30.02–02:51.54 | match |
| T2-as-Eugene-negative | held-out | Tom Will, 20111105_1530, 00:37.12–00:42.40 | no-match |
| N1-TV-announcer-unknown | held-out | Unknown TV announcer, 00:00.00–00:06.74 | no-match |

The selected budget is exactly four extracts, four embeddings, three comparisons, one attempt per span, 49.64 seconds, and no automatic retry. `vid-c57dbd21f993f6d1` is excluded from Eugene evidence because Tom confirmed TV/background overlap.

## Preconditions and deployment

Use a new detached FlightSim release at the exact published SHA and existing verified TitaNet tool release. First run `prepare-eugene-patio-voice-pilot.ps1` without `-WritePlan`; it writes nothing and must report four items, 49.64 seconds and no admission. After review, run it with `-WritePlan` to create the one expected untracked reviewed-plan file. The deployment helper then requires that plan digest, a fresh backup, migration 032, no active voice admission and an explicit approval reference.

The only production writes are the pilot admission/events, one run, four attempts and additive result provenance. Existing annotations, transcripts, legacy queues, originals, proxies, Capture and drains remain unchanged. A failure preserves artifacts and stops; it never retries. No app/worker restart or planned downtime is required. Reserve up to 25 minutes for backup and the capped run.

## Verified plan preparation - 2026-09-08

FlightSim check-only preparation passed on release 31b75255412333894b96f7bebb785d34044dbd8e using verified tool release C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5. It produced plan SHA 99b8a8e93f0bfc7addb1eea05ae0c6e9705de9d0085cecfb0999281df04c59fe for four work items and 49.64 seconds, with private audio, database writes and admission creation all false. The separate plan-write step then created only i13-reviewed-eugene-patio-voice-pilot-plan.json in the detached release. This evidence does not authorize execution.
## First execution stopped before processing - 2026-09-08

The approved helper created the fresh hash-verified backup at `C:\MemoryBox-backups\i13-final-pre-eugene-patio-05e5bce95df54de89133f13fc167032c\memorybox.dump`, then registered admission `f9aa45bc-d5b1-4608-bca1-61cfe9993aeb` for plan `99b8a8e93f0bfc7addb1eea05ae0c6e9705de9d0085cecfb0999281df04c59fe`. The run command failed and the helper stopped that admission at 2026-09-08T10:40:23.938571+00:00.

Read-only status confirms zero run records, attempts, events and results. Therefore no private span was extracted or embedded; this is an inference from the runner's ordering, which claims the admission only after its active-admission, annotation, model and source-hash guards complete. The helper release did not retain the guard's JSON error, so its specific cause is not yet known. The stopped admission cannot restart and must not be retried. A new explicit `check --allow-stopped` diagnostic is being prepared to assess the unchanged evidence and local files without a database write, claim, extraction or inference.
## Stopped-admission diagnostic

Use a new clean detached checkout of `b84b384959a64b5d830d392082a8f97def6bf2bb` on `E:` and run `check-eugene-patio-stopped-pilot.ps1` with that SHA and the existing verified tool release. The helper performs a repeatable-read database check and hashes the existing model and source files. It does not claim the stopped admission, create a run/attempt/event/result, extract audio, start the encoder, create a plan, or write the database. Its success output states `database_writes=false` and `private_audio_processed=false`; a failure prints the original guard JSON. It is diagnostic only and cannot make the stopped admission runnable.
## Acceptance and rollback

A result is acceptance evidence only: E3 should match Eugene; T2 and N1 should be no-match. A different result is recorded and reviewed, never retried automatically. If preparation fails before registration, production is unchanged. After registration, the helper stops the admission in `finally`; preserve output and do not delete results, restore the database or modify media without a separate decision.
