# I14 Phase C — date-bucket Gallery review deploy

**Status:** Redeploy for bounded FlightSim visual review. Not accepted.  
**Date:** 2026-09-15  
**Branch:** `codex/p2-i14-communications`

No migrate. No prepared reload/activate. Flag should already be `MEMORYBOX_I14_GALLERY_COMMS=1`.

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i14-communications
git pull --ff-only
git rev-parse HEAD
.\startmb.cmd -Restart -SkipChrome
```

Confirm `/health` ok, pending empty, ledger 001–038. Confirm `GET /explore/api/prepared-comms?person_id=...&token=x` returns JSON with `"buckets"` (not 404).

Review path: `/explore/ui` — start with **Show me Sue Will in 2017**. Checklist: `Desktop\PHASE-C-FOUNDER-REVIEW.txt` or `docs/prd/p2-i14/PHASE-C-FOUNDER-REVIEW.txt`.

Rollback: unset the flag and recycle serve. Do not alter prepared data.
