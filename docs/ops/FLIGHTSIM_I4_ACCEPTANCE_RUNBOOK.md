# FlightSim Increment 4 acceptance runbook

**Status:** Operational · **Date:** 2026-08-09  
**Scope:** Final I4 acceptance on P1 runtime host only.  
**Not in scope:** Increment 5+, Story, Journal, SMS, Review, visual polish.

## Prerequisites

1. I4 code present on the P1 runtime host (`git pull` after push from desktop).  
2. PostgreSQL + Qdrant + Ollama configured via env (no `MEMORYBOX_ALLOW_DEV_DEFAULTS`).  
3. `config/immich.env` on the host pointing at media-server Immich (gitignored).  
4. Existing PG email/calendar Evidence (from I3 checkpoint) preferred.

## Commands (on P1 runtime host console)

```powershell
cd <repo-root>
# load MEMORYBOX_* from your gitignored env file
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
powershell -ExecutionPolicy Bypass -File scripts\flightsim_accept_i4.ps1
```

Manual:

```powershell
python -m memorybox migrate
python -m memorybox health
python -m memorybox prove-ask --flightsim
```

Expect `"ok": true` with `i4_flightsim_runtime_gate`, Immich required, photo ask, and I4-G degradation checks.

## I4-G note

`prove-ask` exercises Immich-unavailable via `UnavailablePhotoProvider` in-harness (does not take Immich offline for the family). Live Immich is still required for the photo acceptance path.

## After PASS

Paste opaque JSON (`ok`, check names, counts/IDs only) into the Increment 4 acceptance report FlightSim section. Do not paste family content.
