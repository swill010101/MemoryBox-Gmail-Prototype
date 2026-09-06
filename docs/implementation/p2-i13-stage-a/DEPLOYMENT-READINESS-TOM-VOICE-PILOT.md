# FlightSim readiness: bounded Tom voice pilot

## Decision required

Approve one bounded private-audio run using the exact release and procedure below. This package creates one new I13 admission after a fresh verified backup, processes four already owner-confirmed spans, records additive pilot evidence, and stops the admission. It does not authorize Learn, a queue drain, transcription, archive work, a model download/install, a schema migration, model tuning, media conversion, or a broader corpus run.

## Exact release and target

| Item | Value |
| --- | --- |
| Feature commit | `fbc682d0e60a8b27e17d3c433ff40e1ac34490f3` |
| Branch | `codex/p2-i13-stage-a` |
| New detached release | `C:\MemoryBox-releases\p2-i13-tom-voice-pilot-fbc682d` |
| Existing verified tool release | `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5` |
| Target | FlightSim `memorybox` database in Docker container `memorybox-pg` |
| Existing schema | Migration `032_p2_i13_voice_pilot.sql` is already present; no migration is applied |
| Media root | `P:\Photos\Home Videos` |

The read-only preflight passed at `a4316f3a97825c5c49ee07a2341902826e70d73d`. It generated plan SHA-256 `742c9ca477c358b2fd889ed777b89cfdc1e197789bca7cba6ca4548883e45e44`, with four work items and 40.8 selected seconds. It reported no database writes, admission, or private-audio processing. It verified the reused tool release and its TitaNet model.

## Exact bounded scope

| Key | Role | Source | Range | Expected decision against Tom reference |
| --- | --- | --- | --- | --- |
| T2 | training | `vid-da41273dbd9ac4bb` | 00:37.120–00:42.400 | Tom Will reference |
| O1 | held-out positive | `vid-c57dbd21f993f6d1` | 02:32.240–02:38.340 | Tom Will `match` or `uncertain`; never claim success from an unsupported positive result |
| H1-as-Tom-negative | held-out negative | `vid-c57dbd21f993f6d1` | 05:25.220–05:45.560 | Eugene Will; expected Tom `no_match` |
| U1-clear-as-Tom-negative | held-out negative | `vid-c57dbd21f993f6d1` | 02:09.640–02:18.720 | Eugene Will; expected Tom `no_match` |

Limits are fixed in code: four extracts, four embeddings, three comparisons, one attempt per span, 40.8 seconds total, 120 seconds per extract, 120 seconds per embedding, 20 minutes overall, and no automatic retry. TitaNet-Large scoring remains frozen: below 0.30 = `no_match`; 0.30 to below 0.45 = `uncertain`; 0.45 or greater = `match`.

H1 and U1-clear were used in the earlier Eugene pilot. They are declared Tom-negative controls, not a pristine independent model benchmark. Background voices, overlapping speakers, and quiet/mumbled speech are excluded from this run.

## Backup and write set

Before any admission, the guarded script creates a new custom-format `pg_dump`, runs `pg_restore --list`, copies it to `C:\MemoryBox-backups\i13-final-pre-tom-<token>\memorybox.dump`, and compares the container SHA-256 to the copied file. The script stops before an admission if any backup step fails. No fresh backup exists yet; it must be created immediately before the approved run.

The only production writes after the backup are one plan-bearing I13 admission, its register/start/stop audit events, one immutable pilot run, four immutable attempt rows, and reference/result events. The plan file is also written inside the detached release. Machine transcripts, owner annotations, legacy speech/recognition queues, original media, derived browser copies, Historian Capture, and app/worker drains remain unchanged.

## Deployment commands

Create the detached release and run the harmless script check first:

```powershell
& { $ErrorActionPreference='Stop'; $root='C:\MemoryBox'; $release='C:\MemoryBox-releases\p2-i13-tom-voice-pilot-fbc682d'; $sha='fbc682d0e60a8b27e17d3c433ff40e1ac34490f3'; if(Test-Path -LiteralPath $release){throw 'Release path already exists; preserve it and stop.'}; git -C $root fetch origin codex/p2-i13-stage-a; if($LASTEXITCODE -ne 0){throw 'Fetch failed.'}; git -C $root worktree add --detach $release $sha; if($LASTEXITCODE -ne 0){throw 'Worktree creation failed.'}; powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$release\docs\implementation\p2-i13-stage-a\deploy-tom-voice-pilot.ps1" -ExpectedReleaseSha $sha -ApprovalReference 'readiness-check-only' -ToolRelease 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5' }
```

After approval, run the following single command from the configured FlightSim shell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\p2-i13-tom-voice-pilot-fbc682d\docs\implementation\p2-i13-stage-a\deploy-tom-voice-pilot.ps1' -ExpectedReleaseSha 'fbc682d0e60a8b27e17d3c433ff40e1ac34490f3' -ApprovalReference 'founder-approved-tom-voice-pilot-2026-09-06' -ToolRelease 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5' -Execute
```

## Smoke tests and acceptance review

The check-only command must return `migration: 032_p2_i13_voice_pilot.sql already present`, `private_audio_processed: false`, `database_writes: false`, and `admission_created: false`.

The executed command must return a fresh backup path and SHA-256, one new admission ID, the three scored outcomes, `legacy_counts_unchanged: true`, and `automatic_retry: false`. Verify the admission is stopped, then inspect the results in MemoryBox. The run is evidence for this exact Tom reference and these three comparisons only; it does not establish generalized recognition accuracy.

## Availability and rollback

No app or worker restart is needed; no planned user-interface downtime is expected. Reserve up to 25 minutes for backup transfer and the capped run. The app and worker drains remain off.

If preparation fails before registration, no production database write occurred. After registration, the script stops the admission in `finally`, preserves any additive evidence and failure record, and never retries. Normal rollback is to stop using the detached release and leave the existing services running. Do not delete pilot records, rerun automatically, restore the database, or alter original media. A full database restore is an exceptional recovery requiring a separate founder decision.

## Approval record

Tom approved the exact FlightSim deployment above before it ran: commit `fbc682d0e60a8b27e17d3c433ff40e1ac34490f3`, new detached release, fresh hash-verified backup, one four-span Tom pilot run using the already verified tool release, stated smoke checks, no expected downtime, and the stated rollback procedure.

## Completed deployment record

The approved deployment completed with release `fbc682d0e60a8b27e17d3c433ff40e1ac34490f3`. Fresh backup `C:\MemoryBox-backups\i13-final-pre-tom-547048044ed64ccb8b71b42baf16a6e9\memorybox.dump` was copied at 433 MB and verified SHA-256 `8bf0912c631984e9902562105f5076947ab794218e5fc704c3301b8b4e77c9d0`. No migration ran.

Admission `9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea` stopped after one run. O1 matched Tom at `0.4874674861`; H1-as-Tom-negative and U1-clear-as-Tom-negative were `no_match` at `0.1216411184` and `0.0656342374`. The deployed `/review/voice-pilot-results` endpoint confirmed this admission is stopped and `stale: false`; it reported `read_only: true` and `processing_started: false`. Legacy counts were unchanged and automatic retry was false.