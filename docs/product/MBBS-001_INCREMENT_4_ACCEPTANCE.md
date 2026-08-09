# MBBS-001 Increment 4 — Acceptance Report

**Status:** **ACCEPTED**  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_4_DEFINITION.md](MBBS-001_INCREMENT_4_DEFINITION.md) (locked scope)  
**Authorization:** Build Increment 4 only  
**Final acceptance host:** P1 runtime (FlightSim) — `prove-ask --flightsim` → `"ok": true`

---

## Verdict

| Gate | Result |
|------|--------|
| I4 implementation (Ask, planner, context, thin UX, harness) | **COMPLETE** |
| Desktop `prove-ask` | **PASS** |
| P1-runtime final `prove-ask --flightsim` | **PASS** (`ok: true`) |
| Immich on media-server (FlightSim) | **PASS** (`immich` / pong; opaque photo ask `photos=24`) |
| I4-G Immich-unavailable + communications continue | **PASS** |

**Increment 4 is ACCEPTED.**  
**Do not begin Increment 5** or any later increment without explicit authorization.

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
| **I4-I** | PASS | Health increment=4; no host hardcodes in product `.py` |
| **I4-J** | PASS | Living specs + this report |
| **I4-K** | PASS | Generalized Ask; unseen entity variation |
| **Intent-oriented visual** | PASS | `visual_scope` broad / still_only / video_only contract |

No family message bodies, photo binaries, or credentials are recorded here.

---

## FlightSim final (opaque)

| Field | Value |
|-------|-------|
| Date | 2026-08-09 |
| Command | `python -m memorybox prove-ask --flightsim` |
| Result | `"ok": true` |
| Immich | `provider_key=immich`, `ok=true`, `detail=pong` |
| Evidence rows | 13 |
| Indexed (rebuild) | 13 |
| Photo ask (opaque) | `kind=evidence_backed`, `photos=24` |
| Problems | none |

---

## What shipped

| Area | Location |
|------|----------|
| Session context contract | `memorybox/context/` |
| Query Planner v0 + visual_scope | `memorybox/planner/` |
| Orchestrator + retrieval | `memorybox/ask/` |
| In-package Immich HTTP client | `memorybox/providers/photo/_immich_http.py` |
| Thin Ask UX | `GET /ask/ui` |
| CLI | `ask`, `prove-ask`, `prove-ask --flightsim` |
| FlightSim runbook | [FLIGHTSIM_I4_ACCEPTANCE_RUNBOOK.md](../ops/FLIGHTSIM_I4_ACCEPTANCE_RUNBOOK.md) |

---

## Stop

- Increment 4 **ACCEPTED**.  
- **Do not** start Increment 5, Story, Journal, SMS ingest, Guided Capture, Review & Learn, Person teach/merge, video/HVRT, or visual polish without explicit authorization.
