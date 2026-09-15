# I14 Phase C — Gallery date-bucket integration (review)

**Status:** Corrective implementation on `codex/p2-i14-communications`. **Not accepted.** Feature flag still `MEMORYBOX_I14_GALLERY_COMMS`.  
**Date:** 2026-09-15  
**Founder stop:** “Show me Sue Will in 2017” — prior email-browser attach is **not accepted**.  
**Phase B closeout (accepted):** `6500ef032fa038be6e5a34b6ed312c92160fdf91`  
**Do not:** reload/activate prepared data, migrate, I11A, SMS/calendar prepared, stamp threads accepted.

## Corrective contract

Communications join the Gallery’s date-scoped aggregation. The 80-row bound is **thread-detail only**.

1. Person + date Asks constrain **every** media type to that Person and window. Undated Stories/photos/comms are excluded. Other years are excluded.
2. Year-precision Ask → month cards for months that have evidence; counts are complete; expand loads that month’s threads.
3. Person-only Ask → year cards whose counts are the full qualifying year, not an 80-row page.
4. Background buckets update existing Gallery cards; they must not select the Communications pill.
5. Year-chip bar, thread counters, and “Load older email” are diagnostic-only (`?mb_comms_diag=1`).
6. Curator language is natural complete scoped counts (photos, videos, text messages, Stories, Artifacts, calendar, email threads). Zeros omitted. No paging/retrieval jargon.
7. Opened threads keep chronology, parties, warnings, attachments, original-on-demand, Save as Story. Close restores Ask, bucket, filter, and scroll.
8. A new Ask cancels prior tokens and clears prior aggregation.

## Flag

`MEMORYBOX_I14_GALLERY_COMMS=1` on FlightSim serve (already set for review). Default unset = I8 hidden-email path.

## Proof

```powershell
python -m unittest tests.test_i14_gallery_scope tests.test_i14_gallery_prepared -v
```

```powershell
$env:MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_GALLERY_TIMING_ALLOW_FLIGHTSIM = "1"
python -m memorybox i14-gallery-timings
```

Counts JSON: [PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json). Deploy: [PHASE-C-DEPLOY-PLAN.md](PHASE-C-DEPLOY-PLAN.md).
