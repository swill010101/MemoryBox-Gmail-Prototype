# I14 Phase C — Gallery integration (household email)

**Status:** Paging/Ask-path correction on `codex/p2-i14-communications`. **Not exposed on FlightSim serve.** Default flag off.  
**Parent implementation:** `294516751fcf3c1fadc64617f19798dbd3d66bc4` (provisionally accepted).  
**Date:** 2026-09-14  
**Phase B closeout (accepted):** `6500ef032fa038be6e5a34b6ed312c92160fdf91`  
**Scope:** Active prepared household-email generation in Gallery Person Asks. No reload, no activate, no migration, no SMS/calendar prepared, no I11A, no per-thread `accept_thread` stamp.

Counts/timing JSON: [PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json). Deploy plan: [PHASE-C-DEPLOY-PLAN.md](PHASE-C-DEPLOY-PLAN.md).

## Product lock

### Person Ask

Asks such as “Show me Peggy / Sue / Tom” include communication **threads** when an authenticated participant `person_id` matches in **From, To, or Cc**. Gallery participation is not authored voice: do **not** filter `voice_corpus=true`. Do not create Person-specific generations or duplicate prepared rows.

### Progressive loading

Find returns photo/video first. Prepared threads attach from `GET /explore/api/prepared-comms` after paint. A new Ask issues a new token, **clears** prior tokens, and **aborts** in-flight first-page and later-page fetches so stale threads cannot attach. If the active generation is missing, Gallery uses the last complete first page and an “updated through” date — never a partial SQL cut.

If Ask names a Person but does not resolve `person_id`, email is not attached and the curator states that plainly. Photos/video stay. If the resolved Person has **zero** prepared participants, status is `no_prepared_participant` (incomplete set is visible, not silent).

### Paging (history is reachable)

The browser holds **one page of at most 80** email cards (plus photos/video). That is a window, not the archive.

- **Newest page** loads first (`ORDER BY latest_at DESC, display_id DESC`).
- **Load older email** keyset-pages the next 80 (replaces the email window).
- **Year chips** list every year that has `show_by_default` threads; opening a year loads that year’s page and can walk the rest with Load older.
- Year histogram + undated count equals **reachable_total** (`show_by_default` for that Person).

Commercial `suppress_default` and uncertain `hold_uncertain` stay excluded from default Gallery.

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

Founder-facing Gallery holds at most **80** email cards at a time. Every `show_by_default` thread remains reachable via year chips and Load older. Full reachable totals are reported in timings JSON.

## Flag

`MEMORYBOX_I14_GALLERY_COMMS=1` enables Explore prepared reads and progressive attach. Default unset = existing I8 hidden-email / raw retrieve path.

Do **not** set this on FlightSim until the deploy plan is accepted.

## Proof

- Unit: `python -m unittest tests.test_i14_gallery_prepared -v` — **14 passed** (2026-09-14).
- Ask path: `find_ask_person_by_name(..., lazy_seed=False)` for Peggy, Sue, Tom — all `linked`; none unresolved.
- Read-only production-scale SQL (FlightSim Postgres; **serve Gallery flag not set**):

| Person | TTFV (photos) | First comms page | Next page | Year page | Browser email cards | Reachable `show_by_default` | suppress / uncertain | Year walk = histogram | Stale page cancel |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Peggy | Find returns first (comms not on payload) | 189 ms | 87 ms | 67 ms | 80 | **1544** | 128 / 12 | true | true |
| Sue | same | 65 ms | 65 ms | 52 ms | 80 | **1325** | 213 / 52 | true | true |
| Tom | same | 383 ms | 357 ms | 354 ms | 80 | **28284** | 10064 / 611 | true | true |

Histogram covers reachable for all three. Pages disjoint. Interaction proof (original, story, attachments linked not copied, warnings) **ok** on sampled threads. JSON: [PHASE-C-GALLERY-TIMINGS.json](PHASE-C-GALLERY-TIMINGS.json).

```powershell
$env:MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_GALLERY_TIMING_ALLOW_FLIGHTSIM = "1"
python -m memorybox i14-gallery-timings
```

## Out of scope (still)

Reload/activate another generation; SMS/calendar prepared; I11A; FlightSim Gallery go-live; stamping 40996 threads accepted; copying attachment bytes into prepared tables.
