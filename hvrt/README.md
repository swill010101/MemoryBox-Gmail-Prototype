# HVRT

Local **video evidence** producer + **R2 review console** (POC toward Memory Box’s teach-as-you-explore loop).

## R2 Review App (build this)

```powershell
cd C:\memorybox\hvrt
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\review_app.py
# http://127.0.0.1:8788
```

- Mark **places** (spans + optional GPS pin); exemplars saved; **no** place recognition engine  
- **Box face** → enroll to existing person (dropdown) or new (dup-safe)  
- **Voice span** enroll, **OCR** confirm, **Set date**  
- **Learn from annotations** = background job + progress panel  
- **Setting (future)** disabled  
- Rescoring: Owner > User > AI; human confirm = 1.0  

Docs: [docs/HVRT_R2_PRD.md](docs/HVRT_R2_PRD.md) · R3 voice notes: [docs/ROADMAP_R3_VOICE_NOTES.md](docs/ROADMAP_R3_VOICE_NOTES.md)

## Legacy hit viewer

`python scripts\hit_viewer.py` still works for simple hit playback.
