# Marvin Capture (MBC-001)

Proof-of-concept email capture loop for MemoryBox.

**Immutable principle:** Marvin Capture must never lose information in an attempt to be intelligent. The original email, attachments, and reply are the authoritative record.

## Subject keys (minimum)

```text
[MB-JRN] optional headline
[MB-MEM] optional headline
[MB-EVS] optional headline
```

No token/date in the subject is required. Send/receive timestamps are stored on each record. Legacy `[MB-JRN-YYYYMMDD]` still matches.

## EVS batch (review UI)

1. **Extract EVS…** — downloads all EVS responses as a `.txt` (you choose the filename)
2. **Remove all EVS** — deletes EVS rows and their linked files (after extract); JRN/MEM untouched

## Setup

Run these from the **repo root** (`C:\memorybox`), not from `C:\Users\tomwi`.

Until PR #11 is merged, check out the feature branch first:

```powershell
cd C:\memorybox
git fetch origin
git checkout cursor/marvin-capture-v01-3344
git pull origin cursor/marvin-capture-v01-3344

# Confirm you see the files:
dir application\marvin_capture\requirements.txt
dir scripts\run_marvin_capture.py
```

Then install and configure:

```powershell
cd C:\memorybox
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r application\marvin_capture\requirements.txt

Copy-Item config\marvin_capture.example.json config\marvin_capture.json
notepad config\marvin_capture.json
# Set gmail.user_email to your Gmail address
# Optionally adjust sqlite_path / attachment paths for Windows
```

Place Gmail OAuth **Desktop** client JSON at `config\gmail_credentials.json` (gitignored — keep tokens off git).

### Run

```powershell
cd C:\memorybox
.\.venv\Scripts\Activate.ps1

# Review UI only
python scripts\run_marvin_capture.py

# UI + background poll / daily journal worker
python scripts\run_marvin_capture.py --poll
```

Review UI: http://127.0.0.1:8790

### One-shot send / poll

```powershell
python scripts\marvin_send_prompt.py --journal
python scripts\marvin_send_prompt.py --type MEM --token 000123 --headline "Grade school" --body "Tell me about your grade-school days."
python scripts\marvin_poll.py
```

### Dry-run without Gmail

```powershell
python scripts\run_marvin_capture.py --fake
python scripts\marvin_send_prompt.py --journal --fake
```

## Linux / macOS setup

```bash
cd /path/to/MemoryBox-Gmail-Prototype   # must be repo root
git fetch origin && git checkout cursor/marvin-capture-v01-3344

python -m venv .venv
source .venv/bin/activate
pip install -r application/marvin_capture/requirements.txt
cp config/marvin_capture.example.json config/marvin_capture.json
# Edit user_email, paths, whisper endpoint
python scripts/run_marvin_capture.py --poll
```

## Tests (no Gmail required)

```powershell
pip install pytest
pytest tests -q
```

## Layout

| Path | Role |
|------|------|
| `docs/product/MBC-001_MARVIN_CAPTURE_PRD.md` | PRD |
| `application/marvin_capture/` | Library + FastAPI app |
| `config/marvin_capture.example.json` | Config template |
| `database/` | SQLite (gitignored) |
| `attachments/marvin_capture/` | Raw mail + attachments (gitignored) |

## Out of scope (v0.1)

MemoryBox ingestion, multi-user, summarization, knowledge graph, mobile, marvinbot.net hosting.
