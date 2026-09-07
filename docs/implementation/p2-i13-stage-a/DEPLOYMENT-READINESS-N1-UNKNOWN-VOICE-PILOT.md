# FlightSim readiness: N1 Unknown no-match pilot

## Approval requested

Approve one bounded private-audio run against the exact reviewed plan below. It creates one new I13 admission after a new hash-verified PostgreSQL backup, processes four owner-confirmed spans, records additive evidence, then stops. It does not authorize Learn, queue drains, transcription, archive work, a model download or install, migration, tuning, media conversion, or a broader run.

## Release, target, and reviewed plan

| Item | Value |
|---|---|
| Feature commit | `56f2b3de39e2c2b963aa6579a0944d0c99072ece` |
| Branch | `codex/p2-i13-stage-a` |
| Detached release | `C:\MemoryBox-releases\p2-i13-n1-unknown-preflight-56f2b3d` |
| Reviewed plan | `i13-reviewed-n1-unknown-voice-pilot-plan.json` |
| Plan SHA-256 | `a9d2a32115db543c13381592bfed189c38c1ba5fb94f303e99f8df62986cf25d` |
| Existing verified tool release | `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5` |
| Target | FlightSim `memorybox` database, Docker container `memorybox-pg` |
| Existing schema | Migration `032_p2_i13_voice_pilot.sql` already present; no migration is applied |
| Media root | `P:\Photos\Home Videos` |

The read-only preflight and plan write completed successfully. They verified the detached release, model artifact, active annotations, source hashes, exactly four spans, 38.46 seconds, and the plan SHA above. They processed no private audio and made no database writes.

## Exact bounded scope

| Key | Role | Owner-confirmed truth | Range | Expected result against Tom reference |
|---|---|---|---|---|
| T2 | training | Tom Will | `vid-da41273dbd9ac4bb`, 00:37.120?00:42.400 | Reference only |
| O1 | held-out | Tom Will | `vid-c57dbd21f993f6d1`, 02:32.240?02:38.340 | Match |
| H1-as-Tom-negative | held-out | Eugene Will | `vid-c57dbd21f993f6d1`, 05:25.220?05:45.560 | No match |
| N1-TV-announcer-unknown | held-out | Unknown TV announcer; no Person created | `vid-c015e0fe07414fcc`, 00:00.000?00:06.740 | No match |

Limits are fixed: four extracts, four embeddings, three comparisons, one attempt per span, 38.46 seconds, 120 seconds per extract and embedding, 20 minutes overall, and no automatic retry. Thresholds remain frozen: `<0.30` no-match, `0.30?<0.45` uncertain, `>=0.45` match.

## Backup and writes

Immediately before registration, the guarded command creates a custom-format `pg_dump`, verifies it with `pg_restore --list`, copies it to `C:\MemoryBox-backups\i13-final-pre-n1-unknown-<token>\memorybox.dump`, and compares container and local SHA-256 values. Failure at any backup stage stops before registration.

The only production writes are one plan-bearing I13 admission with register/start/stop audit events, one immutable pilot-run row, four attempt rows, and reference/result events. It does not change annotations, transcripts, legacy speech/recognition queues, originals, browser proxies, Historian Capture, services, or drains.

## Deployment commands

First run the no-write execution-script check:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\p2-i13-n1-unknown-preflight-56f2b3d\docs\implementation\p2-i13-stage-a\deploy-n1-unknown-voice-pilot.ps1' -ExpectedReleaseSha '56f2b3de39e2c2b963aa6579a0944d0c99072ece' -ExpectedPlanSha 'a9d2a32115db543c13381592bfed189c38c1ba5fb94f303e99f8df62986cf25d' -ApprovalReference 'readiness-check-only' -ToolRelease 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5'
```

After approval, run the same command with `-ApprovalReference 'founder-approved-n1-unknown-voice-pilot-2026-09-07' -Execute`.

## Smoke tests and acceptance

The check must report the exact release and plan SHA, four items, 38.46 seconds, and no private-audio processing, database write, or admission. The run must report a new backup path/SHA, a stopped admission, three scored outcomes, `legacy_counts_unchanged: true`, and `automatic_retry: false`.

Acceptance is narrow: O1 should match Tom; H1 and N1 should be no-match. Any different result is recorded evidence, not an automatic retry or a claim that the TV announcer has been identified.

## Downtime and rollback

No app/worker restart or planned downtime. Reserve up to 25 minutes for backup and the capped run; drains remain off. If preparation fails before registration, production was untouched. After registration, the script stops the admission in `finally`, retains additive evidence/failure history, and does not retry. Do not delete records, restore the database, or alter original media without a separate founder decision.
