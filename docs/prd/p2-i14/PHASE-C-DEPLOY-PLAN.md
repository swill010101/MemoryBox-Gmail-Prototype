# I14 Phase C — FlightSim deploy / review plan (not executed)

**Status:** Plan only. Do not apply until founder authorization after this commit is on origin.  
**Date:** 2026-09-14  
**Branch:** `codex/p2-i14-communications`

This plan does **not** migrate, reload, or activate. Prepared data stays as Phase B closeout. Gallery remains unpublished until step 3.

## After this implementation SHA is on origin

1. On FlightSim `C:\MemoryBox`, pull the tracking branch (no migrate required for Phase C):

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i14-communications
git pull --ff-only
```

2. Confirm health and prepared counts unchanged (threads 40996, one active household-email generation). Do not run `i14-prepared-activate` or `i14-prepared-load`.

3. **Only after founder says go live:** set `MEMORYBOX_I14_GALLERY_COMMS=1` in the FlightSim serve environment (same place as other `MEMORYBOX_*` serve vars). Recycle Ask/serve. Do not set the flag in this implementation turn.

4. Founder review path (normal screens, no corpus dump):

   - Open Explore `/explore/ui` (or Person Explorer).
   - Ask `Show me Peggy`, then Sue, then Tom.
   - Confirm photos/videos appear first; email cards appear without a separate Comms button (cap 200 newest default-visible threads).
   - Open a thread; confirm cleaned chronology, warnings, attachment open/fail-closed, original on demand.
   - Close; confirm the same Gallery/Ask position.
   - Save as Story from the thread; confirm one `email_thread` memory and return without re-asking.
   - Start a second Ask quickly; confirm the first Ask’s emails do not appear on the second result.

5. Optional: keep `python -m memorybox i14-gallery-timings` for counts (read-only; does not require the serve flag).

## Rollback

Unset `MEMORYBOX_I14_GALLERY_COMMS` and recycle serve. Prepared tables are unchanged. No dump restore required for Gallery-only rollback.
