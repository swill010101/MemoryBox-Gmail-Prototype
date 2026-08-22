# MBBS-001 Increment 8 — Acceptance

**Status:** **ACCEPTED** (FlightSim owner gate)  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_8_DEFINITION.md](MBBS-001_INCREMENT_8_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 8

## Owner gate (I8-OWNER) — PASSED

Tom on FlightSim used `/library/ui` without developer intervention / SQL:

1. Selected an MB Person (required I6 filter)
2. Timeline-first browse (Gallery = same-API alternate)
3. Confirmed multi-modality browse (visual + narrative/comms + other as applicable)
4. Opened card detail — provenance / date basis / people / trust; video Open in Review when available
5. Undated bucket does not invent dates (video segments undated by design)
6. Visual cards show proxied thumbnails/posters sufficient for recognition

| Item | Note |
|------|------|
| Owner Person filter | Eugene Will / Diane Scollay / others exercised on FlightSim |
| Surface | `http://flightsim:8790/library/ui` |

```powershell
cd C:\memorybox
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I8_OWNER_PERSON_ID = "<opaque-person-uuid>"
python -m memorybox prove-library --flightsim
```

## Harness

```text
python -m memorybox prove-library
# ok: true — unified modalities, person filter, date/undated, journal I5A,
#            pagination, Open in Review link, photo/video thumb URLs,
#            provider-down degrade, health=8
```

## Shipped surface

| Surface | Path |
|---------|------|
| Library UI | `/library/ui` |
| Cards API | `GET /library/cards?person_id=&bucket=timeline\|undated\|all` |
| Media proxies | `GET /library/media/photo/{id}`, `GET /library/media/video-poster` |
| Prove | `prove-library [--flightsim]` |

## Lessons carried forward

- Narrator ≠ About subject (Story→Library).  
- Video segments are **Undated** (use Bucket Undated/All).  
- Browser must not call Immich thumb URLs directly (API key) — use MB proxies.

## Stop

Do **not** begin Increment 9 / 10 / Guided Capture / Export without explicit authorization.  
Next definition (review only): [MBBS-001_INCREMENT_9_DEFINITION.md](MBBS-001_INCREMENT_9_DEFINITION.md).
