# MemoryBox — Agent Instructions (Codex / VS Code)

**Integration commit (P2-I12 ACCEPTED):** `9f0d7dc75c7a4cfd633af2175399e4141e7f56ee`  
**Tag:** `increment-12-accepted`  
**Transition branch:** `transition/p2-i12-codex-handoff`  
**Do not merge to `main` without explicit founder direction.** `main` is scaffolding only.

## Start here

Read in order:

1. [docs/codex-handoff/00-START-HERE.md](docs/codex-handoff/00-START-HERE.md)
2. [docs/codex-handoff/02-CURRENT-STATE.md](docs/codex-handoff/02-CURRENT-STATE.md)
3. [docs/product/MBBS-P2_INCREMENT_12_DEFINITION.md](docs/product/MBBS-P2_INCREMENT_12_DEFINITION.md)

## Branch model

| Branch | Role |
|--------|------|
| `cursor/c1t-i11a-gate-repair-5229` | I12 integration line (merged PRs #83–#85) |
| `transition/p2-i12-codex-handoff` | Codex handoff docs + preservation (this work) |
| `cursor/marvin-capture-v01-3344` | PoC Gmail client (`application/marvin_capture/`) — **not on I12 line** |
| `main` | Scaffolding only — **not active development** |

## Hard rules

- **P2-I12 is ACCEPTED (2026-09-04).** Do not reopen without explicit founder direction.
- **No application behavior changes** on preservation/transition branches unless a new increment is authorized.
- **Never commit secrets:** Gmail OAuth credentials/tokens, `.env`, databases, logs, fake-mail runtime dirs, personal media.
- **Historian Capture live Gmail** requires `application/marvin_capture/` from the PoC branch on FlightSim — see [docs/codex-handoff/08-ENVIRONMENT-SETUP.md](docs/codex-handoff/08-ENVIRONMENT-SETUP.md).
- **Fake adapter** is sufficient for automated prove: `MEMORYBOX_HC_EMAIL_PROVIDER=fake`.

## Prove commands (I12)

```bash
python -m memorybox migrate
MEMORYBOX_HC_EMAIL_PROVIDER=fake python -m memorybox prove-historian-capture --slice s5
```

FlightSim live (requires Gmail creds + `application/marvin_capture/`):

```powershell
$env:MEMORYBOX_HC_EMAIL_PROVIDER = "auto"
$env:MEMORYBOX_HC_USER_EMAIL = "memorybox@marvinbot.net"
python -m memorybox prove-historian-capture --flightsim --slice s5
```

## UI entry

- Historian Capture: `/historian-capture/ui`
- Implementation: `memorybox/historian_capture/static/historian_capture.html`

## Product authority

| Topic | Document |
|-------|----------|
| I12 PRD | `docs/product/MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md` |
| I12 acceptance | `docs/product/MBAT-P2-I12_ACCEPTANCE.md` |
| I12 screens | `docs/product/MBSC-P2-I12_HISTORIAN_COLLECTION_SCREEN_CONTRACT.md` |
| I12 UX sign-off | `docs/product/I12_UX_SIGNOFF_20260904.md` |
| Post-I12 roadmap | `docs/product/MBRM-001C_P2_POST_I12_ROADMAP.md` |
| UX foundation | `docs/product/MBUX-001_v0.4.md` |
