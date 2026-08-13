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
| 4 | Location pill | **D** — Location filter = has GPS/Place; Map toggle = spatial lens |
| 5 | Mockup PNG | **Parked / sent** |
| 6 | Route | **Evolve `/people/ui`** (`?person=` → Person Explorer) |

---

## Location pill — locked

**D:** Location filter = has location evidence; Map toggle = spatial lens on current set.

---

## Success criteria (short)

Person context persists; Person-scoped Ask = I4 shared state; Highlights ranked; mixed-media gallery + Timeline + Map; Shared Evidence Viewer restore; About / Family / Learn honest; FlightSim cases 1–13.

## Soft gap (not a hard blocker)

Stories / emails / journals may still associate by **name tokens** rather than person id in some retrieve paths. Do **not** invent separate Person IDs per evidence type — keep one MB Person continuum; harden id-keyed joins later.

## Sign-off

**Visual lock:** ACCEPTED · **Build:** APPROVED · **Location:** D locked
