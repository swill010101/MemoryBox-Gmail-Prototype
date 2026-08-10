# MBBS-001 Increment 9 — Definition (final review — decisions locked; not build-authorized)

**Status:** **FINAL REVIEW** — decisions locked from owner answers; awaiting explicit *Build Increment 9 only*  
**Date:** 2026-08-10  
**Owner acceptance gate (locked):** On FlightSim, Tom can create a **first-class Artifact** for a **real physical family keepsake** (pocket-watch pattern preferred: **≥2** MB-managed representation images where practical) **without developer intervention** — upload/preserve representation(s) on **media-server durable storage**, label + basic **kind**, optional description, **Person association optional** (not required for Library visibility), optionally capture/associate a **Story** (“why it matters”) via earned-in I5/I5A Capture/STT + explicit Save, browse the Artifact as a first-class **Library `artifact` modality card even with no Person**, open/view representation(s), retrieve via Ask by Artifact identity/metadata (not filename-as-meaning), inspect honest provenance, and leave unresolved Place/Event/Person context **explicit**. Synthetic harnesses prove multi-representation, metadata revision without byte duplication, unresolved-context honesty, Library-without-Person, and failure degrade.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 9  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 1 (domain) · Increment 5 / 5A (Story + Capture/STT patterns) · Increment 6 Person · **Increment 8 Library (ACCEPTED)** · Ask (I4)  
**Prior:** [MBBS-001_INCREMENT_8_ACCEPTANCE.md](MBBS-001_INCREMENT_8_ACCEPTANCE.md) — **ACCEPTED**  
**Next after acceptance:** [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md) — Person Profile (**REVIEW ONLY**)  
**Authorization:** *Do not build* until Tom authorizes *Build Increment 9 only*.

---

## 0. Locked decisions (final review)

| Topic | Decision |
|-------|----------|
| Product slice | **Artifact** = conceptual/physical/documentary object being cataloged. **Representation** = preserved media that depicts or contains it. **One Artifact → one or more representations.** Never mint a new Artifact merely because another file was uploaded |
| Artifact ≠ file | Pocket-watch pattern is the teaching example: one Artifact, multiple photos (front/back/engraving). Letter → pages + envelope. Document → PDF/scans. Photograph-of-object is a **kind**, not “each JPEG is an Artifact” |
| Kind / category | Small extensible P1 set: **keepsake/object · letter · document · recipe card · clipping · photograph-of-object · other**. Not a recipe ontology or taxonomy project |
| Representation sources | **Owner gate requires MB-managed upload** (proves cigar-box preserve). **Also support** referencing existing Immich/HVRT Evidence as a representation — without treating provider originals as MB-managed |
| Durable storage (D7) | MB-managed Artifact **original bytes** live on **configurable media-server storage** — **not** FlightSim local disk as archive SoT. FlightSim = app/processing host. Paths config-only |
| Integrity | For every MB-managed representation: preserve original bytes; compute/store **integrity hash**; **never silently overwrite** original; retain upload/provenance metadata; derived thumbs/OCR/indexes **rebuildable** |
| Versioning | **Stable Artifact identity**; **immutable original representations**; **immutable metadata revisions** (label/description/kind/context). Editing metadata must not erase prior owner-authored metadata and must **not** duplicate representation bytes. Smallest clean model after Story/Journal patterns at build time |
| Library | **`artifact` is a first-class Library modality** in I9. Artifacts **must be browsable with NO Person association**. Person filter **narrows** when about/owner/person links exist — Person is **not** required for visibility. Same I8 unified card/read API — **no second Artifact Gallery** |
| Person filter interaction | I8 Person-required browse remains for Person-centric Library use. Artifact browse/list path must allow **Person-optional** (e.g. modality=`artifact` without `person_id`, or dedicated Artifact library entry that uses the same card API). Do not invent a second product |
| Associations | Thin domain relationships: Artifact ↔ **Person**; ↔ **Evidence/media**; ↔ **Story**; ↔ **Place/Event** where already supported. Unresolved context allowed; **never invent** missing context |
| Optional voice Story (EVS-013) | Earn-in **existing I5A Capture/STT** — no Artifact-specific STT. Flow: create Artifact → add representation(s) → label/description → optional “tell me why this matters” voice → STT review/edit → **explicit Save as Story** → link Story ↔ Artifact. Typed Story association also works. Do **not** stuff substantive testimony into Artifact metadata |
| Ask | Retrieve by Artifact **identity / metadata / relationships / representations** — not filename-as-meaning. Architecture should support: “Show me Grandpa’s pocket watch,” “Tell me the story about Grandpa’s pocket watch,” “Show me artifacts that belonged to Grandpa.” Full EVS-004/010 recipe intelligence **OUT** |
| Import jobs | Thin async register/ingest when needed; processing state visible |
| SMS | **OUT of I9**; **remain on P1 backlog** |
| EVS-014 / Guided Capture / Export / Settings / multi-user / polish / Immich write-back / full KG editor / full recipe ontology | **OUT** |
| Prove | **`prove-artifact`**; I1–I8 proves remain runnable; FlightSim owner gate |
| Hosts | FlightSim app + PG; **media-server** durable Artifact originals (config) |

---

## 1. Problem / why now

Library (I8) browses life primarily by **Person**. Stories exist. Provider media is Evidence. Families still lack a first-class home for **things** — pocket watches, letters, clippings, recipe cards — that are **not** “a file” and **not** a Person.

Without I9:

- EVS-013 stays unmet.  
- Risk of one-JPEG-per-Artifact mistakes and Immich-album dumps without MB provenance.  
- “About” collapses to Person-only, contradicting domain truth (about person **or** picture **or** video **or** artifact).

I9 productizes **Artifact + multi-representation + durable preserve + Library/Ask earn-in**, with honest unresolved context.

---

## 2. Objective

1. **Artifact Service** — stable identity; kind; label; description; provenance; metadata revisions.  
2. **Representations** — one-to-many; MB-managed upload (owner gate) + Evidence reference; integrity hash; media-server durable store.  
3. **Thin associations** — Person (optional), Evidence, Story; Place/Event when known.  
4. **Optional voice → Story** via I5A Capture/STT earn-in + explicit Save + link.  
5. **Library** — first-class `artifact` modality; **visible without Person**.  
6. **Ask** — Artifact identity/metadata/relationship retrieve (thin).  
7. Prove via **`prove-artifact`** + FlightSim owner path.

| Field | Content |
|-------|---------|
| **Modules** | Artifact Service; representation store (media-server); associations; Capture/STT earn-in → Story; Library `artifact` modality; Ask earn-in; thin `/artifact/ui` |
| **Flows** | **EF-06**; **EF-05** continued thin; EVS-013 optional voice via Story |
| **EVSs in** | **EVS-013** thin (foundation for 004/010) |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for **I9-OWNER**; harness via **`prove-artifact`**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I9-A** | Create Artifact with kind + label + ≥1 representation + provenance | Harness |
| **I9-B** | One Artifact supports **multiple** representations (no per-file Artifact split) | Harness |
| **I9-C** | MB-managed upload preserves bytes on **media-server** config root; integrity hash stored; no silent overwrite | Harness + FlightSim |
| **I9-D** | Referenced Immich/HVRT Evidence representation supported (provider originals untouched) | Harness |
| **I9-E** | Metadata revision immutable/provenance-preserving; representation bytes not duplicated on label edit | Harness |
| **I9-F** | Unresolved Place/Event/Person disclosed; never invented | Harness |
| **I9-G** | Associate Artifact → Person (optional) | Harness |
| **I9-H** | Associate Artifact → Evidence / Story (typed Story link) | Harness |
| **I9-I** | Optional voice path: Capture/STT (I5A) → explicit Save Story → link Artifact (architecture proven if practical without new research) | Harness / FlightSim |
| **I9-J** | Library: `artifact` modality card; **browsable with no Person association** | Harness + FlightSim |
| **I9-K** | Person filter narrows Artifact results when associated; does not gate visibility | Harness |
| **I9-L** | Open/view representation from Library/Artifact UI | FlightSim |
| **I9-M** | Ask retrieves by Artifact identity/metadata/relationships (not filename-as-meaning) — thin | Harness + FlightSim |
| **I9-N** | Job/provider failure → visible degrade; product up | Harness |
| **I9-O** | No Immich/HVRT schemas as Artifact SoT | Policy / health |
| **I9-OWNER** | Real physical keepsake; ≥2 representations preferred; label; Person optional; optional Story; Library Artifact card without requiring Person; Ask retrieve; provenance honest; no SQL/dev intervention | Tom on FlightSim |
| **I9-P** | I1–I8 proves remain runnable | Prior proves |
| **I9-Q** | Living specs | Decision log + acceptance |
| **I9-R** | SMS out of I9; still on P1 backlog | Note |

---

## 4. Scope

### In

- Artifact entity (PG) distinct from Representation  
- Multi-representation (MB-managed + Evidence reference)  
- Basic kind set (keepsake/object, letter, document, recipe card, clipping, photograph-of-object, other)  
- Durable media-server storage for MB-managed originals + integrity hash  
- Immutable representation bytes; immutable metadata revisions  
- Associations: Person (optional), Evidence, Story; Place/Event when known  
- Optional voice → Story via I5A Capture/STT earn-in  
- Library first-class `artifact` modality; **Person not required**  
- Ask thin retrieve by Artifact meaning  
- Thin `/artifact/ui`  
- **`prove-artifact`** + FlightSim owner path  

### Out

| Out | Notes |
|-----|--------|
| Full recipe / cookbook ontology (EVS-004/010 complete) | Kind=`recipe card` only |
| EVS-014 cross-provider Person | Increment 10 |
| Person Profile / kinship (9A) | Increment 9A |
| Guided Capture (EF-11) | Increment 11 |
| Export (EF-16) | Increment 12 |
| SMS ingest | P1 backlog — not I9 |
| Immich write-back / provider mirror | Forbidden |
| Second Artifact Gallery product | Forbidden |
| Full knowledge-graph editor / Settings / multi-user / polish | Out |
| Artifact-specific STT engine | Reuse I5A Capture/STT |
| FlightSim-local disk as Artifact archive SoT | Forbidden |
| Bulk archive ingest platform | Thin jobs only |

---

## 5. Architecture notes (thin)

```
FlightSim (app / processing)
    ├─ /artifact/ui
    ├─ Artifact Service (PG)
    │     ├─ artifacts (stable id, kind, label, description, current_metadata_revision, …)
    │     ├─ artifact_metadata_revisions (immutable prior owner metadata)
    │     ├─ artifact_representations (1..N; mb_managed | evidence_ref; content_hash; …)
    │     └─ relationships: about_person | cites_evidence | about_artifact / story links | place/event when known
    ├─ Capture/STT (I5A) → Story Save → link Artifact
    ├─ Library cards (I8 API) + modality=artifact (Person optional path)
    └─ Ask earn-in (Artifact identity/metadata)

media-server (durable SoT for MB-managed representation originals)
    └─ configurable Artifact media root (D7 — no hard-coded host/paths in logic)
```

**Story/Journal pattern to inspect at build:** `story_versions` / `journal_versions` = immutable body revisions; I9 mirrors for **metadata** while keeping **representation blobs** single-instance + hash.

Demonstrator `artifact_label` = mine for ideas only — not P1 SoT.

---

## 6. EVS scope (MBEVS-001 v0.8)

### 6.1 In (thin)

| EVS ID | Role in I9 |
|--------|------------|
| **EVS-013** | Box a keepsake, label it, optional voice story — multi-rep Artifact; voice → Story earn-in |

### 6.2 Out / later

| Slice | Increment / track |
|-------|-------------------|
| EVS-004 / 010 richer recipe | Later |
| EVS-014 | 10 |
| Person profile / “my father” | **9A** |
| Guided Capture | 11 |
| Export | 12 |
| SMS | Later communications |

---

## 7. Owner gate (I9-OWNER) — locked preference

**Preferred object:** real physical keepsake in the **pocket-watch pattern** (≥2 photos/files). Alternate meaningful physical family object OK if pocket watch unavailable.

**Must prove without developer intervention:**

1. Create Artifact (+ kind)  
2. Upload/preserve **≥1** representation (prefer **≥2**) to durable media-server store  
3. Label (+ optional description)  
4. Associate Person **if known** — **not required**  
5. Optionally associate/create Story (typed and/or voice→STT→Save) about why it matters  
6. See Artifact as **Library Artifact card** (works **without** Person)  
7. Open/view representation(s)  
8. Retrieve Artifact via Ask  
9. Inspect honest provenance  
10. Unresolved context remains explicit  

Harness covers: multi-rep, metadata revision without byte dup, unresolved context, Library-without-Person, failure degrade.

---

## 8. Build plan (only after *Build Increment 9 only*)

1. Inspect Story/Journal versioning + domain schema; choose smallest metadata-revision + representation model.  
2. Migration: artifacts, representations, metadata revisions, kinds, hashes, storage URIs.  
3. Configurable media-server Artifact root (D7); upload + hash + no overwrite.  
4. Artifact Service APIs (CRUD thin; multi-rep add; associate).  
5. Evidence-ref representation path.  
6. Library: `artifact` modality + Person-optional browse path on unified cards API.  
7. Ask earn-in (identity/metadata/relationships).  
8. Optional voice → I5A Capture/STT → Story Save → link.  
9. Thin `/artifact/ui`.  
10. **`prove-artifact`** + `--flightsim`.  
11. Confirm I1–I8 proves.  
12. Acceptance; **stop** (then 9A review/build separately).

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| One-file-per-Artifact mistake | Locked Artifact vs Representation |
| FlightSim disk as archive | Media-server durable root required |
| Second Gallery | Unified Library cards only |
| Narrative stuffed into Artifact fields | Voice/testimony → Story |
| Recipe ontology creep | Small kind enum only |
| SMS / EVS-014 pull-in | Hard OUT |
| Metadata edit clones blobs | Revision model forbids byte dup |

---

## 10. Open questions (residual — non-blocking unless Tom objects)

§9 owner answers are **locked** (keepsake multi-photo; MB-managed upload for gate; immutable metadata revisions + immutable originals; Library modality without Person; SMS out).

Residual for build-time only:

1. Exact media-server Artifact root env name / layout (ops).  
2. Exact metadata revision table shape after Story/Journal inspection.  
3. Library API shape for Person-optional Artifact browse (extend `GET /library/cards` vs thin companion query — must remain one card model).

---

## 11. Authorization gate

**Status: FINAL REVIEW — decisions locked. No implementation yet.**

Reply with **Build Increment 9 only** to authorize code.  
Do **not** begin Increment 9A / 10 / Guided Capture / Export under this authorization.

---

## 12. Stop line

After I9 acceptance: **Increment 9A** (Person Profile) is next review/build track, then **Increment 10** (EVS-014). No silent expansion into recipe ontology, SMS, or Export.

---

*End of Increment 9 definition — final review; do not build until authorized.*
