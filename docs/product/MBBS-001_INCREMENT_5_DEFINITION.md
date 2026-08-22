# MBBS-001 Increment 5 — Definition

**Status:** **ACCEPTED**  
**Date:** 2026-08-09  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5  
**Acceptance:** [MBBS-001_INCREMENT_5_ACCEPTANCE.md](MBBS-001_INCREMENT_5_ACCEPTANCE.md)  
**Depends on:** Increment 1 · Increment 4 (accepted)

---

## Locked decisions (as built)

| Topic | Decision |
|-------|----------|
| Product slice | Story service + EF-10 + first-class Ask retrieval modality (no silo) |
| STT / voice | **OUT** |
| Journal | **OUT** → **5A** |
| Ask blend | All applicable modalities + provenance labels |
| Story retrieval | Direct `stories` / `story_versions` (+ relationships) |
| Associations | I1 `narrator_person_id` + `relationships` (`about_person`, `cites_evidence`) |
| Acceptance | Synthetic automated + real owner Story on FlightSim UX; opaque reports only |
| AI | Never silently become Story; never auto-save |

Owner-authored Story content is provenance-bearing recollection and may be saved/retrieved without independent corroborating archive Evidence. Ask attribution distinguishes recollection vs archive Evidence vs AI.

---

## Authorization after acceptance

Increment 5 is **ACCEPTED**. Do **not** begin Increment **5A** (Journal) or Increment **6** without explicit authorization.
