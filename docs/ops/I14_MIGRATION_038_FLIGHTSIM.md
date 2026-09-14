# FlightSim — migration 038 applied (voice CHECK)

**Status:** 038 is applied. A replacement unpublished household-email generation is loaded. Do not activate, publish, start Gallery, or start I11A.

**SQL identity:** commit `bf618960fbf3f3e39e49348f3455f1e2e4c23ff7` blob `1efe54148f932dc3a3a49c21273e9b5f43504ac0` (`memorybox/migrations/038_p2_i14_voice_without_recipient_identity.sql`).

**Not authorized next:** generation activation, publish, Gallery, Ask/I11A.

## Sanitized apply + replace record (2026-09-14)

| Item | Result |
| --- | --- |
| Desktop HEAD | `bf618960fbf3f3e39e49348f3455f1e2e4c23ff7` |
| Pending immediately before migrate | exactly `038_p2_i14_voice_without_recipient_identity.sql` |
| Backup | `E:\MemoryBox-backups\pre-i14-038-20260914-074522\memorybox.dump` — **499252376** bytes; `pg_restore -l` **707** lines |
| Migrate | Desktop `python -m memorybox migrate` against FlightSim Postgres applied **only** 038. Second run applied **none**. |
| Ledger | **001–038**; pending empty |
| Constraint | `comms_prepared_messages_voice_corpus_ck`: `NOT voice_corpus OR (quote_quality=clean AND authorship=authenticated_focal)` |
| Baseline unchanged | evidence **188656**, sources **27**, `communication_rfc_ids` **287010** |
| `/health` | `ok=true` after apply |
| Replacement load | unpublished, inactive, published **0**, active **0**, failed **0**, eligible **1** |
| Prior snapshot | marked failed then deleted; cannot activate |

## Rollback

Restore the verified dump only if founder authorizes. Do not DROP 038 ad hoc.

## FlightSim git

Pull `codex/p2-i14-communications` so local files match the applied 038 blob and the corrected loader. Do **not** re-run migrate or reload. Serve recycle is optional for HEAD alignment only (`startmb.cmd -Restart`); startup migrate must apply nothing.
