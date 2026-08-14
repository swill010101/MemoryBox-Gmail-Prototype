# MBBS — P2-I5 Universal Person Surfaces · Product Request Document

**Status:** **ACCEPTED** (Tom 2026-08-14) · answers locked below  
**Date:** 2026-08-13 (build) · 2026-08-14 (accepted)  
**Owner:** Tom  
**Increment:** P2-I5 (MBRM-001A) — Universal Person Surfaces · F+U  
**Branch:** `cursor/p2-i5-universal-person-surfaces-3061` (from I4)  
**Acceptance record:** [MBBS-P2_INCREMENT_5_DEFINITION.md](MBBS-P2_INCREMENT_5_DEFINITION.md)

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
| 5 | Mockup PNG | **RECEIVED** (Peggy Smith exemplar · dark Person Explorer) |
| 6 | Route | **Evolve `/people/ui`** (`?person=` → Person Explorer) |

### Highlights ranking (locked refinement · Tom 2026-08-14)

**Quality first**, then year shape:
1. Prefer clear, focused, face-forward photos (large/centered face box when known; high identity/confidence score when present).
2. Bulk of the set from recent years (~last 10).
3. Still reach back ~10–20 years with best-per-year picks from that archive window.
4. All Memories remains the full eligible set (no ranking cull).

### Timeline indicators (locked rule · Tom 2026-08-14)

Timeline density dots / indicators **must never exceed the timeline track**. Zoom clears and re-plots only in-view markers. While zoomed, a slight outward pull on the left or right handle restores the full archive span (Reset does the same).

---

## Location pill — locked

**D:** Location filter = has location evidence; Map toggle = spatial lens on current set.

---

## Success criteria (short)

Person context persists; Person-scoped Ask = I4 shared state; Highlights ranked; mixed-media gallery + Timeline + Map; Shared Evidence Viewer restore; About / Family / Learn honest; FlightSim cases 1–13.

## Soft gap (not a hard blocker)

Stories / emails / journals may still associate by **name tokens** rather than person id in some retrieve paths. Do **not** invent separate Person IDs per evidence type — keep one MB Person continuum; harden id-keyed joins later.

## Accepted with known backlog (Tom 2026-08-14)

| ID | Gap | Disposition |
|----|-----|-------------|
| **P2-BL-I5-01** | Immich preferred person portrait not showing on Person Explorer (Sue Will has preferred face in Immich; MB still shows letter initial) | **Backlog** — not an I5 reopen. See [MBBS_P2_BACKLOG_PLANNING.md](MBBS_P2_BACKLOG_PLANNING.md). |

## Sign-off

**Visual lock:** ACCEPTED (Peggy Smith mockup on file) · **Build:** APPROVED · **Location:** D locked  
**Increment:** **ACCEPTED** (2026-08-14 — Tom)
