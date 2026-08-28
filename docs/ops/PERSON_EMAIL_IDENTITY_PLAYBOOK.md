# Address-centric email identity (Peggy / peggo417)

**PRD:** `docs/ops/PRD_ADDRESS_CENTRIC_EMAIL_IDENTITY.md`  
**Branch:** `cursor/p2-i11a-address-centric-email-49da`

## Architecture

```
communication_identities  (archive-wide address ledger)
  address → observed_display_names {Peggy George, Peg Legg, …}
         → resolved_person_id?
         → resolution_status

Person resolve:
  name/aliases → find addresses in structured headers
              → corroborate → person_contact_points
              → backfill person_ids on all messages with that address
```

Does **not** require Person to already have the email before discovery.

- Structured From/To/CC = identity-grade  
- Quoted/forwarded body headers = lower confidence (inventory only; not sole proof)

## FlightSim

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-address-centric-email-49da
.\startmb.cmd -Restart

REM 1) Required investigation — structured vs quoted display names
python -m memorybox probe-email-address --flightsim --address peggo417@hotmail.com

REM Optional: attach/resolve onto Peggy George
python -m memorybox probe-email-address --flightsim --address peggo417@hotmail.com --person-id <PEGGY_GEORGE_ID>

REM 2) Full-evidence V2 (same Ask path as Gallery)
python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Paste `probe-email-address` JSON (especially `structured_header.has_peggy_george` / `has_peg_legg` and quoted counterparts) plus V2 `by_source.email`.

**Stop** after V2 metrics. No historian summarization.
