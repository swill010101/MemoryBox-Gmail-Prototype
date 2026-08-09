# MBBS-001 Increment 4 — Corrective Acceptance Report

**Status:** **CORRECTIVE FIX COMPLETE — DESKTOP PROVE PASS; FLIGHTSIM RE-PROVE REQUIRED**  
**Date:** 2026-08-09  
**Scope:** Targeted planner/context defect correction only (rules A–H). **No Increment 5.**  
**Prior acceptance:** Reopened after manual owner testing exposed semantic context failures.

---

## Verdict

| Gate | Result |
|------|--------|
| Corrective implementation (planner typed slots, supersede, refs, ambiguity, constrained retrieval) | **COMPLETE** |
| Desktop `prove-ask` including `i4_context_semantics_AH` | **PASS** (`ok: true`) |
| FlightSim full `prove-ask --flightsim` re-run | **PENDING operator** (same remoting limit) |

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

---

## New acceptance check

| ID | Result (desktop) | Detail |
|----|------------------|--------|
| **i4_context_semantics_AH** | PASS | Generalized Northland/Morgan + unseen Rivermark/Sam; no Alaska/Peggy/Christmas in planner |

Prior I4-A…K / intent-oriented visual / Immich-unavailable / no-false-memory gates remain in the suite.

---

## FlightSim re-prove (operator)

```powershell
cd C:\MemoryBox
git pull origin cursor/marvin-capture-v01-3344
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
python -m memorybox prove-ask --flightsim
```

Expect `"ok": true` including `i4_context_semantics_AH`. Paste opaque JSON into § below when done.

### FlightSim corrective final

| Field | Value |
|-------|-------|
| Date | _pending_ |
| `prove-ask --flightsim` | _pending_ |

---

## Stop

- Corrective code + desktop prove complete.  
- **No Increment 5** / Story / Journal / SMS / HVRT / polish.  
- Full I4 re-acceptance after FlightSim `"ok": true`.
