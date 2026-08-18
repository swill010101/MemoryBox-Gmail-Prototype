# MBBS — P2 backlog planning sequence

**Status:** Living parking note · **Updated:** 2026-08-18 (I8 definition DRAFT, awaiting approval)  
**Authority:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (approved planning direction) · I1 definition: [MBBS-P2_INCREMENT_1_DEFINITION.md](MBBS-P2_INCREMENT_1_DEFINITION.md)  
**Owner:** Tom

## Gate (hard)

- **No build** until Tom approves the next definition and explicitly authorizes build.
- Prefer **one** authorized increment at a time.
- **I4 is ACCEPTED** (2026-08-18). Remaining Explore visual defects are **P2-BL-I4-01** (non-blocking). Do not reopen I4 unless a defect affects function, context continuity, filtering, Timeline/Gallery sync, modal return, trust, or the accepted interaction model. Do not skip later Explore work for I8 attachment surprises.
- Combined host floor vs buy (chip, RAM, 1 TB NVMe, 10 TB USB sources): [MBBS-P2_HOST_SIZING.md](../ops/MBBS-P2_HOST_SIZING.md) (2026-08-17).
- Immich lives on FlightSim: [FLIGHTSIM_IMMICH_CUTOVER.md](../ops/FLIGHTSIM_IMMICH_CUTOVER.md). Do not leave `config/immich.env` on media-server.

## Backlog absorption (normalized)

| Parked item | Roadmap home |
|-------------|--------------|
| TASK-P1P2-004 Immich Status Photos inventory | **P2-I3** (minimal in I1 only if required for sync/queue status) |
| TASK-P1P2-001 Universal Immich lazy-teach | **P2-I1** (Ask/media path) + **P2-I5** (remaining surfaces) |
| TASK-P1P2-002 Kinship inference | **P2-I6** |
| Ops SMS / mbox | **P2-I7 / P2-I8** |
| TASK-P1P2-003 Export import-back | **P2-I17** (EVS-020) |

## Post–I4 carry-forward (ACCEPTED with gap)

P2-I4 Mixed-Media Find / Explore is **ACCEPTED** (2026-08-18 — Tom: functional and UX acceptance satisfactory). The following did **not** block acceptance and must not reopen I4 unless a defect is found to affect **function**, **context continuity**, **filtering**, **Timeline/Gallery synchronization**, **modal return state**, **trust**, or the **accepted interaction model**:

| ID | Theme | Evidence | Suggested home |
|----|--------|----------|----------------|
| **P2-BL-I4-01** | Explore **visual polish** (chrome, crop, density, mockup aesthetic) | Founder: remaining issues are minor aesthetic/polish. Mixed-Media Find mockup was hierarchy/calm-aesthetic **anchor**, not pixel spec. Includes leftover visual mismatch (e.g. curator/header crop vs Immich preferred thumb on Explore; card/chrome vs mockup). Not a new Explore interaction. | Later UX cleanup increment when Tom authorizes. **Not I8 email.** Cross-ref Person header portrait **P2-BL-I5-01**. |

Authority: [MBBS-P2_INCREMENT_4_DEFINITION.md](MBBS-P2_INCREMENT_4_DEFINITION.md).

## Post–I5 carry-forward (ACCEPTED with gap)

P2-I5 Universal Person Surfaces is **ACCEPTED** (2026-08-14). The following did **not** block acceptance and must not reopen I5:

| ID | Theme | Evidence | Suggested home |
|----|--------|----------|----------------|
| **P2-BL-I5-01** | Immich **preferred person portrait** on Person Explorer (header + curator avatar) | Sue Will preferred face visible in Immich People UI; MemoryBox Person Explorer still shows letter initial after portrait endpoint + name-resolve work (2026-08-14) | Thin follow-up / polish slice when Tom authorizes — likely Immich person-thumb API rights, mapping persistence, or proxy path. Not I6 Kinship. |

Authority: [MBBS-P2_INCREMENT_5_DEFINITION.md](MBBS-P2_INCREMENT_5_DEFINITION.md) · [MBBS-P2_I5_UNIVERSAL_PERSON_SURFACES_PRD.md](MBBS-P2_I5_UNIVERSAL_PERSON_SURFACES_PRD.md)

## Post–I6 carry-forward (ACCEPTED with gap)

P2-I6 Relationship Graph & Derived Kinship is **ACCEPTED** (2026-08-14 — Tom: “i6 passes”). The following did **not** block acceptance and must not reopen I6:

| ID | Theme | Evidence | Suggested home |
|----|--------|----------|----------------|
| **P2-BL-I6-01** | EVS-209 kinship-in-photo | Graph filter ready; full pass needs an open photo with recognized People | Later viewer / People-rail earn-in — **not I7 SMS** |

Authority: [MBBS-P2_INCREMENT_6_DEFINITION.md](MBBS-P2_INCREMENT_6_DEFINITION.md).

## Post–I7 carry-forward (ACCEPTED with gap)

P2-I7 SMS/Text Evidence is **ACCEPTED** (2026-08-15 — Tom: “i7 is accepted”). The following did **not** block acceptance and must not reopen I7:

| ID | Theme | Evidence | Suggested home |
|----|--------|----------|----------------|
| **P2-BL-I7-01** | SMS / iMessage **attachment bytes** | **BUILD AUTHORIZED** 2026-08-15 (Tom: matcher, no wipe; run from Downloads then copy to Sources). Export Attachments names (`YYYY-MM-DD HH MM SS - Chat - Type`) join existing SMS rows on timestamp+chat. UUID/exact first. Same-second collisions and orphan files stay unmatched. `ingest-sms --attachments-dir`. Not Immich. Does not reopen I7. | After I7 ACCEPTED — this revision. |

Authority: [MBBS-P2_INCREMENT_7_DEFINITION.md](MBBS-P2_INCREMENT_7_DEFINITION.md) · [MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md](MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md)

## I8 constraint parked now (do not wait to rediscover)

| ID | Theme | Why now | Home |
|----|--------|---------|------|
| **P2-BL-I8-01** | I8 email ingest must include **attachment files up front** | I7 accepted CSV-only; attachment bytes were missing and had to be parked. Do not repeat that gap for email. | **P2-I8** richer email — part of I8 definition/build, not a later surprise |

## Next increment

**P2-I7A AI Model Trace & Observability** — [definition](MBBS-P2_INCREMENT_7A_DEFINITION.md) · **ACCEPTED** 2026-08-15.

**MBQL-001 Ask, Query & Command Language** — [definition](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) · [PRD](MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md). **ACCEPTED** 2026-08-18 (Tom: “MBQL is accepted”).

**P2-I8 Richer Email** — [definition](MBBS-P2_INCREMENT_8_DEFINITION.md) · [PRD](MBPRD-P2-I8_RICHER_EMAIL.md). **DRAFT 2026-08-18 — awaiting Tom approval. Not build authorized.**

**P2-I8 is not started** (needs locked Q1–Q6 + explicit build authorization). Sequence: **I7A ACCEPTED → MBQL-001 ACCEPTED → I8** when Tom authorizes (I8.5 remains after I8; I9 stays after I8.5). **P2-I4 ACCEPTED** 2026-08-18; Explore visual polish is **P2-BL-I4-01**.
