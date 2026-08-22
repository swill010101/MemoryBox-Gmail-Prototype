# MBBS-001 Increment 7 — Acceptance

**Status:** **ACCEPTED** (FlightSim owner + trusted-provider bootstrap gate)  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_7_DEFINITION.md](MBBS-001_INCREMENT_7_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 7

## Owner gate (I7-OWNER + I7-BOOTSTRAP) — PASSED

Tom on FlightSim used `/review/ui` without developer intervention / SQL / API patching:

1. Enrolled a video face for an Immich-named person **not** previously created in MemoryBox `/people/ui` (**Diane Scollay**)
2. Trusted-provider bootstrap materialized/reused the canonical MB Person via I6
3. Ask **“show videos of Diane Scollay”** → **2** person-linked video hits

| Item | Opaque id |
|------|-----------|
| Owner taught Person (Diane Scollay) | *(FlightSim PG — display name confirmed; UUID not required for gate)* |
| Media root | `\\media-server\photos\home videos` |

## Harness

```text
python -m memorybox prove-video
# ok: true — provider, span-merge, worker-down, teach, Ask, identity-survival,
#            second-person, trusted-provider bootstrap (seed/reuse/Ask/correction/no silent merge)
```

## Shipped surface

| Surface | Path |
|---------|------|
| Review UI | `/review/ui` |
| Video worker | `python -m memorybox.video_worker` |
| Prove | `prove-video [--flightsim]` |
| Env | `MEMORYBOX_VIDEO_WORKER_URL`, `MEMORYBOX_VIDEO_MEDIA_ROOT` (`\\media-server\photos\home videos`), `MEMORYBOX_VIDEO_PRESENCE_GAP_SEC` |
| Bootstrap | I6 `resolve_or_seed_trusted_provider_person` / `teach_provider_person(photo=…)` — no HVRT-side Person mint |

Laughing/speech-emotion: **deferred** (not required for I7).

## Stop

Do **not** begin Increment 8 / EVS-014 / Guided Capture / Gallery without explicit authorization.
