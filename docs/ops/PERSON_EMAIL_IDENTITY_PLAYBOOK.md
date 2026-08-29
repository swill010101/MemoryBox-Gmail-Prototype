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

Pull the latest tip first (cold-create / Immich rename / delivery order live here):

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

Delivery (any one wakes the cloud agent):
1. **Always** force-pushes gate artifacts to `cursor/flightsim-address-centric-result-49da` **first**
2. If `gh` is already authenticated: posts the gate JSON as a comment on PR #74
   (skips comment when gh is missing/unauthed — never hangs on auth)
3. Desktop + notepad VERDICT + console paste block

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

**FlightSim Person bootstrap (operator gate only):**
1. Prefer existing exact \"Peggy George\".
2. Else rename unique Immich single-token \"Peggy\" → \"Peggy George\" when
   structured Peg Legg exists on peggo417 (quoted Peggy George optional).
3. Else cold-create \"Peggy George\" from structured Peg Legg alone when no
   usable Peggy Person exists (thin Takeout / Immich-absent).
4. Full-Evidence on P1 does **not** Immich-lazy-seed a new \"Peggy\" stub.
