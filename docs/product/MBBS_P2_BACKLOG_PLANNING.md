# MBBS — P2 backlog planning sequence

**Status:** Living parking note · **Updated:** 2026-08-14 (P2-I8.5 inserted after I8; Learn rail blocked)  
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

## Thin Settings (started 2026-08-14 — not I13)

Mature Settings remains **P2-I13 / P2-SET-01 / CAP-P2-023**. Tom authorized a **thin** `/settings/ui` for knobs already decided. First card: Home Videos physical library path. See [MBBS-P2_THIN_SETTINGS_VIDEO_SOURCES_PRD.md](MBBS-P2_THIN_SETTINGS_VIDEO_SOURCES_PRD.md).

Do not treat this as I13. Do not add provider catalogs, processing controls, or confidence dials here.

## P2-I8.5 — Face evidence ownership (inserted 2026-08-14)

**Authority:** [MBBS-P2_I8.5_FACE_EVIDENCE_OWNERSHIP_PRD.md](MBBS-P2_I8.5_FACE_EVIDENCE_OWNERSHIP_PRD.md) · [increment definition](MBBS-P2_INCREMENT_8.5_DEFINITION.md)  
**Sequence:** I6 → I7 SMS → I8 Email → **I8.5** → I9 Spoken  
**ID lock:** **P2-I8.5** (retired draft ID: I7.5). Executes after I8 acceptance, not between I7 and I8.

**No build** until I8 is ACCEPTED and Tom authorizes I8.5.

### Why it is parked here

FlightSim Learn (photo modal, Immich “ownership,” video Learn) still treats Immich face state as the working authority. That is a product-architecture gap, not a viewer polish issue. I8.5 imports Immich face observations into MB-owned records, switches overlays/recognition reads to those records, and makes owner corrections override later provider sync.

### Blocks

| ID | Theme | Disposition |
|----|--------|-------------|
| **P2-BL-I8.5-01** | Shared Evidence Viewer **Learn rail** face editing (Assign / Reassign / Adjust box / Unassign / Learn from this face) | **Blocked on I8.5 ACCEPTED.** Do not complete Learn-rail implementation against live Immich face rows. Current Explore Learn chrome is provisional. Follow-on only after I8.5 (which is after I8). |
| **P2-BL-I8.5-02** | Immich write-back of face boxes, assignments, merges, or recognition | **Forbidden.** Immich stays read-only. |

Do not reopen I5 for this. Do not treat I1 Immich face-asset earn-in as sufficient ownership.

