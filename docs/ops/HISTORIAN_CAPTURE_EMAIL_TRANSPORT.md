# Historian Capture email transport (FlightSim)

**Do not commit** mailbox passwords, OAuth client secrets, or refresh tokens.

Production Historian Capture uses the dedicated Namecheap Private Email mailbox `memorybox@marvinbot.net`. It must not use family `config/gmail_credentials.json` / `config/gmail_token.json`. Do not create a Google Workspace mailbox for this channel.

Optional Gmail API transport remains in-tree for `MEMORYBOX_HC_EMAIL_PROVIDER=gmail` only. It is not the configured production path.

## Serve configuration

`startmb.ps1` defaults:

```
MEMORYBOX_HC_EMAIL_PROVIDER=privateemail
MEMORYBOX_HC_USER_EMAIL=memorybox@marvinbot.net
```

Store the Namecheap **application password** (not the webmail master password) in gitignored host env or the dedicated credentials file:

```
MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD=<app-password>
```

or gitignored `config/historian_capture_privateemail_credentials.json` (see `config/historian_capture_privateemail_credentials.json.example`). Environment variables override the file. Never commit the password.

Optional host/port overrides:

```
MEMORYBOX_HC_IMAP_HOST=mail.privateemail.com
MEMORYBOX_HC_IMAP_PORT=993
MEMORYBOX_HC_SMTP_HOST=mail.privateemail.com
MEMORYBOX_HC_SMTP_PORT=465
MEMORYBOX_HC_FROM_DISPLAY_NAME=MemoryBox Historian for Tom
MEMORYBOX_HC_MAIL_TIMEOUT=20
# Optional subject templates. Production default still includes [MB-HC-{token}].
# Do not switch to founder-review wording until Tom approves.
# MEMORYBOX_HC_QUESTION_SUBJECT_TEMPLATE=[MB-HC-{token}] {title}
# MEMORYBOX_HC_THANKYOU_SUBJECT_TEMPLATE=[MB-HC-{token}] Thank you — MemoryBox
```

TLS certificate validation stays enabled. IMAP/SMTP calls use bounded timeouts.

IMAP poll checkpoints are gitignored files under the MemoryBox application root (or `MEMORYBOX_HOME` / `MEMORYBOX_DATA_DIR` / `MEMORYBOX_HC_STATE_DIR`):

`.memorybox_hc_state/imap_checkpoint__namecheap_privateemail_imap_smtp__<mailbox>.json`

They are not the sole duplicate barrier. PostgreSQL `idx_hc_items_inbound_msg` on `historian_capture_items.inbound_message_id` is.

## Visible From and subject (founder review)

Production From: `MemoryBox Historian for Tom <memorybox@marvinbot.net>`

Production subject (unchanged default): `[MB-HC-<token>] <campaign title>`

Proposed wording — **not the production default until founder approval**:

- Initial: `A MemoryBox question from Tom about <Person or campaign title>`
- Thank-you: `Thank you for sharing this memory`

Correlation remains in Reply-To (`memorybox+hc-<token>@marvinbot.net`) and `X-MemoryBox-HC-Token`. Replies that keep the plus-address work even if the visible subject has no token. Replies that drop both the plus-address and the subject token will not correlate (same I12 risk if Reply-To is ignored).

Autonomous five-minute cadence (HC-2) is documented in [HISTORIAN_CAPTURE_HC2_CADENCE.md](HISTORIAN_CAPTURE_HC2_CADENCE.md). **HC-2 ACCEPTED 2026-09-11.**

## Later FlightSim procedure (do not execute until founder authorizes)

1. Deploy an approved commit.
2. In Namecheap Private Email / webmail for `memorybox@marvinbot.net`, create a dedicated **application password**.
3. Place it only in gitignored `config/memorybox_app.env` (`MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD`) or `config/historian_capture_privateemail_credentials.json`.
4. Restart MemoryBox with `C:\MemoryBox\.venv\Scripts\python.exe` (PATH `python` is not the serve interpreter).
5. Confirm `GET /historian-capture/email-status` is `"ok": true`, `"reason": "live_ok"`, `"provider_key": "namecheap_privateemail_imap_smtp"`.
6. Founder reviews From name, subject, and one prepared message.
7. Founder authorizes one bounded send.
8. Verify receipt and a reply through the same thread.
9. Verify the reply is ingested exactly once.
10. Only then authorize campaign operation.

## Verify (no send)

```powershell
Invoke-RestMethod http://127.0.0.1:8790/historian-capture/email-status
```

Disconnected `reason` values are sanitized: `missing_credentials`, `missing_user_email`, `imap_unavailable`, `smtp_unavailable`, `authentication_failed`, `configuration_invalid`, `unavailable`. Never paste passwords, paths, or exception text.

## Optional Gmail API provider

Only if explicitly set `MEMORYBOX_HC_EMAIL_PROVIDER=gmail`. Restore dedicated (never family) OAuth files:

- `config/historian_capture_gmail_credentials.json`
- `config/historian_capture_gmail_token.json`

A failed Namecheap connection must not fall back to Gmail or fake transport.
