# I14 unpublished v3 load (040 + v3 alongside v1/v2)

**Status:** Founder authorized apply 040 and load one unpublished v3 generation. **Not authorized to activate or publish.** Do not start I11A.  
**Date:** 2026-09-16  
**SHA at authorization:** `feade9f` pre-load gate; load SHA follows this file.

## Confirm strings

| Step | Flag / confirm |
| --- | --- |
| Load alongside v1 + keep v2 | `MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM=1` `MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB=1` `MEMORYBOX_I14_LOAD_ALONGSIDE_ACTIVE=1` `MEMORYBOX_I14_LOAD_KEEP_UNPUBLISHED_V2=1` `MEMORYBOX_I14_LOAD_CONFIRM=household-email-unpublished-v3-alongside-v1-v2` |
| Activate | **do not set** |

040 SQL: `memorybox/migrations/040_p2_i14_voice_requires_displayable_authored.sql`  
Algo: `i14-prepared-email-v3`  
Packet (gitignored): `working/i14-household-email-review-v3/`

## Sequence

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i14-communications
git pull

python -m memorybox migrate   # pending must be exactly 040; second run none

$env:MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM = "1"
$env:MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_LOAD_ALONGSIDE_ACTIVE = "1"
$env:MEMORYBOX_I14_LOAD_KEEP_UNPUBLISHED_V2 = "1"
$env:MEMORYBOX_I14_LOAD_CONFIRM = "household-email-unpublished-v3-alongside-v1-v2"
$env:MEMORYBOX_I14_REVIEW_EMIT_PRIVATE = "1"
$env:MEMORYBOX_I14_REVIEW_OUT = "working/i14-household-email-review-v3"
$env:MEMORYBOX_I14_LOAD_PUBLIC_OUT = "docs/prd/p2-i14/PHASE-C-V3-LOAD-COUNTS.json"
$env:MEMORYBOX_I14_LOAD_PRIVATE_OUT = "E:\MemoryBox-backups\i14-040-v3-private.json"
$env:MEMORYBOX_I14_LOAD_DEADLINE_S = "10800"
python -m memorybox i14-prepared-load
```

Do **not** call `i14-prepared-activate`. v1 stays active. v2 stays unpublished validated.

## Gates

- Completeness: `91281 = prepared + 26 omitted + 2 missing From + 6 held + 0 unexplained`
- v3 every message has a non-null six-way disposition; voice only when `authored_displayable`
- Active v1 child counts unchanged (40996 / 91247 / 294061 / 28467)
- Unpublished v2 id, status, checksum, and child counts unchanged
- Archive baseline unchanged (188656 / 27 / 287010)
