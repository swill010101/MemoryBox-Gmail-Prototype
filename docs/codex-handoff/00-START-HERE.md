# Codex Handoff — Start Here

**Date:** 2026-09-04  
**Owner:** Tom  
**Accepted increment:** P2-I12 Historian Collection & Campaigns V1  
**Historical integration SHA:** `9f0d7dc75c7a4cfd633af2175399e4141e7f56ee`  
**Tag:** `increment-12-accepted`

## What this folder is

`docs/codex-handoff/` is the **onboarding spine** for OpenAI Codex in VS Code after Cursor development ended. It points to authoritative product docs already in Git and records decisions that previously lived only in Cursor sessions.

## Read order

| # | File | Purpose |
|---|------|---------|
| 00 | This file | Orientation |
| 01 | [01-SYSTEM-ARCHITECTURE.md](01-SYSTEM-ARCHITECTURE.md) | Modules, boundaries, email architecture |
| 02 | [02-CURRENT-STATE.md](02-CURRENT-STATE.md) | Branch map, accepted vs active vs deferred |
| 03 | [03-DOMAIN-RULES.md](03-DOMAIN-RULES.md) | Evidence ownership, HC lifecycle |
| 04 | [04-IMPLEMENTATION-PATTERNS.md](04-IMPLEMENTATION-PATTERNS.md) | Code layout, APIs, UI patterns |
| 05 | [05-TESTING-AND-ACCEPTANCE.md](05-TESTING-AND-ACCEPTANCE.md) | Prove harnesses, I12 acceptance |
| 06 | [06-KNOWN-ISSUES.md](06-KNOWN-ISSUES.md) | Backlog, limitations, deferred work |
| 07 | [07-DECISION-LOG.md](07-DECISION-LOG.md) | Founder locks and session decisions |
| 08 | [08-ENVIRONMENT-SETUP.md](08-ENVIRONMENT-SETUP.md) | FlightSim, env vars, dependencies |

## Authoritative product docs (not duplicated here)

- **Roadmap after I12:** [MBRM-001C](../product/MBRM-001C_P2_POST_I12_ROADMAP.md)
- **I12 definition:** [MBBS-P2_INCREMENT_12](../product/MBBS-P2_INCREMENT_12_DEFINITION.md)
- **I12 PRD:** [MBPRD-P2-I12](../product/MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)
- **I12 acceptance:** [MBAT-P2-I12](../product/MBAT-P2-I12_ACCEPTANCE.md)
- **I12 UX sign-off:** [I12_UX_SIGNOFF_20260904](../product/I12_UX_SIGNOFF_20260904.md)
- **Increment table:** [MBRM-001A](../product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)

## Accepted implementation evidence

| Artifact | Path |
|----------|------|
| HC backend | `memorybox/historian_capture/` |
| HC UI | `memorybox/historian_capture/static/historian_capture.html` |
| Migration | `memorybox/migrations/025_historian_capture_i12.sql` |
| Prove harness | `memorybox/historian_capture/acceptance.py` |
| Sanitized prove output | `docs/test-output/historian-capture/prove-fake-s*-20260904.json` |
| Accepted screen refs | `docs/source/Screens/MBUX Historian Capture Screens/` |

## What is *not* authoritative

- `codex/historian-capture-reference-screens-20260829` @ `fe913a4` — **layout reference only** (August 22); superseded by shipped MB-dark UI
- `application/marvin_capture/` on branch `cursor/marvin-capture-v01-3344` — PoC transport; not merged into I12 line

## Next increment (not authorized to build)

Per [MBRM-001C](../product/MBRM-001C_P2_POST_I12_ROADMAP.md): **P2-I13 Video, Face, STT & Voice Pipeline Revalidation**.
