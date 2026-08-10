# MBBS-001 Increment 7 — Acceptance

**Status:** **BUILD SHIPPED — AWAITING FLIGHTSIM OWNER + BOOTSTRAP GATE**  
**Date:** 2026-08-10  
**Definition:** [MBBS-001_INCREMENT_7_DEFINITION.md](MBBS-001_INCREMENT_7_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 7

Do **not** mark I7 **ACCEPTED** until **I7-BOOTSTRAP** (harness) and **I7-OWNER** (FlightSim) both pass.

## Owner gate (I7-OWNER + I7-BOOTSTRAP) — PENDING

On FlightSim, Tom uses `/review/ui` without developer intervention / SQL / API patching:

1. Choose a real family person who is **already named in Immich** and **not** yet manually created/confirmed in MemoryBox `/people/ui`
2. Refresh videos from configured media-server family-video path
3. Open/play/scrub **≥1 real family video**
4. Create face candidate at playhead (rubber-band box) → Teach / Confirm as that Immich name via I6 (lazy Person seed allowed)
5. Confirm MB Person materialized/reused; Immich + HVRT identities map to the **same** `people.id` (Immich UUID is **not** the Person PK)
6. Ask for videos of that person → person-linked segment
7. Provenance: Immich mapping remains **trusted-provider** origin unless Tom explicitly owner-confirms that Person identity as such

Second real family person is **not** required (harness covers second-person + bootstrap edge cases).

| Item | Opaque id |
|------|-----------|
| Owner taught Person (bootstrap) | *(set after UX)* |

```powershell
cd C:\memorybox
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I7_OWNER_PERSON_ID = "<opaque-person-uuid>"
# optional alias if different from owner:
# $env:MEMORYBOX_I7_BOOTSTRAP_PERSON_ID = "<same-or-other-uuid>"
python -m memorybox prove-video --flightsim
```

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
| Env | `MEMORYBOX_VIDEO_WORKER_URL`, `MEMORYBOX_VIDEO_MEDIA_ROOT`, `MEMORYBOX_VIDEO_PRESENCE_GAP_SEC` |
| Bootstrap | I6 `resolve_or_seed_trusted_provider_person` / `teach_provider_person(photo=…)` — no HVRT-side Person mint |

Laughing/speech-emotion: **deferred** (not required for I7).

## Stop

Do **not** begin Increment 8 / EVS-014 / Guided Capture without explicit authorization.
