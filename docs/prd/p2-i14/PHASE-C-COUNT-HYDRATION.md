# Phase C — Communications count hydration (I14 remaining defects)

**Status:** Implemented, not I14-accepted. Prepared v3 unchanged.  
**Date:** 2026-09-16  
**Cache:** `explore.js?v=i14-c8`

## Root causes

1. **Partial Communications total.** After email buckets arrived, the parent pill summed `threads + sms` with SMS still 0 and showed **1,257** as if it were the final Communications count. Curator `naturalCommsSummary` omitted “Text messages loading…”.
2. **Filter freeze ~20 s.** Applying Text/Communications while SMS cards were not yet visible called `presentWithoutRewritingAsk("sms")`, which re-ran Find with a blocking 10,000-row SMS retrieve. Hydration was not reused.
3. **Immich vs MB (Sue 5,015 vs 4,923).** Person library fetch was hard-capped at **5,000** (`search_by_person_ids` and Ask `photo_limit`). That is a pagination/cap defect. Live equation for Tom/Sue/Cora is the remaining proof after recycle.

## After

- First paint: available grains + **Text messages loading…** (never a partial combined total as final).
- Hydration updates Curator, Communications, Email, Text pills, and cards automatically.
- Filter click paints immediately; SMS query stays background; in-flight/cached hydrate is reused.
- Person library fetch cap **25,000**.
- I15 backlog: `docs/prd/p2-i14/I15-POST-I14-VISUAL-CONSISTENCY-BACKLOG.md`

## Tests

`python -m unittest tests.test_i14_phase_c_correctness tests.test_i14_gallery_scope tests.test_i14_gallery_prepared`
