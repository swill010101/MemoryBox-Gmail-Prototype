# MBBS-001 Increment 5 — Definition (locked · authorized to build)

**Status:** **LOCKED — BUILD AUTHORIZED** (*Build Increment 5 only*)  
**Date:** 2026-08-09  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**Depends on:** Increment 1 (domain + relationships) · Increment 4 Ask (accepted)  
**Prior increment:** [MBBS-001_INCREMENT_4_ACCEPTANCE.md](MBBS-001_INCREMENT_4_ACCEPTANCE.md) — **ACCEPTED**  
**Acceptance:** [MBBS-001_INCREMENT_5_ACCEPTANCE.md](MBBS-001_INCREMENT_5_ACCEPTANCE.md) (created at prove)

---

## 0. Locked decisions (build freeze)

| Topic | Decision |
|-------|----------|
| Product slice | Story service + EF-10 + **first-class Ask retrieval modality** (no silo) |
| STT / voice | **OUT** |
| Journal | **OUT** → **5A** |
| Ask blend | Return **all applicable modalities** together with clear provenance labels (I4-style) |
| Story retrieval mechanism | Query **`stories` / `story_versions` (+ relationships) directly** in Ask — do **not** require `story_passage` Evidence materialization for I5 |
| Associations | I1 `narrator_person_id` + `relationships` (`about_person`, `cites_evidence`); Place/Event via same graph if needed; **STOP on domain gap** (none for I5 minimum) |
| Acceptance | Synthetic automated + ≥1 real owner Story on FlightSim UX; opaque reports only |
| AI | Never silently become Story; never auto-save |
| Out | Journal, STT, Guided Capture, SMS, HVRT/video, Person teach/merge, multi-user, visual polish |

---

## 1–8. Normative content

Same as prior review draft: objectives I5-A…L, version semantics, I5-E provenance (owner recollection is provenance-bearing; no corroboration required to save/retrieve), Ask no-silo rules, I1 association table — **unchanged in meaning**. See git history `3131a0d` for full narrative sections retained below in condensed form.

### Objective
Owner-saved Stories with immutable versions; **current** Story is a first-class Ask modality alongside Evidence and photos.

### Version semantics
Explicit Save · immutable priors · current default · prior retrievable · no AI auto-save · edit→new version.

### Provenance (I5-E)
Distinguish owner/narrator recollection · independently corroborating archive Evidence · AI-generated/inferred (never auto-persist as Story).

### Ask
After Save, exploratory know-about retrieves current Story with other modalities; narrowed intents still win; no Story silo.

### Associations (I5 minimum)
Narrator + Story↔Person + Story↔Evidence via I1 model.

### Acceptance corpus
Synthetic (generalized subjects ≠ real owner Story) + real FlightSim owner-saved Story; reports: opaque IDs/counts/status only.

---

## 9. Authorization

**Build Increment 5 only** is authorized. Do **not** begin 5A / Inc 6 / polish without explicit authorization.
