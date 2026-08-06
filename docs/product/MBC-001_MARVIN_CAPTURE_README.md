# Marvin Capture (MBC-001)

Proof-of-concept email capture loop for MemoryBox.

**Immutable principle:** Marvin Capture must never lose information in an attempt to be intelligent. The original email, attachments, and reply are the authoritative record.

## What it does

1. Sends scheduled / ad-hoc prompts with subject tags like `[MB-JRN-20260806]`
2. Polls Gmail for replies
3. Preserves raw `.eml` + every attachment byte-for-byte
4. Extracts only Tom’s newly written text (additive)
5. Queues audio for Whisper transcription (audio retained)
6. Labels messages `MB/Processed`
7. Serves a local Inbox / Reviewed page

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r application/marvin_capture/requirements.txt
cp config/marvin_capture.example.json config/marvin_capture.json
# Edit user_email, paths, whisper endpoint
```

Place Gmail OAuth **Desktop** client JSON at `config/gmail_credentials.json` (gitignored patterns apply to secrets; keep tokens off git).

## Run

```bash
# Review UI
python scripts/run_marvin_capture.py

# UI + background poll / daily journal worker
python scripts/run_marvin_capture.py --poll

# One-shot send / poll
python scripts/marvin_send_prompt.py --journal
python scripts/marvin_send_prompt.py --type MEM --token 000123 --headline "Grade school" --body "Tell me about your grade-school days."
python scripts/marvin_poll.py
```

Review UI: http://127.0.0.1:8790

## Tests (no Gmail required)

```bash
pip install pytest
pytest tests/ -q
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
