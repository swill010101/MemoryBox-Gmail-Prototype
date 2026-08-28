# Person Email Identity Expansion — Trace + Fix

**Branch:** `cursor/p2-i11a-email-operator-attach-49da`  
**Stop point:** Peggy email in Gallery/common Person retrieve + Full-Evidence V2. No historian semantic redesign.

## Root cause (stacked)

| Layer | Behavior |
|------|----------|
| **Email retrieve** | Person SQL is GIN `person_ids` + confirmed header addresses (`header_fallback=False`). No confirmed email → empty GIN pages → Email: 0. |
| **Peggy state** | No confirmed email on `person_contact_points`. Ingest never stamped `person_ids` (chicken-and-egg). |
| **To/CC JSON** | Ingest stores `to`/`cc` as arrays; `->>'to'` is NULL — fixed to `(payload_json->'to')::text` + `*_parsed`. |
| **Hotmail headers** | Many rows are bare `peggo417@hotmail.com` or first-name-only (`Peggy`). Auto corroboration requires a **full** display-name match → still rejects. |
| **SMS** | Phone contacts + sender_name SQL fallback → ~2298 hits. |

Gallery uses the same `search_email_messages` path → zero email until a confirmed contact exists.

## Fix

1. Discover/corroborate from From/To/CC (full display-name; first-name-only rejected for **auto**).
2. Persist + backfill `person_ids`.
3. Retrieve matches GIN **or** confirmed header addresses.
4. **Operator attestation:** `repair-email-identities --person-id <ID> --address peggo417@hotmail.com` attaches when the address is present in headers and unclaimed, even if display name is bare/first-name-only. Provenance: `comm_identity_operator_attested`. Ask auto-expand never does this.

## Why metrics still had no `email` section (1:02PM / commit `019dc5b`)

Benchmark `by_source` only lists sources that returned items. Expand found **0** confirmed addresses (auto path), GIN returned 0 email rows → identical inventory to V1 (SMS 2298 / Photo 428 / Video 93 / Total 2820).

## FlightSim (required order)

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-email-operator-attach-49da
.\startmb.cmd -Restart

python -m memorybox prove-person-email-identity

REM Trace first — look at rows_with_address, hint, operator_attested_probe
python -m memorybox person-email-identity-trace --person-id <PEGGY_ID> --address peggo417@hotmail.com

REM Operator attest + backfill (REQUIRED when headers lack full name)
python -m memorybox repair-email-identities --person-id <PEGGY_ID> --address peggo417@hotmail.com

REM Expect known_address_results[0].accepted true, backfill.updated > 0
REM Then Gallery Peggy → Email should list messages

python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Do **not** pass `--from-dir` pointing at V1 — that freezes the old zero-email inventory.

If `rows_with_address` is **0**, the address is not in ingested headers (wrong spelling or mbox not ingested) — attestation cannot invent it.

## V1 vs V2 (fill after FlightSim)

| Metric | V1 | V2 |
|--------|----|----|
| SMS | 2298 | ? |
| Email | 0 | ? |
| Photo | 428 | ? |
| Video | 93 | ? |
| Total items | 2820 | ? |
| Est. tokens | 225804 | ? |

Also record: addresses used, provenance (`operator_attested` vs header full-name), email message/thread counts, earliest/latest, email bytes/tokens.
