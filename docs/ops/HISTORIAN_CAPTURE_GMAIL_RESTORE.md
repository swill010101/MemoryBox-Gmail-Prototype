# Historian Capture Gmail restore (FlightSim)

**Do not commit** OAuth client secrets, refresh tokens, or mailbox passwords.

Historian Capture uses a dedicated capture mailbox, not family `config/gmail_credentials.json` / `config/gmail_token.json`.

## Serve configuration

`startmb.ps1` may default `MEMORYBOX_HC_EMAIL_PROVIDER=auto`. It does **not** set `MEMORYBOX_HC_USER_EMAIL`.

Set the dedicated mailbox in gitignored host env (`config/memorybox_app.env`) or gitignored `config/historian_capture.json`. The committed example files use a placeholder and must be replaced on the host.

```
MEMORYBOX_HC_EMAIL_PROVIDER=auto
MEMORYBOX_HC_USER_EMAIL=<dedicated-capture-mailbox>
```

Optional path overrides (still dedicated files only):

```
MEMORYBOX_HC_GMAIL_CREDENTIALS=config/historian_capture_gmail_credentials.json
MEMORYBOX_HC_GMAIL_TOKEN=config/historian_capture_gmail_token.json
```

Live transport depends on `google-api-python-client` and `google-auth-oauthlib` from `memorybox/requirements.txt`.

## Restore dedicated OAuth files

On the FlightSim serve tree (typically `C:\MemoryBox`):

1. Confirm `application/marvin_capture/gmail_client.py` is present (this increment).
2. Copy **only** these gitignored files from the last known-good FlightSim backup or a new OAuth consent for the dedicated capture mailbox:
   - `config/historian_capture_gmail_credentials.json`
   - `config/historian_capture_gmail_token.json`
3. Do not copy or rename family `gmail_*.json` into those names without a dedicated capture-mailbox OAuth client.
4. Confirm `MEMORYBOX_HC_USER_EMAIL` is set in gitignored host env (not via `startmb.ps1` defaults).
5. Restart serve (`startmb.ps1` or equivalent). Do not send campaign mail until status is connected.

## Verify (no send)

```powershell
# After serve is up:
Invoke-RestMethod http://127.0.0.1:8790/historian-capture/email-status
```

Expect `"ok": true`, `"reason": "live_ok"`, `"live": true`, and a `detail` that names the capture channel. Open `/historian-capture/ui` and confirm the green connected banner.

If `"ok": false`, use `reason` (`missing_user_email`, `missing_credentials`, `missing_token`, `missing_transport`, `family_gmail_rejected`, `unavailable`). The API `detail` is written for the UI and must not contain filesystem paths or exception text.

## New OAuth (only if restore files are gone)

Use a Google Cloud OAuth client for the dedicated capture mailbox only. Store the installed-app credentials JSON and the resulting token JSON in the two dedicated filenames above. Do not reuse the family Gmail OAuth client.
