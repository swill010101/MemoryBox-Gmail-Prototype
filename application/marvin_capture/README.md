# Historian Capture email transport (vendored Gmail subset)

Source: `origin/cursor/marvin-capture-v01-3344` @ `fe913a4c18e76beb32467306e6f653bbe93c43b9`

This directory is **only** helpers plus the **optional** Gmail API transport. Production Historian Capture uses Namecheap Private Email (`MEMORYBOX_HC_EMAIL_PROVIDER=privateemail`).

## Vendored files

| File | Why |
|------|-----|
| `__init__.py` | Package marker |
| `gmail_client.py` | Optional `build_live_gmail_client` |
| `plus_address.py` | Plus-address helpers (also used with Namecheap) |
| `reply_extract.py` | Reply body extraction |

Not vendored (PoC-only): `app.py`, `db.py`, `config.py`, `mail_store.py`, `mem_bank.py`, `service.py`, `whisper_client.py`, `static/*`.

PoC `config.py` defaults to family `config/gmail_credentials.json`. Historian Capture must **not** load that module.

## Production (Namecheap)

```
MEMORYBOX_HC_EMAIL_PROVIDER=privateemail
MEMORYBOX_HC_USER_EMAIL=memorybox@marvinbot.net
```

Store the app password in gitignored env or `config/historian_capture_privateemail_credentials.json`.

See `docs/ops/HISTORIAN_CAPTURE_EMAIL_TRANSPORT.md`.
