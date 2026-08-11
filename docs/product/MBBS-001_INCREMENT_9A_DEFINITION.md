# MBBS-001 Increment 9A — Person Profile, Facts & Relationships — Definition (review only — not build-authorized)

**Status:** **REVIEW ONLY** — awaiting explicit *Build Increment 9A only* (and §10 answers)  
**Date:** 2026-08-11  
**Roadmap placement:** **After Increment 9 Artifact (ACCEPTED)** · **Before Increment 10 (EVS-014)**  
**Owner acceptance gate (proposed):** On FlightSim, Tom can open a thin **Person Profile** surface **without developer intervention**, record **owner-authoritative facts** (e.g. Eugene Will birthdate **1927-06-11**) with provenance, record **family relationships** (e.g. **Eugene Will = Tom’s father**), see facts/relationships distinct from identity mappings, and use Ask to resolve relational language such as **“my father”** to the correct MB Person for retrieval — without inventing facts or collapsing identity / profile / relationships / life dates into one flat Person row. Synthetic harnesses prove layered model, provenance, relational resolve, correction, and no silent overwrite.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) (Person & Identity foundation in Inc 6; gap closure as **9A**) · Living Specs  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** **Increment 6 Person & Identity (ACCEPTED)** · Ask (I4) · Library (I8 ACCEPTED) · **Increment 9 Artifact (ACCEPTED)** (roadmap order; Artifact not required to prove 9A core facts/relationships)  
**Prior:** [MBBS-001_INCREMENT_9_ACCEPTANCE.md](MBBS-001_INCREMENT_9_ACCEPTANCE.md) — **ACCEPTED**  
**Next (after 9A):** Increment 10 — EVS-014  
**Authorization:** *Do not build* until Tom authorizes *Build Increment 9A only*.

---

## 0. Why 9A exists (gap)

| Layer | What I6–I9 delivered | Still missing |
|-------|----------------------|---------------|
| **Identity** | Canonical MB Person; provider mappings; teach/confirm/reject; trust authority; Immich lazy-teach on some surfaces | — (I6/I7; Artifact pickers) |
| **Browse / media** | Library + Ask by Person; video Review; Artifact modality | — (I7/I8/I9) |
| **Profile facts** | Minimal `display_name` only | Birth/death, contact facts, nicknames, free-form owner facts with provenance |
| **Relationships** | Generic `relationships` for Story/Journal/Artifact *about* — **not** a family/role model | Father/son/…; “my father” resolve; revision + provenance |
| **Life events / dates** | Journal/Story temporal; media dates | Person-attached life dates (birth, marriage, anniversary) as first-class facts — not invented from EXIF |

**Product rule:** Do **not** collapse **identity**, **profile facts**, **relationships**, and **life events** into one flat `people` row. Separate stores/projections with shared Person FK and provenance.

Illustrative owner truths for FlightSim gate (locked preference):

- **Eugene Will** is **Tom’s father** (relationship + role).  
- **Eugene Will** birthdate **1927-06-11** (profile / life-date fact with provenance).

FlightSim People already exercised in I8/I9 (e.g. Eugene Will, Anne Will, Tom Will) — 9A uses those identities; it does not re-teach faces.

---

## 1. REQUIRED EVS AUDIT (authoritative catalog)

**Source audited:** `docs/source/MBEVS-001_EVS_Catalog_v0.8.xlsx` (v0.8) — sheets *EVS Catalog*, *Reference*, *Coverage*.  
**Deprecated markdown** `docs/MBBC/MBEVS-001_EVS_CATALOG.md` was **not** used as authority (D1).

**Taxonomies in scope:** People & Identity · Relationships · Events & Timeline (person life dates) · Corrections & Learning (owner correction of person facts) · Trust & Evidence (uncertainty about person) · Communications (person contact / “emails from Dad”) where they require profile/relationship resolve.

**Coverage note (v0.8):** Relationships taxonomy = **6** active EVSs; People & Identity = **39**. Many People & Identity EVSs are **retrieval** (already I6–I8) rather than profile/relationship **write**. Those are marked PARTIAL (relational resolve earn-in) or DEFERRED.

### 1.1 Traceability table (no relevant EVS left unassigned)

| EVS ID | Scenario (short) | Proposed I9A status | Notes |
|--------|------------------|---------------------|-------|
| **EVS-084** | Define relationship Eugene Will ↔ myself as **my father** | **IN** | Owner-gate exemplar |
| **EVS-085** | Record birthdate of Eugene Will **1927-06-11** | **IN** | Owner-gate exemplar; life-date fact + provenance |
| **EVS-083** | Define relationship between person one and person two | **IN** | Generalized relationship write |
| **EVS-087** | Record Matt Will as **my son** | **IN** | Family role write |
| **EVS-088** | Record Cora Grace Will as **granddaughter** of Tom Will | **IN** | Kinship role write |
| **EVS-089** | Record John Henry Meyer as **my grandfather** | **IN** | Kinship role write |
| **EVS-069** | Identify relationship among Peggy, George, Rick George | **PARTIAL** | Write/query owner relationship graph; full multi-party UX polish OUT |
| **EVS-086** | Record marriage date Eugene & Anne Will **1947-09-25** | **IN** | Life-event / shared date fact with provenance (thin) |
| **EVS-021** | Enter information about the person next to Dad | **PARTIAL** | Thin profile-fact entry on Person; not full CRM |
| **EVS-102** | Show me pictures of **my father** | **PARTIAL** | Ask relational resolve → existing photo Ask/Library; no new photo stack |
| **EVS-054** | Show me pictures of **my dad** smiling | **PARTIAL** | Relational resolve + existing smile/photo path |
| **EVS-067** | Show me a picture of **my Uncle Al** | **PARTIAL** | Role+name resolve → Person → photo retrieve |
| **EVS-045** | Show me Dad with **the grandkids** | **PARTIAL** | Relationship graph expand → multi-person retrieve; full inference OUT |
| **EVS-034** | Show me emails from Dad | **PARTIAL** | Relational resolve to Person; contact facts thin only |
| **EVS-066** | Mom and Dad’s **wedding** pictures | **PARTIAL** | Marriage/wedding life-event may seed filter; photo retrieve remains Immich/Ask |
| **EVS-101** | Pictures on **my anniversary** date | **PARTIAL** | Owner anniversary fact + media date filter; holiday window system OUT |
| **EVS-103** | All media of my father at Christmastime | **DEFERRED** | Season windows → later Events/Ask; not 9A core |
| **EVS-011** | Who is the woman behind Matt? | **DEFERRED** | Review teach + identity (I6/I7) |
| **EVS-014** | Teach face in video → same in Ask/Immich | **DEFERRED** | **Increment 10** |
| **EVS-022** | That person is Peggy | **DEFERRED** | **Done in I6** |
| **EVS-023** | These pictures are all Peggy | **DEFERRED** | **Done in I6** |
| **EVS-024** | This is Peggy when younger | **DEFERRED** | Age/appearance → later |
| **EVS-025** | Add this story to Peggy | **DEFERRED** | Story↔Person (I5) |
| **EVS-026** | This voice is Dad | **DEFERRED** | Speaker enroll → later |
| **EVS-027** | Dad’s handwriting | **DEFERRED** | P2 document attribution |
| **EVS-028–044**, **055–056**, **062–063**, **068**, **075–076**, **127** | Person-centered media retrieve / organize / expressions | **DEFERRED** or **already I6–I8** | Except “my father/dad/uncle” resolve → PARTIAL above |
| **EVS-001**, **003**, **007**, **009**, **032**, etc. | Named-person media asks | **DEFERRED** / prior | 9A only if relational pronoun/role |
| **EVS-162**, **163**, **171** | Why/how sure / unsure about person | **PARTIAL** | Disclose fact/relationship provenance & uncertainty on Profile |
| **EVS-100** | Merge two faces into one person | **DEFERRED** | Person merge already I6 |
| **EVS-107** | Email count to Peggy at her email address | **DEFERRED** | Communications productization later |
| **EVS-090**, **105**, **128** | Residence / place aliases | **DEFERRED** | Places track |
| **EVS-091–098**, **104**, **110–114**, **116** | Setting/season teach | **DEFERRED** | Not Person Profile |
| **EVS-018** | Invite relative | **DEFERRED** | P3 Family Contribution |
| **EVS-149**, **156**, **159**, **160** | Artifacts mentioning people | **DEFERRED** | **Done in I9** Artifact foundation |
| Contact email/phone as Person identifiers (I6 OUT) | — | **PARTIAL** | Optional **contact facts** on profile with provenance; not Immich write-back |
| Nicknames / aliases (sparse EVS coverage) | Owner need still real | **IN** (thin) | Profile aliases with provenance |

**Assignment rule:** Every People & Identity / Relationships EVS touching **profile facts, kinship roles, life dates, or relational Ask language** is **IN**, **PARTIAL**, or **DEFERRED** above.

---

## 2. Proposed locked decisions (for review)

| Topic | Decision |
|-------|----------|
| Product slice | **Person Profile** + **Person Facts** + **Person↔Person Relationships** + thin **life dates/events** bound to Person — layered, not flat |
| Roadmap | **9 (ACCEPTED) → 9A → 10**; do not pull EVS-014 into 9A |
| Identity boundary | **I6 remains SoT for Person identity & provider mappings.** 9A must not mint a second Person PK path |
| Fact model | Owner-asserted facts (birthdate, death date, nickname/alias, contact, free-form note) with **provenance**, authority, revision — never silent overwrite |
| Relationship model | **Person↔Person** relationships with **role** (father, son, …), optional inverse, provenance, revision |
| Relational Ask | Resolve “my father”, “my son”, “my uncle Al” via **owner** + relationship graph (+ optional name hint) before media retrieve |
| Events | Birth/marriage/anniversary as **dated facts / thin life events** linked to Person(s) — not a full Event ontology |
| UX | Thin **Person Profile** UI (functional); face teach stays People/Review |
| Person pickers on Profile | Prefer MB People; allow Immich **lazy-teach** on associate (same pattern as I9 Artifact) — **not** full [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md) inventory of every surface |
| Exact-name enroll | Typos create distinct People; no fuzzy merge in 9A; merge remains I6 `/people/ui` |
| Library / Ask | Earn-in only: Profile facts visible in Person detail; Ask uses relational resolve; **no** second Gallery |
| Artifact (I9) | Already associates Artifact↔Person; 9A may deep-link Profile from Library People — **not** required for 9A core gate |
| Immich write-back / auto-inferred family tree | **OUT** |
| Multi-user “whose father” beyond single owner | **OUT** (single-owner P1: relationships relative to owner Person) |
| Prove | **`prove-person-profile`** with named subchecks + `--flightsim` |
| SMS / full email identity providers | **OUT** of 9A core (contact facts optional thin) |
| Universal lazy-teach everywhere | **OUT of 9A** → [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md) |

---

## 3. Problem / why now

I6 answered “which MB Person is this face?” I7–I9 answered “show media / artifacts for that Person.”  
The family still cannot answer:

1. Who is this person (beyond a display name)?  
2. What important facts do we know, and **from where**?  
3. How are they related to me / others?  
4. Which dates belong to their life?  
5. Can Ask understand **“my father”**?

Without 9A, EVS-084/085/087–089 stay unmet and relational Ask remains lexicon hacks rather than domain truth.

---

## 4. Objective

1. **Layered Person Profile read model** — identity (I6) ≠ facts ≠ relationships ≠ life dates.  
2. **Write paths** — owner records facts and relationships with provenance.  
3. **Ask relational resolve** — “my father” → MB Person id(s).  
4. **Thin Profile UX** + People deep-link.  
5. **`prove-person-profile`** + FlightSim owner path (Eugene father + birthdate).

| Field | Content |
|-------|---------|
| **Modules** | Person Profile/Facts service; Relationship service (Person↔Person); Ask resolve earn-in; thin Profile UX |
| **Flows** | EF-07/08 continued thin; relational Ask thin |
| **EVSs in** | **EVS-084**, **085**, **083**, **086**, **087–089** IN; **021**, **034**, **045**, **054**, **066**, **067**, **069**, **101**, **102**, **162/163/171** PARTIAL |

---

## 5. Success criteria (acceptance)

| ID | Criterion | Proof |
|----|-----------|-------|
| **I9A-A** | Facts stored separately from `people` identity row (or clearly layered projection) | Harness |
| **I9A-B** | Record Eugene Will birthdate 1927-06-11 with provenance | Harness + FlightSim |
| **I9A-C** | Record Eugene Will → owner as **father** (EVS-084) with provenance | Harness + FlightSim |
| **I9A-D** | Additional kinship write (son / granddaughter / grandfather) thin | Harness |
| **I9A-E** | Marriage/anniversary life-date thin (EVS-086 class) | Harness |
| **I9A-F** | Ask “show pictures of my father” resolves to Eugene Will Person (when taught) | Harness + FlightSim |
| **I9A-G** | Correction revises fact/relationship; prior retained; no silent overwrite | Harness |
| **I9A-H** | Missing fact/relationship → disclose; do not invent | Harness |
| **I9A-I** | Profile UI shows identity vs facts vs relationships distinctly | FlightSim |
| **I9A-J** | Aliases/nicknames thin with provenance | Harness |
| **I9A-K** | I6 mappings/trust unchanged by fact writes | Harness |
| **I9A-L** | I1–I9 proves remain runnable | Prior proves |
| **I9A-OWNER** | FlightSim: Eugene = father + birthdate recorded; Ask relational resolve; no SQL/dev intervention | Tom |
| **I9A-M** | Living specs updated | Decision log + acceptance |
| **I9A-N** | EVS-014 not claimed | Note → Inc 10 |

---

## 6. Scope

### In

- Person Fact records (typed + free-form) + provenance + revision  
- Person↔Person relationships + roles + provenance + revision  
- Thin life dates (birth, death, marriage, anniversary) as facts/events bound to Person(s)  
- Thin aliases/nicknames  
- Optional thin contact facts (email/phone strings) — **not** full provider identity productization  
- Ask relational resolve (“my father”, …)  
- Thin Person Profile UX  
- Immich lazy-teach **only** on Profile Person pickers (earn-in I9 pattern)  
- Prove harness + FlightSim owner gate  

### Out

| Out | Notes |
|-----|--------|
| EVS-014 cross-provider enroll loop | Increment 10 |
| Full Event/Place ontology | Later tracks |
| Auto-inferred genealogy from photos | Forbidden without owner |
| Immich write-back | Forbidden |
| Multi-user relationship relativity | Single-owner P1 |
| Expression/scene teaching | Not profile |
| SMS ingest / full communications identity | Later |
| Artifact boxing product work | **Done in I9** — do not reopen |
| Universal lazy-teach on all MB surfaces | [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md) |
| Polish / Settings / family-tree chrome | Out |

---

## 7. Architecture sketch (non-binding until build)

```
people (I6 identity + display_name + status)
    ├─ provider_identities / assertions (I6)     ← identity
    ├─ person_facts (+ provenance, versions)   ← profile facts / life dates
    ├─ person_aliases (nicknames)              ← profile
    └─ person_relationships (from_person, to_person, role, provenance)
         └─ Ask: "my father" → resolve via owner + role → person_id → existing retrieve
```

Do **not** overload Story `about_person` or Artifact `about_person` for kinship. Kinship is Person↔Person.

Hosts unchanged: **FlightSim** = app + PostgreSQL; **media-server** = durable media (I9 Artifacts / Immich / video). 9A is PG-domain only.

---

## 8. Build plan (only after *Build Increment 9A only*)

1. Domain migration for facts / aliases / person↔person relationships (layered).  
2. Service APIs: record/correct/list facts & relationships.  
3. Ask relational resolve hook (before media retrieve).  
4. Thin Profile UX (`/people/ui` panel or `/people/profile`).  
5. `prove-person-profile` + `--flightsim`.  
6. Confirm I1–I9 proves.  
7. Acceptance; **stop** (do not start I10).

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Flat Person god-row | Locked layered model |
| Invented relatives from face clusters | Owner-asserted only |
| Pulling EVS-014 into 9A | Hard OUT → Inc 10 |
| Lexicon hacks replacing domain | Relational resolve must read MB relationships |
| Scope into Places/Events platform | Life dates thin only |
| Contact facts becoming second identity system | Optional strings; I6 mappings remain SoT |
| Exact-name duplicate People | Warn on enroll; merge via I6; no fuzzy auto-merge |
| Expanding to universal lazy-teach | Stay on TASK-P1P2-001 |

---

## 10. Open questions for Tom (before build auth)

1. **Owner Person:** Confirm the MB Person that means “myself / Tom” for relationship relativity on FlightSim (e.g. **Tom Will** vs other Tom rows — merge first?).  
2. **Inverse relationships:** Auto-create son↔father inverse on write, or explicit only?  
3. **Multiple fathers / step-relations:** Allow multiple with roles/notes, or single primary?  
4. **Fact types v1 list:** birth, death, marriage, anniversary, nickname, email, phone, free-form — add/remove?  
5. **Profile UX host:** Extend `/people/ui` vs new `/people/profile` route?  
6. **Marriage EVS-086:** Record as one shared fact on both Persons, or one Person + linked spouse Person?

*(I9 ordering question retired — I9 is ACCEPTED; 9A is next.)*

---

## 11. Authorization gate

**Status: REVIEW ONLY. No implementation.**

Reply with **Build Increment 9A only** (and §10 answers) to authorize.  
Do **not** begin Increment 10 / Guided Capture / Export / TASK-P1P2-001 under this definition.

---

## 12. Stop line

After acceptance of 9A: proceed only to **Increment 10** with new authorization.  
Do not silently expand into Places platform, EVS-014, multi-user genealogy, or universal lazy-teach.

---

*End of Increment 9A definition — review only. EVS audit against MBEVS-001 v0.8. Prior: I9 ACCEPTED.*
