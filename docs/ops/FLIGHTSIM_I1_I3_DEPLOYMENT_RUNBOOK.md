# FlightSim deployment runbook — MemoryBox I1–I3 checkpoint

**Status:** Operational runbook · **Date:** 2026-08-09  
**Scope:** Deploy **accepted Increments 1–3 only** to the P1 runtime host; run health/acceptance proves; run **real** email + calendar smoke.  
**Not in scope:** Increment 4, Ask/UX, SMS, photo ingest, Story, Journal.  
**Topology (D7):** App + PostgreSQL + Qdrant + Ollama on **FlightSim**; Immich/Plex/media libraries stay on **media-server** (remote providers later — not required for this checkpoint).

---

## 1. Minimum procedure

| Step | Action |
|------|--------|
| 1 | On **dev box**: ensure I1–I3 accepted code is committed and pushed to GitHub |
| 2 | On **FlightSim**: `git pull` (or fresh clone) into the MemoryBox repo path |
| 3 | Install Python deps: `python -m pip install -r memorybox/requirements.txt` |
| 4 | Ensure **PostgreSQL** is running on FlightSim; create role/db `memorybox` (or use your chosen names) |
| 5 | Ensure **Qdrant** is running on FlightSim; note URL (e.g. `http://127.0.0.1:6333` **only as local host config value**, never baked into code) |
| 6 | Ensure **Ollama** is running on FlightSim; pull embed model used in config |
| 7 | Create a **gitignored** env file (e.g. `config/memorybox_app.env`) — see §2 |
| 8 | Confirm real **mbox** and **ICS** exist on FlightSim (archive LAN sync — see `docs/GIT_SYNC.md`). Prepare smoke slices if needed (§3) |
| 9 | Run `scripts/flightsim_checkpoint_i1_i3.ps1` on FlightSim |
| 10 | File the JSON prove outputs into the checkpoint report (IDs/counts only) |

---

## 2. Required environment variables (FlightSim)

Set in the shell or a gitignored env file **before** running the checkpoint. **Do not** set `MEMORYBOX_ALLOW_DEV_DEFAULTS=1` on FlightSim for this checkpoint.

| Variable | Purpose |
|----------|---------|
| `MEMORYBOX_DATABASE_URL` | PostgreSQL URL on this host |
| `MEMORYBOX_QDRANT_URL` | Qdrant HTTP URL on this host |
| `MEMORYBOX_QDRANT_COLLECTION` | Collection name (default `memorybox_evidence`) |
| `MEMORYBOX_OLLAMA_BASE_URL` | Ollama HTTP URL on this host (preferred) |
| `MEMORYBOX_OLLAMA_EMBED_MODEL` | Embed model name |
| `MEMORYBOX_OLLAMA_CHAT_MODEL` | Chat model name (I2 prove / future) |
| `MEMORYBOX_HOST` / `MEMORYBOX_PORT` | API bind (optional for checkpoint) |
| `MEMORYBOX_SMOKE_MBOX_URI` | Path to real mbox or `working/smoke/email_slice.mbox` |
| `MEMORYBOX_SMOKE_ICS_URI` | Path to real `.ics` under `working/smoke/calendar/…` |
| `MEMORYBOX_SMOKE_LIMIT` | Max messages/events for smoke (default `5`) |

Example template (placeholders only): see `config/memorybox_app.env.example`.

---

## 3. Real-data smoke inputs

Archive originals stay under `archive/` (LAN robocopy; **not** in Git). On FlightSim:

```powershell
cd <repo-root>
python scripts\prepare_smoke_slices.py `
  --mbox "<path-to-real-mbox-on-this-host>" `
  --mbox-limit 5 `
  --takeout-zip "<path-to-takeout-zip-with-Calendar-ics>"
```

Then set:

- `MEMORYBOX_SMOKE_MBOX_URI` → `working\smoke\email_slice.mbox`  
- `MEMORYBOX_SMOKE_ICS_URI` → one extracted `.ics` path under `working\smoke\calendar\`

**If either path is missing:** stop. Do **not** mark real-data smoke complete using synthetic fixtures.

---

## 4. Checkpoint commands (on FlightSim)

```powershell
cd <repo-root>
# load env vars first
powershell -ExecutionPolicy Bypass -File scripts\flightsim_checkpoint_i1_i3.ps1
```

Manual equivalents:

```powershell
python -m memorybox migrate
python -m memorybox health
python -m memorybox seed-synthetic
python -m memorybox prove-synthetic
python -m memorybox prove-providers
python -m memorybox prove-ingest
```

`prove-ingest` clears/rebuilds the configured Qdrant collection from PostgreSQL Evidence and runs the fixed retrieval check.

---

## 5. Git workflow

```powershell
# Dev box
cd C:\memorybox
git push -u origin <branch-with-i1-i3>

# FlightSim
cd <repo-root>
git fetch
git checkout <branch-with-i1-i3>
git pull
```

Secrets, `working/`, `archive/` binaries, databases, and caches remain **out of Git**.

---

## 6. Media-server

No action in this checkpoint. Do not copy Immich/Plex libraries to FlightSim.

---

## 7. Portability / ops notes

- Application logic must not hard-code hostnames, IPs, drive letters, or credentials (D7 / I3-G).  
- Dev-box `MEMORYBOX_ALLOW_DEV_DEFAULTS=1` is for local prove only.  
- If Qdrant/Ollama/Postgres are not listening on FlightSim, install/start them before the checkpoint script.  
- From the **dev box**, admin remoting (SSH/WinRM/SMB `C$`) may be unavailable; run the checkpoint **on FlightSim** interactively or after remoting is enabled.
