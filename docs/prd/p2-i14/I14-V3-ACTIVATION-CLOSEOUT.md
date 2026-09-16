# I14 v3 activation closeout (attempt stopped)

**Date:** 2026-09-16  
**Authorization:** activate the existing validated v3 generation only (backup, one guarded activate, FlightSim code at `aa6c4aa`, one serve recycle after successful activate, read-only proof).  
**Outcome:** **v3 was not published.** The guarded activator called `comms_prepared_activate_generation` once inside an uncommitted transaction, then crashed in postcheck. PostgreSQL rolled back. Live household-email generation remains **v1**. Serve was **not** recycled. The activator was not run a second time.

No generation UUIDs, addresses, bodies, or dump payloads in this file.

---

## Backup identity and validation

| Field | Value |
|-------|--------|
| Folder (C:) | `C:\MemoryBox-backups\pre-i14-v3-activate-20260916-150336` |
| Copy (E:) | `E:\MemoryBox-backups\pre-i14-v3-activate-20260916-150336` |
| File | `memorybox.dump` (custom `-Fc`) |
| Bytes (C: and E:) | 603,422,224 |
| SHA-256 (C: and E:) | `D65BAD0720E0BD869A58571D41B605BC612A8706F0362A075A29D39B88A9E196` |
| `pg_dump` | PostgreSQL 17.10 |
| `pg_restore` | PostgreSQL 17.10 |
| `pg_restore -l` non-comment TOC lines | 693 |
| Validate | **ok** (`ok=true` in `BACKUP-VALIDATE.json` on both copies) |

Backup gate passed. Activation was allowed to proceed.

---

## Pre-activation gates (passed)

| Gate | Result |
|------|--------|
| FlightSim tracked tree | Detached **`aa6c4aa7e98f61d5f323e8782b8b76516fc305c9`**, tracked porcelain empty (was `46e6700` on `codex/p2-i14-communications`; origin tip `7f65ccd` was **not** checked out) |
| Ledger | 001–040, `/health` pending empty, `applied_n=40` |
| Generations | v1 sole published+active; v2 validated unpublished inactive; v3 validated unpublished inactive; failed/building 0 |
| v3 identity | `E:\MemoryBox-backups\i14-040-v3-private.json` matched live `i14-prepared-email-v3` |
| `comms_prepared_assert_generation_ready(v3)` | succeeded immediately before the activate call |
| v3 messages / dispositions / unexplained / blank voice / forbidden+voice | 91,247; six-way complete; unexplained 0; blank voice 0; forbidden+voice 0 |
| Completeness identity | **91,281 = 91,247 + 26 + 2 + 6 + 0** |
| Archive | 188,656 evidence / 27 sources / 287,010 RFC IDs |

---

## Activation attempt

| Field | Value |
|-------|--------|
| Tool | `python -m memorybox.ops.i14_prepared_activate_v3` (not the 038 first-generation CLI) |
| Confirm | `activate-unpublished-v3-retain-v1-v2` |
| Wall start (UTC) | 2026-09-16T20:10:26Z |
| Wall end (UTC) | 2026-09-16T20:11:07Z |
| SQL | `comms_prepared_assert_generation_ready` then `comms_prepared_activate_generation` **once**, same transaction |
| Client result | **KeyError `id`** in postcheck (`SELECT` omitted `id` while comparing v1 child counts) |
| Database result | **rollback** — v1 `updated_at` still 2026-09-14; v3 still validated unpublished |
| Persisted activation timestamp | **none** |
| Retry | **not performed** |

Postcheck was corrected afterward to `SELECT id, algo_version, status, published, is_active` so a **future founder authorization** can complete. That correction was not executed against FlightSim.

---

## Exact generation-state table (live, after rollback)

| algo_version | status | published | is_active |
|--------------|--------|-----------|-----------|
| `i14-prepared-email-v1` | published | true | true |
| `i14-prepared-email-v2` | validated | false | false |
| `i14-prepared-email-v3` | validated | false | false |

`comms_prepared_active_generations`: **1** row, v1. Published count: **1**. Failed/building: **0**.

---

## Structural, completeness, disposition, commercial, quote, voice (unchanged v3 store)

These are the still-unpublished v3 rows (not Gallery-live). v1 remains what Gallery resolves.

| Kind | Count |
|------|------:|
| Threads / messages / participants / attachments | 40,996 / 91,247 / 294,061 / 28,467 |
| Completeness | 91,281 = 91,247 + 26 + 2 + 6 + 0 |
| authored_displayable | 90,001 |
| non_substantive | 169 |
| correctly_empty | 323 |
| attachment_only | 695 |
| prepared_text_unavailable | 59 |
| uncertain | 0 |
| Voice Tom / Peggy / Sue | 11,578 / 1,345 / 210 |

Commercial and quote tallies were not re-printed here because the activator never reached a successful postcheck JSON. Pre-activation six-way and voice gates matched the authorized numbers.

---

## Archive comparison

| Table | Expected | After attempt |
|-------|--------:|--------:|
| evidence | 188,656 | unchanged (precheck match; no loader) |
| sources | 27 | unchanged |
| communication_rfc_ids | 287,010 | unchanged |

---

## Health / Historian Capture

Read-only after the rolled-back attempt (no serve recycle):

- `GET /health` on FlightSim: **ok**, database ok, migrations pending **empty**, `applied_n=40`, increment 12.
- Historian Capture email-status: **ok**, Namecheap Private Email live path, cadence **active** (not delayed), last tick result **ok** (~20:10 UTC).
- Windows `schtasks` query from this desktop to FlightSim was not used (API cadence already healthy). Task name remains **MemoryBox Historian Capture Tick**.

---

## FlightSim runtime SHA

| Surface | SHA |
|---------|-----|
| FlightSim clone on disk (`\\flightsim\…\MemoryBox`) | `aa6c4aa7e98f61d5f323e8782b8b76516fc305c9` (detached, tracked clean) |
| Live serve process | **not recycled**; still the process that was running before this authorization (last on-disk checkout before FF was `46e6700`) |
| Desktop app clone `C:\MemoryBox` | also `aa6c4aa` tracked-clean (untracked mail/oauth/tmp only) |
| Edit repo `E:\MemoryBox-dev\p2-i13-stage-a` | `7f65ccd` plus this closeout |

Gallery was not re-proven against v3. Immutable-original links were not exercised in a browser this run; archive counts and loader contract are unchanged.

---

## Rollback readiness

- Fresh pre-activation dump above is valid and duplicated.
- Because activate **did not persist**, restoring the dump is **not** required to keep v1 active.
- Authorized rollback later remains: restore that dump, **or** revalidate v1 and `comms_prepared_activate_generation(v1)` under 040 (still needs founder go).
- v1, v2, and v3 rows were not deleted or rewritten.

---

## Remaining Phase C defects / stops

Still true, and **not** in this authorization:

- v3 is validated but **not** the active/published generation.
- Gallery/Explore still follow **v1** (blank-voice and short-text behavior unchanged in the UI).
- 59 `prepared_text_unavailable` (open original); 169 non_substantive; voice smaller than v1 by the accepted 038/039/v3 rules.
- SMS / calendar prepared stores, I11A, Gallery/SMS product fixes, and performance work are untouched.
- Serve recycle to pick up `aa6c4aa` while v3 is active **did not run**. Disk is already at `aa6c4aa`; a crash-restart of serve would load that SHA **without** v3 published.
- Completing activation requires a **new founder go** using the guarded v3 activator (postcheck now selects `id`). Do not use the 038 CLI. Do not load, migrate, delete v2, or rewrite generations.

---

## Stop

Stopped after verification of the rollback. No second activate, no recycle, no migrate, no reload.
