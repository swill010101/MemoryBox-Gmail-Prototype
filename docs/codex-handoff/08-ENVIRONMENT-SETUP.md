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

# Historian Capture — live
$env:MEMORYBOX_HC_EMAIL_PROVIDER = "auto"
$env:MEMORYBOX_HC_USER_EMAIL = "memorybox@marvinbot.net"
# Credentials (local only, never commit):
#   config/historian_capture_gmail_credentials.json
#   config/historian_capture_gmail_token.json
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
| `cursor/marvin-capture-v01-3344` | `fe913a4` | `application/marvin_capture/` (16 files) |

### Why absent from I12 integration line

I12 was built as a MemoryBox-native module (`memorybox/historian_capture/`) with selective PoC reuse **behind an adapter**. The PoC package was never merged into `cursor/c1t-i11a-gate-repair-5229` to avoid pulling SQLite SoT, old review UI, and unrelated PoC surface area.

### Can I12 run from a clean clone?

| Mode | Works? | Requirements |
|------|--------|--------------|
| `prove-historian-capture` (fake) | **Yes** | Postgres + `MEMORYBOX_HC_EMAIL_PROVIDER=fake` |
| HC UI (read cached data) | **Yes** | Postgres + serve |
| Live Gmail send/poll | **No** | PoC package + OAuth creds on FlightSim |

### Safest reproducibility path (FlightSim)

**Option A (current, no repo change):** Checkout PoC files alongside integration branch:

```powershell
git fetch origin cursor/marvin-capture-v01-3344
git checkout origin/cursor/marvin-capture-v01-3344 -- application/marvin_capture
# Do NOT commit unless founder authorizes vendor decision
```

**Option B (future, needs decision):** Vendor minimal transport modules into `memorybox/historian_capture/transport/` and drop PoC import.

**Option C (future):** Git submodule or documented pip path — not implemented.

### Config files

| File | In Git? | Purpose |
|------|---------|---------|
| `config/historian_capture.json.example` | Yes | Template |
| `config/historian_capture_gmail_credentials.json` | **No** (gitignored) | OAuth client secret |
| `config/historian_capture_gmail_token.json` | **No** (gitignored) | OAuth token |
| `config/historian_capture.json` | Local optional | Overrides example |

Env overrides: `MEMORYBOX_HC_CONFIG`, `MEMORYBOX_HC_GMAIL_CREDENTIALS`, `MEMORYBOX_HC_GMAIL_TOKEN`, `MEMORYBOX_HC_USER_EMAIL`.

## Gitignored runtime dirs

Do not commit:

- `.memorybox_hc_fake_mail/` — fake prove mail
- `.memorybox_gc_fake_mail/` — guided capture fake mail
- `.memorybox_capture_fake/` — capture fake media
- `memorybox_artifact_media/` — local promotion test files
- `.memorybox_hc_mail/` — live mail preservation (if present)

## Related ops docs

- [FLIGHTSIM_IMMICH_CUTOVER.md](../ops/FLIGHTSIM_IMMICH_CUTOVER.md)
- [MBBS-P2_HOST_SIZING.md](../ops/MBBS-P2_HOST_SIZING.md)
- [GIT_SYNC.md](../GIT_SYNC.md)
