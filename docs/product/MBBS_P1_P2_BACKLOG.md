# MBBS — P1 → P2 backlog tasks

**Status:** Living backlog  
**Owner:** Tom  
**Rule:** Do **not** expand the current authorized increment to absorb these. Schedule after P1 acceptance closeout / before or as early P2 planning.

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

*Add new TASK-P1P2-### sections below as they arise.*
