# MBBS-001 Increment 4 — Acceptance Report

**Status:** **BUILT — DESKTOP PROVE PASS; P1-RUNTIME FINAL PENDING**  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_4_DEFINITION.md](MBBS-001_INCREMENT_4_DEFINITION.md) (locked scope)  
**Authorization:** Build Increment 4 only  
**Host note:** Desktop prove ran on `Toms-Desktop`. Final acceptance requires the P1 runtime host (FlightSim) per locked definition. Agent remoting to FlightSim (SMB auth / SSH) is unavailable from this workstation — same constraint as the I1–I3 checkpoint.

---

## Verdict

| Gate | Result |
|------|--------|
| I4 implementation (Ask, planner, context, thin UX, harness) | **COMPLETE** |
| Desktop `python -m memorybox prove-ask` (I4-A…K structural + Immich-unavailable + generalized Ask) | **PASS** (`ok: true`) |
| Immich photo path (media-server Immich reachable from desktop; opaque counts only) | **Exercised** — 24 photo hits on generic “Show me pictures” (not a substitute for FlightSim final) |
| P1-runtime final `prove-ask --flightsim` with `MEMORYBOX_P1_RUNTIME_HOST=1` | **PENDING** — run [FLIGHTSIM_I4_ACCEPTANCE_RUNBOOK.md](../ops/FLIGHTSIM_I4_ACCEPTANCE_RUNBOOK.md) on FlightSim console |

**Increment 4 is not fully ACCEPTED until FlightSim final prove returns `ok: true`.**  
**Do not begin Increment 5** or any later increment.

---

## Criteria map (desktop prove)

| ID | Result | Opaque detail |
|----|--------|---------------|
| **I4-A** | PASS | Evidence-backed ask; citations present |
| **I4-B** | PASS | Insufficient disclosure on unsupported ask |
| **I4-C** | PASS | EVS-005/006 shaped asks executed; no inventing |
| **I4-D** | PASS | EF-02 follow-ups with inherited context |
| **I4-E** | PASS | Clear / change context; no stale leak |
| **I4-F** | PASS | Breadcrumb + thin Ask UX shell (`/ask/ui`) |
| **I4-G** | PASS | Photo provider unavailable surfaced; communications Ask still cited Evidence |
| **I4-H** | PASS | No false memories / inventing gate |
| **I4-I** | PASS | Health increment=4; no host hardcodes in product `.py` |
| **I4-J** | PASS | Definition + this report + decision log |
| **I4-K** | PASS | Cascadia/Jordan + Rivermark/Sam unseen variation; no Peggy/Florida hardcoding in planner |
| **Intent-oriented visual** | PASS | Broad pictures/images/show-me-person → `visual_scope=broad` (stills+video intent); photos → still_only; videos → video_only; emails → not visual. No HVRT/video provider in I4 |

No family message bodies, photo binaries, or credentials are recorded here.

---

## What shipped

| Area | Location |
|------|----------|
| Session context contract (in-memory; persistable later) | `memorybox/context/` |
| Query Planner v0 (generalized) | `memorybox/planner/` |
| Orchestrator + retrieval (PG/Qdrant/Photo) | `memorybox/ask/` |
| Thin Ask UX | `memorybox/ask/static/ask.html` → `GET /ask/ui` |
| API | `POST /ask`, context GET/PATCH/DELETE |
| CLI | `python -m memorybox ask "…"`, `prove-ask`, `prove-ask --flightsim` |
| FlightSim operator script | `scripts/flightsim_accept_i4.ps1` |

---

## Operator action to finish acceptance

On **FlightSim console** (after `git pull` of this I4 code):

```powershell
# load MEMORYBOX_* env (no ALLOW_DEV_DEFAULTS)
powershell -ExecutionPolicy Bypass -File scripts\flightsim_accept_i4.ps1
```

Paste opaque `"ok": true` JSON into § FlightSim final below, then flip status to **ACCEPTED**.

### FlightSim final (fill after prove)

| Field | Value |
|-------|-------|
| Date/time | _pending_ |
| `prove-ask --flightsim` | _pending_ |
| Immich ok | _pending_ |
| Evidence row count | _pending_ |
| Photo hit count (opaque) | _pending_ |

---

## Stop

- Increment 4 **build complete**; **final acceptance pending FlightSim**.  
- **Do not** start Increment 5, Story, Journal, SMS ingest, Guided Capture, Review & Learn, Person teach/merge, or visual polish without explicit authorization.
