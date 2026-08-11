# MBBS-001 Increment 9A — Person Profile, Facts & Relationships — Definition (final review — decisions locked; not build-authorized)

**Status:** **FINAL REVIEW** — decisions locked from owner answers; awaiting explicit *Build Increment 9A only*  
**Date:** 2026-08-11  
**Roadmap placement:** **After Increment 9 Artifact (ACCEPTED)** · **Before Increment 10 (EVS-014)**  
**Owner acceptance gate (locked):** On FlightSim, Tom can open the thin **Person Profile** surface on **`/people/ui`** **without developer intervention**, with one **canonical owner Person** (`owner_person_id` → MB `people.id`) as the relativity anchor for “my … / me”. He can record **owner-authoritative facts** (e.g. Eugene Will birthdate **1927-06-11**) with provenance, record **family relationships** (e.g. **Eugene Will father_of owner**) as **one** provenance-bearing assertion with **derived inverse** semantics, record a **shared marriage/anniversary life event** for Eugene & Anne (EVS-086 class) associated with **both** participants, see identity / aliases / facts / contacts / relationships / life events distinctly (not one flat Person row), and use Ask so that **“Who is my father?”**, **“When was my father born?”**, and **“Show me pictures of my father.”** resolve via **owner → Relationship service → MB Person id → existing retrieve** — never via display-name string substitution. Correction must supersede a wrong relationship (e.g. uncle → father) while retaining prior provenance and stopping Ask from treating the withdrawn edge as current. Synthetic harnesses prove layered model, inverse resolution, qualified multi-parent support, shared marriage event, correction, ambiguity disclosure, and no silent overwrite.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) · Living Specs  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** **Increment 6 Person & Identity (ACCEPTED)** · Ask (I4) · Library (I8 ACCEPTED) · **Increment 9 Artifact (ACCEPTED)**  
**Prior:** [MBBS-001_INCREMENT_9_ACCEPTANCE.md](MBBS-001_INCREMENT_9_ACCEPTANCE.md) — **ACCEPTED**  
**Next (after 9A):** Increment 10 — EVS-014  
**Authorization:** *Do not build* until Tom authorizes *Build Increment 9A only*.

---

## 0. Locked decisions (final review)

| Topic | Decision |
|-------|----------|
| Product slice | **Person Profile** + layered **facts / aliases / contacts / Person↔Person relationships / shared life events** — not a flat `people` god-row |
| Roadmap | **9 (ACCEPTED) → 9A → 10**; EVS-014 hard OUT of 9A |
| **Owner / “myself” anchor** | One explicit **canonical owner Person** via authoritative **`owner_person_id`** (or equivalent domain/config reference) to MB `people.id`. Relational language (**my father / my son / my grandfather / my anniversary / pictures of me**) resolves **relative to that owner**. **Do not** infer “myself” by searching `display_name` (“Tom”). Duplicate owner rows on FlightSim → **I6 merge** before I9A-OWNER |
| Identity boundary | **I6 remains SoT** for Person identity & provider mappings; 9A does not mint a second Person PK path |
| **Relationship SoT / inverses** | Persist **one** provenance-bearing relationship assertion; **derive inverse semantics** in the Relationship service (e.g. Eugene `father_of` Tom ⇒ Tom `child`/`son_of` Eugene; `grandparent_of` ↔ `grandchild_of`; spouse/partner & sibling **symmetric** where appropriate). **Do not** create two independently editable inverse rows that can drift. Acceptance **must** prove inverse resolution |
| **Multiple / qualified relationships** | **No** one-father / one-mother schema constraint. Support multiple qualified edges thin P1 set: **parent**, **biological parent**, **adoptive parent**, **step-parent**, **spouse/partner**, **sibling**, **grandparent/grandchild** (and thin father/mother/son/daughter as role labels where useful). **No** full genealogy ontology. Conflicting unresolved edges → **disclose ambiguity**; never silently pick one |
| **Life event vs Person fact** | Marriage/anniversary (EVS-086) is a **shared life event/relationship fact** with provenance, associated with **both** participants + date — **not** a duplicated flat field on two profiles. Same truth answers “when did Eugene and Anne marry?”, “when did Anne and Eugene marry?”, “what is their anniversary?”. Smallest clean shared-life-event representation — **not** a full Event platform |
| Fact model boundaries | **Person facts:** birth date, death date, free-form notes (where appropriate). **Aliases:** nickname / alternate name. **Contact points:** email, phone (provenance + correction history; **not** login accounts; **not** a second provider identity system). **Relationships:** Person↔Person. **Shared life events:** marriage/anniversary class. Do **not** turn `person_facts` into a junk drawer if specialized structures fit |
| Profile UX | **Extend `/people/ui`** into the thin Person Profile surface where practical. One coherent place: identity · aliases · profile facts · contacts · relationships · life events · provider trust/mappings (already available). **Do not** reimplement face teaching or invent a second People product |
| Ask relational resolve | **owner/person → Relationship service → MB Person id → existing Ask/media retrieve**. **Forbidden:** raw string substitution (`"my father" = "Eugene Will"`). Acceptance minimum: “Who is my father?” → Eugene; “When was my father born?” → birth fact; “Show me pictures of my father.” → resolve then existing media path; **inverse** resolution from the same authoritative relationship record |
| Correction | Incorrect relationship can be **withdrawn/superseded**; corrected edge becomes current; **prior provenance retained**; Ask no longer treats withdrawn edge as current. Synthetic: **uncle → corrected to father** |
| Immich lazy-teach on Profile pickers | Thin earn-in of I9 pattern for selecting Persons on Profile **only** — **not** [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md) universal inventory |
| Exact-name enroll | Typos create distinct People; no fuzzy auto-merge; merge via I6 |
| Prove | **`prove-person-profile`** + `--flightsim` |
| Scope locks | EVS-014 → Inc 10 · no full genealogy/tree visualization · no auto-inferred family tree · no Immich write-back · no multi-user relationship relativity · no full Places/Event platform · no universal lazy-teach · no polish |

---

## 1. Why 9A exists (gap)

| Layer | What I6–I9 delivered | Still missing |
|-------|----------------------|---------------|
| **Identity** | Canonical MB Person; mappings; teach/confirm/reject; trust; Immich lazy on some surfaces | Explicit **owner_person_id** relativity anchor |
| **Browse / media / Artifact** | Library, Ask, Review, Artifact | — |
| **Profile facts / aliases / contacts** | `display_name` only | Birth/death, notes, nicknames, email/phone with provenance |
| **Kinship** | Generic `relationships` for Story/Journal/Artifact *about* — not family roles | Authoritative Person↔Person roles + derived inverses |
| **Shared life events** | Journal/Story temporal; media dates | Marriage/anniversary as shared event/fact for both spouses |

---

## 2. REQUIRED EVS AUDIT (authoritative catalog)

**Source audited:** `docs/source/MBEVS-001_EVS_Catalog_v0.8.xlsx` (v0.8).  
Deprecated markdown `docs/MBBC/MBEVS-001_EVS_CATALOG.md` was **not** used as authority (D1).

### 2.1 Traceability (no relevant EVS left unassigned)

| EVS ID | Scenario (short) | I9A status | Notes |
|--------|------------------|------------|-------|
| **EVS-084** | Eugene Will ↔ myself as **my father** | **IN** | Owner-gate; owner_person_id relativity |
| **EVS-085** | Eugene Will birthdate **1927-06-11** | **IN** | Person fact + provenance |
| **EVS-083** | Relationship between person one and person two | **IN** | Generalized Person↔Person write |
| **EVS-087** | Matt Will as **my son** | **IN** | Derived/explicit child role vs parent assertion |
| **EVS-088** | Cora Grace Will as **granddaughter** of Tom Will | **IN** | grandparent↔grandchild inverse pair |
| **EVS-089** | John Henry Meyer as **my grandfather** | **IN** | Relativity via owner |
| **EVS-069** | Relationships among Peggy, George, Rick George | **PARTIAL** | Graph write/query; polish OUT |
| **EVS-086** | Marriage date Eugene & Anne Will **1947-09-25** | **IN** | **Shared** life event/fact both participants |
| **EVS-021** | Enter information about the person next to Dad | **PARTIAL** | Thin profile-fact entry |
| **EVS-102** | Pictures of **my father** | **PARTIAL** | Relational resolve → existing photo path |
| **EVS-054** | Pictures of **my dad** smiling | **PARTIAL** | Resolve + existing smile/photo path |
| **EVS-067** | Picture of **my Uncle Al** | **PARTIAL** | Role+name → Person → photo |
| **EVS-045** | Dad with **the grandkids** | **PARTIAL** | Graph expand; full inference OUT |
| **EVS-034** | Emails from Dad | **PARTIAL** | Resolve Person; contact facts thin |
| **EVS-066** | Mom and Dad’s **wedding** pictures | **PARTIAL** | Marriage event may seed filter; media path existing |
| **EVS-101** | Pictures on **my anniversary** | **PARTIAL** | Shared anniversary date → media date filter thin |
| **EVS-103** | Father at Christmastime | **DEFERRED** | Season windows later |
| **EVS-011** | Who is the woman behind Matt? | **DEFERRED** | I6/I7 Review teach |
| **EVS-014** | Cross-provider face enroll | **DEFERRED** | **Increment 10** |
| **EVS-022 / 023** | Peggy teach / bulk | **DEFERRED** | Done I6 |
| **EVS-024–027** | Younger / story / voice / handwriting | **DEFERRED** | Later tracks |
| Media retrieve EVSs without relational language | — | **DEFERRED** / prior | Unless “my father/dad/uncle” → PARTIAL |
| **EVS-162 / 163 / 171** | Certainty / uncertainty | **PARTIAL** | Disclose provenance on Profile |
| **EVS-100** | Merge faces | **DEFERRED** | I6 merge (also used for owner-row cleanup) |
| Contact/email productization EVSs | — | **PARTIAL** | Contact points thin only |
| Nicknames / aliases | Owner need | **IN** (thin) | Alias structure |
| Artifact EVSs | — | **DEFERRED** | Done I9 foundation |

---

## 3. Problem / why now

I6–I9 answer “which Person?” and “show their media/artifacts.” The family still cannot answer:

1. Who is this person beyond a display name?  
2. What facts do we know, and from where?  
3. How are they related to **me** (canonical owner)?  
4. Which shared life dates (marriage/anniversary) apply to a couple?  
5. Can Ask understand **“my father”** without string hacks?

---

## 4. Objective

1. **Canonical owner_person_id** for P1 relativity.  
2. **Layered Profile** — identity ≠ aliases ≠ facts ≠ contacts ≠ relationships ≠ shared life events.  
3. **Relationship service** — one assertion SoT; derived inverses; qualified multi-edges; correction/supersede.  
4. **Shared marriage/anniversary** representation (EVS-086 class).  
5. **Ask** relational resolve (no string substitution).  
6. **Extend `/people/ui`** Profile surface.  
7. **`prove-person-profile`** + FlightSim owner path.

| Field | Content |
|-------|---------|
| **Modules** | Owner config/ref; Profile/Facts/Aliases/Contacts; Relationship service (SoT + inverse projection); Shared life-event (marriage class); Ask resolve earn-in; `/people/ui` Profile |
| **Flows** | EF-07/08 continued thin; relational Ask thin |
| **EVSs in** | **084, 085, 083, 086, 087–089** IN; listed PARTIALs |

---

## 5. Success criteria (acceptance)

| ID | Criterion | Proof |
|----|-----------|-------|
| **I9A-A** | Layered stores/projections — not flat Person god-row | Harness |
| **I9A-B** | Authoritative `owner_person_id` configured; “myself/me/my …” does **not** search display_name | Harness + FlightSim |
| **I9A-C** | Eugene Will birthdate 1927-06-11 as Person fact + provenance | Harness + FlightSim |
| **I9A-D** | Eugene `father_of` owner (one assertion); Ask/inverse sees Tom as child/son_of Eugene | Harness + FlightSim |
| **I9A-E** | Inverse resolution from same SoT (no dual editable inverse rows) | Harness |
| **I9A-F** | Qualified multi-parent / step / adoptive thin roles allowed; ambiguity disclosed when unsafe | Harness |
| **I9A-G** | Shared marriage/anniversary event for Eugene & Anne (both participants + date); query either order / anniversary | Harness + FlightSim |
| **I9A-H** | Ask: “Who is my father?” → Eugene | Harness + FlightSim |
| **I9A-I** | Ask: “When was my father born?” → birth fact | Harness + FlightSim |
| **I9A-J** | Ask: “Show me pictures of my father.” → resolve then existing media path | Harness + FlightSim |
| **I9A-K** | Correction: uncle → father; withdrawn not current; prior provenance retained; Ask updated | Harness |
| **I9A-L** | Aliases + contact points with provenance; contacts ≠ provider identity | Harness |
| **I9A-M** | `/people/ui` Profile shows identity / aliases / facts / contacts / relationships / life events distinctly | FlightSim |
| **I9A-N** | Missing/ambiguous → disclose; never invent | Harness |
| **I9A-O** | I6 mappings/trust unchanged by fact/relationship writes | Harness |
| **I9A-P** | I1–I9 proves remain runnable | Prior proves |
| **I9A-OWNER** | FlightSim: owner_person_id set; duplicates merged if needed; Eugene father + birthdate; marriage event if practical; Ask relational path; no SQL/dev intervention | Tom |
| **I9A-Q** | Living specs updated | Decision log + acceptance |
| **I9A-R** | EVS-014 / tree viz / auto-genealogy / Immich write-back / multi-user / Places platform / universal lazy-teach / polish **not** claimed | Note |

---

## 6. Scope

### In

- `owner_person_id` (config/domain) → MB `people.id`  
- Person facts (birth, death, free-form notes) + provenance + revision  
- Aliases (nickname / alternate name) + provenance  
- Contact points (email, phone) + provenance + correction history  
- Person↔Person relationships: **one SoT assertion** + **derived inverses**; qualified role set thin P1  
- Shared life events: marriage/anniversary class (both participants + date)  
- Ask relational resolve (owner → relationships → Person → existing retrieve)  
- Relationship correction / supersede  
- Extend `/people/ui` Profile surface  
- Immich lazy-teach on Profile Person pickers only (I9 earn-in)  
- `prove-person-profile` + FlightSim owner gate  
- Pre-OWNER: I6 merge of duplicate owner Person rows if present  

### Out

| Out | Notes |
|-----|--------|
| EVS-014 | Increment 10 |
| Full genealogy ontology / tree visualization | Forbidden |
| Auto-inferred family tree from photos | Forbidden |
| Immich write-back | Forbidden |
| Multi-user “whose father” | Single-owner P1 |
| Full Places / Event platform | Marriage class only |
| Dual independently editable inverse rows | Forbidden |
| Infer myself via display_name search | Forbidden |
| Universal lazy-teach all surfaces | TASK-P1P2-001 |
| Artifact boxing reopen | Done I9 |
| SMS / login accounts from contacts | Forbidden |
| Polish / Settings / family-tree chrome | Out |

---

## 7. Architecture sketch (non-binding until build)

```
config/domain: owner_person_id ──────────────────────────────┐
                                                             │
people (I6 identity SoT)                                     │
    ├─ provider_identities / assertions (I6)                 │
    ├─ person_aliases                                        │
    ├─ person_facts (birth, death, notes + provenance)       │
    ├─ person_contact_points (email, phone + provenance)     │
    ├─ person_relationship_assertions (SoT; one edge)        │◄── relativity
    │     └─ Relationship service: derive inverse views      │
    └─ shared_life_events (marriage/anniversary; N persons)  │
                                                             │
Ask: "my father" → owner_person_id → Relationship service ───┘
                 → target person_id → existing photo/Library/Ask retrieve
```

Hosts unchanged: **FlightSim** = app + PostgreSQL; **media-server** = durable media. 9A is **PG-domain** (+ config for owner).

---

## 8. Build plan (only after *Build Increment 9A only*)

1. Owner anchor: `owner_person_id` config/domain; document FlightSim merge of duplicate Toms if needed.  
2. Migration: aliases, facts, contact points, relationship assertions (SoT), shared life events — layered.  
3. Relationship service: write one assertion; project inverses; qualify roles; supersede/withdraw; ambiguity disclosure.  
4. Shared marriage/anniversary write/read for both participants.  
5. Ask relational resolve hook (no string substitution).  
6. Extend `/people/ui` Profile panels.  
7. `prove-person-profile` (inverses, multi-qualified, correction uncle→father, shared marriage, Ask trio) + `--flightsim`.  
8. Confirm I1–I9 proves.  
9. Acceptance; **stop** (do not start I10).

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Flat Person god-row | Locked layered model + specialized structures |
| Dual inverse drift | Single SoT assertion; derived inverses only |
| Silent one-father constraint | Explicit multi-qualified support |
| String-hack Ask | Forbidden; acceptance proves domain resolve |
| Marriage duplicated on two profiles | Shared life-event record |
| Contacts becoming identity providers | Provenance strings only; I6 mappings SoT |
| Infer myself by name | Forbidden; owner_person_id required |
| Scope into Event platform / EVS-014 / tree viz | Hard OUT |
| Universal lazy-teach creep | TASK-P1P2-001 |

---

## 10. Residual ops notes (non-blocking unless Tom objects)

1. Exact env/config name for `owner_person_id` (e.g. `MEMORYBOX_OWNER_PERSON_ID`) — choose at build; D7 portable.  
2. Exact table names / revision shape after Story/Journal/I6 patterns at build.  
3. Thin role vocabulary enum vs open text + controlled set — smallest clean model at build.  

§0–§9 owner decisions are **locked**. No remaining product open questions blocking review sign-off.

---

## 11. Authorization gate

**Status: FINAL REVIEW — decisions locked. No implementation yet.**

Reply with **Build Increment 9A only** to authorize code.  
Do **not** begin Increment 10 / Guided Capture / Export / TASK-P1P2-001 under this authorization.

---

## 12. Stop line

After 9A acceptance: **Increment 10** (EVS-014) only with new authorization.  
No silent expansion into Places platform, genealogy chrome, multi-user relativity, or universal lazy-teach.

---

*End of Increment 9A definition — final review; do not build until authorized.*
