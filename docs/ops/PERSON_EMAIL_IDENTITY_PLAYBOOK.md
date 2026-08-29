# Address-centric email identity (Peggy / peggo417)

**Governing rule:** MemoryBox discovers communication identities from the archive
first, resolves those identities to People second, and then uses the resolved
identities to retrieve complete Person evidence.

**PRD:** `docs/ops/PRD_ADDRESS_CENTRIC_EMAIL_IDENTITY.md`  
**Branch:** `cursor/p2-i11a-stabilize-a3b9`

## Do not use historian-full-evidence-benchmark for email identity

That command **re-retrieves the whole Peggy pack** (photos + SMS + email). `--fixture`
only feeds the compression funnel; it does **not** skip retrieve.

A previous Ask path inventoried `peggo417` with `body_text LIKE` + JSON unnest on
every mail row. That is why it ran overnight. Ask retrieve now uses **contacts +
ledger only**. Probe inventory is header-only and times out at 60s.

If a python still sitting on `inventory_email_address`: Ctrl+C is enough. Do not
re-run the historian benchmark until identity e2e is green.

## Pipeline

```
1. DISCOVER  probe-email-address → communication_identities (once)
2. RESOLVE   ledger → Person contacts (cheap)
3. RETRIEVE  Person → trusted addresses → mail (no archive inventory)
```

## FlightSim — identity gate (this is the email extraction check)

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-stabilize-a3b9
.\startmb.cmd -Restart

python -m memorybox migrate
python -m memorybox prove-address-centric-email-e2e --flightsim
```

Expect finish in minutes, not hours. Paste the prove JSON (`"ok": true`).

The prove now **fails closed** if Peggy's confirmed emails include owner/noreply/marketplace
addresses or if retrieve looks like the whole mailbox (the previous pass had
700+ co-recipient addresses and ~42k hits). It prunes those contacts first.

If a prior run already attached co-recipients, prune is included in e2e. Standalone:

```bat
python -m memorybox repair-email-identities --flightsim --person-id <PEGGY_ID> --prune-uncorroborated --address peggo417@hotmail.com
python -m memorybox prove-address-centric-email-e2e --flightsim
```

Optional one-address probe (header scan, 60s cap):

```bat
python -m memorybox probe-email-address --flightsim --address peggo417@hotmail.com
```

## Historian / L1 chunks (only after identity e2e is green)

`--from-dir` reuses a frozen pack. `--fixture` does **not** skip retrieve.

```bat
python -m memorybox historian-full-evidence-benchmark --flightsim --from-dir docs\test-output\full-evidence --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

If `docs\test-output\full-evidence` is missing, identity e2e already proved email.
Do not start a fresh full-archive retrieve just to extract mail.

## Ask name forms

Ask resolves `Peggy`, `Peggy George`, and `Peg Legg` (confirmed alias or unique
nickname-family multi-token Person). Display names remain observations on the
address; the address is the retrieve key once resolved.
