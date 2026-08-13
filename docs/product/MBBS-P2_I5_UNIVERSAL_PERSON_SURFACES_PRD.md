# MBBS — P2-I5 Universal Person Surfaces · Product Request Document

**Status:** BUILD APPROVED (Tom 2026-08-13) · answers locked below  
**Date:** 2026-08-13  
**Owner:** Tom  
**Increment:** P2-I5 (MBRM-001A) — Universal Person Surfaces · F+U  
**Branch:** `cursor/p2-i5-universal-person-surfaces-3061` (from I4)

**Authority**
- Visual / interaction lock: approved mockup *Universal Person Surfaces* (Peggy Smith exemplar)
- Implementation directive: MEMORYBOX P2 — I5 UNIVERSAL PERSON SURFACES (2026-08-13)
- Roadmap: [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) § P2-I5
- UX: [MBUX-001 v0.4](MBUX-001_v0.4.md) (§4.3 People as anchors)
- Reuse: I4 shared Explore state — **no Person-only search fork**

---

## Locked answers (Tom 2026-08-13)

| # | Question | Decision |
|---|----------|----------|
| 1 | Highlights v1 | **Real ranking** (not identical to All Memories) |
| 2 | Theme | **Dark** Person surface |
| 3 | Audio tab | **Show now; empty OK** |
| 4 | Location pill | **Pending** — options below; provisional build = **D** |
| 5 | Mockup PNG | **Parked / sent** |
| 6 | Route | **Evolve `/people/ui`** (`?person=` → Person Explorer) |

---

## Location pill — need Tom pick

Mockup shows **both** filter pill “Location” **and** Gallery | Map toggle — they should differ.

| Option | Behavior |
|--------|----------|
| **A** | Has-location filter only (Gallery stays; hide items without GPS/Place) |
| **B** | Location pill opens Map mode (redundant with Map toggle) |
| **C** | Place picker / named Place refine |
| **D (recommended)** | **Location filter** = has location evidence; **Map toggle** = spatial lens on current set |

Reply `4=A|B|C|D` to lock. Building with **D** until then.

---

## Success criteria (short)

Person context persists; Person-scoped Ask = I4 shared state; Highlights ranked; mixed-media gallery + Timeline + Map; Shared Evidence Viewer restore; About / Family / Learn honest; FlightSim cases 1–13.

## Sign-off

**Visual lock:** ACCEPTED · **Build:** APPROVED · **Pending:** Location letter A/B/C/D
