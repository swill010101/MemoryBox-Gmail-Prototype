# MBBS-001 Increment 9 — Definition (review only — not build-authorized)

**Status:** **REVIEW ONLY** — awaiting explicit *Build Increment 9 only* authorization  
**Date:** 2026-08-10  
**Owner acceptance gate (proposed):** On FlightSim, Tom can create/import a **first-class Artifact** (with representation + label) **without developer intervention**, associate it thinly (**about** person and/or cited Evidence such as photo/video, and/or Story), find it via Ask and/or Library when associations allow, leave **unresolved context** explicit (no invented Place/Event), and keep originals untouched with provenance. Synthetic harnesses prove Artifact service, associations, search/cite, unresolved-context honesty, and provider-down degrade where applicable.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 9  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 1 (domain) · Increment 5 / 5A (Story / Journal patterns) · Increment 6 Person · **Increment 8 Library (ACCEPTED)** — Ask (I4) for searchable/citable earn-in  
**Prior:** [MBBS-001_INCREMENT_8_ACCEPTANCE.md](MBBS-001_INCREMENT_8_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization:** *Do not build* until Tom authorizes *Build Increment 9 only*.

---

## 0. Proposed locked decisions (for review)

| Topic | Decision |
|-------|----------|
| Product slice | **Artifact** as a first-class MemoryBox domain entity (not a Story subtype; not an Immich album dump) with **label**, optional narrative/description, **representation** (MB-managed file and/or referenced Evidence), and **thin associations** |
| About-graph (product truth) | MemoryBox associations are **about something**: **Person**, **photo/video Evidence**, **Artifact**, Story/Journal as narrative containers — not “narrator-only.” I9 productizes **Artifact** as an about-target and thin links among Artifact ↔ Person ↔ Evidence ↔ Story |
| Flows | **EF-06** thin (Artifact) + **EF-05 continued** thin (import/jobs where needed for Artifact representations) — not Guided Capture (11), not Export (12), not EVS-014 (10) |
| Primary EVS | **EVS-013** thin; foundation for later **004 / 010** (recipe / richer artifact) |
| Unresolved context | Artifact may exist with **incomplete** Place/Event/Person context. **Disclose** unresolved; **do not invent** missing context |
| Import jobs | Thin async **import/register** path for Artifact representations when needed (jobs table / processing state). UX shows processing. No full archive ingest platform |
| Search / cite | Artifact is **searchable** and **citable** in Ask (Evidence First). Library earn-in: Artifact cards when Person (or other locked filter) association exists — **do not** invent a second Library product |
| Person / Evidence / Story links | Thin `about_person` / `cites_evidence` / Story↔Artifact associations (or equivalent domain relationships). Narrator ≠ subject (I8 lesson stays) |
| Originals | MB-managed Artifact bytes are family-owned; referenced provider originals remain untouched. No Immich write-back |
| SMS | **OUT of I9** — remains deferred communications work (charter note tying SMS to “Inc 9” is superseded: I9 = Artifact). Must not drop SMS from P1 plan entirely |
| EVS-014 / Guided Capture / Export / Settings / multi-user / polish | **OUT** |
| Full recipe ontology / EVS-004/010 complete | **OUT** — foundation only |
| Prove | **`prove-artifact`** primary; I1–I8 proves remain runnable; FlightSim owner acceptance |
| Hosts (D7) | FlightSim app + PG; media paths config-only |

---

## 1. Problem / why now

Library (I8) browses life by **Person**. Stories/Journals exist. Photos/videos are Evidence via providers. Families still lack a first-class home for **things** — recipes, scanned letters, heirlooms, labeled objects — that are neither a Person nor a raw provider asset dump.

Without I9:

- EVS-013 stays unmet.  
- “About” collapses to Person-only in UX, contradicting the domain (about person **or** picture **or** video **or** artifact).  
- Risk of stuffing artifacts into Story bodies or Immich albums without MB provenance.

I9 productizes **Artifact + thin associations + searchable/citable presence**, with honest unresolved context.

---

## 2. Objective

1. **Artifact Service** — create/read/update (version or immutable revision policy thin); label; representation; provenance.  
2. **Thin associations** — Artifact ↔ Person; Artifact ↔ Evidence (photo/video/communication as applicable); Artifact ↔ Story (optional earn-in).  
3. **Import/register job** thin — async when representation ingest is non-trivial; processing state visible.  
4. **Ask + Library earn-in** — searchable/citable; Library can surface Artifact cards when Person filter (I8) associations allow — no second Gallery.  
5. Prove via **`prove-artifact`** + FlightSim owner path.

| Field | Content |
|-------|---------|
| **Modules** | Artifact Service; thin association APIs; optional import job; thin Artifact UX; Ask/Library earn-in |
| **Flows** | **EF-06**; **EF-05** continued thin |
| **EVSs in** | **EVS-013** thin (foundation for 004/010) |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for **I9-OWNER**; harness via **`prove-artifact`**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I9-A** | Artifact create with label + representation + provenance | `prove-artifact` |
| **I9-B** | Unresolved context allowed and disclosed (no invented Place/Event/Person) | Harness |
| **I9-C** | Thin associate Artifact → Person (`about_person` or equivalent) | Harness |
| **I9-D** | Thin associate Artifact → Evidence (photo and/or video external/Evidence ref) | Harness |
| **I9-E** | Optional Story association earn-in (Artifact cited by / linked from Story) | Harness |
| **I9-F** | Artifact searchable / citable in Ask without inventing content | Harness + FlightSim |
| **I9-G** | Library earn-in: Artifact modality/card appears under Person filter when associated | Harness / FlightSim |
| **I9-H** | Import/register job thin: non-trivial ingest is async; processing state visible | Harness |
| **I9-I** | Originals sacred: provider originals untouched; MB-managed bytes additive | Policy + harness |
| **I9-J** | Provider/job failure → visible degrade; product remains up | Harness |
| **I9-K** | No Immich/HVRT native schemas as Artifact SoT | Health / policy |
| **I9-OWNER** | FlightSim: create/import ≥1 real Artifact; label; associate Person and/or Evidence; find via Ask and/or Library; no developer intervention / SQL | Tom on FlightSim |
| **I9-L** | I1–I8 proves remain runnable | Prior prove commands |
| **I9-M** | Living specs | Decision log + acceptance report |
| **I9-N** | SMS not required for I9; still on P1 backlog | Note |

---

## 4. Scope

### In

- Artifact domain entity + service (PG authoritative)  
- Label + representation (MB-managed and/or referenced Evidence)  
- Thin associations: Person, Evidence (photo/video/…), Story earn-in  
- Unresolved context honesty  
- Thin import/register job path  
- Ask search/cite earn-in; Library Artifact card earn-in under existing Person filter  
- **`prove-artifact`** + FlightSim owner path  
- Thin functional Artifact UX (no polish)

### Out

| Out | Notes |
|-----|--------|
| Full recipe / cookbook product (EVS-004/010 complete) | Foundation only in I9 |
| Guided Capture (EF-11) | Increment 11 |
| EVS-014 cross-provider Person loop | Increment 10 |
| Export (EF-16) | Increment 12 |
| SMS ingest | Deferred communications — not Artifact |
| Immich write-back / provider mirror | Forbidden |
| Full knowledge-graph editor / Settings / multi-user / polish | Out |
| Replacing Library Person-required filter with Artifact-primary browse | Out of I9 (may earn later) |
| Bulk archive ingest platform | Out — thin jobs only |

---

## 5. Architecture notes (thin)

```
memorybox serve (FlightSim)
    ├─ /artifact/ui   ← I9 thin
    ├─ Artifact Service (PG)
    │     ├─ artifacts / representations / versions (thin)
    │     └─ relationships: about_person | cites_evidence | story links
    ├─ Ask earn-in (cite Artifact Evidence)
    └─ Library earn-in (Artifact cards under Person filter)
```

**About-graph reminder:** Narrator/author ≠ subject. Associating “about Eugene” or “about this photo” is explicit — same lesson as I8 Story→Library.

Demonstrator `artifact_label` concepts = mine for ideas only — not P1 SoT.

---

## 6. EVS scope (MBEVS-001 v0.8)

### 6.1 In (thin)

| EVS ID | Role in I9 |
|--------|------------|
| **EVS-013** | Artifact with representation + label; unresolved context allowed |

### 6.2 Out / later

| Slice | Increment / track |
|-------|-------------------|
| EVS-004 / 010 richer recipe | Later (foundation in I9) |
| EVS-014 | 10 |
| Guided Capture | 11 |
| Export | 12 |
| SMS | Later communications |

---

## 7. Build plan (only after *Build Increment 9 only*)

1. Domain migration: Artifact tables + relationship kinds as needed.  
2. Artifact Service (create/get/list; label; representation; provenance).  
3. Thin association APIs (Person, Evidence, Story earn-in).  
4. Import/register job thin + processing state.  
5. Ask cite/search earn-in; Library Artifact card earn-in.  
6. Thin `/artifact/ui`.  
7. **`prove-artifact`** + `--flightsim`.  
8. Confirm I1–I8 proves.  
9. Acceptance report; **stop**.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Premature breadth (full recipe ontology) | EVS-013 thin; 004/010 later |
| Stuffing artifacts into Story only | First-class Artifact entity |
| Invented Place/Event | Unresolved context disclosed |
| Second Library product | Earn-in under I8 Person filter only |
| SMS scope creep from old charter wording | Explicit OUT; keep on P1 backlog |
| Job UX invisible | Processing state required |

---

## 9. Open questions for Tom (resolve before or at build auth)

1. **Owner gate Artifact type:** one real scanned letter / recipe card / heirloom photo-as-artifact — which family object for FlightSim?  
2. **Representation default:** prefer MB-managed upload vs reference existing Immich/HVRT Evidence for I9-OWNER?  
3. **Versioning:** Story-like immutable versions on edit, or single mutable row + provenance note for P1 thin?  
4. **Library modality:** new `artifact` modality pill in I8 Library — confirm earn-in in I9 (recommended).  
5. **SMS:** confirm remains **out** of I9 (recommended; charter Inc-3 note was aspirational sequencing).

---

## 10. Authorization gate

**Status: REVIEW ONLY.**

Reply with **Build Increment 9 only** (and answers to §9 as needed) to authorize implementation.  
Do **not** begin Increment 10 / Guided Capture / Export without separate authorization.

---

## 11. Stop line

After review: no code until authorized. After acceptance: do **not** begin Increment 10+ without new authorization.

---

*End of Increment 9 definition — review only.*
