# I14-035 FlightSim deploy incident (2026-09-12)

035 SQL from blob `345bd26fa337cb159626c70fbd9e741fa010506f` (schema-review SHA `4c13f70aae0d18f217eec4dcf43a98e6b964b14d`) is **applied** on production. Ledger row is `035` / `035_p2_i14_communications_lineage.sql`. Six `comms_*` tables exist and are empty. Baseline counts unchanged (evidence=188656, sources=27, `communication_rfc_ids`=287010). Serve was not restarted onto a post-apply SHA.

## Failures (none of these re-applied or rolled back SQL)

1. **Missing `MEMORYBOX_QDRANT_URL`** in the deploy wrapper (present in `startmb` defaults). Migrate never connected. No SQL.
2. **Successful migrate, false failure.** Stdout JSON `{"applied":["035_p2_i14_communications_lineage.sql"]}`. Wrapper treated `Start-Process` exit=1 as SQL failure and skipped verify/restart.
3. **`-ResumeAfterMigrate` schema snapshot.** `execute(sql, ())` with `LIKE 'comms_%'` → psycopg `only '%s'... got '%'`. No migrate, no restart.
4. **CHECK text matching (desktop only).** Patch `388c523` was never run on FlightSim. Disposable PostgreSQL then failed because the validator required `source_kind IN (...)` while PostgreSQL renders `source_kind = ANY (ARRAY[...])`.

## Correction (this repository SHA)

- Catalog queries enumerate the six table names; they do not use `LIKE 'comms_%'`.
- `catalog_execute` refuses SQL containing `%` unless parameters are supplied.
- CHECK validation is structural (name, `contype='c'`, `convalidated`, table, columns). It does not parse `pg_get_constraintdef`.

## Recovery (founder authorization; not executed in the validator-fix turn)

A. Check out the corrected SHA.  
B. Run `python -m memorybox.ops.i14_migration_035 verify-schema` read-only against production.  
C. Only if that exits 0: `.\startmb.cmd -Restart`.  
D. Verify `/health`, Namecheap HC email-status, Scheduled Services. Startup migrate must apply nothing.

Do not use `-ResumeAfterMigrate`. Do not re-apply 035. Do not rollback unless a later founder decision says so.
