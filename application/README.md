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
| **Ask** | Conversation front door (proxies Desktop Ask API when configured; local memories always searchable) |
| **Review** | HVRT teach/learn (iframe → `:8788` until fully mounted) |
| **Library** | Timeline/browse across local memories (+ Ask evidence when wired) |

## Teach loop (shipped in shell)

- **Archive Updated** — quiet toast after save/edit
- **Edit Memory** — edit transcript/story text → **new version** → latest is searchable (audio re-record deferred)

## Import still needed

Email/text Ask tree from Desktop (`application/api` historian) is not in git yet. Set `MBD_ASK_ORIGIN` when that service is up to proxy `/api/ask`. Until then Ask searches **versioned local memories**.
