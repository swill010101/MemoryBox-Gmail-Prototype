# Historian Capture HC-2 — autonomous five-minute cadence

**Status:** implemented, not FlightSim-accepted. Do not register, enable, or send live mail until founder gates below.

**HC-1 accepted base:** `f777832cb4581344b294fcbd961eea5a0ecc4e10`  
**Production provider:** Namecheap Private Email (`privateemail`), mailbox `memorybox@marvinbot.net`  
**Subject templates:** unchanged from HC-1. Friendly wording is a separate founder decision.

## Architecture

Windows Task Scheduler only wakes the process every five minutes. It contains no campaign rules.

Each wake runs one in-process CLI:

```text
C:\MemoryBox\.venv\Scripts\python.exe -m memorybox hc-tick
```

That CLI calls the same `tick_scheduler` service used by campaign start and **Send next question now**. There is no second email pipeline and no unauthenticated HTTP tick.

### Tick order

1. Acquire a PostgreSQL session advisory lock (`pg_try_advisory_lock`).
2. Read configured HC email provider status (sanitized).
3. Poll IMAP Inbox and HC plus-address folders (HC-1 adapter).
4. Ingest and deduplicate replies (`idx_hc_items_inbound_msg` remains the duplicate barrier).
5. Apply reply-driven transitions (answered, cancel follow-up, schedule next question per I12 cadence, opt-out).
6. Recalculate due outbound work.
7. Send permitted due questions / reminders; apply no-response after a reminder window — I12 gates unchanged (running campaign, active respondent, pause, follow-up interval, reminder-then-no-response).
8. Persist heartbeat and a bounded log line.
9. Release the lock.

Inbound polling always happens before outbound evaluation. A reply waiting in the mailbox is ingested before a reminder can send.

Thank-you mail remains owner-triggered after review (`send_thank_you_if_enabled`). The tick does not auto-send thank-you bodies.

## Cadence and catch-up

- Interval: **five minutes**.
- Timestamps are stored and compared in **UTC**. Campaign timezone and UI display are unchanged.
- A due action should fire on the first tick after its configured time. Campaign schedules are not rewritten.
- `MEMORYBOX_HC_MAX_SENDS_PER_TICK` defaults to **5** (questions + reminders). Excess work stays due for later ticks. No-response marks are not SMTP sends and are not counted against the cap.
- The first tick after downtime must not burst more than the cap.

## Locking and idempotency

The database lock is authoritative. Task Scheduler **Do not start a new instance** (`IgnoreNew`) is secondary.

If the lock is held (scheduled tick overlapping another tick or **Send next question now**):

- result `already_running`
- no sends and no campaign writes
- exit code 0 (not an operational failure)

SMTP failure leaves the delivery `pending` (retryable) with `fail_detail` / `retry_count`. It is not marked sent. Reminder failure does not set `reminder_sent_at`.

Restart after a partial tick is safe: already-`waiting` deliveries are not resent; unique inbound ids prevent duplicate capture items.

## IMAP failure

If IMAP polling fails (exception or adapter `last_poll_debug.error`):

- fail closed for **reminders, follow-ups, and no-response** on that tick
- do not assume the mailbox is empty
- do not advance those items
- record sanitized `imap_unavailable`
- retry on the next tick

Initial due questions may still send if the provider itself is healthy; they are not waiting on a reply.

## Heartbeat, Admin Jobs, and logs

Persisted (gitignored `.memorybox_hc_state/` and table `historian_capture_tick_heartbeat` from migration `034`):

- latest heartbeat (`tick_heartbeat.json`)
- run history (`tick_history.json`, newest first, keep ~200)
- bounded technical log (`tick.log`, last 200 JSON lines)

**Application heartbeat is authoritative** for whether an HC tick actually completed. Windows Task Scheduler History only proves the OS launched the process.

Owner-facing operational history is **Admin → Processing Jobs** (`/admin/jobs/ui`): a **Scheduled Services** section with one persistent **Historian Capture email** card (not one job row per tick). Expand the card for the most recent 20 runs. The I13 face/voice processing-job table below it is unchanged.

The Historian Capture panel keeps the concise cadence line and a **View run history** link to that Admin section.

Admin status precedence (first match):

1. **Not configured** — Windows task is not registered (manual-tick heartbeat cannot make this look configured).
2. **Disabled** — registered but disabled (old failures do not override this).
3. **Error** — enabled and the latest completed tick failed (sanitized category). `already_running` is not Error.
4. **Delayed** — enabled, no successful completion within 15 minutes.
5. **Active** — enabled and successfully completed within 15 minutes.

`next_expected_run_at` is blank for Not configured and Disabled.

`GET /admin/api/scheduled-services` does **not** run `schtasks` on every browser refresh. It uses in-process memory plus `.memorybox_hc_state/tick_task_status.json` (60s TTL). `schtasks /Query` is a 2-second Windows truth check only when that cache is stale; stdout is discarded after reading the Status line. The browser never executes Task Scheduler commands.

Never logged or shown: passwords, message bodies, secret filesystem paths, raw exceptions.

Admin API (not mixed into I13 `GET /admin/api/jobs`):

```http
GET /admin/api/scheduled-services
```

```json
{
  "ok": true,
  "services": [
    {
      "id": "historian_capture_email",
      "kind": "recurring_service",
      "title": "Historian Capture email",
      "status": "Active",
      "schedule": "Every 5 minutes",
      "provider": "Namecheap Private Email",
      "mailbox": "memorybox@marvinbot.net",
      "last_successful_run_at": "2026-09-11T19:58:00+00:00",
      "next_expected_run_at": "2026-09-11T20:03:00+00:00",
      "last_result": "ok",
      "replies_imported": 1,
      "emails_sent": 1,
      "actions_deferred": 0,
      "last_error": null,
      "recent_runs": []
    }
  ]
}
```

The `services` array is the extension point for later recurring jobs. Only Historian Capture is implemented now.

## CLI

```powershell
& C:\MemoryBox\.venv\Scripts\python.exe -m memorybox hc-tick
& C:\MemoryBox\.venv\Scripts\python.exe -m memorybox hc-tick --dry-run
```

`--dry-run` still polls and may ingest waiting replies; it does not send and does not mark no-response.

Exit codes: `0` ok / already_running / smtp_partial; `2` IMAP or SMTP retryable; `3` configuration; `1` unexpected.

## Windows task (create disabled)

Task name: **MemoryBox Historian Capture Tick**

| Action | Script |
|--------|--------|
| Register (disabled) | `scripts/historian-capture/Register-HcTickTask.ps1` |
| Status | `scripts/historian-capture/Get-HcTickTask.ps1` |
| Disable | `scripts/historian-capture/Disable-HcTickTask.ps1` |
| Remove | `scripts/historian-capture/Unregister-HcTickTask.ps1` |
| Manual launch | `scripts/historian-capture/Invoke-HcTick.ps1` |

Register uses:

- absolute repo and `.venv\Scripts\python.exe`
- working directory = repo root
- `config\memorybox_app.env` loaded by the launcher (no passwords in task arguments)
- same FlightSim defaults as `startmb` when unset: Postgres URL, `MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333`, capture mailbox
- 5-minute repetition
- Interactive Limited principal (the MemoryBox Windows user)
- MultipleInstances = IgnoreNew
- **Disabled** after register (`-Enable` is refused)

Do not register or enable during development.

## Credentials

Unchanged from HC-1: `MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD` or gitignored `config/historian_capture_privateemail_credentials.json`. Never in task XML or CLI args.

## Deployment / acceptance / rollback (prepare only — do not execute)

1. Deploy the approved HC-2 SHA to FlightSim (`C:\MemoryBox`), venv Python, load `memorybox_app.env`.
2. `python -m memorybox migrate` — apply `034_historian_capture_hc2_tick.sql` (requires HC I12 tables). Verify `historian_capture_tick_heartbeat` and `idx_hc_items_inbound_msg`.
3. `GET /historian-capture/email-status` remains `live_ok` / `namecheap_privateemail_imap_smtp`.
4. One manual dry tick: `python -m memorybox hc-tick --dry-run`.
5. Create the scheduled task **disabled** via `Register-HcTickTask.ps1`.
6. Verify command, identity, paths, working directory, env loading (`Get-HcTickTask.ps1`).
7. Founder authorizes **one** controlled scheduled/manual tick (not `--dry-run` if sending is intended; prefer a paused-except-one-test campaign).
8. Verify inbound-first processing and no duplicate actions.
9. Founder authorizes enabling the five-minute schedule (`Enable-ScheduledTask` — not this repo script).
10. Observe at least three successful ticks.
11. Verify heartbeat on the HC panel and Task Scheduler history.
12. Founder accepts HC-2.

Rollback: `Disable-HcTickTask.ps1` or `Unregister-HcTickTask.ps1`. Serve continues; cadence stops. HC-1 transport is unchanged. Migration 034 is additive.

## Tests (offline)

```powershell
python -m unittest tests.test_hc2_cadence tests.test_hc_privateemail tests.test_hc_gmail_connector tests.test_hc_ingest_idempotent -v
```

No live email. Schema-dependent cases skip if Historian Capture Postgres is absent. Do not migrate the desktop database silently.
