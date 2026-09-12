# FlightSim — apply I14 migration 035

**Status:** Script tracked; **not executed** until founder authorization.  
**Schema-review commit (035 SQL):** `4c13f70aae0d18f217eec4dcf43a98e6b964b14d`  
**Prior production SHA:** `743c76712cb286ccdae3ad1108fb260dbd04770d`  
**Release SHA:** the founder-approved ops-pack commit the operator checks out **before** running the script (must be a descendant of `4c13f70` with identical 035 SQL).

## Purpose

Bounded FlightSim **application of migration 035 only**, while keeping the tracked ops pack on HEAD. The script does **not** change Git commits during apply. Creates six empty communications lineage tables. Does not change Ask/UI behavior, HC-2 cadence rules, or existing evidence.

## Explicitly out of scope

Do **not** seed logical sources, backfill mappings, ingest mail/calendar/SMS, merge or delete evidence, run Peggy, change Ask/UI, register tasks, send email, run a campaign, or perform the live duplicate audit.

## Prerequisites

- Run **on FlightSim** from `C:\MemoryBox` (not Toms-Desktop).
- Operator has already fetched and checked out the approved **full** release SHA. Detached HEAD at that SHA is expected and supported (`git checkout <SHA>`).
- Tracked git tree clean. Untracked files are listed and never deleted, overwritten, staged, or committed.
- `-ReleaseSha` equals `HEAD` and, unless `-AllowOfflineOrigin` is separately authorized, equals `origin/codex/p2-i14-communications`.
- That SHA is a descendant of schema-review `4c13f70`. Git blob IDs for `memorybox/migrations/035_p2_i14_communications_lineage.sql` at HEAD and `4c13f70` match.
- Ops script, Python validator, tests, runbook, and 035 SQL are present for the whole run.
- Ledger is exactly versions **001–034** with FlightSim filenames for **009** and **025–029**.
- 035 absent from the ledger; six `comms_*` tables absent.
- Serve is up on the prior production SHA first so `/health` can be `ok` with pending empty **before** the release checkout. After checkout, top-level `/health` `ok` is false because 035 is pending on disk; the script requires database ok and pending exactly `035_p2_i14_communications_lineage.sql`.
- Docker container `memorybox-pg` available for `pg_dump`.
- Serve interpreter is `C:\MemoryBox\.venv\Scripts\python.exe`.

## Execution

Substitute the same founder-approved full SHA in both checkout and `-ReleaseSha`.

Preflight only (no backup, migrate, or restart; Git HEAD unchanged):

```powershell
cd C:\MemoryBox
git fetch origin
git checkout <new full ops-fix SHA>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1 -ReleaseSha <same full SHA> -PreflightOnly
```

Authorized apply (after separate founder go-ahead):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1 -ReleaseSha <same full SHA>
```

`-WhatIf` skips mutating steps (`SupportsShouldProcess`). `-AllowOfflineOrigin` is only for separately authorized offline use.

## Hard stops

- `-ReleaseSha` missing or not a full 40-character SHA
- Tracked files dirty
- HEAD ≠ `-ReleaseSha`
- `-ReleaseSha` is not a descendant of `4c13f70`
- `origin/codex/p2-i14-communications` ≠ `-ReleaseSha` (unless offline mode)
- 035 SQL blob at HEAD differs from `4c13f70`
- Ops pack file missing
- Ledger is not the ordered 001–034 set, 035 is present, or 009/025–029 filenames differ
- Any `comms_*` table already exists
- `/health` unreachable, database not ok, or pending is not exactly `035_p2_i14_communications_lineage.sql` (top-level `ok=false` is expected while 035 is pending)
- `pg_dump` fails, dump empty, or `pg_restore -l` cannot read it
- Pending set is not exactly `035_p2_i14_communications_lineage.sql`
- `python -m memorybox migrate` applies anything else or fails
- Post-apply schema contract fails or baseline counts change
- Health poll (60s) does not reach `ok=true` with pending empty
- HC email-status not ok or provider is not Namecheap Private Email
- scheduled-services does not contain exactly one Historian Capture recurring service, or status is Error / Disabled / Not configured
- Git HEAD changes during apply

A **Delayed** HC service is reported, not concealed, and does not fail the deploy.

## Backup

Custom-format dump via `docker exec memorybox-pg pg_dump`, copied to `E:\MemoryBox-backups\pre-i14-035-<stamp>\memorybox.dump` (or `C:\MemoryBox-backups\...`). Size must be > 0; `pg_restore -l` must succeed.

## Verification

Python catalog checks (`memorybox.ops.i14_migration_035`) remain importable after apply. They assert six empty tables, PKs, every FK including `ON DELETE RESTRICT`, composite same-lineage FKs, source-membership PK/`UNIQUE(source_id, logical_source_id)`, UNIQUE constraints, CHECK clauses, expected indexes, and **non-unique** `source_id` on extracts. Checkpoint delete action must be RESTRICT. Evidence / sources / `communication_rfc_ids` counts must match the pre-apply snapshot.

After restart, poll `/health` up to 60 seconds, then assert email-status and scheduled-services. No mail is sent. Ops pack presence is re-checked after migrate and after restart.

## Rollback

Only after a verified deploy/migration regression:

1. Stop serve.
2. Save diagnostic output (HEAD, git status, sanitized health) under the backup root.
3. Check out prior production SHA `743c76712cb286ccdae3ad1108fb260dbd04770d`.
4. Verify 035 is absent from that SHA (git object and working tree).
5. Confirm all six 035 tables are empty.
6. Drop in order: aliases → identities → checkpoint → extracts → memberships → logical sources.
7. Delete only the exact `schema_migrations` row `035` / `035_p2_i14_communications_lineage.sql`.
8. Restart serve and re-verify health / HC status.

If any 035 table has rows, **do not drop**. Stop and restore from the verified dump.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1 -ReleaseSha <same full SHA> -Rollback
```
