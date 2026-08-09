# MBBS-001 Increment 4 — Acceptance Report

**Status:** **ACCEPTED** (including corrective reopen + owner manual validation)  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_4_DEFINITION.md](MBBS-001_INCREMENT_4_DEFINITION.md)  
**Corrective report:** [MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md](MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md)  
**Authorization:** Build Increment 4 only (corrective reopen authorized for planner/context + exploratory multimodal; no Increment 5)  
**Final acceptance host:** P1 runtime (FlightSim) + owner manual Ask validation

---

## Verdict

| Gate | Result |
|------|--------|
| I4 implementation (Ask, planner, context, thin UX, harness) | **COMPLETE** |
| Desktop `prove-ask` (initial + corrective suites) | **PASS** |
| P1-runtime `prove-ask --flightsim` (initial Immich path) | **PASS** (`ok: true`) |
| Immich on media-server (FlightSim) | **PASS** (`immich` / pong; opaque photo path exercised) |
| I4-G Immich-unavailable + communications continue | **PASS** |
| Corrective A–H context semantics + generalized Ask | **PASS** (desktop prove + owner manual) |
| Exploratory / know-about multimodal Ask | **PASS** (desktop `i4_exploratory_multimodal` + owner manual) |
| Owner manual-validation checkpoint | **PASS** (approved by Tom) |

**Increment 4 is ACCEPTED.**  
**Do not polish Increment 4 further.**  
**Do not begin Increment 5** without explicit authorization (*Build Increment 5 only*).

---

## Criteria map

| ID | Result | Opaque detail |
|----|--------|---------------|
| **I4-A** | PASS | Evidence-backed ask; citations present |
| **I4-B** | PASS | Insufficient disclosure on unsupported ask |
| **I4-C** | PASS | EVS-005/006 shaped asks; no inventing |
| **I4-D** | PASS | EF-02 follow-ups with inherited context |
| **I4-E** | PASS | Clear / change context; no stale leak |
| **I4-F** | PASS | Breadcrumb + thin Ask UX (`/ask/ui`) |
| **I4-G** | PASS | Provider unavailable surfaced; communications Ask still cited Evidence |
| **I4-H** | PASS | No false memories / inventing gate |
| **I4-I** | PASS | Health increment ≥4; no host hardcodes in product `.py` |
| **I4-J** | PASS | Living specs + acceptance / corrective reports |
| **I4-K** | PASS | Generalized Ask; unseen entity variation |
| **Intent-oriented visual** | PASS | `visual_scope` broad / still_only / video_only contract |
| **Context semantics A–H** | PASS | Typed slots, supersede, refs, ambiguity, constrained retrieval, display=effective |
| **Exploratory multimodal** | PASS | Know-about / tell-me-about always multimodal across I4 modalities; narrowing wins |

No family message bodies, photo binaries, or credentials are recorded here.

---

## Corrective reopen (included in acceptance)

| Topic | Outcome |
|-------|---------|
| Context contamination (person→place/trip; stale events; then/other-trip) | Fixed under rules A–H; `i4_context_semantics_AH` |
| `show me <person>` skipped Immich | Fixed; broad visual when no explicit media word |
| Exploratory “know about / tell me about” skipped Immich | Fixed; always multimodal for I4-available modalities (not photo-fallback) |
| Desktop prove after corrective | `ok: true` including `i4_exploratory_multimodal` |
| Owner manual validation | Approved — context-semantic corrections + generalized multimodal exploratory Ask |

### Post-acceptance defect policy

Additional Ask-language edge cases discovered in normal use are recorded as **defects / EVS refinements** and addressed in the **appropriate future increment**, unless they expose a **fundamental architectural or trust failure** (Evidence First / No False Memories / inventing). Do **not** continue polishing I4.

---

## FlightSim final (opaque)

| Field | Value |
|-------|-------|
| Date | 2026-08-09 |
| Command | `python -m memorybox prove-ask --flightsim` |
| Result | `"ok": true` (initial Immich acceptance path) |
| Immich | `provider_key=immich`, `ok=true`, `detail=pong` |
| Evidence rows (opaque) | 13 (initial report) |
| Indexed (rebuild, opaque) | 13 |
| Photo ask (opaque, initial) | photos returned under Immich path |
| Corrective commits (examples) | `3d906d8`, `2c0a25e`, `c8839c2` |
| Problems | none recorded for accepted path |

---

## What shipped

| Area | Location |
|------|----------|
| Session context contract | `memorybox/context/` |
| Query Planner v0 + visual_scope + exploratory multimodal | `memorybox/planner/` |
| Orchestrator + retrieval | `memorybox/ask/` |
| In-package Immich HTTP client | `memorybox/providers/photo/_immich_http.py` |
| Thin Ask UX | `GET /ask/ui` |
| CLI | `ask`, `prove-ask`, `prove-ask --flightsim` |
| FlightSim runbook | [FLIGHTSIM_I4_ACCEPTANCE_RUNBOOK.md](../ops/FLIGHTSIM_I4_ACCEPTANCE_RUNBOOK.md) |

---

## Stop

- Increment 4 **ACCEPTED** (corrective + owner manual included).  
- **No further I4 polish.**  
- **Do not** start Increment 5, Story, Journal, SMS ingest, Guided Capture, Review & Learn, Person teach/merge, video/HVRT, or visual polish without explicit authorization.  
- Next: Increment 5 **definition for review only** — [MBBS-001_INCREMENT_5_DEFINITION.md](MBBS-001_INCREMENT_5_DEFINITION.md).
