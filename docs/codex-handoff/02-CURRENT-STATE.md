# Current State (2026-09-04)

## Accepted increments (do not reopen)

| ID | Status | Prove |
|----|--------|-------|
| I1–I8A, MBQL-001 | ACCEPTED | `prove-p2-i1` … `prove-p2-i8a`, `prove-mbql-001` |
| I10, I10A/B/C, I10A.1, I10A.2 | ACCEPTED | `prove-p2-i10`, `prove-story`, `prove-i10c`, etc. |
| **I12 Historian Capture** | **ACCEPTED 2026-09-04** | `prove-historian-capture` |

## Build authorized but not accepted

| ID | Status |
|----|--------|
| I9 Spoken | BUILD AUTHORIZED; FlightSim ACCEPTED pending |
| I11 Narration | BUILD AUTHORIZED |
| I11A Inference | BUILD AUTHORIZED; not FlightSim ACCEPTED |

## Deferred / planning only

| ID | Status |
|----|--------|
| I11B Curator Learning | Planning only; BUILD NOT AUTHORIZED |
| I13–I19 | See [MBRM-001C](../product/MBRM-001C_P2_POST_I12_ROADMAP.md) |

## Git landmarks

| Ref | SHA | Meaning |
|-----|-----|---------|
| `increment-12-accepted` (tag) | `9f0d7dc` | Accepted I12 integration commit |
| `cursor/c1t-i11a-gate-repair-5229` | `9f0d7dc` | I12 merged here (PRs #83–#85) |
| `transition/p2-i12-codex-handoff` | (this branch) | Codex preservation docs |
| `main` | `0ef49aa` | Scaffolding only — **not dev line** |

## I12 PR merge chain (completed)

1. #83 planning → `cursor/c1t-i11a-gate-repair-5229`
2. #84 S1–S4 → planning branch
3. #85 S5 live prove → S1–S4 branch

## Shipped I12 capabilities

- Campaign CRUD (draft, start, pause, resume, stop, delete)
- One-question-at-a-time email cadence with separate follow-up interval (default 7 days)
- Inbound correlate by `[MB-HC-token]` / `+hc-token`
- Immutable capture items + versioned review drafts
- Owner assessment (4 labels) + verdict (retain / reject / promote)
- Story and Artifact promotion with provenance chain
- Thank-you ack with leak guard
- STOP opt-out per respondent
- Unmatched quarantine + Archive Health integration
- MB-dark Historian Capture UI at `/historian-capture/ui`
- Fake and live Gmail adapters
- FlightSim staged prove (`--flightsim --slice s5`)

## Open backlog (non-blocking)

- **P2-BL-I4-01** Explore visual polish
- **P2-BL-I5-01** Person portrait from Immich
- **P2-BL-I7-01** SMS attachment bytes
- **P2-BL-I8A-01** Promo/newsletter classifier
- Face-SoT (later)
- External Historical Context (deferred; was old I12 row)
