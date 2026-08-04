# MB-RECONCILE-001 — Core Terminology and Principles

| Field | Value |
|-------|--------|
| **Doc ID** | MB-RECONCILE-001 |
| **Title** | Core Terminology and Principles |
| **Version** | 0.1 |
| **Status** | Binding — terminology and conflict resolutions for the core product set |
| **Authority** | Does not supersede Founder's Book or MBPS on product intent. Records shared glossary and locked conflict resolutions across MB-FB-001, MBPS-001, MBUX-001, MBKM-001, MBMS-001, and MBIA-001. Domain glossary-of-record rules below apply when definitions clash. |
| **Scope** | Terminology + principles alignment only. No schema, UI, or full document rewrites. |

---

## 1. Purpose and authority

Tom asked to reconcile **Founder's Book, MBPS, MBUX, MBKM, MBMS, and MBIA** for consistent terminology and principles. This document is the binding reconciliation: shared terms, principle alignment, and conflict resolutions.

### Document hierarchy (unchanged)

```
Founder's Book (MB-FB-001)
  → MBPS-001
    → MBUX-001 · MBKM-001 · MBMS-001 · MBIA-001  (peers under MBPS for their domains)
      → MBX-A-*
```

| Doc | Domain |
|-----|--------|
| MB-FB-001 | Why / philosophy |
| MBPS-001 | WHAT — product capability names |
| MBUX-001 | Experience behavior / conversation / copy |
| MBKM-001 | Conceptual vocabulary (knowledge concepts) |
| MBMS-001 | Mental model — anchors vs supporting vs lenses |
| MBIA-001 | Discovery / IA flow — entry, layers, modes |

### Conflict rule

1. **Higher wins on product intent** (FB → MBPS → domain peers → MBX-A-*).
2. For **term definitions**, the glossary-of-record wins for its domain:
   - **MBKM** — knowledge concepts
   - **MBMS** — anchors vs supporting vs lenses
   - **MBIA** — entry / discovery / modes structure
   - **MBUX** — conversation, copy, behavior
   - **MBPS** — product capability names
3. Where MBX-A-* is more specific on Evidence-First mechanics (Facts / Observations / Inferences / Unknowns), that specificity stands unless a higher document contradicts it.
4. This reconcile doc **records which wins when they clash**; it does not invent new product law above FB/MBPS.

---

## 2. Term glossary

Canonical definition · **Owner** · Aliases / forbidden confusions.

### Anchors and knowledge concepts

| Term | Canonical definition | Owner | Aliases / forbidden confusions |
|------|----------------------|-------|--------------------------------|
| **Person** | A human being (living or deceased; known or initially unknown). Accumulates stories, relationships, places, moments, artifacts, and memories. | MBKM | Not merely a face or contact card. |
| **People** | The Person anchor as experienced in the mental model / IA. | MBMS / MBIA | One of four anchors. |
| **Story** | Human/curated container of meaning. First-class. Connects people, places, moments, artifacts, evidence. | MBKM (concept); MBMS (anchor) | **Not** Narrative. FB: “Stories, written by a human, are first-class citizens.” |
| **Narrative** | AI assembly / explanation from evidence in response to a question. | MBPS / MBIA (discovery loop) | **Not** Story. UX may say “story” colloquially; product model keeps the split. |
| **Moment** | A meaningful period of time (birthday, vacation, deployment, wedding…). Often contains many evidence items. | MBKM | Anchor (MBMS/MBIA). |
| **Place** | A location that carries meaning — not merely coordinates. | MBKM | Anchor (MBMS/MBIA). |
| **Artifact** | Something intentionally preserved / meaningful keepsake (photo, recipe, pocket watch, letter, medal…). Objects become meaningful through stories. | MBKM | Absorbs Founder's **Thing** for vocabulary. Roles overlap with Media/Evidence — see conflict register. |
| **Thing** | Legacy Founder's Book term for meaningful non-folder objects. | FB (legacy) | **Fold into Artifact** for vocabulary. Do not treat as a fifth parallel object type beside Artifact. |
| **Evidence** | Epistemic support role — anything supporting understanding (photos, video, audio, documents, OCR, transcripts, calendar…). Supports stories; never replaces them. | MBKM | Role, not a duplicate object type vs Media/Artifact. |
| **Media** | Physical or digital representation (image, video, audio, document). | MBKM | Representation role; “Media is evidence, not understanding.” |
| **Relationship** (legacy MBKM wording) | In MBKM 0.1: how two or more people are connected. | MBKM 0.1 | Prefer the split below until MBKM 0.2. |
| **SocialRelationship** | Typed Person–Person social tie (father, friend, mentor…). | Reconcile → MBKM 0.2 | What MBKM 0.1 mostly means by “Relationship.” |
| **KnowledgeLink** | Typed edge among concepts other than (or beyond) Person–Person social ties (e.g. Story–Place, Artifact–Moment). | Reconcile → MBKM 0.2 | Do not overload “Relationship” for all graph edges. |
| **Conversation** | Human interaction (written, spoken, recorded); also the primary UX/IA entry point. | MBKM (concept); MBMS/MBIA (front door) | Capability/entry, not an anchor. |
| **Collection** | Meaningful grouping that emerges from life — not a folder. As object: can exist. As “Collections” in Timeline/Search/filter UI: a **lens**. | MBKM (object); MBMS/MBIA (lens when viewing) | Reconcile names: object vs lens. |
| **Tradition** | Recurring family experience connecting generations. | MBKM | Supporting concept. |
| **Season** | Life-season context (not merely weather). | MBKM | Supporting / contextual. |
| **Timeline** | Perspective on time; every Person/Story/Place/Relationship/Collection can have one. | MBKM | **Lens/view by default**, not a peer destination to the four anchors (MBMS/MBIA). |
| **Narrator** | Individual telling the story; perspective is preserved (Rick's / Tom's / Sue's story about Peggy). | MBKM | Role on telling; related to Contributor. |
| **Memory** | Human interpretation of events; may stand with or without evidence; preserve uncertainty when appropriate. | MBKM | Not interchangeable with Story or Narrative. |
| **Life Chapter** | Supporting first-class concept (MBMS). | MBMS | **Not** a fifth anchor until product decides. |
| **Contributor** | Person who adds memories, stories, annotations. | MBPS | **Role on Person**, not a separate species of human. |
| **User** | Current operator of the system; orientation of session/privacy. | MBPS | Role on Person (or session), not a graph entity competing with Person. |
| **Four anchors** | People, Stories, Moments, Places. | MBMS / MBIA | Destinations of memory. Other MBKM concepts are supporting or lenses and must not compete as primary destinations. |

### Claim labels and trust

| Term | Canonical definition | Owner | Aliases / forbidden confusions |
|------|----------------------|-------|--------------------------------|
| **Facts / Observations / Inferences / Unknowns** | Engineering/product epistemic quartet (MBX-A-001 MB-P-008). | MBX-A-001 | UX uses **human phrasing** (MBUX). Never present raw “Confidence 71%” as the primary trust signal. |
| **Evidence visibility** | Evidence is **invisible by default** in presentation; **always available on request** for trust — never hidden. | MB-RECONCILE (MBMS §6 ↔ MBUX Trust Is Visible) | “Invisible” ≠ “unavailable.” |

### Capability / experience terms (thin)

| Term | Canonical definition | Owner | Notes |
|------|----------------------|-------|-------|
| **Capture / Discover / Teach / Learn / Remember / Share** | Product capability groups. | MBPS | Capability names of record. |
| **Guided Exploration / Explorer / Contributor / Family / Underage / Administrator** | Modes that change experience, never the archive. | MBIA (structure); MBMS (subset) | MBUX elaborates behavior. |
| **Lens** | Changes how visitors view the archive (Timeline, Search, Review & Learn, Favorites, Collections-as-filter, Expert tools). Not a destination. | MBMS / MBIA | |
| **Review & Learn** | Stewardship entry / lens for improving the archive. | MBIA / MBMS | Not primarily discovery. |

---

## 3. Principles map

Shared principle IDs for cross-document alignment. Sources are digests of governing wording — FB and MBPS remain authoritative on intent; MBUX on experience behavior. **MBCP-001** (upload, not canonized in this pass) is cited only as an optional principles digest subordinate to Founder's Book.

| ID | Principle | FB | MBPS | MBUX (signal) | MBMS / MBIA | MBCP digest (optional) |
|----|-----------|----|------|---------------|-------------|-------------------------|
| **P-01** | People are the reason / anchors | ✓ People are the anchors; People are the reason | ✓ People are the anchors | Experience around people & stories | Four anchors include People | Principle 1 |
| **P-02** | Stories are first-class (human) | ✓ Stories written by a human | ✓ Stories are first-class objects | Narrative chapter + story primacy | Stories anchor | Principle 2 |
| **P-03** | Meaning over media / artifacts from meaning | ✓ Preserves meaning more than media; Artifacts matter because of meaning | ✓ Artifacts gain value from meaning | Evidence supports, never replaces | Evidence invisible; museum metaphor | Principles 2, 8 |
| **P-04** | Never invent / fabricate memories | ✓ Never invent; fact-based & confidence-biased | ✓ Never fabricate memories | Never pretend; trust chapter | — | Principle 9 |
| **P-05** | Trust before convenience; evidence available | ✓ Trust before convenience | ✓ Preserve provenance; users control privacy | Trust Is Visible; evidence always available | Evidence invisible by default (reconciled) | Principle 7 |
| **P-06** | Capture easier than organization | ✓ | ✓ | Invitation over instruction | Conversation as front door | — |
| **P-07** | Curator, not exhibit; invite never instruct | Implied historian/curator stance | Asks thoughtful questions | Always invite; never instruct | Curator; museum guide | Principles 3, 4 |
| **P-08** | Family teaches; system remembers | Collaboration / ask when uncertain | Teach & Learn capabilities | Teaching loops | Learning / knowledge loops | Principle 5 |
| **P-09** | Conversation / curiosity as front door | Conversational interface | Conversation primary | Conversation commandments | Conversation front door; IA entry | — |
| **P-10** | Technology should disappear; AI serves the story | AI invisible; trust visible (MBPS goals) | AI invisible in goals | Narrative first; tech disappears | Modes change experience not archive | Principles 9, 10, 11 |

---

## 4. Conflict register (locked resolutions)

| Issue | Resolution | Applies when |
|-------|------------|--------------|
| **Story vs Narrative** | **Story** = human/curated meaning. **Narrative** = AI assembly from evidence. | MBKM lists both; MBPS defines Narrative; MBIA discovery loop uses Narrative; FB/MBMS treat Story as anchor. |
| **Relationship** | Split: **SocialRelationship** (Person–Person) vs **KnowledgeLink** (typed edges among concepts). Note in MBKM; full wording in MBKM 0.2. | MBKM “Relationship” vs graph edges elsewhere. |
| **Artifact / Evidence / Media** | **Roles**, not duplicate objects: Media = representation; Evidence = epistemic support; Artifact = intentional preserve/keepsake. One item may wear multiple roles. | Overlapping lists in MBKM / FB / MBPS. |
| **Thing (Founder's)** | Fold into **Artifact** for vocabulary. | FB Human Model lists Things and Artifacts. |
| **Evidence invisible (MBMS) vs always available (MBUX)** | **Invisible by default; always available on request** — never hidden from trust. | MBMS §6 vs MBUX Trust Is Visible. |
| **Four anchors vs MBKM vocabulary** | Anchors = **People, Stories, Moments, Places**. Other MBKM concepts = supporting (must not compete as destinations). | MBMS/MBIA vs full MBKM concept list. |
| **Life Chapters** | Supporting first-class concept (MBMS); **not** a fifth anchor until product decides. | MBMS open question. |
| **Contributor / User / Narrator** | **Roles on Person** (matrix already implied across MBPS/MBKM). | Separate concept lists. |
| **Timeline** | **Lens/view by default**, not a peer destination to anchors. | MBKM timeline-per-entity vs MBMS/MBIA lenses. |
| **Collections** | Object can exist; “Collections” as filter/viewing = **lens**. Glossary keeps both senses. | MBKM object vs MBMS/MBIA lens lists. |
| **Claim labels** | Facts / Observations / Inferences / Unknowns remain engineering/product truth labels (MBX-A-001); UX uses human phrasing (MBUX). | Architecture vs UX copy. |

---

## 5. Implications for MBX-A-003 / MBDM

- Derive the life-graph / conceptual data model from **MBKM-001 + this glossary**, not a fork.
- Prefer node types aligned to: Person, Story, Moment, Place, Artifact (incl. legacy Thing), Evidence/Media as roles or facets, SocialRelationship, KnowledgeLink, Collection, Tradition, Season, Life Chapter (supporting), Conversation (as interaction/provenance as needed).
- **Timeline** is primarily a view/lens over time-bearing links — not necessarily a peer destination node type.
- **Contributor / User / Narrator** are roles or attributes on Person (and session), not competing human entity types.
- Epistemic quartet (Facts / Observations / Inferences / Unknowns) remains the claim-label set for reconstruction; presentation stays human-language per MBUX.
- Do **not** silently promote Pets or Organizations to first-class nodes until the open questions below are closed.

---

## 6. Unresolved open questions

Explicitly unresolved — **do not invent** answers in downstream docs:

1. **Pets** — first-class concept, specialization of Person/Relationship/Story, or out of model? (MBKM open question)
2. **Organizations** — first-class vs specialization? (MBKM open question)
3. **Favorites, Values, Beliefs** — first-class vs specializations of Stories/Relationships? (MBKM)
4. **Life Chapters as fifth anchor** — deferred; supporting until product decides (MBMS)
5. **MBKM 0.2** — full Relationship → SocialRelationship / KnowledgeLink rewrite; role matrix for Contributor/User/Narrator; Artifact/Evidence/Media role formalization
6. Stories vs People as primary interface anchor — contextual vs fixed (MBMS / MBIA)
7. Whether / how to visualize the knowledge graph in Explorer Mode (MBMS / MBIA)
8. Default home: Conversation always vs resume Continue Exploring (MBIA)
9. MBCP-001 canonization — out of scope this pass; remains optional digest under FB if later canonized

---

## Related

- Product index: [docs/product/README.md](README.md)
- Architecture: [docs/architecture/README.md](../architecture/README.md) — MBX-A-003 derives from MBKM + this document
- Prior architecture reconciles (reports): [MBX-A-001-RECONCILE](../architecture/MBX-A-001-RECONCILE%20Founders%20Book%20and%20MBPS%20vs%20Functional%20Architecture.md), [MBX-A-001-RECONCILE-MBUX](../architecture/MBX-A-001-RECONCILE-MBUX.md)
