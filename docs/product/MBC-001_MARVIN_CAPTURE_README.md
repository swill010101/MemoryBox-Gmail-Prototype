# Marvin Capture (MBC-001)

Proof-of-concept email capture loop for MemoryBox.

**Immutable principle:** Marvin Capture must never lose information in an attempt to be intelligent. The original email, attachments, and reply are the authoritative record.

## Plus-address capture (MBC-004)

Inbound mail is routed by **Gmail plus-address**, not subject tags. After verified capture, Marvin moves that Gmail message to **Trash** (single message, not the whole thread).

| Address | Destination |
|---------|-------------|
| `you+journal@…` | Journal (JRN) — compose or reply |
| `you+jrn@…` | Journal (JRN) — same |
| `you+MEM@…` | Memory bank answers — **reply only** to Marvin's MEM question |

(`you` = local-part of `gmail.user_email` in config.)

- Mail with only old `[MB-…]` subject and **no** accepted plus-address → **unmatched** (not captured).  
- MEM questions are sent to plain `you@…` with `Reply-To: you+MEM@…`.  
- EVS (MBC-003) is **retired** — see `MBC-004_PLUS_ADDRESS_TRASH_RETIRE_EVS_PRD.md`.

## MEM question bank (MBC-002)

1. Copy `config/mem_questions.example.json` → `config/mem_questions.json` and fill `1…N`
2. In `config/marvin_capture.json` set `mem_bank.enabled: true`, `hour: 1`, `to: swill01@gmail.com`, and `schedule.daily_journal.enabled: false`
3. Restart via deploy script — M–F at 01:00 sends next unsent; unanswered resent after 7 days
4. **Extract MEM** in the review UI writes `exports/mem_bank/mem_batch_…/` (combined + per-Q files + attachments)

See `docs/product/MBC-002_MEM_QUESTION_BANK_PRD.md`.

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
