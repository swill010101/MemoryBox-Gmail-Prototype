# MemoryBox Demonstrator (MBD-001)

Approved PRD: [docs/product/MBD-001_MEMORYBOX_DEMONSTRATOR_PRD.md](../docs/product/MBD-001_MEMORYBOX_DEMONSTRATOR_PRD.md)

## Run (Media-Server)

```powershell
cd C:\memorybox
# Prefer project venv
.\hvrt\.venv\Scripts\Activate.ps1   # or a dedicated .venv
pip install -r application/requirements.txt

# Terminal A — HVRT Review (existing POC)
cd hvrt
python scripts\review_app.py
# http://127.0.0.1:8788

# Terminal B — Demonstrator shell
cd C:\memorybox
python scripts\run_demonstrator.py
# http://127.0.0.1:8780
```

Tailscale: open `http://<media-server-tailscale-ip>:8780` (Tom only).

## Consoles

| Nav | Role |
|-----|------|
| **Ask** | Search POC archives; open evidence cards → **Tell me more** |
| **Review** | Full HVRT tools **embedded** (box face, enroll, spoken text, Learn) — no second process required |
| **People** | Select a person → face hits → Open in Review |

Teach stays hidden until you open evidence and choose to add a note.

## POC databases

Defaults (override with env):

| DB | Default path |
|----|----------------|
| Email/SMS/calendar/photos cache | `database/memorybox.db` |
| HVRT faces/transcripts | `hvrt/database/hvrt.sqlite` |
| Versioned teach memories | `database/mbd_demonstrator.sqlite` |

On Media-Server / Desktop these should already exist from the two POCs. If Ask says databases not found, set:

```powershell
$env:MBD_MEMORYBOX_DB="C:\memorybox\database\memorybox.db"
$env:MBD_HVRT_DB="C:\memorybox\hvrt\database\hvrt.sqlite"
```

Immich: copy `config/immich.env.example` → `config/immich.env` and fill key/URL.
