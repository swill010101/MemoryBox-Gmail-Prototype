# FlightSim Increment 4 acceptance runbook

**Status:** Operational · **Date:** 2026-08-09  
**Scope:** Final I4 acceptance on P1 runtime host only.  
**Not in scope:** Increment 5+, Story, Journal, SMS, Review, visual polish.

## Prerequisites

1. I4 code present on the P1 runtime host (`git pull` after push from desktop).  
2. PostgreSQL + Qdrant + Ollama configured via env (no `MEMORYBOX_ALLOW_DEV_DEFAULTS`).  
3. **Immich required for final prove:**
   - `config/immich.env` on the host (gitignored) **or** `MEMORYBOX_IMMICH_ENV` pointing to it  
   - `IMMICH_BASE_URL` + `IMMICH_API_KEY` set (media-server Immich)  
   - Immich client is **in-package** (`memorybox.providers.photo`) — no `application/api` dependency  
   - Do **not** leave `MEMORYBOX_PHOTO_PROVIDER=unavailable` set for final acceptance  
   - Prefer unset or `MEMORYBOX_PHOTO_PROVIDER=immich`  
4. Existing PG email/calendar Evidence (from I3 checkpoint) preferred.

### Quick Immich check (before prove)

```powershell
# Should NOT print "unavailable"
$env:MEMORYBOX_PHOTO_PROVIDER  # blank or immich
Test-Path .\config\immich.env
Get-Content .\config\immich.env
```

`config/immich.env` must look like this (two lines minimum; **no** spaces around `=`; URL must include `http://` or `https://`):

```text
IMMICH_BASE_URL=http://MEDIA_HOST:2283/api
IMMICH_API_KEY=your_real_api_key_here
```

Bad (causes the `immich_base_url=http` error):

```text
IMMICH_BASE_URL=immich_base_url=http://...
IMMICH_BASE_URL = http://...
```

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
