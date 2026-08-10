# MBBS-001 Increment 8 — Acceptance

**Status:** **BUILD SHIPPED — AWAITING FLIGHTSIM OWNER GATE**  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_8_DEFINITION.md](MBBS-001_INCREMENT_8_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 8

## Owner gate (I8-OWNER) — PENDING

On FlightSim, Tom uses `/library/ui` without developer intervention / SQL:

1. Select an MB Person (required filter — I6)
2. Timeline-first browse (optional Gallery view = same cards)
3. Confirm **≥3** modalities with mix: ≥1 visual (photo|video) + ≥1 narrative/comms (email|Story|Journal) + ≥1 other distinct
4. Open card detail — see date provenance / trust / Open in Review for video when available
5. Confirm Undated bucket does not invent dates

| Item | Opaque id |
|------|-----------|
| Owner Person filter | *(set after UX)* |

```powershell
cd C:\memorybox
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I8_OWNER_PERSON_ID = "<opaque-person-uuid>"
python -m memorybox prove-library --flightsim
```

Tip: Diane Scollay (I7 bootstrap) may work if photo/video mappings exist and at least one Story/Journal/email modality is also associated.

## Harness

```text
python -m memorybox prove-library
# ok: true — unified modalities, person filter, date/undated, journal I5A,
#            pagination, Open in Review link, provider-down degrade, health=8
```

## Shipped surface

| Surface | Path |
|---------|------|
| Library UI | `/library/ui` |
| Cards API | `GET /library/cards?person_id=&bucket=timeline\|undated\|all` |
| Prove | `prove-library [--flightsim]` |

## Stop

Do **not** begin Increment 9 / 10 / Guided Capture / Export without explicit authorization.
