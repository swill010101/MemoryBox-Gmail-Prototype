# I14 Phase C — Gallery integration (household email)

**Status:** Implemented on `codex/p2-i14-communications`. **Not exposed on FlightSim serve.** Default flag off.  
**Date:** 2026-09-14  
**Phase B closeout (accepted):** `6500ef032fa038be6e5a34b6ed312c92160fdf91`  
**Scope:** Active prepared household-email generation in Gallery Person Asks. No reload, no activate, no migration, no SMS/calendar prepared, no I11A, no per-thread `accept_thread` stamp.

Counts/timing JSON: [PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json). Deploy plan: [PHASE-C-DEPLOY-PLAN.md](PHASE-C-DEPLOY-PLAN.md).

## Product lock

### Person Ask

Asks such as “Show me Peggy / Sue / Tom” include communication **threads** when an authenticated participant `person_id` matches in **From, To, or Cc**. Gallery participation is not authored voice: do **not** filter `voice_corpus=true`. Do not create Person-specific generations or duplicate prepared rows.

### Progressive loading

Find returns photo/video first. Prepared threads attach from `GET /explore/api/prepared-comms` after paint. A new Ask issues a new token and **clears** prior tokens so stale threads cannot attach. If the active generation is missing, Gallery uses the last complete list and an “updated through” date — never a partial SQL cut.

### Commercial default (display only)

| Class / eligibility | Gallery default |
| --- | --- |
| `not_commercial` / `retain_life_evidence` → thread `show_by_default` | Display |
| `suppress_default` | Do not display automatically |
| `uncertain` → thread `hold_uncertain` | Retain; do not display automatically |

Filtering does not delete or rewrite prepared rows or Evidence.

### Cards and thread

Cards: media type email, subject, Gallery date (or range), trusted participant names, prepared-text preview, attachment count. No raw archive noise, tracking links, or technical ids.

Thread: cleaned chronology (From/To/Cc, time, subject, authored text). Attachments via existing `/explore/api/email-attachment/{parent_evidence_id}?index=` using `gallery_action` (`view_image` / `open_pdf` / `open_document` / `record_only`). Immutable original via `/explore/api/email/{evidence_id}`. Unverified parties labeled unverified. Quote/identity warnings when not clean.

### Navigation and Story

Close restores the same Gallery/Ask snapshot. Breadcrumb: “Gallery · Email”. Save as Story posts the **entire** prepared thread as one `email_thread` memory (`source_id` = display id). Attachment bytes are not copied.

### Review state

Founder Accept of generation 038 was a bounded quality gate. Per-thread `founder_review_state` remains `unreviewed` unless previously marked.

### Performance bound

Founder-facing Gallery cards are capped at **200** newest `show_by_default` threads per Person. Full matching totals are reported in timings JSON.

## Flag

`MEMORYBOX_I14_GALLERY_COMMS=1` enables Explore prepared reads and progressive attach. Default unset = existing I8 hidden-email / raw retrieve path.

Do **not** set this on FlightSim until the deploy plan is accepted.

## Proof

- Unit: `python -m unittest tests.test_i14_gallery_prepared -v` — **11 passed** (2026-09-14).
- Read-only production-scale SQL (FlightSim Postgres; **serve Gallery flag not set**):

| Person Ask | List SQL `query_ms` | Gallery cards (cap 200) | `show_by_default` total | `suppress_default` | `hold_uncertain` | 8-thread open sample | Attachments in sample (unavailable) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Peggy | 142 | 200 | 1544 | 128 | 12 | 93 ms | 5 (0) |
| Sue | 43 | 200 | 1325 | 213 | 52 | 80 ms | 6 (0) |
| Tom | 303 | 200 | 28284 | 10064 | 611 | 65 ms | 3 (0) |

Cancel previous Ask token: **true**. Time to first visual Gallery content is existing photo/video Find (comms are not on that payload). Communications availability is the list query above (142–303 ms) plus browser fetch after paint — inside the 10–20 s useful-content target. JSON: [PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json).

```powershell
$env:MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_GALLERY_TIMING_ALLOW_FLIGHTSIM = "1"
python -m memorybox i14-gallery-timings
```

## Out of scope (still)

Reload/activate another generation; SMS/calendar prepared; I11A; FlightSim Gallery go-live; stamping 40996 threads accepted; copying attachment bytes into prepared tables.
