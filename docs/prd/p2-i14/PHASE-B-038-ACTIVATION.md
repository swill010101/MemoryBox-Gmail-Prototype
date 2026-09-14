# I14 Phase B — household-email generation activated (SQL)

**Status:** The visually accepted 038 household-email generation is **published and active** in PostgreSQL. Gallery UI, Person Ask cards, and I11A were **not** changed.

**Date:** 2026-09-14  
**Branch:** `codex/p2-i14-communications`  
**Activator SHA:** `dc01513a0834200306504c5e83ce605fd0097474`  
**038 SQL blob:** `1efe54148f932dc3a3a49c21273e9b5f43504ac0`

Counts-only JSON: [PHASE-B-038-ACTIVATION.json](PHASE-B-038-ACTIVATION.json). No generation UUID. No bodies.

## What ran

1. Pre-activation dump `E:\MemoryBox-backups\pre-i14-activate-038-20260914-130717\memorybox.dump` — **499250406** bytes; `pg_restore -l` **707** lines.
2. Dry-run `comms_prepared_assert_generation_ready` (rolled back).
3. One call: `comms_prepared_activate_generation` via `python -m memorybox i14-prepared-activate` with confirm `activate-unpublished-voice-038-v1`.

No `python -m memorybox migrate`. No reload. No Gallery/I11A code.

## After

| Check | Result |
| --- | --- |
| Published | **1** |
| Active (`comms_prepared_active_generations`) | **1** |
| Eligible unpublished | **0** |
| Failed | **0** |
| Threads / messages / participants / attachments | **40996 / 91247 / 294061 / 28467** |
| Voice From | Tom **12071**, Peggy **1368**, Sue **307** |
| Archive baselines | evidence **188656**, sources **27**, RFC ids **287010** |
| `/health` | `ok`, pending empty, `applied_n=38` |
| Historian Capture email | `live_ok`, `namecheap_privateemail_imap_smtp` |
| `historian_capture_email` | **Active** |

## Still blocked (separate founder gates)

- Gallery communications cards / default retrieval / suppression UX.
- Person Ask attaching prepared messages.
- I11A / Narrative consuming prepared voice.
- Calendar/SMS prepared generations.
- Replacing this generation.

The active view is live in the database. Do not wire Gallery or Ask to it without a new authorization.

## Rollback

Restore `E:\MemoryBox-backups\pre-i14-activate-038-20260914-130717\memorybox.dump` only if founder authorizes. Older pre-038 dump reverts 038 and the load as well. There is no deactivate function.

## FlightSim git

Pull `codex/p2-i14-communications` at `dc01513` or later so the activator CLI is on disk. Do **not** remigrate or reload. Serve recycle is optional; activation is already committed in Postgres.
