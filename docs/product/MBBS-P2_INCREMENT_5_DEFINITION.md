# MBBS — P2-I5 Universal Person Surfaces · Increment Definition / Acceptance

**Status:** **ACCEPTED** (2026-08-14 — Tom)  
**Authority:** [MBBS-P2_I5_UNIVERSAL_PERSON_SURFACES_PRD.md](MBBS-P2_I5_UNIVERSAL_PERSON_SURFACES_PRD.md) · MBRM-001A § P2-I5 · MBUX-001 v0.4 §4.3  
**Branch:** `cursor/p2-i5-universal-person-surfaces-3061` (from I4)  
**Depends on:** P2-I4 Mixed-Media Explore (shared Ask / Gallery / Timeline / Map / Evidence Viewer)

---

## What shipped (ACCEPTED)

- Person Explorer on `/people/ui?person=` (dark theme); admin form via `?admin=1`
- People are anchors — reuse I4 shared exploration state (no Person-only search fork)
- Highlights = real quality-first ranking (bulk recent + 10–20y reach-back); All Memories = full set
- Location **D** (has GPS/Place filter; Map = spatial lens)
- About / Family / Learn drawers; Audio empty OK
- Timeline: indicators clipped to track; outward handle pull / Reset restores full archive
- Soft gap retained: some story/email joins may still be name-token heavy (do not invent per-type Person IDs)

---

## Carry-forward / backlog (not ACCEPTED blockers)

| ID | Item | Notes |
|----|------|-------|
| **P2-BL-I5-01** | Immich **preferred person portrait** on Person Explorer header / curator avatar | Sue Will preferred face exists in Immich UI; MemoryBox still shows letter initial after I5 portrait endpoint + name-resolve attempts (2026-08-14). **Accepted with gap** — fix in a later thin slice; do not reopen I5. |

Full backlog parking: [MBBS_P2_BACKLOG_PLANNING.md](MBBS_P2_BACKLOG_PLANNING.md) § Post–I5 carry-forward.

---

## Authorization stop-line

| Step | Status |
|------|--------|
| PRD + locked answers (Highlights, dark, Audio, Location D, route) | **LOCKED** |
| Build | **AUTHORIZED** (2026-08-13) |
| Implementation | **COMPLETE** on `cursor/p2-i5-universal-person-surfaces-3061` |
| Founder FlightSim acceptance | **ACCEPTED** (2026-08-14 — Tom: “accepted, i5”) |
| Immich preferred portrait | **BACKLOG** P2-BL-I5-01 (not a reopen) |

P2-I5 is **ACCEPTED**. **P2-I6 Kinship** is **ACCEPTED** (2026-08-14). Next: [P2-I7 SMS/Text Evidence](MBBS-P2_INCREMENT_7_DEFINITION.md) (draft; no build until authorized).
