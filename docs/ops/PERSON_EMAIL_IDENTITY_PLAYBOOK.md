# Person Email Identity Expansion — Trace + Fix

**Branch:** `cursor/p2-i11a-person-email-identity-49da`  
**Stop point:** Peggy email in Gallery/common Person retrieve + Full-Evidence V2. No historian semantic redesign.

## Root cause

| Path | Behavior |
|------|----------|
| **Email** | Person retrieve SQL is GIN `person_ids` only (`header_fallback=False`). Confirmed email addresses were consulted only *after* SQL, so empty GIN pages never reached Python filters. |
| **Peggy state** | No confirmed email on `person_contact_points`. Ingest never stamped `person_ids` on her mail (`resolve_handles` needs prior contacts). Chicken-and-egg. |
| **SMS** | Phone contacts + auto-map/repair + **sender_name SQL fallback** → ~2298 hits. |

Gallery uses the same `search_email_messages` path → zero email is expected given the above.

## Fix (common capability)

Module: `memorybox/person/comm_identity.py`

1. Snapshot Person names/aliases/phones/emails/provider ids  
2. Discover candidates from **From/To/CC headers only** (full display-name match; first-name-only rejected)  
3. Corroborate conservatively (unclaimed address, unique full-name Person, provenance)  
4. Persist to `person_contact_points` with provenance `comm_identity_expand`  
5. Backfill `person_ids` on matching email evidence payloads  
6. Bounded rounds until identity set stable; skip archive rediscovery when confirmed emails already exist  

Retrieve: `search_email_messages` expands identities then SQL-matches **GIN person_ids OR confirmed email headers** (not body ILIKE).

## FlightSim

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-person-email-identity-49da
.\startmb.cmd -Restart

python -m memorybox prove-person-email-identity

REM Trace Peggy (replace PERSON_ID with Peggy George id from People UI / profile)
python -m memorybox person-email-identity-trace --person-id PERSON_ID --address peggo417@hotmail.com

python -m memorybox repair-email-identities --person-id PERSON_ID

REM Gallery: open Peggy → Email tab should show mail

REM Preserve V1; rebuild V2 full-evidence
python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Leave V1 outputs under `docs\test-output\full-evidence\` or `historian-full-evidence\peggy\` unchanged.

## V1 vs V2 (fill after FlightSim)

| Metric | V1 | V2 |
|--------|----|----|
| SMS | 2298 | ? |
| Email | 0 | ? |
| Photo | 428 | ? |
| Video | 93 | ? |
| Total items | 2820 | ? |
| Est. tokens | 225804 | ? |

Also record: addresses used, email message/thread counts, earliest/latest, email bytes/tokens.
