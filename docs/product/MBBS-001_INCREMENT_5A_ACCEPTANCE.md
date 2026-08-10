# MBBS-001 Increment 5A — Acceptance

**Status:** **ACCEPTED** (FlightSim owner gate + `prove-journal --flightsim`)  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_5A_DEFINITION.md](MBBS-001_INCREMENT_5A_DEFINITION.md)

## Owner gate (I5A-OWNER) — PASSED

Tom opened the FlightSim Journal client, created **one typed** and **one spoken** entry without developer intervention, saved both, and retrieved them through MemoryBox Ask.

| Item | Opaque id |
|------|-----------|
| Owner typed Journal | `248fc736-faff-46e7-9bba-b98226594202` |
| Owner voice Journal | `0416280d-a3f9-465b-aeec-80206d5c9b55` |

Voice path: browser mic device picker → Record → STT draft → review → explicit Save (`channel=voice` + `audio_uri`).

## FlightSim prove

```text
python -m memorybox prove-journal --flightsim
# ok: true
# i5a_j_owner_typed / i5a_j_owner_voice / i5a_owner_ask_retrieve green
# MEMORYBOX_P1_RUNTIME_HOST=1
```

## Shipped surface

| Surface | Path |
|---------|------|
| Journal UI | `/journal/ui` (mic picker + live level) |
| Capture/STT | `POST /capture/transcribe` (Whisper behind provider) |
| Journal API | `/journal` + versions |
| Ask Journal | direct PG + Journal attribution; intent → capture |
| Prove | `prove-journal [--flightsim]` |

## Stop

Do **not** begin Guided Capture / EF-11 / Increment 7 without explicit authorization. Increment 6 is separately authorized.
