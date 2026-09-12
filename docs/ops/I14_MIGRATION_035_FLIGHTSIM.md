# FlightSim — apply I14 migration 035

**Status:** Script tracked; **not executed** until founder authorization.  
**Authorized SHA:** `4c13f70aae0d18f217eec4dcf43a98e6b964b14d` on `codex/p2-i14-communications`  
**Prior deployed SHA:** `743c76712cb286ccdae3ad1108fb260dbd04770d`

## Purpose

Bounded FlightSim deployment of that SHA and **application of migration 035 only**. Creates six empty communications lineage tables. Does not change Ask/UI behavior, HC-2 cadence rules, or existing evidence.

## Explicitly out of scope

Do **not** seed logical sources, backfill mappings, ingest mail/calendar/SMS, merge or delete evidence, run Peggy, change Ask/UI, register tasks, send email, run a campaign, or perform the live duplicate audit.

## Prerequisites

- Run **on FlightSim** from `C:\MemoryBox` (not Toms-Desktop).
- Tracked git tree clean. Untracked files are listed and left untouched; checkout stops if they collide with incoming paths.
- Ledger is exactly versions **001–034** with FlightSim filenames for **009** and **025–029**.
- 035 absent; six `comms_*` tables absent.
- `/health` ok with pending empty.
- Docker container `memorybox-pg` available for `pg_dump`.
- Serve interpreter is `C:\MemoryBox\.venv\Scripts\python.exe`.

## Execution

Preflight only (no backup, fetch, migrate, or restart):

```powershell
cd C:\MemoryBox
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1 -PreflightOnly
```

Authorized apply (after founder go-ahead):

```powershell
cd C:\MemoryBox
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1
```

`-WhatIf` is the same as preflight for mutating steps (`SupportsShouldProcess`).

## Hard stops

- HEAD is not the prior SHA `743c767` and not already the target SHA
- Tracked files dirty
- Untracked path would be overwritten by checkout
- Ledger is not the ordered 001–034 set, 035 is present, or 009/025–029 filenames differ
- Any `comms_*` table already exists
- `/health` not ok before apply
- `pg_dump` fails, dump empty, or `pg_restore -l` cannot read it
- Origin SHA is not `4c13f70`
- Pending set is not exactly `035_p2_i14_communications_lineage.sql`
- `python -m memorybox migrate` applies anything else or fails
- Post-apply schema contract fails or baseline counts change
- Health poll (60s) does not reach `ok=true` with pending empty
- HC email-status not ok or provider is not Namecheap Private Email
- scheduled-services does not contain exactly one Historian Capture recurring service, or status is Error / Disabled / Not configured

A **Delayed** HC service is reported, not concealed, and does not fail the deploy.

## Backup

Custom-format dump via `docker exec memorybox-pg pg_dump`, copied to `E:\MemoryBox-backups\pre-i14-035-<stamp>\memorybox.dump` (or `C:\MemoryBox-backups\...`). Size must be > 0; `pg_restore -l` must succeed.

## Verification

Python catalog checks (`memorybox.ops.i14_migration_035`) assert six empty tables, PKs, every FK including `ON DELETE RESTRICT`, composite same-lineage FKs, source-membership PK/`UNIQUE(source_id, logical_source_id)`, UNIQUE constraints, CHECK clauses, expected indexes, and **non-unique** `source_id` on extracts. Checkpoint delete action must be RESTRICT. Evidence / sources / `communication_rfc_ids` counts must match the pre-apply snapshot.

After restart, poll `/health` up to 60 seconds, then assert email-status and scheduled-services as above. No mail is sent.

## Rollback

Only after a verified deploy/migration regression:

1. Stop serve.
2. Restore git SHA `743c76712cb286ccdae3ad1108fb260dbd04770d` so `035_p2_i14_communications_lineage.sql` is absent from disk.
3. Confirm all six 035 tables are empty.
4. Drop in order: aliases → identities → checkpoint → extracts → memberships → logical sources.
5. Delete only the exact `schema_migrations` row `035` / `035_p2_i14_communications_lineage.sql`.
6. Restart serve and re-verify health / HC status.

If any 035 table has rows, **do not drop**. Stop and restore from the verified dump.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1 -Rollback
```
