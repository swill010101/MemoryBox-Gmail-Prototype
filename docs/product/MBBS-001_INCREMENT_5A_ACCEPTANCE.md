# MBBS-001 Increment 5A — Acceptance (desktop harness green; FlightSim owner gate open)

**Status:** Desktop prove **PASS** · Owner FlightSim gate **OPEN** (I5A-OWNER)  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_5A_DEFINITION.md](MBBS-001_INCREMENT_5A_DEFINITION.md)

## Owner gate (required for FlightSim accept)

Tom can open the FlightSim Journal client, create **one typed** and **one spoken** entry without developer intervention, save both, and subsequently retrieve them through MemoryBox Ask.

## Desktop harness

```text
python -m memorybox migrate
python -m memorybox prove-journal
# ok: true (I5A-A…P synthetic; opaque ids only)
python -m memorybox prove-story   # remains green under increment 5A health
python -m memorybox health        # increment=5A, journal_versions present
```

## Shipped surface

| Surface | Path |
|---------|------|
| Journal UI | `/journal/ui` |
| Capture/STT draft | `POST /capture/transcribe` (no Journal persist) |
| Journal API | `POST/GET /journal`, versions |
| Ask Journal | `want_journal` + Journal attribution; intent → `/journal/ui` |
| Prove | `python -m memorybox prove-journal [--flightsim]` |

## FlightSim owner prove (after UX saves)

```powershell
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I5A_OWNER_TYPED_JOURNAL_ID = "<typed-uuid>"
$env:MEMORYBOX_I5A_OWNER_VOICE_JOURNAL_ID = "<spoken-uuid>"
python -m memorybox prove-journal --flightsim
```

STT: install `faster-whisper` (or set `MEMORYBOX_WHISPER_ENDPOINT`) and `pip install python-multipart`. Prefer `MEMORYBOX_STT_PROVIDER=faster_whisper` on FlightSim when Whisper is local.

## Stop

Do not start Guided Capture / Increment 6 without authorization.
