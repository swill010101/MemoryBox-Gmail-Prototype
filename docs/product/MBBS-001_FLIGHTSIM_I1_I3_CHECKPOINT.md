# FlightSim I1–I3 deployment checkpoint report

**Date:** 2026-08-09  
**Status:** **PASSED**  
**Type:** Deployment / validation checkpoint (not a product increment)  
**Host:** P1 runtime (FlightSim) under user `tomwi`  
**Code:** `cursor/marvin-capture-v01-3344` (includes Ollama embed fix `aec0913` + synthetic mbox fixture `2b55f8f`)  
**Runbook:** [FLIGHTSIM_I1_I3_DEPLOYMENT_RUNBOOK.md](../ops/FLIGHTSIM_I1_I3_DEPLOYMENT_RUNBOOK.md)

---

## Verdict

**FlightSim deployment + synthetic proves + real email/calendar smoke: PASSED.**  
Qdrant used as **network** derived index (`allow_dev_defaults: false`).  
**Increment 4 not started.**

---

## Runtime stack (FlightSim)

| Component | How it ran |
|-----------|------------|
| Git | Branch checked out on FlightSim |
| Python | 3.12.10 for user `tomwi` |
| PostgreSQL | Docker `memorybox-pg` on host port 5432 |
| Qdrant | Docker `memorybox-qdrant` on host port 6333 |
| Ollama | Installed for `tomwi`; embed path fixed / fallback available |
| Media-server | Not used; media libraries not moved |

---

## Proves

| Gate | Result |
|------|--------|
| Synthetic email + calendar ingest / payload / originals | **PASS** |
| Real email smoke (limit 5) | **PASS** — inserted 5; Evidence IDs recorded (no bodies in report) |
| Real calendar smoke (limit 5) | **PASS** — inserted 5; Evidence IDs recorded (no event text in report) |
| I3-D clear + rebuild + retrieval | **PASS** — `rebuild_indexed: 13` |
| I3-C / I3-E / I3-F / I3-G | **PASS** |
| Overall `prove-ingest` | **`"ok": true`** |

### Safe operational evidence (IDs / counts only)

- Synthetic email Evidence: `7f769f8a-09c2-4bc1-a0b8-14517fb9149a`  
- Synthetic calendar Evidence: `4c6ab75e-…`, `ec1b5904-…`  
- Real email smoke: 5 Evidence IDs (see operator console JSON)  
- Real calendar smoke: 5 Evidence IDs (see operator console JSON)  
- Config: `qdrant_url_scheme=network`, `allow_dev_defaults=false`, smoke URIs configured  

No real family message/event content is reproduced in this document.

---

## Issues discovered during deploy (resolved or noted)

| Issue | Resolution |
|-------|------------|
| Agent remoting from desktop (SMB/WinRM/SSH) | Deploy ran **on FlightSim console** instead |
| Docker engine not running initially | Started Docker Desktop |
| No Postgres service | Docker `postgres:16` |
| No Qdrant | Docker `qdrant/qdrant` |
| No real Python (Store stubs only) | `winget` Python 3.12.10 for `tomwi` |
| Synthetic `.mbox` missing from Git | Allowlisted fixture; commit `2b55f8f` |
| Ollama embed HTTP 404 | `/api/embed` + `/api/embeddings` + Fake fallback; commit `aec0913` |

---

## Stop

Checkpoint **complete**. Do **not** begin Increment 4 / Ask / UX / SMS / photo / Story / Journal without explicit authorization.
