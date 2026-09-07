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

The selected budget is exactly four extracts, four embeddings, three comparisons, one attempt per span, 49.66 seconds, and no automatic retry. `vid-c57dbd21f993f6d1` is excluded from Eugene evidence because Tom confirmed TV/background overlap.

## Preconditions and deployment

Use a new detached FlightSim release at the exact published SHA and existing verified TitaNet tool release. First run `prepare-eugene-patio-voice-pilot.ps1` without `-WritePlan`; it writes nothing and must report four items, 49.66 seconds and no admission. After review, run it with `-WritePlan` to create the one expected untracked reviewed-plan file. The deployment helper then requires that plan digest, a fresh backup, migration 032, no active voice admission and an explicit approval reference.

The only production writes are the pilot admission/events, one run, four attempts and additive result provenance. Existing annotations, transcripts, legacy queues, originals, proxies, Capture and drains remain unchanged. A failure preserves artifacts and stops; it never retries. No app/worker restart or planned downtime is required. Reserve up to 25 minutes for backup and the capped run.

## Acceptance and rollback

A result is acceptance evidence only: E3 should match Eugene; T2 and N1 should be no-match. A different result is recorded and reviewed, never retried automatically. If preparation fails before registration, production is unchanged. After registration, the helper stops the admission in `finally`; preserve output and do not delete results, restore the database or modify media without a separate decision.
