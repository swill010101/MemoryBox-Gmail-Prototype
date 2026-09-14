# I14 Phase B — activation plan (unpublished 038 household-email generation)

**Status:** Executed 2026-09-14. SQL published+active. Gallery/I11A still unwired. See [PHASE-B-038-ACTIVATION.md](PHASE-B-038-ACTIVATION.md).  
**Depends on:** [PHASE-B-038-ACTIVATION-REVIEW-ACCEPT.md](PHASE-B-038-ACTIVATION-REVIEW-ACCEPT.md) (founder visual review accepted 2026-09-14).  
**Execute record:** [PHASE-B-038-ACTIVATION.md](PHASE-B-038-ACTIVATION.md)

## Problem

The replacement household-email generation is `validated` and visually accepted, but Gallery’s active view is empty until `comms_prepared_activate_generation` runs. Activation is a one-way SoT flag change. It must not be improvised as a raw `UPDATE`, and it must not silently start Gallery or I11A.

## Success criteria (when later authorized)

1. Exactly one eligible unpublished generation remains the target; checksum and `validated` still hold.
2. `comms_prepared_assert_generation_ready` succeeds (canonical record on every message, From present, voice has authenticated From Person).
3. One transaction calls `comms_prepared_activate_generation` only. No row-by-row `published`/`is_active` writes.
4. After: published **1**, active **1**, `comms_prepared_active_generations` **1**, failed **0**, eligible unpublished **0**. Child row counts unchanged.
5. Archive baselines unchanged: evidence **188656**, sources **27**, RFC ids **287010**.
6. `/health` `ok`; Historian Capture email still Namecheap `live_ok`; `historian_capture_email` not Error/Disabled.
7. Voice From counts unchanged: Tom **12071**, Peggy **1368**, Sue **307**.
8. Counts-only JSON (no UUIDs, bodies, addresses). No HTML. No corpus dump.
9. Gallery UI, Explore Ask cards, and I11A prompts are **not** changed in that same increment.

## Scope

### In (activation increment only)

- New pre-activation `pg_dump` of FlightSim `memorybox` (separate from the pre-038 dump).
- FlightSim git at a SHA that contains 038 + corrected loader (`bf61896` or later on this branch). Do not remigrate or reload.
- Guarded CLI (not yet written) that:
  - refuses unless FlightSim/memorybox allow flags and an exact confirm string are set;
  - selects the single `validated` unpublished inactive `household_email` generation;
  - optionally dry-runs `comms_prepared_assert_generation_ready`;
  - then `SELECT comms_prepared_activate_generation(%s)` once;
  - never calls Gallery, Ask, or I11A.
- Read-only post-checks listed under success criteria.
- Sanitized ops note (ledger, flags, dump path/bytes, SHA). No generation UUID in git.

### Out (separate founder gates after activation)

- Gallery communications cards, default retrieval, suppression UX.
- Person Ask (“Show me Peggy/Sue”) attaching prepared messages.
- I11A / Narrative consuming `cleaned_authored_text`.
- Calendar/SMS prepared generations.
- Replacing or superseding this generation again.
- Restoring the pre-038 dump except as emergency rollback.

## Constraint: activate is publish

Migration 036’s `comms_prepared_activate_generation` sets `published=TRUE`, `is_active=TRUE`, and `status='published'` in the same statement. There is no activate-without-publish API.

Direct `UPDATE` of those flags raises `row_by_row_publication_forbidden`.

Today no application query except I14 ops/tests reads `comms_prepared_*`. Activating therefore changes SoT and fills `comms_prepared_active_generations`, but does **not** by itself render threads in Gallery. Product exposure still needs a later wiring authorization. Treat the DB view as live as soon as activation succeeds.

There is no deactivate function. Rollback is restore of the **pre-activation** dump (preferred) or the older pre-038 dump (reverts 038 and the load).

## Preconditions (re-verify immediately before execute; do not migrate/reload)

| Check | Expected |
| --- | --- |
| Ledger | 001–038; pending empty |
| 038 blob | `1efe54148f932dc3a3a49c21273e9b5f43504ac0` |
| Voice CHECK | `NOT voice_corpus OR (quote_quality=clean AND authorship=authenticated_focal)` |
| Generations | one `validated` unpublished inactive; published 0; active 0; failed 0 |
| Prepared counts | threads **40996**, messages **91247**, participants **294061**, attachments **28467** |
| Completeness | unexplained **0** |
| New dump | exists, size recorded, `pg_restore -l` recorded, taken **after** visual accept and **before** activate |
| HC | `/historian-capture/email-status` ok + `namecheap_privateemail_imap_smtp`; scheduled `historian_capture_email` not forbidden status |
| Confirm string (proposed) | `activate-unpublished-voice-038-v1` plus `MEMORYBOX_I14_ACTIVATE_ALLOW_FLIGHTSIM=1` and `MEMORYBOX_I14_ACTIVATE_ALLOW_MEMORYBOX_DB=1` |

Do not print the generation UUID in git or chat. The CLI may read it in-process only.

## Sequencing (execute only after founder “go”)

1. Pull FlightSim `C:\MemoryBox` to the authorized SHA. `git status` tracked-clean. Hash 038. **No** `python -m memorybox migrate`. **No** `i14-prepared-load`.
2. Take pre-activation dump under `E:\MemoryBox-backups\`.
3. Re-run the precondition queries read-only.
4. Dry-run ready-assert.
5. Activate once.
6. Post-check counts, health, HC.
7. Stop. Do not open Gallery wiring or I11A.

Optional `startmb.cmd -Restart` only if serve HEAD must match; startup migrate must apply nothing.

## Risks

- Activating the wrong generation: refuse unless unpublished eligible count is exactly 1.
- Missing canonical/From/voice rows: ready-assert aborts; prior active (none today) stays unchanged.
- Dump after activate is not a substitute for the pre-activation dump.
- Future Gallery work could start reading the active view without a new load; keep that wiring gated.

## Confirmed before execute

1. SQL publish+activate with Gallery/I11A unwired.
2. Confirm string `activate-unpublished-voice-038-v1`.
3. New pre-activation dump required.
4. FlightSim git pull still cannot run from Toms-Desktop (SSH closed); SQL activate was run from desktop against FlightSim Postgres. Pull the activator SHA on FlightSim for tree alignment only.
