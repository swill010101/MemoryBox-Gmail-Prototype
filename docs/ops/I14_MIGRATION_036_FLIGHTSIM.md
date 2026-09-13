# FlightSim — migration 036 applied (empty schema)

**Status:** Empty prepared-communications schema is **applied**. Do not re-apply 036. Do not load rows, activate a generation, or publish.

**SQL identity:** commit `cbd5434314ac09c9931237e5dd2f4150e064e67c` blob `399f15b27207440a08380f970779987e3b5295d9` (`memorybox/migrations/036_p2_i14_prepared_communications.sql`).

**Not authorized next:** prepared-email generation/load, Peggy/Sue/household rows, generation activation, Gallery/Ask, SMS/calendar schema, I11A, evidence cleanup.

## Sanitized apply record (2026-09-13)

| Item | Result |
| --- | --- |
| Prior FlightSim HEAD | `47c45f7aab3e5aa806ec36dfca4376e0469e3fb1` (detached, tracked-clean) |
| Checkout | Detached `cbd5434314ac09c9931237e5dd2f4150e064e67c` |
| Pre-apply health | `ok=true`, pending empty, `applied_n=35` |
| Pending immediately before migrate | exactly `036_p2_i14_prepared_communications.sql` |
| Backup | `C:\MemoryBox-backups\pre-i14-036-20260913-172352\memorybox.dump` — **433188932** bytes; `pg_restore -l` **630** lines; local copy `E:\MemoryBox-backups\pre-i14-036-20260913-172352\memorybox.dump` |
| Migrate | `C:\MemoryBox\.venv\Scripts\python.exe -m memorybox migrate` applied **only** `036_p2_i14_prepared_communications.sql` |
| Ledger | **001–036** (`applied_n=36`); 036 filename matches |
| New objects | five `comms_prepared_*` tables, view `comms_prepared_active_generations`, 7 functions, 5 triggers, 39 check constraints; no `ON DELETE SET NULL` on prepared tables |
| Empty proof | all five prepared tables **0** rows; active-generation view **0**; no `published`/`is_active` generation |
| Baseline unchanged | evidence **188656**, sources **27**, `communication_rfc_ids` **287010** |
| 035 lineage | six tables still **0** rows |
| Post-apply `/health` | `ok=true`, pending empty, `applied_n=36` |
| Historian Capture | email `ok`, `provider_key=namecheap_privateemail_imap_smtp`; scheduled `historian_capture_email` **Active** |
| Load | **not** performed |
| Serve process recycle | **not** completed (no SSH/WinRM/PsExec/task-create from Toms-Desktop). Live `/health` already green because pending is computed from disk+ledger. In-memory uvicorn may still be the pre-checkout process until a FlightSim console `.\startmb.cmd -Restart`. |

## Rollback

Restore the verified dump only if founder authorizes. Do not DROP 036 objects ad hoc.

## Git after apply

FlightSim `C:\MemoryBox`: detached `cbd5434`, tracked-clean. Loading prepared email requires a new founder authorization.
