# Person Email Identity — People Contacts Are Enough

**Branch:** `cursor/p2-i11a-email-confirmed-retrieve-49da`  
**Stop point:** Peggy email in Gallery + Full-Evidence V2 from **People confirmed contacts**. No hardcoded address.

## Confirmed

If Peggy George’s People screen already shows a confirmed email contact (e.g. `peggo01417@hotmail.com`), that **is** enough for Ask/Gallery/full-evidence retrieve. No bake-in, no `--repair-address`, no Peggy-specific constant.

Path: `person_contact_points` (confirmed) → `expand_emails_for_retrieve` → SQL match on From/To/CC / `*_parsed` → optional `person_ids` backfill.

## Why V2 was still Email: 0

1. Earlier probes used **`peggo417@hotmail.com`** — People shows **`peggo01417@hotmail.com`** (different local-part). Hardcoding the wrong spelling cannot help.
2. When a confirmed contact already existed, expand **skipped backfill** of `person_ids` onto matching rows (fixed: still backfill).
3. Python keep-filter only read `*_parsed`; raw header fallback added for older rows.
4. `normalize_handle` now extracts bare address from `Peg Legg <addr@host>`.

## FlightSim (no repair flag)

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-email-confirmed-retrieve-49da
.\startmb.cmd -Restart

REM Trace uses People contact automatically (no --address needed)
python -m memorybox person-email-identity-trace --person-id <PEGGY_ID>

python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Check `PEGGY_EMAIL_IDENTITY_DIAG.json`:
- `confirmed_emails` should list `peggo01417@hotmail.com`
- `rows_with_address` > 0 if archive headers match that spelling
- If `rows_with_address` is 0, the People contact spelling does not appear in ingested From/To/CC — fix the contact or the archive, don’t hardcode

`--repair-address` remains optional only when People has **no** email yet.
