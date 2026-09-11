# Historian Capture Gmail transport (vendored subset)

Source: `origin/cursor/marvin-capture-v01-3344` @ `fe913a4c18e76beb32467306e6f653bbe93c43b9`

This directory is **only** the Gmail transport used by `memorybox.historian_capture`. It is not the Marvin Capture PoC application.

## Vendored files

| File | Why |
|------|-----|
| `__init__.py` | Package marker |
| `gmail_client.py` | `build_live_gmail_client` |
| `plus_address.py` | Plus-address helpers |
| `reply_extract.py` | Reply body extraction |

Not vendored (PoC-only): `app.py`, `db.py`, `config.py`, `mail_store.py`, `mem_bank.py`, `service.py`, `whisper_client.py`, `static/*`.

PoC `config.py` defaults to family `config/gmail_credentials.json`. Historian Capture must **not** load that module for live mail.

## Live Gmail

Use dedicated files only (gitignored):

- `config/historian_capture_gmail_credentials.json`
- `config/historian_capture_gmail_token.json`

Serve env:

```
MEMORYBOX_HC_EMAIL_PROVIDER=auto
MEMORYBOX_HC_USER_EMAIL=<dedicated-capture-mailbox>
```

See `docs/ops/HISTORIAN_CAPTURE_GMAIL_RESTORE.md`.
