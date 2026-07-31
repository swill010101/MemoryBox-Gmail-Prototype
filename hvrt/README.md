# HVRT

Local **video evidence** producer + **R2 review console** (POC toward Memory Box’s teach-as-you-explore loop).

## R2 Review App

Pull/copy R2 into the local tree, then run:

```powershell
cd C:\memorybox
git fetch origin cursor/hvrt-hit-viewer-13aa
git checkout cursor/hvrt-hit-viewer-13aa -- hvrt

cd hvrt
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\review_app.py
# http://127.0.0.1:8788
```

If git checkout is blocked by local changes, download instead:

```powershell
cd C:\memorybox\hvrt
New-Item -ItemType Directory -Force -Path scripts, hvrt\static, hvrt | Out-Null
$base = "https://raw.githubusercontent.com/swill010101/MemoryBox-Gmail-Prototype/cursor/hvrt-hit-viewer-13aa/hvrt"
Invoke-WebRequest "$base/scripts/review_app.py" -OutFile "scripts\review_app.py"
Invoke-WebRequest "$base/hvrt/__init__.py" -OutFile "hvrt\__init__.py"
Invoke-WebRequest "$base/hvrt/schema_r2.py" -OutFile "hvrt\schema_r2.py"
Invoke-WebRequest "$base/hvrt/annotations.py" -OutFile "hvrt\annotations.py"
Invoke-WebRequest "$base/hvrt/rescoring.py" -OutFile "hvrt\rescoring.py"
Invoke-WebRequest "$base/hvrt/learning.py" -OutFile "hvrt\learning.py"
Invoke-WebRequest "$base/hvrt/static/review.html" -OutFile "hvrt\static\review.html"
Invoke-WebRequest "$base/requirements.txt" -OutFile "requirements.txt"
python scripts\review_app.py
```

- Mark **places** (spans + optional GPS pin); exemplars saved; **no** place recognition engine  
- **Box face** → enroll to existing person (dropdown) or new (dup-safe)  
- **Voice span** enroll, **OCR** confirm, **Set date**  
- **Learn from annotations** = background job + progress panel  
- **Setting (future)** disabled  
- Rescoring: Owner > User > AI; human confirm = 1.0  

Docs: [docs/HVRT_R2_PRD.md](docs/HVRT_R2_PRD.md) · R3 voice notes: [docs/ROADMAP_R3_VOICE_NOTES.md](docs/ROADMAP_R3_VOICE_NOTES.md)

## Add a new / older video to the POC sample

**Learn from annotations** does **not** ingest new video files. It only updates galleries from human marks.

### From the review UI (preferred)

1. Keep `python scripts\review_app.py` running on **8788**
2. Click **Add & process videos**
3. Multi-select files (local disk or a mapped share like `P:` — the browser uploads them to the local app)
4. Files land in `sample\`, then `scripts\process_videos.py` runs in the background with an in-page progress panel
5. When status is done, click **Load hits**

Requires your Desktop `scripts\process_videos.py` (the Phase 1 pipeline). Do not stop the review app while it runs.

### CLI (same pipeline)

```powershell
cd C:\memorybox\hvrt
# copy files into sample\ first, then:
.\.venv\Scripts\Activate.ps1
python scripts\process_videos.py
```

Optional second-window DB watcher:

```powershell
python scripts\process_status.py
```

Older clips with no GPS/date still get metadata rows (`file_mtime`, duration, etc.). Place/date for those come from review markup later.

