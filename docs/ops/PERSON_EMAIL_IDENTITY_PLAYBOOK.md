# Address-centric email identity (Peggy / peggo417)

**Governing rule:** MemoryBox discovers communication identities from the archive
first, resolves those identities to People second, and then uses the resolved
identities to retrieve complete Person evidence.

**PRD:** `docs/ops/PRD_ADDRESS_CENTRIC_EMAIL_IDENTITY.md`  
**Branch:** `cursor/p2-i11a-address-centric-email-49da`

## Pipeline

```
1. DISCOVER  archive → communication_identities (address + Peg Legg / Peggy George …)
2. RESOLVE   identity → Person (corroborate; fail closed if shared)
3. RETRIEVE  Person → trusted addresses → all mail for those addresses
```

## FlightSim

If `tools\flightsim-address-centric-gate.cmd` is not on disk yet (first pull):

```bat
cd C:\memorybox
git fetch origin cursor/p2-i11a-address-centric-email-49da
git checkout -B cursor/p2-i11a-address-centric-email-49da origin/cursor/p2-i11a-address-centric-email-49da
```

Primary gate (Gallery + Full-Evidence email > 0; **no historian**):

```bat
cd C:\memorybox
tools\flightsim-address-centric-gate.cmd
```

The script checks out `cursor/p2-i11a-address-centric-email-49da`, restarts, then
runs `tools\flightsim-address-centric-prove.ps1` (loads `config\memorybox_app.env`
the same way `startmb` does — so migrate/prove hit the Takeout archive DB, not a
silent ALLOW_DEV localhost). Paste the printed gate block
(need `"ok": true` and `"flightsim": true`). Gate `runtime` stamps `database`,
`database_url_set`, and `git_head`.

If structured headers show Peg Legg on peggo417 but **no** same-address
Peggy George observation (quoted or structured), auto nickname attach stays
fail-closed (so unrelated `Peg *` mailboxes are not claimed). In that case
`prove-address-centric-email-e2e --flightsim` auto-runs operator repair for
`peggo417@hotmail.com` when structured hits exist; or run:

```bat
python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --repair-address peggo417@hotmail.com
```

`--fixture …\HISTFIX_peggy_*.json` is optional (funnel metrics only; omit if missing).
**Stop** after V2 — no historian summarization.

## Ask name forms

Ask resolves `Peggy`, `Peggy George`, and `Peg Legg` (confirmed alias or unique
nickname-family multi-token Person). Display names remain observations on the
address; the address is the retrieve key once resolved.

**FlightSim prerequisite:** prefer an existing multi-token Person \"Peggy George\".
If only Immich single-token \"Peggy\" exists **and** inventory shows Peg Legg
(structured) + Peggy George (quoted/structured) on peggo417, the gate prove
operator-renames that unique Immich Person to \"Peggy George\" before attach.
Full-Evidence on P1 does **not** Immich-lazy-seed a new \"Peggy\" stub.
