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
| **Ask** | Searches **memorybox.db** + **hvrt.sqlite** (+ Immich when configured) |
| **Review** | HVRT teach/learn (iframe → `:8788`) |
| **Library** | Timeline/browse across POC archives + versioned memories |

Teach stays **hidden** until you select evidence and click **Teach about this**.

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
