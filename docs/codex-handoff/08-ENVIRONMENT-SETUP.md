# Environment Setup

## Prerequisites

- Python 3.11+ (3.14 OK)
- PostgreSQL 16+ (`MEMORYBOX_DATABASE_URL`)
- Docker Compose (optional, for local Postgres)
- FlightSim: Immich, HVRT, Qdrant, Ollama per increment needs

## Quick start (Historian Capture prove)

```bash
cd /path/to/memorybox
pip install -r memorybox/requirements.txt
python -m memorybox migrate
MEMORYBOX_HC_EMAIL_PROVIDER=fake python -m memorybox prove-historian-capture --slice s5
```

## Serve locally

```bash
MEMORYBOX_HC_EMAIL_PROVIDER=fake python -m memorybox serve
# http://127.0.0.1:8790/historian-capture/ui
```

## FlightSim (Tom's host)

```powershell
cd C:\memorybox
git fetch origin
git checkout cursor/c1t-i11a-gate-repair-5229   # or transition branch
git pull

$env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
$env:MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"

# Historian Capture — fake prove
$env:MEMORYBOX_HC_EMAIL_PROVIDER = "fake"
python -m memorybox prove-historian-capture --slice s5

# Historian Capture — live (Namecheap Private Email)
$env:MEMORYBOX_HC_EMAIL_PROVIDER = "privateemail"
$env:MEMORYBOX_HC_USER_EMAIL = "memorybox@marvinbot.net"
# App password (gitignored only):
#   MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD
#   or config/historian_capture_privateemail_credentials.json
python -m memorybox prove-historian-capture --flightsim --slice s5
```

## `application/marvin_capture/` dependency

### What I12 imports

| Symbol | File | Required for |
|--------|------|--------------|
| `build_plus_address`, `parse_plus_tag` | `plus_address.py` | Live + fake (has inline fallback) |
| `extract_reply_text` | `reply_extract.py` | Live + fake (has inline fallback) |
| `build_live_gmail_client` | `gmail_client.py` | **Live only** |

Call sites:

- `memorybox/historian_capture/email_adapter.py` (lines 21–25)
- `memorybox/historian_capture/gmail_live.py` (lines 26–27, 107–112)

### Where it lives

| Branch | Tip | Path |
|--------|-----|------|
| `cursor/marvin-capture-v01-3344` | `fe913a4` | Full PoC `application/marvin_capture/` (16 files) |
| `codex/p2-i13-stage-a` (HC-1) | this line | Vendored subset: `__init__.py`, `gmail_client.py`, `plus_address.py`, `reply_extract.py` |

### Why absent from I12 integration line

I12 was built as a MemoryBox-native module (`memorybox/historian_capture/`) with selective PoC reuse **behind an adapter**. The PoC package was never merged into `cursor/c1t-i11a-gate-repair-5229` to avoid pulling SQLite SoT, old review UI, and unrelated PoC surface area.

### Can I12 run from a clean clone?

| Mode | Works? | Requirements |
|------|--------|--------------|
| `prove-historian-capture` (fake) | **Yes** | Postgres + `MEMORYBOX_HC_EMAIL_PROVIDER=fake` |
| HC UI (read cached data) | **Yes** | Postgres + serve |
| Live Namecheap IMAP/SMTP | **Yes** | Dedicated app password + `MEMORYBOX_HC_EMAIL_PROVIDER=privateemail` |
| Optional live Gmail API | **Yes** | Vendored `application/marvin_capture` + dedicated OAuth files; not production |

### Production transport (HC-1)

Production provider is Namecheap Private Email (`privateemail`) for `memorybox@marvinbot.net`. `startmb.ps1` defaults `MEMORYBOX_HC_EMAIL_PROVIDER=privateemail` and `MEMORYBOX_HC_USER_EMAIL=memorybox@marvinbot.net`. Store the app password only in gitignored env or `config/historian_capture_privateemail_credentials.json`. Optional Gmail API remains behind `MEMORYBOX_HC_EMAIL_PROVIDER=gmail`. See [HISTORIAN_CAPTURE_EMAIL_TRANSPORT.md](../ops/HISTORIAN_CAPTURE_EMAIL_TRANSPORT.md).

HC-2 autonomous tick (`python -m memorybox hc-tick`, five-minute Windows task **MemoryBox Historian Capture Tick**) is documented in [HISTORIAN_CAPTURE_HC2_CADENCE.md](../ops/HISTORIAN_CAPTURE_HC2_CADENCE.md). **HC-2 ACCEPTED 2026-09-11** at FlightSim SHA `743c76712cb286ccdae3ad1108fb260dbd04770d`.

The I13 line still vendors `gmail_client.py`, `plus_address.py`, `reply_extract.py`, and `__init__.py` from `fe913a4` under `application/marvin_capture/` for the optional Gmail provider and plus-address helpers.

### Config files

| File | In Git? | Purpose |
|------|---------|---------|
| `config/historian_capture.json.example` | Yes | Template |
| `config/historian_capture_privateemail_credentials.json` | **No** (gitignored) | Namecheap app password |
| `config/historian_capture_gmail_credentials.json` | **No** (gitignored) | Optional Gmail OAuth client secret |
| `config/historian_capture_gmail_token.json` | **No** (gitignored) | Optional Gmail OAuth token |
| `config/historian_capture.json` | Local optional | Overrides example |

Env overrides: `MEMORYBOX_HC_CONFIG`, `MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD`, `MEMORYBOX_HC_PRIVATEEMAIL_CREDENTIALS`, `MEMORYBOX_HC_GMAIL_CREDENTIALS`, `MEMORYBOX_HC_GMAIL_TOKEN`, `MEMORYBOX_HC_USER_EMAIL`.

## Gitignored runtime dirs

Do not commit:

- `.memorybox_hc_fake_mail/` — fake prove mail
- `.memorybox_gc_fake_mail/` — guided capture fake mail
- `.memorybox_capture_fake/` — capture fake media
- `memorybox_artifact_media/` — local promotion test files
- `.memorybox_hc_imap_checkpoint.json` — legacy IMAP UID checkpoint
- `.memorybox_hc_state/` — provider/mailbox-scoped IMAP checkpoints, HC-2 heartbeat and tick log

## Related ops docs

- [HISTORIAN_CAPTURE_EMAIL_TRANSPORT.md](../ops/HISTORIAN_CAPTURE_EMAIL_TRANSPORT.md)
- [HISTORIAN_CAPTURE_HC2_CADENCE.md](../ops/HISTORIAN_CAPTURE_HC2_CADENCE.md)
- [FLIGHTSIM_IMMICH_CUTOVER.md](../ops/FLIGHTSIM_IMMICH_CUTOVER.md)
- [MBBS-P2_HOST_SIZING.md](../ops/MBBS-P2_HOST_SIZING.md)
- [GIT_SYNC.md](../GIT_SYNC.md)
