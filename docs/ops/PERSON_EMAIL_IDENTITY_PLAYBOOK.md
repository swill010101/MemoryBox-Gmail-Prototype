# Peggy resolve + Peg Legg nickname (email)

**Branch:** `cursor/p2-i11a-peggy-resolve-nickname-49da`

## What the diag proved

Ask `"tell me what you know about Peggy"` resolved Person **`Peggy`** (`549b…`) with:
- `known_name_forms: ["peggy"]` only
- **no confirmed emails**

That is an Immich lazy-seed **stub**, not **Peggy George**. Full-evidence therefore never saw `peggo417@hotmail.com`.

Explore `"show peggy george"` hits the real Person / name filter — which is why the UI showed 27 email threads while the benchmark stayed at Email: 0.

## Archive truth (screenshots)

- From: **`Peg Legg <peggo417@hotmail.com>`** (real hotmail local-part is `peggo417`, not `peggo01417`)
- Some thread titles show **names only** (`Peggy George`) because ingest `people[]` stores `display_name or address` (name preferred). Raw `from` often has `Name <email>`. Explore was concatenating both → duplicate “Peg Legg” + “Peg Legg \<addr\>”. Not a load error — metadata + UI. Title builder now prefers the angle-bracket form when both exist.

## Fixes

1. **Ask resolve:** single-token `"Peggy"` prefers unique multi-token **`Peggy George`** over exact stub `"Peggy"`.
2. **Nickname identity:** header `Peg Legg` + address corroborates to Peggy George when she is the unique multi-token Person in the Peg/Peggy family; seeds alias **Peg Legg**; attaches `peggo417@hotmail.com`.
3. Discovery still runs even when some People email already exists (find additional addresses).

## FlightSim

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-peggy-resolve-nickname-49da
.\startmb.cmd -Restart

python -m memorybox person-email-identity-trace --person-id <PEGGY_GEORGE_ID>
REM or omit --person-id after asking; diag on next bench should show Peggy George

python -m memorybox historian-full-evidence-benchmark --flightsim --out-dir docs\test-output\historian-full-evidence\peggy-v2 --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Expect metrics `email` > 0, diag `display_name: Peggy George`, `confirmed_emails` includes `peggo417@hotmail.com`, People card gains alias **Peg Legg**.

Optional cleanup: merge stub Person `"Peggy"` (`549b…`) into Peggy George in People UI so it cannot win again.
