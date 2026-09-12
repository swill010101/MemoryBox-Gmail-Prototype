# FlightSim — apply I14 migration 035

**Status:** 035 SQL is committed on FlightSim. Serve has not been restarted onto a validator-fixed SHA. Do not re-apply 035. Do not run `-ResumeAfterMigrate`. Next authorized step is read-only `verify-schema` then `.\startmb.cmd -Restart`.  
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

Authorized apply (after separate founder go-ahead; do **not** use this if 035 is already committed):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ops\Deploy-I14Migration035.ps1 -ReleaseSha <same full SHA>
```

**Do not use `-ResumeAfterMigrate` for the current recovery.** That wrapper is leftover from the aborted apply. 035 is already committed; the remaining work is a read-only schema check, then a normal serve restart. Do not create or run another production resume wrapper.

Final recovery (founder authorization required; 035 already applied):

```powershell
cd C:\MemoryBox
git fetch origin
git checkout <new full ops-fix SHA>

$env:MEMORYBOX_DATABASE_URL = 'postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox'
'{"evidence":188656,"sources":27,"communication_rfc_ids":287010}' | C:\MemoryBox\.venv\Scripts\python.exe -m memorybox.ops.i14_migration_035 verify-schema
```

Only if that command exits 0:

```powershell
.\startmb.cmd -Restart
```

Then verify `/health` (`ok=true`, pending empty; startup `migrate()` must apply nothing), Historian Capture email-status (`provider_key=namecheap_privateemail_imap_smtp`), and Scheduled Services (`historian_capture_email` not Error / Disabled / Not configured).

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
- Required runtime settings missing after startmb-equivalent loading (`MEMORYBOX_QDRANT_URL`, `MEMORYBOX_DATABASE_URL`). Checked before backup and migrate.
- `python -m memorybox migrate` configuration failure (`migrate_not_started`) or SQL/runtime failure (`migrate_failed`); post-apply validation and restart are skipped
- Post-apply schema contract fails or baseline counts change
- Health poll (60s) does not reach `ok=true` with pending empty
- HC email-status not ok or provider is not Namecheap Private Email
- scheduled-services does not contain exactly one Historian Capture recurring service, or status is Error / Disabled / Not configured
- Git HEAD changes during apply

A **Delayed** HC service is reported, not concealed, and does not fail the deploy.

## Backup

Custom-format dump via `docker exec memorybox-pg pg_dump`, copied to `E:\MemoryBox-backups\pre-i14-035-<stamp>\memorybox.dump` (or `C:\MemoryBox-backups\...`). Size must be > 0; `pg_restore -l` must succeed.

## Verification

Python catalog checks (`memorybox.ops.i14_migration_035 verify-schema`) remain importable after apply. They assert six empty tables, expected columns, PKs, UNIQUE constraints by ordered columns, FKs by source/target columns and delete action, expected indexes, **non-unique** `source_id` on extracts, no `UNIQUE(source_id)` on extracts, exact ledger row `035` / `035_p2_i14_communications_lineage.sql`, and unchanged evidence / sources / `communication_rfc_ids` counts.

CHECK constraints are validated **structurally** only: expected name, `contype='c'`, `convalidated=true`, owning table, constrained columns. PostgreSQL may render `source_kind IN (...)` as `source_kind = ANY (ARRAY[...])`. The validator must not parse `pg_get_constraintdef` text and must never call `execute(sql, ())` when SQL contains a literal `%`. Catalog queries enumerate the six table names (`= ANY(%s)`), they do not use `LIKE 'comms_%'`.

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

## Deployment record (FlightSim)

**Stage 1 preflight:** completed 2026-09-12 on release `cbf17296d7f1da19a879ef117e50ba2ff5de9e27`. HEAD unchanged. Ledger 001–034, 035 absent, six `comms_*` tables absent, counts evidence=188656 sources=27 `communication_rfc_ids`=287010. `/health` pending exactly 035.

**Verified backup (no SQL applied):** `C:\MemoryBox-backups\pre-i14-035-20260912-092044\memorybox.dump` — 433154420 bytes; `pg_restore -l` succeeded during the failed apply attempt.

**Failed apply:** 2026-09-12 09:20:44 local. Category: **missing required runtime configuration**. `Settings.from_env()` raised `MEMORYBOX_QDRANT_URL is required` before migrate connected to PostgreSQL. **No migration SQL was applied.** Serve remained the existing 743c767 process.

**Cause:** `Deploy-I14Migration035.ps1` loaded dotenv files and defaulted `MEMORYBOX_DATABASE_URL` / `MEMORYBOX_P1_RUNTIME_HOST` only. `startmb.ps1` `Load-MbEnv` also defaults `MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333` (and related non-secret production settings). The failed apply process had no Qdrant URL, so migrate never started.

**Read-only confirmation after failure:** schema_migrations 001–034 only; 035 absent; all six `comms_*` tables absent; counts unchanged; `/health` still reachable with pending 035.

**Second apply (c887949), 2026-09-12 ~09:36 local:** Backup `C:\MemoryBox-backups\pre-i14-035-20260912-093628\memorybox.dump` — 433154420 bytes. Script then reported `migrate_failed:sql_or_runtime:exit=1` and skipped verify/restart.

Captured migrate files (`%TEMP%\mb-i14-035-migrate.*.txt`): stdout 72 bytes success JSON `{"applied":["035_p2_i14_communications_lineage.sql"]}`; stderr empty.

**Production after that run (read-only):** **changed.** `schema_migrations` has **35** rows including `035` / `035_p2_i14_communications_lineage.sql`. All six `comms_*` tables exist and are **empty**. evidence=188656, sources=27, `communication_rfc_ids`=287010. `/health` `ok=true`, pending empty, applied_n=35. Constraints/indexes for 035 are present. Serve was **not** restarted by the script; the existing process still answers `/health` against the updated catalog.

**Transaction behavior:** `memorybox.db.connection()` uses one connection, `commit()` on success, `rollback()` on exception. `migrate()` applies pending files then inserts `schema_migrations` in that same transaction. 035 committed as a unit. `_apply_sql` may swallow a first `execute()` of the whole file and retry statements; this run’s stdout shows `migrate()` returned the 035 filename.

**Root cause of script failure:** not SQL. `interpret_migrate_process` treated **any nonzero process exit** as SQL failure and ignored success JSON. `Start-Process` reported exit=1 with empty stderr after a successful apply. No disposable rehearsal database was created because production is no longer pre-035.

**ResumeAfterMigrate (012059f), 2026-09-12:** Git/origin/clean/035 blob gates passed. Resume printed counts evidence=188656 sources=27 rfc=287010 then stopped in `collect_schema_snapshot`: psycopg `ProgrammingError` because `execute(sql, ())` treated `LIKE 'comms_%'` as a placeholder. **No migrate. No serve restart.** 035 remains applied; tables still empty.

**Validator LIKE/CHECK incident (388c523 unused on FlightSim), 2026-09-12:** A follow-up empty-params LIKE patch was pushed as `388c523` but **never run on FlightSim**. Isolated disposable PostgreSQL then failed the next check: substring matching required `source_kind IN (...)` while PostgreSQL stores/renders `source_kind = ANY (ARRAY['email'::text, 'calendar'::text, 'sms'::text])`. Production CHECKs match the `= ANY` form. Do not require a particular `pg_get_constraintdef` spelling.

**Corrected validator (this SHA):** catalog queries use `tablename = ANY(%s)` with the six names, or parameterized placeholders; `catalog_execute` refuses SQL containing `%` without parameters. CHECKs are name/contype/validated/table/columns only. Disposable rehearsal: apply 035 on a fresh non-`memorybox` database, run the complete validator twice, keep `docs/ops/I14_035_VALIDATOR_REHEARSAL.json`.

**Next FlightSim action (not this turn):** checkout this SHA, run `verify-schema` read-only against production, then `.\startmb.cmd -Restart` only if the validator exits 0. Do not re-apply 035. Do not use `-ResumeAfterMigrate`.
