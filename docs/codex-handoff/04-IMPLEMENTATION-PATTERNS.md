# Implementation Patterns

## Module layout

```
memorybox/
  historian_capture/
    __init__.py          # Domain API (campaigns, items, poll, tick, promote)
    email_adapter.py     # Protocol + fake adapter + get_email_adapter()
    gmail_live.py        # Live Gmail adapter
    acceptance.py        # prove-historian-capture
    static/
      historian_capture.html   # Single-page MB UI
  migrations/
    025_historian_capture_i12.sql
  app.py               # Routes under /historian-capture/*
```

## Key API routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/historian-capture/ui` | HC single-page UI |
| GET/POST | `/historian-capture/campaigns` | List / create |
| GET/PUT/DELETE | `/historian-capture/campaigns/{id}` | Detail / edit draft / delete |
| POST | `/historian-capture/campaigns/{id}/start` | Start campaign |
| POST | `/historian-capture/campaigns/{id}/pause` | Pause |
| POST | `/historian-capture/campaigns/{id}/resume` | Resume |
| POST | `/historian-capture/campaigns/{id}/stop` | Stop |
| POST | `/historian-capture/campaigns/{id}/advance` | Send next question now (guarded) |
| POST | `/historian-capture/tick` | Scheduler tick |
| POST | `/historian-capture/poll` | Poll inbound mail |
| GET | `/historian-capture/items` | List capture items |
| GET | `/historian-capture/items/{id}/source` | Download original as `.txt` |
| POST | `/historian-capture/items/{id}/thank-you` | Send thank-you (optional extra text) |

## Email adapter selection

```python
# memorybox/historian_capture/email_adapter.py :: get_email_adapter()
MEMORYBOX_HC_EMAIL_PROVIDER=fake   # harness / CI / clean clone
MEMORYBOX_HC_EMAIL_PROVIDER=auto   # live if creds present, else unavailable
```

## UI patterns (accepted)

- `data-mb-surface="historian-capture"` on `<html>` — dark theme override
- Canonical MB header via `explore.css` chrome (`#mb-hc-chrome`)
- Entry: Review & Learn nav → Historian Capture
- Tabs: Needs review · Kept · Rejected · Campaigns · Needs attention
- **No** engineering controls (Tick, Poll, stage IDs) in product UI
- Inline flash messages next to action buttons (not bottom toast only)
- Person picker: dropdown with search (not raw `<select>`)
- Campaign delete: confirmation modal (Stories/Artifacts pattern)
- Breadcrumbs on campaign detail and review screens

## CSS override note

`shell.css` light-theme `.card` rules are excluded for `data-mb-surface` values including `historian-capture`. HC HTML also uses `!important` dark overrides.

## Promotion pattern

Verdict `promotion_authorized` → user chooses Story or Artifact → existing I10A/I10B editors with provenance chain stored on promotion record.

## Testing pattern

```bash
MEMORYBOX_HC_EMAIL_PROVIDER=fake python3 -m memorybox prove-historian-capture --slice s2
```

Fake adapter uses `.memorybox_hc_fake_mail/` locally (gitignored) for preserved `.eml` stubs.

## Do not

- Add HC identifiers (HC-01, etc.) to product-facing UI copy
- Use left-rail admin console layout
- Auto-promote on inbound receipt
- Trash inbound mail after processing (label only)
