# Person Email Identity Expansion — Trace + Fix

**Branch:** `cursor/p2-i11a-email-operator-attach-49da`  
**Stop point:** Peggy email in Gallery/common Person retrieve + Full-Evidence V2. No historian semantic redesign.

## Root cause (stacked)

| Layer | Behavior |
|------|----------|
| **Email retrieve** | Person SQL is GIN `person_ids` + confirmed header addresses (`header_fallback=False`). No confirmed email → empty GIN pages → Email: 0. |
| **Peggy state** | No confirmed email on `person_contact_points`. Ingest never stamped `person_ids` (chicken-and-egg). |
| **To/CC JSON** | Ingest stores `to`/`cc` as arrays; `->>'to'` is NULL — fixed to `(payload_json->'to')::text` + `*_parsed`. |
| **Header display name** | Archive uses **`Peg Legg <peggo417@hotmail.com>`**, while Person display is **`Peggy George`**. Discovery previously prefiltered only the longest form (`peggy george`) and never saw `Peg Legg`. Auto corroboration requires a full-name form/alias match. |
| **SMS** | Phone contacts + sender_name SQL fallback → ~2298 hits. |

## Fix

1. Discover with **all** multi-token known forms (display + aliases) via `LIKE ANY`, not only the longest.
2. Corroborate + persist + backfill `person_ids`.
3. Retrieve: GIN **or** confirmed header addresses.
4. **Operator attestation:** `repair-email-identities --person-id <ID> --address peggo417@hotmail.com` attaches when the address is in headers and unclaimed (even if display is `Peg Legg` / bare). Seeds `Peg Legg` as an `alternate_name` alias when seen on headers so later auto-discovery works. Ask auto-expand never operator-attests.

## FlightSim (one command — repair then rebuild V2)

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-email-operator-attach-49da
.\startmb.cmd -Restart

python -m memorybox historian-full-evidence-benchmark --flightsim --repair-address peggo417@hotmail.com --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Then open:
- `PEGGY_FULL_EVIDENCE_METRICS.json` → `by_source.email` and `email_identity_diag` / `email_identity_repair`
- `PEGGY_EMAIL_IDENTITY_DIAG.json` → `likely_blocker`, `rows_with_address`, `seeded_aliases`

If email is still 0, paste `PEGGY_EMAIL_IDENTITY_DIAG.json` (not just metrics).

### Manual repair (optional)

```bat
python -m memorybox person-email-identity-trace --person-id <PEGGY_ID> --address peggo417@hotmail.com
python -m memorybox repair-email-identities --person-id <PEGGY_ID> --address peggo417@hotmail.com
```

Do **not** pass `--from-dir` pointing at V1.

## V1 vs V2 (fill after FlightSim)

| Metric | V1 | V2 |
|--------|----|----|
| SMS | 2298 | ? |
| Email | 0 | ? |
| Photo | 428 | ? |
| Video | 93 | ? |
| Total items | 2820 | ? |
| Est. tokens | 225804 | ? |

Also record: addresses (`peggo417@hotmail.com`), header name (`Peg Legg`), provenance, email message/thread counts, dates, tokens.
