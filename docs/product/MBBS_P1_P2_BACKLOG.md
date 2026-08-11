# MBBS — P1 → P2 backlog tasks

**Status:** Living backlog  
**Owner:** Tom  
**Rule:** Do **not** expand the current authorized increment to absorb these. Schedule after P1 acceptance closeout / before or as early P2 planning — **unless** Tom explicitly resequences (e.g. kinship before EVS-014).

---

## TASK-P1P2-001 — Universal Immich lazy-teach / trusted-provider Person bootstrap

**Logged:** 2026-08-11 (during I9 Artifact owner testing)  
**Priority:** Product consistency — every owner surface that needs a Person  
**Do not start under:** Increment 9 / 9A / 10 authorization as written

### Problem

Owner already created **named people in Immich**. MemoryBox must not force a separate `/people/ui` pre-create before those names are usable. I6/I7 introduced **trusted-provider lazy seed / teach** (`resolve_or_seed_trusted_provider_person`, `teach_provider_person`). Some surfaces still present **MB People only** (Story About-person, Library filter, Journal author/subject pickers, etc.), which recreates the “lazy names” failure.

I9 Artifact associate was patched to include Immich names + `from-provider` teach/map — that is a **local fix**, not the universal policy.

### Product rule (locked intent)

> **Lazy teach is the default everywhere in MemoryBox:** if Immich (or another trusted provider) already has an owner-created name, any Person picker / associate / “about” control should offer that name and materialize/map the canonical MB Person on use — not require a prior MB-only census.

Authority stack remains: **owner-confirmed > trusted-provider > candidate**. No silent same-name merge; ambiguity still owner-resolved. Immich UUID never becomes `people.id`.

### In scope (when authorized)

1. Inventory every UI/API that selects or creates a Person (Story, Journal, Library, Ask clarifications, Artifact, Review, People, future Guided Capture, etc.).  
2. Shared control / API pattern: MB People + Immich named identities; associate/teach via one Person service path.  
3. Prove: no surface requires `/people/ui` first when Immich already has the unique exact name.  
4. Docs: Living Spec / engineering rule note; retire one-off pickers.

### Out of scope for this task

- Bulk Immich Person import  
- Flattening identity authority  
- Expanding I9 / 9A / 10 mid-flight  

### Acceptance sketch

- Owner can pick an Immich-named person from **any** Person-bearing P1 surface without pre-teaching in `/people/ui`.  
- One shared service path; provenance discloses trusted-provider vs owner-confirmed.  
- Ambiguous names still force owner resolution.

### Trigger

After **P1** stop-line / acceptance wrap — open as explicit *Build TASK-P1P2-001* (or fold into early P2 Person UX epic). **Not** silent pull into remaining P1 increments.

---

## TASK-P1P2-002 — Kinship inference graph (minimal facts → cousins / gendered resolve)

**Logged:** 2026-08-11 (during I9A FlightSim owner acceptance)  
**Priority:** High product value after I9A; **not** Increment 10 (EVS-014) as chartered  
**Status:** Backlog — **do not build** under I10 authorization unless Tom resequences  
**Related:** I9A ACCEPTED with thin spouse-of-father/mother inference only

### Problem

I9A stores **one SoT relationship assertion** and derives **direct inverses** only (e.g. `father_of` ↔ `child_of`; `son_of` ↔ `parent_of`). That is intentionally **not** a genealogy engine.

FlightSim residual (accepted as known limit): Tom recorded **Tom Will `son_of` Eugene Will**. Inverse projects as **Eugene `parent_of` Tom**, not `father_of`. Gendered Ask (“my father” / spouse-of-father mother inference) therefore does **not** treat Eugene as father without an explicit `father_of` (or a future inference rule). Owner accepted I9A as-is; full inference deferred.

Families should enter **minimal facts** and get safe, disclosed inferences, e.g.:

| Given (minimal SoT) | Infer (disclosed) |
|---------------------|-------------------|
| A `father_of` B; A `spouse_of` C | C is B’s mother (I9A thin — already shipped) |
| B `son_of` A (or `child_of`) | A is B’s parent; **gendered father/mother** when role or other facts allow — without inventing gender from `parent_of` alone |
| A `brother_of` B; A `child_of` P; C `child_of` B | A and C are **cousins** (or uncle/nephew paths as appropriate) |
| Parent + sibling chains | uncle/aunt, nephew/niece, grandparent — where unique and safe |

### Product rules (intent for when authorized)

1. **Owner assertions outrank inference.** Never overwrite SoT with inferred edges as editable truth.  
2. **Disclose inference** in Ask/Profile (“inferred from …”).  
3. **Ambiguity → ask / disclose**, never silently pick among multiple candidates.  
4. **No full genealogy ontology / tree visualization** unless separately authorized (I9A lock remains).  
5. **No auto-inferred family tree from photos.**  
6. Prefer **composition of existing roles** (`brother_of`, `child_of`, `father_of`, `spouse_of`) over minting dozens of new SoT kinds.

### In scope (when authorized)

1. Relationship **inference service** (read-model / query-time or materialised derived edges clearly marked `inferred`).  
2. Gendered resolve from gendered SoT **and** safe inverse paths (e.g. `son_of` → treat as father for “my father” when the child role is son).  
3. Cousin / uncle-aunt / grandparent composition from minimal sibling+child facts.  
4. Ask resolve earn-in for “my cousin”, “my uncle”, etc. where EVS demand.  
5. Harness: synthetic graphs with **minimal facts only**; ambiguity cases; no invention.  
6. Living-spec update; optional thin Profile “also understood via inference” panel (not tree viz).

### Out of scope for this task

- EVS-014 cross-provider Person (Increment 10)  
- Immich write-back / photo auto-genealogy  
- Multi-user relativity  
- Polished family-tree chrome  
- Expanding I10 mid-flight without resequence authorization  

### Acceptance sketch

- With only `brother_of` + `child_of` / `father_of` facts, Ask can resolve **cousins** (and disclose how).  
- `son_of` / `daughter_of` SoT answers gendered parent asks without forcing a duplicate `father_of`/`mother_of` row when safe.  
- Conflicting or multi-path graphs disclose ambiguity.  
- Owner SoT remains single editable assertion; inferences are not dual-editable inverses.

### Trigger

**Locked (2026-08-11):** Remains **P2** — do not fold into Increment 10 (EVS-014). Open as explicit *Build TASK-P1P2-002* (or a numbered P2 kinship slice) after P1 stop-line / I10 acceptance closeout.

---

## TASK-P1P2-003 — Export import-back / round-trip restore (portability)

**Why parked:** Increment 12 (EF-16) proves **exit/export** only. Families need a way out now; full backup-and-restore is later portability work and must not expand I12/P1 acceptance.

**Intent (when authorized):** Import a `memorybox_export_format` package (starting with format `1`) back into MemoryBox (or a documented successor path) preserving MB-created knowledge, retained version history, Guided Capture context, and MB-managed originals — without inventing Immich/HVRT library restore.

**Explicitly OUT of:** I12 / P1 owner acceptance.

**Trigger:** After I12 acceptance / P1 stop-line — open only as explicit *Build TASK-P1P2-003* (or a numbered portability slice). **Not** silent pull into I12.

---

*Add new TASK-P1P2-### sections below as they arise.*
