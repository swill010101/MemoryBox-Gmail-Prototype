# I14 Phase B — closeout (household-email activation)

**Status:** Phase B complete. One household-email generation is published and active. Phase C (Gallery) is **not** started.

**Date:** 2026-09-14  
**Branch:** `codex/p2-i14-communications`  
**Runtime SHA (FlightSim, founder-confirmed):** `ecf3e6726456c40f64f8bc38ea5d59f46c164b31`  
**038 blob:** `1efe54148f932dc3a3a49c21273e9b5f43504ac0`  
**Activator CLI:** `dc01513a0834200306504c5e83ce605fd0097474`

Counts-only JSON: [PHASE-B-CLOSEOUT.json](PHASE-B-CLOSEOUT.json). No generation UUID, addresses, bodies, or backup paths in JSON.

## Authorization this turn

Founder authorized atomic activation of exactly the accepted unpublished generation, plus backup, FlightSim sync, optional serve restart, and read-only proof. Reload, extra generations, extra migrations, Gallery/Ask/I11A code, Gallery display, and SMS/calendar were not authorized.

## What this turn did

Read-only verification and this closeout. **Did not** call `comms_prepared_activate_generation` again (generation already published/active from the guarded CLI on 2026-09-14). **Did not** migrate, reload, restart serve, or change application code.

Pre-activation unpublished/published=0 checks applied to the moment before that earlier atomic call. They cannot hold now: published **1**, unpublished **0**. Re-calling activate would violate “exactly the accepted generation / no second generation.”

## Backup identity (pre-activation)

`pre-i14-activate-038-20260914-130717` custom dump: **499250406** bytes; `pg_restore -l` **707** (re-validated this turn). Taken before the atomic activate. Not a post-activation dump.

## FlightSim / desktop git

| Tree | HEAD | Tracked |
| --- | --- | --- |
| FlightSim `C:\MemoryBox` | `ecf3e6726456c40f64f8bc38ea5d59f46c164b31` (founder paste) | 038 blob match |
| Desktop workspace before this closeout commit | same SHA | clean |

## Activation result (already applied)

Guarded path: `python -m memorybox i14-prepared-activate` → `comms_prepared_activate_generation` once. Confirm `activate-unpublished-voice-038-v1`. No row-by-row publish.

| Check | Result |
| --- | --- |
| Generations total | **1** |
| `published` + `is_active` + `status=published` | **1** |
| `comms_prepared_active_generations` | **1** (`household_email`) |
| Other published/active | **0** |
| Eligible unpublished | **0** |
| Failed | **0** |

## Packet identity

Active generation contains all **11** packet threads and all **26** FOCUS Evidence-refs from `working/i14-activation-review/` (gitignored), including `T-2312-M-02` and `T-2345-M-02` (`voice_corpus`, `quote_quality=clean`). Same generation the founder accepted.

## Founder marks

Defect / hold marks **0**. All **40996** threads remain `unreviewed` in the table (packet Accept was not written back as `accept_thread` rows). No unresolved split/merge/incorrect/needs_investigation marks.

## Counts reconciliation

| Measure | Expected | Live |
| --- | ---: | ---: |
| Threads | 40996 | 40996 |
| Messages | 91247 | 91247 |
| Participants | 294061 | 294061 |
| Attachments | 28467 | 28467 |
| Duplicate omitted (sum) | 26 | 26 |
| Identities / aliases | 91247 / 182494 | 91247 / 182494 |
| Tom / Peggy / Sue voice | 12071 / 1368 / 307 | 12071 / 1368 / 307 |
| Evidence / sources / RFC ids | 188656 / 27 / 287010 | 188656 / 27 / 287010 |

Completeness (from accepted load; prepared+omitted re-checked): `91281 = 91247 + 26 + 2 + 6 + 0`. Unexplained **0**.

Ledger **001–038**; `/health` pending empty; `applied_n=38`; `ok`.

Historian Capture: Namecheap `live_ok`; `historian_capture_email` **Active**.

## Remaining risks

- Gallery/Ask do not read `comms_prepared_*`; product UI still has no household-email cards.
- Table-level founder_review_state is still `unreviewed` for every thread.
- Serve was not recycled; DB flags do not require a process restart for this closeout.
- After this docs commit, FlightSim HEAD will lag until a docs-only pull (no migrate).
- Rollback remains restore of the pre-activation dump.

## Not started

Phase C Gallery integration. I11A. SMS/calendar prepared load. Application behavior changes.
