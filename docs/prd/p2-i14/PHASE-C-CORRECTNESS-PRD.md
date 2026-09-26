# Phase C correctness — diagnosis and Gallery pipeline (PRD)

**Status:** Authorized for diagnosis, instrumentation, and Gallery/Ask correctness. **Not accepted.**  
**Date:** 2026-09-16  
**Prepared-email data:** closed. Do not modify the active v3 generation or preparation rules.  
**Do not:** migrate, reload, activate, I11A, archive write, FlightSim serve recycle.

## Problem

After v3 activation, founder review of Ask/Gallery (not prepared text) found:

1. Person Asks take ~25–40 s even when year-bounded Asks should do less work.
2. Curator omits email-thread counts; Communications pill does not include email.
3. Tom’s Ask showed ~90 email threads as **one** card under **1970**.
4. Cora’s Ask showed unrelated Stories for Tom, Sue, Peggy, Mom, and Dad.
5. Immich vs MemoryBox visual counts disagree without an equation.

Existing notes: [PHASE-C-PERFORMANCE-DEFECT.md](PHASE-C-PERFORMANCE-DEFECT.md), [PHASE-C-COUNT-CORRECTION.md](PHASE-C-COUNT-CORRECTION.md), [PHASE-C-GALLERY.md](PHASE-C-GALLERY.md). Prepared-email SQL timings (~hundreds of ms) do not explain the wait.

## Success

- One Ask correlation token times browser submit → first visual Gallery → background SMS/email completion (cold and warm for the five named Asks).
- Blocking vs background stages identified; no blind optimization.
- Unbounded Person Ask: one year card per real year, correct thread counts; no synthetic 1970 card unless evidence is truly 1970.
- One scoped-count object drives Curator, pills, cards, buckets, modal. Zeros suppressed. Communications = email + SMS (filters independent).
- Cora Ask shows only Stories linked to Cora. New Ask clears prior results and aborts stale fetches.
- Immich→MB equation with unexplained = 0 before claiming match.
- Photos/video + Curator shell first; SMS and prepared email hydrate later without resetting Gallery position.
- Tests listed in the founder request. Stop before FlightSim deploy.

## In / out

**In:** Ask/Explore instrumentation; Gallery bucket/card/curator/pill JS; find/orchestrator retrieve order; story person-scope; Immich count probe (read-only); regression tests.

**Out:** v3 rows/rules; migrations; activation; I11A; SMS/calendar prepared stores; serve recycle.

## Constraints

FlightSim DB read-only for diagnosis. Feature flag `MEMORYBOX_I14_GALLERY_COMMS` unchanged. Cache-bust `explore.js`.
