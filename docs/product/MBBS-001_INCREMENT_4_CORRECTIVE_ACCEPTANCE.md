# MBBS-001 Increment 4 — Corrective Acceptance Report

**Status:** **CORRECTIVE FIX COMPLETE — DESKTOP PROVE PASS; FLIGHTSIM RE-PROVE REQUIRED**  
**Date:** 2026-08-09  
**Scope:** Planner/context defects (rules A–H) + exploratory/know-about multimodal intent + show-me person photo path. **No Increment 5.**  
**Prior acceptance:** Reopened after manual owner testing; remains reopened until FlightSim + manual re-test pass.

---

## Verdict

| Gate | Result |
|------|--------|
| Corrective implementation (A–H + exploratory multimodal + show-me person) | **COMPLETE** |
| Desktop `prove-ask` including `i4_context_semantics_AH` + `i4_exploratory_multimodal` | **PASS** (pending this push) |
| FlightSim full `prove-ask --flightsim` re-run | **PENDING operator** |
| Manual Ask re-test (trip know-about → Immich + Evidence) | **PENDING operator** |

I4 remains the authorized increment. **Do not begin Increment 5.**

---

## Defects addressed

| # | Observed | Fix |
|---|----------|-----|
| 1 | `place`/`trip` contaminated with person names; stale event retained | Typed slots (C); supersede on subject change (D) |
| 2 | Explicit new trip did not clear incompatible event | Rule D in planner |
| 3 | “around then” unconstrained / unrelated hits | Resolve “then” (E) + constraint filter (G) |
| 4 | “other trip” silent unrelated hit | Clarification / ambiguity (F) |
| 5 | Displayed context ≠ retrieval | plan_slots + constraints on response (H); context update from plan only |
| 6 | `show me <person>` used email/calendar only | Broad visual when no explicit media word; case-insensitive person extract |
| 7 | “What do you know about our \<Trip\> trip?” skipped Immich despite photos existing | Exploratory/know-about = always multimodal across I4 modalities (not photo-fallback) |

---

## New acceptance checks

| ID | Result (desktop) | Detail |
|----|------------------|--------|
| **i4_context_semantics_AH** | PASS | Generalized Northland/Morgan + unseen Rivermark/Sam |
| **i4_exploratory_multimodal** | PASS | Photo-only / evidence-only / both / neither / narrowed emails + Harborwick variation |

---

## FlightSim re-prove (operator)

```powershell
cd C:\MemoryBox
git fetch
git checkout cursor/marvin-capture-v01-3344
git pull
# Restart Ask if running:
python -m memorybox serve
# Acceptance:
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox prove-ask --flightsim
```

Manual smoke: Clear context → `What do you know about our Alaska trip?` → expect visual/still/photo **and** communication/calendar in Effective retrieval; Immich hits when photos exist.

Expect `"ok": true` including `i4_exploratory_multimodal`. Paste opaque JSON into § below when done.

### FlightSim corrective final

| Field | Value |
|-------|-------|
| Date | _pending_ |
| `prove-ask --flightsim` | _pending_ |

---

## Stop

- Corrective code + desktop prove complete after push.  
- **No Increment 5** / Story / Journal / SMS / HVRT / polish.  
- Full I4 re-acceptance after FlightSim `"ok": true` + manual trip ask.
