# MBBS — P2 backlog planning sequence

**Status:** Living parking note · **Updated:** 2026-08-15 (I7 ACCEPTED; I7A definition locked, no build)  
**Authority:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (approved planning direction) · I1 definition: [MBBS-P2_INCREMENT_1_DEFINITION.md](MBBS-P2_INCREMENT_1_DEFINITION.md)  
**Owner:** Tom

## Gate (hard)

- **No build** until Tom approves the next definition and explicitly authorizes build.
- Prefer **one** authorized increment at a time.

## Backlog absorption (normalized)

| Parked item | Roadmap home |
|-------------|--------------|
| TASK-P1P2-004 Immich Status Photos inventory | **P2-I3** (minimal in I1 only if required for sync/queue status) |
| TASK-P1P2-001 Universal Immich lazy-teach | **P2-I1** (Ask/media path) + **P2-I5** (remaining surfaces) |
| TASK-P1P2-002 Kinship inference | **P2-I6** |
| Ops SMS / mbox | **P2-I7 / P2-I8** |
| TASK-P1P2-003 Export import-back | **P2-I17** (EVS-020) |

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
| **P2-BL-I7-01** | SMS / iMessage **attachment bytes** | iMazing CSV lists 8,644 attachment rows / 7,212 unique names; `inspect-sms` 2026-08-15: `attachment_files_on_disk` = 0 (folder is CSV-only). Tom will Export Attachments (or set `MEMORYBOX_SMS_ATTACHMENTS_DIR`) then `ingest-sms` backfill. Not Immich. Not I7A. | After I7 ACCEPTED — thin follow-up when Tom authorizes. Do not reopen I7. |

Authority: [MBBS-P2_INCREMENT_7_DEFINITION.md](MBBS-P2_INCREMENT_7_DEFINITION.md) · [MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md](MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md)

## I8 constraint parked now (do not wait to rediscover)

| ID | Theme | Why now | Home |
|----|--------|---------|------|
| **P2-BL-I8-01** | I8 email ingest must include **attachment files up front** | I7 accepted CSV-only; attachment bytes were missing and had to be parked. Do not repeat that gap for email. | **P2-I8** richer email — part of I8 definition/build, not a later surprise |

## Next increment (definition locked — no build)

**P2-I7A AI Model Trace & Observability** — [definition](MBBS-P2_INCREMENT_7A_DEFINITION.md) · [PRD ingest](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md) · [MBRM v0.2 insertion](MBRM-001_v0.2_AI_TRACE_INSERTION.md). **DEFINITION LOCKED** 2026-08-15 (Q1–Q6). Inserted **before MBQL-001**. **No I7A runtime** until Tom explicitly authorizes I7A build. **No MBQL in I7A.**

Sequence after I7: **I7A → MBQL-001 → I8** (I8.5 remains after I8).
