# MBBS — P2 backlog planning sequence

**Status:** Living parking note · **Updated:** 2026-08-24 (I10A.2 PRD **ready for founder lock**; not build-authorized)  
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
| **P2-BL-I8-01** | I8 email ingest must include **attachment files up front** | I7 accepted CSV-only; attachment bytes were missing and had to be parked. Do not repeat that gap for email. | **Absorbed in P2-I8 ACCEPTED** 2026-08-18 |

## Post–I8 carry-forward (ACCEPTED with gap)

P2-I8 Richer Email is **ACCEPTED** (2026-08-18 — Tom: FlightSim §9 all pass). The following did **not** block acceptance and must not reopen I8:

| ID | Theme | Evidence | Suggested home |
|----|--------|----------|----------------|
| **P2-I8A** | Unified Communications Gallery & Timeline Precision | Founder: combined day cards + density-aware aggregation + Calendar filter + Attachments only; screens 00–11 accepted | **ACCEPTED** 2026-08-19 — [I8A definition](MBBS-P2_INCREMENT_8A_DEFINITION.md) |
| **P2-BL-I8-02** | Ask “how many times did I send an email to Peggy?” must **lock Peggy George** (canonical Person) **before** count + Gallery | Owner 2026-08-18: curator count + Gallery showed email and it worked, but first-name Peggy was not resolved to Peggy George first, so extra mail that is not Peggy George was included. Does not reopen I8. | **Absorbed in P2-I8A ACCEPTED** 2026-08-19 |

## Next increment

**P2-I8 Richer Email** — [definition](MBBS-P2_INCREMENT_8_DEFINITION.md) · [PRD](MBPRD-P2-I8_RICHER_EMAIL.md). **ACCEPTED** 2026-08-18.

**P2-I8A Unified Communications Gallery & Timeline Precision** — [definition](MBBS-P2_INCREMENT_8A_DEFINITION.md) · [PRD](MBPRD-P2-I8A_UNIFIED_COMMS.md). **ACCEPTED** 2026-08-19. **P2-BL-I8-02 absorbed.**

**P2-I9 Spoken Moments** — [definition](MBBS-P2_INCREMENT_9_DEFINITION.md). **BUILD AUTHORIZED** 2026-08-20 (runtime on this tree; FlightSim owner ACCEPTED still pending).

**P2-I10A Stories** — [definition](MBBS-P2_INCREMENT_10A_DEFINITION.md) · [PRD](MBPRD-P2-I10A_STORIES.md). **ACCEPTED** 2026-08-22 (Tom: “i10A is accepted”). **Not I11.**

**Sequence after I10A (owner 2026-08-23, I10B already shipped):** I10A.1 Person Profile Editor → I10A.2 Unified Voice Capture & Transcription (Stories first) → I10C Journal → I11 only after those plus required transcription/recognition work. I10B **ACCEPTED** 2026-08-23.

**P2-I10B Artifacts** — [definition](MBBS-P2_INCREMENT_10B_DEFINITION.md) · [PRD](MBPRD-P2-I10B_ARTIFACTS.md) · [assessment](MBAS-P2-I10B_ASSESSMENT_RECONCILIATION.md). **ACCEPTED** 2026-08-23 (Tom: “i10B is accepted”). Tell its story opens the shared Story editor (`?artifact=`); the recorder is I10A.2. Implementation: `cursor/p2-i10b-artifacts-49da`.

**P2-I10A.1 Person Profile and Editor** — [PRD](MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md) · [screen contract](MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md) · [acceptance](MBAT-P2-I10A1_ACCEPTANCE.md). **ACCEPTED** 2026-08-24 (Tom: “i10a.1 is accepted”). About = `/people/{id}/edit?view=1`; Edit = `/people/{id}/edit`. `prove-person-i10a1` remains the regression gate. No Immich write-back. Do not reopen.

**P2-I10 Cross-Source Correlation** — [definition](MBBS-P2_INCREMENT_10_DEFINITION.md) · [PRD](MBPRD-P2-I10_CROSS_SOURCE.md). **ACCEPTED** 2026-08-21 (Tom: “i10 has been accepted”). **I11 narrative is not I10.**

## Post–I8B park (do not reopen I8B for playback UX)

I8B stores appearance `start_sec` / `end_sec` and posters at start. Explore seeks to start and **does not stop**. Owner 2026-08-20: HVRT-style visit playback as a **view into the original** (no physical cut).

| ID | Theme | Evidence | Suggested home |
|----|--------|----------|----------------|
| **ACR-P2-001** | Person appearance view: play start → stop, then end; gallery thumb = frame at `start_sec` | Card already has the range; player ignored stop. No derived clip files. | [MBACR-P2-001](MBACR-P2-001_PERSON_APPEARANCE_VIEW.md) — **BUILD AUTHORIZED** 2026-08-20 |
| **ACR-P2-001-A** | Continue on tape after stop | Learn / watch past `end_sec` on the same original | Work list on that ACR; **not now** |

## Next increment

**Next:** **I10A.2** — [PRD](MBPRD-P2-I10A2_SPEECH_INPUT.md) **ready for founder lock**, **not build-authorized**. Shared narrative editor first; authored-memory vs convenience speech. Then **I10C** Journal. **I11 is not authorized** until I10A + I10A.1 + I10A.2 + I10B + I10C and required transcription/recognition work. Face-SoT (**I8.5**) **later**. **P2-I4 ACCEPTED**; Explore visual polish is **P2-BL-I4-01**. **ACR-P2-001** is parked and is not I10. Do not reopen I10A.1.
