# Address-centric email identity (Peggy / peggo417)

**Governing rule:** MemoryBox discovers communication identities from the archive
first, resolves those identities to People second, and then uses the resolved
identities to retrieve complete Person evidence.

**PRD:** `docs/ops/PRD_ADDRESS_CENTRIC_EMAIL_IDENTITY.md`  
**Branch:** `cursor/p2-i11a-stabilize-a3b9`

## Pipeline

```
1. DISCOVER  archive → communication_identities (address + Peg Legg / Peggy George …)
2. RESOLVE   identity → Person (corroborate; fail closed if shared)
3. RETRIEVE  Person → trusted addresses → all mail for those addresses
```

## FlightSim

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-stabilize-a3b9
.\startmb.cmd -Restart

python -m memorybox migrate
python -m memorybox probe-email-address --flightsim --address peggo417@hotmail.com

python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json --repair-address peggo417@hotmail.com
```

`probe-email-address` fills the address ledger (Peg Legg / Peggy George observations).
Full-evidence then resolves ledger → Person → all mail. `--repair-address` is
operator attestation if auto-resolve is still empty.

Single-command E2E gate (Gallery + Full-Evidence email > 0; no historian):

```bat
python -m memorybox prove-address-centric-email-e2e --flightsim
```

Paste prove JSON + V2 `ADDRESS_CENTRIC_GATE.json` (need `"ok": true`) + `by_source.email`.
**Stop** after V2 — no historian summarization.

## Ask name forms

Ask resolves `Peggy`, `Peggy George`, and `Peg Legg` (confirmed alias or unique
nickname-family multi-token Person). Display names remain observations on the
address; the address is the retrieve key once resolved.
