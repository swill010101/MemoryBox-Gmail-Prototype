# Phase C — deferred Ask performance defect (open)

**Status:** Open Phase C acceptance item. **Not accepted. Do not optimize in the empty-body / prepared-text recovery work.**  
**Date:** 2026-09-15  
**Gate:** After prepared-data recovery authorization, before Phase C close.  
**Not caused by** the current empty-body notices or HTML source-selection correction (those do not run on the live Ask path against the active generation).

## Observed on FlightSim

| Ask | User-visible wait |
|-----|-------------------|
| Show me Sue Will | ~20–25 seconds |
| Show me Sue Will in 2017 | ~20–25 seconds |

The year-constrained Ask has a much smaller evidence scope and **must** be materially faster. Thread compression and prepared communications were intended to improve response time, not hold first paint for the full pipeline. Photos and video should appear before slower communication hydration.

Existing `i14-gallery-timings` / [PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json) measure prepared-email SQL only (hundreds of ms). That does **not** explain the ~20–25 s user-visible delay.

## Required before Phase C closes (instrument; do not do this now)

Instrument the complete user-visible timeline, not only prepared-email SQL:

1. Ask submission → Person / date resolution
2. Photo / video query
3. Story / Artifact query
4. SMS retrieval
5. Prepared-email aggregation
6. Curator generation
7. First Gallery render
8. Background communications completion

Report **cold and warm** timings for **bounded and unbounded** Peggy, Sue, and Tom Asks.

Identify what creates the approximately **fixed** 20–25 s delay. Prove that adding a year constraint reduces the **relevant** work (not a constant wait that ignores scope).

## Explicitly out of this increment

- No Ask/Explore pipeline rewrite
- No prefetch / progressive-render change
- No SMS or prepared-email query optimization
- No migrate, reload, or activate

Preserve this gate for after prepared-data recovery.
