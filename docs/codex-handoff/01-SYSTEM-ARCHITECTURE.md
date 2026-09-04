# System Architecture (Post I12)

## MemoryBox shape

MemoryBox is a **Python modular monolith** (`memorybox/`) with:

- **FastAPI** app (`memorybox/app.py`) serving UI static files and JSON APIs
- **PostgreSQL** domain tables (migrations in `memorybox/migrations/`)
- **Prove harnesses** (`python -m memorybox prove-*`) for increment acceptance
- **Provider adapters** for Immich, HVRT, Gmail, etc.

Host reference: FlightSim (`C:\MemoryBox` on Tom's machine).

## Historian Capture (P2-I12) architecture

```text
/historian-capture/ui  →  historian_capture.html (MB dark shell)
        │
        ▼
memorybox/historian_capture/__init__.py   (domain: campaigns, deliveries, items, review)
        │
        ├── email_adapter.py              (interface + fake harness)
        ├── gmail_live.py                 (live Gmail adapter)
        └── acceptance.py                 (prove-historian-capture)
        │
        ▼
PostgreSQL  historian_capture_* tables   (migration 025)
        │
        ▼
Email transport
  ├── fake: FakeHistorianEmailAdapter (prove / dev)
  └── live: MarvinGmailHistorianEmailAdapter → application.marvin_capture.gmail_client
```

## Email channel model (locked)

| Concept | Value | Notes |
|---------|-------|-------|
| **Capture channel** | `memorybox@marvinbot.net` | Logical Historian Capture mailbox |
| **Gmail API transport** | Often a personal Gmail (e.g. hosting account) | Sends via API; receives replies in that inbox |
| **Correlation** | `[MB-HC-<token>]` subject + `+hc-<token>` plus-address | Matches inbound to `historian_capture_deliveries` |
| **Processed label** | `MemoryBox/HC-Processed` | Applied after ingest; mail **not** trashed |

UI banner explains capture channel vs transport account when they differ.

## Inbound poll model

- `poll_and_ingest()` polls Gmail, correlates by token, creates `historian_capture_items`
- `tick_scheduler()` calls `poll_and_ingest()` at start, then sends due questions / reminders
- HC UI calls `POST /historian-capture/poll` on boot and when opening a campaign (`syncInbox`)

There is **no standalone background cron** in V1.

## Integration surfaces

| Surface | Integration |
|---------|-------------|
| People (I10A.1) | Respondent picker; email from `/people/{id}/profile` contacts |
| Stories (I10A) | Promotion target from review verdict |
| Artifacts (I10B) | Optional promotion target |
| Ask / narration (I11) | Retrieves promoted testimony with attribution |
| Archive Health (I2) | `hc_unmatched` / `hc_new` counts |
| Guided Capture (I11 legacy) | Separate module; HC replaces owner-run capture pattern |

## `application/marvin_capture/` dependency

**Not on the I12 integration line.** Required for **live Gmail only**.

| I12 import | PoC module | Purpose |
|------------|------------|---------|
| `build_plus_address`, `parse_plus_tag` | `plus_address.py` | Plus-address construction/parsing |
| `extract_reply_text` | `reply_extract.py` | Strip quoted reply from inbound body |
| `build_live_gmail_client` | `gmail_client.py` | OAuth Gmail API client |

**Branch:** `cursor/marvin-capture-v01-3344` @ `fe913a4`  
**Fallback:** `email_adapter.py` has inline fallbacks when import fails (fake/harness only).

See [08-ENVIRONMENT-SETUP.md](08-ENVIRONMENT-SETUP.md) for reproducibility guidance. **Do not vendor without separate decision.**

## Provider boundary rules

- Domain tables are MemoryBox-owned (Postgres).
- Provider systems (Immich, HVRT, Gmail) map through adapters — never second source of truth.
- Inbound capture items are **immutable evidence**; editing happens only in versioned Review Drafts.
