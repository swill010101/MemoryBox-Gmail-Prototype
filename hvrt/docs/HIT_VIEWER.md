# HVRT Hit Viewer

Light local UI to select face/transcript hits and play the video at that timestamp.

Browsers cannot reliably open `file://` links from an `http://` page, so this viewer streams each original file **read-only** over HTTP and seeks to `start_sec`.

## Run (on Toms-Desktop)

```powershell
cd C:\memorybox\hvrt

# If these files are new from git, copy them into your existing hvrt tree:
#   scripts\hit_viewer.py
#   hvrt\static\viewer.html

.\.venv\Scripts\Activate.ps1
python scripts\hit_viewer.py
```

Open **http://127.0.0.1:8788**

1. Mode: **Faces** (or Spoken text)
2. Pick **Rick George** / **Peggy George**
3. Click a hit — the player jumps to that moment
4. Optional: **Copy VLC command** for external playback

Port `8788` by default so it can run beside `run_api.py` on `8787`.
