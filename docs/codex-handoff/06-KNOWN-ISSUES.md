# Known Issues and Deferred Work

## I12 V1 limitations (accepted)

| Issue | Detail | Workaround |
|-------|--------|------------|
| No background poll daemon | Inbound mail ingested on UI load + `tick_scheduler` | Open HC dashboard or call `POST /historian-capture/poll` |
| `application/marvin_capture/` external | Live Gmail requires PoC branch checkout on FlightSim | See [08-ENVIRONMENT-SETUP.md](08-ENVIRONMENT-SETUP.md) |
| Person email edit | No email edit in People UI; HC reads profile contacts | Type email manually in new campaign form |
| HC reference mockups | Aug 22 branch is layout-only reference | Use shipped UI + screen refs in `docs/source/Screens/` |
| README stale sections | Root README stops at I8A | Use `AGENTS.md` and codex-handoff |

## Bugs fixed during acceptance (do not regress)

| Bug | Fix |
|-----|-----|
| Inbound replies not appearing | Auto-poll on UI boot + `tick_scheduler` calls `poll_and_ingest` |
| FS-10 `outbound_sent: 0` in flightsim prove | Count deliveries with `sent_at` not just tick `sent` list |
| White cards in HC UI | `shell.css` exclusion + HC `!important` dark overrides |
| `ConnectionResetError` in video_worker | Suppress client disconnect errors during media stream |

## Open backlog items

| ID | Theme |
|----|-------|
| P2-BL-I4-01 | Explore visual polish |
| P2-BL-I5-01 | Immich preferred portrait on Person Explorer |
| P2-BL-I7-01 | SMS attachment bytes ingest |
| P2-BL-I8A-01 | Promo/newsletter classifier |
| Face-SoT | Later increment |
| I11A FlightSim | BUILD AUTHORIZED; not founder ACCEPTED |
| I11B | Planning only |

## Not in scope for I12

- Curator-generated questions
- Contributor accounts
- Automatic Story generation on receipt
- Voice contributor workflow
- Multi-user editing
- PoC SQLite as source of truth

## Dependency decision pending

Whether to vendor `application/marvin_capture/` into the main integration line requires a **separate founder decision**. Do not merge or copy without authorization.
