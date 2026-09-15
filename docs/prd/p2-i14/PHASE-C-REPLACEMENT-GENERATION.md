# I14 replacement household-email generation (039 + unpublished v2 load)

**Status:** Authorized to migrate 039 and load one unpublished generation. **Not authorized to activate.** Phase C Gallery remains in review.  
**Date:** 2026-09-15

## Confirm strings

| Step | Flag / confirm |
| --- | --- |
| Backup | `MEMORYBOX_I14_BACKUP_ALLOW_FLIGHTSIM=1` `MEMORYBOX_I14_BACKUP_CONFIRM=pre-039-replacement-generation-v1` |
| Load alongside active | `MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM=1` `MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB=1` `MEMORYBOX_I14_LOAD_ALONGSIDE_ACTIVE=1` `MEMORYBOX_I14_LOAD_CONFIRM=household-email-unpublished-v2-alongside-active` |
| Activate | **do not set** |

039 SQL: `memorybox/migrations/039_p2_i14_voice_requires_prepared_text.sql`  
Algo: `i14-prepared-email-v2`  
Packet (gitignored): `working/i14-household-email-review-v2/`

## Sequence (FlightSim)

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i14-communications
git pull
# tracked-clean; 039 blob matches origin

$env:MEMORYBOX_I14_BACKUP_ALLOW_FLIGHTSIM = "1"
$env:MEMORYBOX_I14_BACKUP_CONFIRM = "pre-039-replacement-generation-v1"
python -m memorybox.ops.i14_flightsim_backup

python -m memorybox migrate   # pending must be exactly 039; second run none

$env:MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM = "1"
$env:MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_LOAD_ALONGSIDE_ACTIVE = "1"
$env:MEMORYBOX_I14_LOAD_CONFIRM = "household-email-unpublished-v2-alongside-active"
$env:MEMORYBOX_I14_REVIEW_EMIT_PRIVATE = "1"
$env:MEMORYBOX_I14_REVIEW_OUT = "working/i14-household-email-review-v2"
$env:MEMORYBOX_I14_LOAD_PUBLIC_OUT = "docs/prd/p2-i14/PHASE-C-REPLACEMENT-LOAD-COUNTS.json"
$env:MEMORYBOX_I14_LOAD_PRIVATE_OUT = "E:\MemoryBox-backups\i14-039-private.json"
python -m memorybox i14-prepared-load
```

Do **not** call `i14-prepared-activate`. Do not start I11A. Do not create SMS/calendar prepared stores.

## Gates

- Completeness: `91281 = prepared + 26 omitted + 2 missing From + 6 held + 0 unexplained`
- One prepared message per surviving evidence id
- Active generation child counts unchanged (40996 / 91247 / 294061 / 28467)
- Archive: evidence 188656, sources 27, RFC ids 287010
- John evidence `5941e1bb-5354-4bba-9bac-fb1f0a9fd963` recovered authored text
- Dispositions: authored, correctly empty, attachment-only, prepared_text_unavailable, cleanup_removed_meaningful, unexplained=0
- `comms_prepared_assert_generation_ready` succeeds on the **new** id; blank+voice cannot activate
- New generation `validated`, unpublished, inactive
