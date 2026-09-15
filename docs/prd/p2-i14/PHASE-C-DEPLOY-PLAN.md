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

Hard-refresh so `explore.js?v=i14-c5` loads.

FlightSim checkout path: `\\flightsim\FlightSim User\MemoryBox` (maps to `C:\MemoryBox` on the host). Recycle **on FlightSim** through `.venv`:

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i14-communications
git pull --ff-only
git rev-parse HEAD
.\startmb.cmd -Restart -SkipChrome
```

Desktop cannot WinRM/PsExec recycle. Do not run `startmb` from Toms-Desktop against this share.

Review path: `/explore/ui` — start with **Show me Sue Will in 2017**. Checklist: `docs/prd/p2-i14/PHASE-C-FOUNDER-REVIEW.txt`. Count correction: `docs/prd/p2-i14/PHASE-C-COUNT-CORRECTION.md`.

Rollback: unset the flag and recycle serve. Do not alter prepared data.
