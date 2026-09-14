# FlightSim — migration 037 applied (empty CHECK widen)

**Status:** Empty prepared identifier CHECKs are **applied**, and serve was recycled through `startmb.cmd -Restart`. Do not re-apply 037. Do not load rows, create/activate/publish a generation, or start Gallery/I11A.

**SQL identity:** commit `7e4efbc36432f2b303689119be2d57dc80822500` blob `ddcd0ee101aecadc8165fe1af11789562a9a0a1b` (`memorybox/migrations/037_p2_i14_prepared_evidence_ref_scale.sql`). 036 SQL bytes were not modified.

**Not authorized next:** unpublished household-email generation/load, 035 or prepared row inserts, generation activation, Gallery/Ask, I11A, evidence cleanup.

Household authored voice (loader, not this SQL): any authenticated canonical From Person may qualify; To/Cc never becomes voice; `IdentityLedger.focal_person_id` does not gate another Person’s From. Ask later joins From `person_id`.

## Sanitized apply record (2026-09-13)

| Item | Result |
| --- | --- |
| Prior FlightSim HEAD | `cbd5434314ac09c9931237e5dd2f4150e064e67c` (detached, tracked-clean) |
| Checkout | Detached `7e4efbc36432f2b303689119be2d57dc80822500` |
| Pre-apply health | `ok=true`, pending empty, `applied_n=36` (then pending exactly 037 after checkout) |
| Pending immediately before migrate | exactly `037_p2_i14_prepared_evidence_ref_scale.sql` |
| Backup | `C:\MemoryBox-backups\pre-i14-037-20260913-215601\memorybox.dump` — **433234997** bytes; `pg_restore -l` **707** lines; local copy `E:\MemoryBox-backups\pre-i14-037-20260913-215601\memorybox.dump` |
| Migrate | Desktop `python -m memorybox migrate` against FlightSim Postgres applied **only** `037_p2_i14_prepared_evidence_ref_scale.sql`. Second run applied **none**. |
| Ledger | **001–037** (`applied_n=37`); 037 filename matches |
| Constraint change | dropped 036 narrow `T-[0-9]{4}` / `M-[0-9]{2}` CHECKs; added `comms_prepared_threads_display_id_scale_check` (`^T-[0-9]{4,}$`) and `comms_prepared_messages_evidence_ref_scale_check` (`^T-[0-9]{4,}-M-[0-9]{2,}$`) |
| Empty proof | all five prepared tables **0** rows; active-generation view **0**; no `published`/`is_active` generation |
| Baseline unchanged | evidence **188656**, sources **27**, `communication_rfc_ids` **287010** |
| 035 lineage | six tables still **0** rows |
| Post-apply `/health` | `ok=true`, pending empty, `applied_n=37` |
| Historian Capture | email `ok`, `provider_key=namecheap_privateemail_imap_smtp`; scheduled `historian_capture_email` **Active** |
| Load | **not** performed |
| Serve process recycle | **completed** 2026-09-13 ~22:04 local. `startmb.cmd -Restart` spawned by repository venv `C:\MemoryBox\.venv\Scripts\python.exe`. `/health` dropped then returned `ok` within ~7s. Pending stayed empty (startup migrate applied nothing). |

## Closeout (2026-09-13)

Serve recycle verified: `/health` ok, ledger 001–037, pending empty, prepared tables 0, active generations 0, baseline unchanged, 035 lineage empty, Historian Capture email ok and `historian_capture_email` Active, Git detached `7e4efbc` tracked-clean, 037 blob `ddcd0ee101aecadc8165fe1af11789562a9a0a1b`.

Household voice disposable proof: `tests.test_i14_prepared_loader.PreparedLoaderPg.test_household_voice_is_authenticated_from_not_focal_person` (Peggy/Sue/Tom From voice counts stay 1/1/1 when ledger focal is swapped). 037 disposable: `tests.test_p2_i14_037_schema`.

## Rollback

Restore the verified dump only if founder authorizes. Do not DROP 037 CHECKs ad hoc.

## Git after apply

FlightSim `C:\MemoryBox`: detached `7e4efbc`, tracked-clean.
