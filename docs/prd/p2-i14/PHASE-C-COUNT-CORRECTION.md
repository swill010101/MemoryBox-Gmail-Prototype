# I14 Phase C — scoped Curator / SMS / count correction

**Status:** In review, not accepted. **Do not activate** a replacement prepared generation.  
**Date:** 2026-09-15  
**Flag:** `MEMORYBOX_I14_GALLERY_COMMS=1`  
**Cache:** `explore.js?v=i14-c4`

## Root causes

1. **Curator bland / incomplete.** Server curator used photo/video item counts only, then JS `refreshCuratorFromVisible` overwrote with paging-style “N memories · range”. SMS and scoped email totals were omitted.
2. **SMS missing.** Prepared email attach skipped raw email (correct) but SMS hydrate either never ran, hid texts on All, or dropped SMS when merging prepared buckets. `items_from_ask_result` crashed on SMS hits with empty `people` (`people[0]`), swallowed by `_attach_hidden_sms`, so `sms_available` stayed 0 on live 5c5a3b5. Filter merge treated prepared buckets as email-only.
3. **1328 vs 11.** Unscoped / wrong-year `thread_total` (Tom 2025 all-years card) leaked into year Asks. Thread drill-down used Ask `date_from`/`date_to` even when opening a month, so a month modal could list the year (or page of 80) instead of that month. Modal “1 of N” is **navigation** in the opened bucket, with “Show more conversations” if the 80-row detail page continues; bucket `thread_n` is the complete scoped total.
4. **Empty John reply (T-39987 ordinal 2).** Prepared `cleaned_authored_text` is empty; `quote_quality=clean`, `commercial_class=not_commercial`. Original evidence still has body. Quote cleanup emptied authored text. **UI** now states the prepared text is missing and links the immutable original. **Do not edit this generation.** Corpus: **8343** empty cleaned bodies of **91247** active-generation messages (**7633** `not_commercial` / `retain_life_evidence`). Replacement generation needs separate authorization. Private TXT: `working/i14-thread-review/T-39987-empty-john.txt` (gitignored).
5. **Attachments.** Record-only / missing bytes rendered as a blank or “unavailable or record-only”. Now plain-language state labels; JPG/PNG preview; PDF/document open the **attached file**, not the thread.
6. **Person portrait.** Comms cards now use `/people/{askPersonId}/portrait`, not another participant’s face.

## Authoritative expected (existing SMS retrieve + prepared buckets)

Live **before** this SHA (`5c5a3b5` serve): Sue 2017 find `sms_available=0`, curator “254 memories, including 246 photos, 8 video moments.”

| Ask | photos | videos | SMS (retrieve match_total) | email threads (scoped buckets) | Stories (dated in window) |
|-----|--------|--------|----------------------------|----------------------------------|---------------------------|
| Sue Will in 2017 | 246 | 8 | **328** | **10** | 0 undated in 2017 |
| Tom Will (unbounded) | (find) | (find) | **3717** | year cards, not 80 | |
| Tom Will in 2024 | (find) | (find) | scoped SMS | **~1284–1296** (not 1328=2025 unbounded) | |

Peggy / unbounded Sue: use the same Person+date rules; zeros omitted from Curator.

## Filters

- All: mixed Gallery includes photos/videos/SMS/email buckets (and calendar when counted).
- Communications parent; Email / SMS independent.
- Email off: email cards and email counts gone; SMS remains if on.
- Pills, Curator, cards, expanded cards, modal totals share one scoped count.

## Deploy

No migrate. No prepared reload. Recycle serve after pull (`explore.js?v=i14-c4`). Diagnostic bar: `/explore/ui?mb_comms_diag=1` only.
