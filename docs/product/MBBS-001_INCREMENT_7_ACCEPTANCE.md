# MBBS-001 Increment 7 — Acceptance

**Status:** **BUILD SHIPPED — AWAITING FLIGHTSIM OWNER GATE**  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_7_DEFINITION.md](MBBS-001_INCREMENT_7_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 7

## Owner gate (I7-OWNER) — PENDING

On FlightSim, Tom uses `/review/ui` without developer intervention to:

1. Refresh videos from configured media-server family-video path  
2. Open/play/scrub **≥1 real family video**  
3. Create face candidate at playhead → Teach / Confirm via I6  
4. Ask for videos of that MB Person → person-linked segment with `identity_trust=confirmed`

Second real family person is **not** required (harness covers second-person).

| Item | Opaque id |
|------|-----------|
| Owner taught Person | *(set after UX)* |

```powershell
cd C:\memorybox
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I7_OWNER_PERSON_ID = "<opaque-person-uuid>"
python -m memorybox prove-video --flightsim
```

## Harness

```text
python -m memorybox prove-video
# ok: true — provider, span-merge, worker-down degrade, teach, Ask, identity-survival, second-person
```

## Shipped surface

| Surface | Path |
|---------|------|
| Review UI | `/review/ui` |
| Video worker | `python -m memorybox.video_worker` |
| Prove | `prove-video [--flightsim]` |
| Env | `MEMORYBOX_VIDEO_WORKER_URL`, `MEMORYBOX_VIDEO_MEDIA_ROOT`, `MEMORYBOX_VIDEO_PRESENCE_GAP_SEC` |

Laughing/speech-emotion: **deferred** (not required for I7).

## Stop

Do **not** begin Increment 8 / EVS-014 / Guided Capture without explicit authorization.
