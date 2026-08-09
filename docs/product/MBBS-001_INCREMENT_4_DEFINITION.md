# MBBS-001 Increment 4 — Definition (for review)

**Status:** **CORRECTIVE REOPEN — desktop prove PASS (exploratory multimodal); awaiting FlightSim re-prove + manual re-test**  
**Date:** 2026-08-09  
**Acceptance:** [MBBS-001_INCREMENT_4_ACCEPTANCE.md](MBBS-001_INCREMENT_4_ACCEPTANCE.md) · corrective [MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md](MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md)  
**Build:** Corrective planner/context fix authorized; no Increment 5.

---

## 0. Final locked scope decisions

| Topic | Decision |
|-------|----------|
| Product slice | **Ask** (EF-01) + **Query Planner v0** + **basic contextual follow-up** (EF-02 basic) + thin EF-04 |
| EVS gate | **EVS-005** and **EVS-006** must pass on the P1 single-owner path |
| Acceptance locus | **FlightSim only** — final I4 acceptance must run on the defined P1 MemoryBox runtime host |
| Photo provider | **Immich on media-server is required** for I4 photo acceptance |
| Immich degradation | **Explicitly tested:** Immich unavailable → photo Ask reports provider unavailability (not “no photos”); non-photo Ask via PostgreSQL/Qdrant Evidence continues to work |
| Acceptance corpus | **Existing real Immich library** + **existing PostgreSQL email/calendar Evidence** where practical. Controlled fixture pack **only if** real archive data cannot reliably exercise a required acceptance condition. **Never** put family content into Git or acceptance reports |
| Ask UX | **Thin functional shell** is sufficient. Required: Ask Bar, results, evidence/citation view, visible context breadcrumb, clear/change-context controls. **No visual polish** this increment |
| Session context | **In-memory / process-session** for I4. Context **contract** designed so persistence can be added later without redesigning Ask |
| SMS | **Out of Increment 4** (Sources CSV remains staged only; later communications / Inc 9) |
| Citation rule | Every **factual claim about family history** must be traceable to supporting Evidence / provider provenance. **Do not** require artificial family-evidence citations for system-status statements, counts, UI language, or explicit missing-evidence disclosures |
| Generalized Ask (**I4-K**) | Planner/context behavior must **not** be hard-coded to Peggy, Florida, acceptance phrases, specific dates, IDs, or other demo data. Acceptance includes ≥1 equivalent **unseen variation** with different entities/context |
| **Intent-oriented Ask (visual)** | Ask is **intent-oriented**, not media-object jargon. Broad visual requests (“show me X”, “pictures/images of X”) mean **relevant visual memories** (stills **and** video/segments **when available**). Explicit narrowing respected (“photos” → stills; “videos” → video). “Show me” is a **presentation verb**, not a media-type ID. **I4 does not build video/HVRT**; I4 returns currently available visual modalities (PhotoProvider/stills) and keeps the planner contract expandable for video later without changing owner NL |
| Evidence First / No False Memories | Hard gates. An answer unsupported by available family evidence must **disclose insufficiency** rather than infer a convenient family fact |
| Hosts (D7) | App + PG + Qdrant + Ollama on **FlightSim**; Immich/media on **media-server**; config-only; no host hardcodes |
| Out of I4 | Story, Journal, Person teach/merge productization (Inc 6), **HVRT/Review / video processing**, Guided Capture, SMS ingest, multi-user, tone dial, visual polish |

---

## 0.1 Intent-oriented Ask — visual semantics (locked)

MemoryBox Ask must be **intent-oriented**. The owner should not need to understand internal media/object types.

| Owner language | Intended meaning |
|----------------|------------------|
| “Show me Peggy” / “pictures of …” / “images of …” / “Peggy at Christmas” | **Broad visual memories** — relevant stills **and** relevant video/segments **when those modalities are available** |
| “Show me photos of Peggy” | May **narrow to stills** when wording/context clearly means still photos only |
| “Show me videos of Peggy” | **Video only** |
| “Show me emails from Peggy” | Email Evidence (not visual) |
| “Show me the relationship between Peggy and Dad” | Relationship/domain information supported by Evidence (not a visual default) |
| “What did Peggy say about Alaska?” | Communications / audio / transcript / story Evidence **when those sources exist** |

**Normative rules:**

1. **“Show me” is a presentation/request verb**, not a media-type identifier. The Query Planner chooses domain objects, Evidence kinds, and media modalities from the rest of the intent.  
2. **Do not hard-code “pictures” as permanently equivalent to PhotoProvider-only retrieval.** Broad visual wording maps to a `visual_scope=broad` plan (stills + video intent).  
3. **Increment 4:** Do **not** add video/HVRT processing. I4 returns visual modalities **currently available** (still/PhotoProvider). The planner/retrieval **contract** (`visual_scope`, `want_visual` / `want_still` / `want_video`) must allow later video providers to satisfy the same owner NL without a new Ask architecture.  
4. Explicit video-only asks in I4 disclose that video modality is not wired yet — **never invent** video results.

---

## 0.1b Exploratory / know-about intent (corrective lock)

Broad exploratory asks mean: **explore what MemoryBox knows about that subject across all applicable currently available modalities** — not communications-only, and **not** photos-as-fallback.

| Owner language (illustrative) | Intended meaning |
|-------------------------------|------------------|
| “What do you know about our \<Trip\> trip?” / “Tell me about our \<Trip\> trip.” / “What do we have from our \<Trip\> trip?” | Multimodal explore: stills + email/calendar Evidence (+ later modalities when wired) |
| “Tell me about \<Person\>.” / “What do you know about \<Event\>?” / “What do I have about \<Place/Event/Trip\>?” | Same exploratory multimodal treatment for the named subject |

**Normative rules:**

1. Exploratory / know-about / tell-me-about / what-do-I-have-about is **always multimodal** for I4-available providers (Immich stills + communication + calendar Evidence). Do **not** wait for communications to return zero.  
2. **Explicit narrowing still wins:** emails-only, photos-only, videos-only, “what did \<Person\> say…” stay modality-focused.  
3. Results may present available modalities together so the owner can drill down with follow-ups.  
4. Generalized intent only — **no** hard-coded demo people/places/trips/events/IDs.  
5. I4 uses only modalities already available — **no** HVRT/video build, Story, Journal, SMS, or Increment 5.

Regression: `i4_exploratory_multimodal` (photo-only → photo-backed; evidence-only → evidence-backed; both → multimodal; neither → insufficient; narrowed communication stays communication-focused).

---

## 0.2 Context / planner semantic rules (corrective lock)

Manual owner testing exposed context contamination. These rules are **normative** for I4 Ask:

| ID | Rule |
|----|------|
| **A** | **Current utterance > inherited context.** Explicit entities/dates/places/events/trips/people/modalities/constraints in the current utterance always outrank session context. |
| **B** | **Inherit only missing slots.** Session context fills omissions; it must not overwrite or contaminate explicit utterance information. |
| **C** | **Typed context slots.** Person, Place, Event, Trip, Date/Time, Selection, Modality are distinct. A Person must not populate Place/Trip/Event. |
| **D** | **Supersede incompatible context.** Explicit subject change (e.g. new trip vs prior holiday event) clears/replaces incompatible prior event/trip/place. |
| **E** | **Resolve references before retrieval.** “then,” “there,” “that trip,” “those,” “the other trip” resolve against session context before retrieval. |
| **F** | **Ambiguity must be disclosed.** If “the other trip” cannot be uniquely resolved, ask for clarification — never silently pick unrelated Evidence. |
| **G** | **Context-constrained retrieval.** Resolved temporal/event/trip constraints apply before/alongside semantic retrieval; vector similarity alone must not override active context. |
| **H** | **Displayed context = effective retrieval context.** Breadcrumb / plan_slots must match constraints actually used. |

Regression coverage: acceptance check `i4_context_semantics_AH` (generalized entities + unseen variation). No hard-coded Alaska/Peggy/Christmas in planner.

---

## 1. Problem / why now

I1–I3 delivered domain storage, providers, and email/calendar Evidence with a rebuildable derived index on the P1 runtime. Without Ask + planner + basic continuity, the owner still cannot **ask** and get Evidence-backed answers with follow-ups. Increment 4 is the first user-facing Ask gate (EVS-005/006).

---

## 2. Objective (MBBS)

Deliver **Evidence-backed Ask** and **conversational continuity** without requiring the user to restate full context (EF-02 basic), via Query Planner v0, thin Experience Orchestrator, session context state, and Ask UX — proven on **FlightSim**, generalized beyond demo phrases, with Immich required for photo paths and visible degradation when Immich is unavailable.

---

## 3. Success criteria (acceptance)

An increment is accepted only when **demonstrated on FlightSim** (the defined P1 MemoryBox runtime host). Desktop may be used for interim development; it does **not** satisfy final I4 acceptance.

| ID | Criterion | How we will prove it |
|----|-----------|----------------------|
| **I4-A** | Ask returns Evidence-backed family-history answers | Owner ask on FlightSim → results where each **factual family-history claim** is traceable to Evidence IDs and/or photo hits with provider `external_id` + provenance. Inventing family facts = **fail**. System-status, counts, UI language, and missing-evidence disclosures need no artificial family-evidence citations |
| **I4-B** | Missing / insufficient evidence disclosed | Ask where corpus cannot support an answer → clear insufficiency disclosure; **no** inferred convenient family fact |
| **I4-C** | EVS-005 / EVS-006 | Demonstrate both EVSs per MBEVS-001 v0.8 on single-owner P1 **on FlightSim** (scenario IDs + pass/fail in acceptance report; no family content in report) |
| **I4-D** | EF-02 basic follow-ups | After an active result/entity context, follow-ups such as “Just the ones with Peggy,” “What happened right after that?,” “What else do I have from that trip?” resolve using inherited context without restating the prior ask. These phrases are **illustrative**, not hard-coded triggers (see **I4-K**) |
| **I4-E** | Clear / change context | Owner can clear or change context; subsequent asks do not leak stale context |
| **I4-F** | Context breadcrumb + controls | UX shows current inherited context (person/place/event/time/selection as applicable) and provides clear/change-context controls |
| **I4-G** | Immich unavailable degradation (strengthened) | **Deliberately** make Immich unavailable on FlightSim: (1) perform a **photo Ask** and verify MemoryBox reports **provider unavailability** (not “no photos” / empty success); (2) then perform a **communications/calendar Ask** and verify PostgreSQL/Qdrant Evidence modalities continue to function. Ollama/Qdrant failure also surfaced when exercised |
| **I4-H** | No false memories | Acceptance script includes ≥1 inventing-temptation case that must refuse or disclose insufficiency rather than invent |
| **I4-I** | Keep runnable + portable | `health` / prior I1–I3 proves still pass on FlightSim; no forbidden host hardcodes (D7) |
| **I4-J** | Living specs | Decision log + affected docs updated before acceptance |
| **I4-K** | Generalized Ask | Planner/context behavior is **not** hard-coded to Peggy, Florida, acceptance phrases, specific dates, IDs, or other demo data. Acceptance includes **≥1 equivalent unseen variation** using different entities/context and demonstrates correct planning, retrieval, context inheritance, and evidence-backed response |

**Illustrative conversation (must feel natural — MBBS; not a hard-coded script):**

1. “Show me pictures from Florida.”  
2. “Just the ones with Peggy.”  
3. “What happened right after that?”  
4. “What else do I have from that trip?”  

Photo steps require Immich on media-server. Communications/temporal follow-ups must work when photo provider is degraded (**I4-G**). An equivalent conversation with **different** people/places/trips must also pass (**I4-K**).

**Acceptance data:** Use existing Immich library + existing PG email/calendar Evidence where practical. Create a controlled fixture pack only if real archive data cannot reliably exercise a required criterion. Never commit or paste family content into Git or acceptance reports (opaque metrics / Evidence IDs / pass-fail only).

---

## 4. Scope

### In

| Area | Detail |
|------|--------|
| **Query Planner v0** | Interprets ask + session context → retrieval plan (email/calendar Evidence; photo provider queries). **Generalized** — no demo-entity hardcoding |
| **Experience Orchestrator (thin)** | Runs plan; assembles answer; enforces Evidence First + citation rule in §0 |
| **Conversation / UX context state** | Process-session context (person, place, event, time window, gallery/result selection) with a **clean contract** for later persistence |
| **Ask UX (thin)** | Ask Bar, results, evidence/citation view, context breadcrumb, clear/change-context — functional only |
| **Retrieval** | PG Evidence + derived Qdrant for communications/calendar; PhotoProvider → Immich on media-server for photos |
| **LLM** | Via `LlmProvider` only (Ollama on FlightSim); never invent family facts |
| **POC reuse** | `rag.py` / `retrieve.py` earn-in **behind** planner/orchestrator — not as product architecture |
| **Acceptance harness** | FlightSim scripts covering I4-A–K including deliberate Immich-unavailable path and unseen variation |

### Out (explicit)

| Out | Where it goes |
|-----|----------------|
| Story / Journal | Inc 5 / 5A |
| Person teach/merge product UX | Inc 6 |
| HVRT / Review & Learn | Inc 7 |
| SMS ingest / SMS-primary Ask corpus | Later communications increment / Inc 9 |
| Guided Capture | Inc 11 |
| Export | Inc 12 |
| Multi-user / tone dial | P2 |
| Visual polish / MBUX pixel fidelity | Later P1 polish |
| Session context persistence across restart | Later; contract prepared in I4 |
| Dual-write to POC SQLite | Forbidden |
| Hard-coded hosts/paths/credentials | Forbidden (D7) |
| Hard-coded demo entities / phrases in planner | Forbidden (**I4-K**) |

### 4.1 Deferred but must not be dropped

| Capability | Plan anchor |
|------------|-------------|
| **SMS → Evidence → Ask** | Later communications increment / Increment 9; Sources CSV already on media-server |
| **Rich Person identity in Ask (EVS-014)** | Increment 10 (after Inc 6) |
| **Full EF-02 / deeper continuity** | Later P1 polish; I4 ships **basic** only |
| **Durable Ask session / context persistence** | Later; I4 designs the contract |

---

## 5. Architecture / modules (proposed)

```text
memorybox/
  ask/                 # API + orchestrator entry
  planner/             # Query Planner v0 (generalized)
  context/             # session context state + clear contract
  ux/ or static Ask shell  # thin functional
  providers/           # existing Photo / Llm (read paths)
  ingest/              # unchanged; Ask reads Evidence produced by I3
```

**Authority:** PostgreSQL Evidence + Sources (referenced) remain authoritative; Qdrant remains **derived**. Photo hits remain provider-mapped (`external_id`), never Immich UUID as Person PK.

**Planner visual contract (I4):**

| Field | Meaning |
|-------|---------|
| `visual_scope` | `none` \| `broad` \| `still_only` \| `video_only` |
| `want_visual` / `want_still` / `want_video` | Intent flags; I4 executes stills via PhotoProvider when `want_still`; `want_video` reserved for later providers |
| `want_photo` | I4 compat alias for still retrieval on the current provider |

**Citation rule (normative):**

- **Must cite / be traceable:** factual claims about family history (people, places, events, what happened, who was there, trip content, etc.) → Evidence and/or provider provenance.
- **Need not cite as family Evidence:** system-status statements, result counts, UI chrome/language, explicit missing/insufficient-evidence disclosures, provider-unavailable status.

---

## 6. Flows / EVSs

| Item | I4 treatment |
|------|----------------|
| **EF-01** | Ask path — in scope |
| **EF-02** | **Basic** only — inherited context follow-ups + clear/change |
| **EF-04** | Thin (as needed for Ask continuity) |
| **EVS-005, EVS-006** | Must pass on FlightSim |
| **Evidence First / No False Memories** | Hard acceptance gates; unsupported → disclose insufficiency |

---

## 7. Configuration & deployment (D7)

| Concern | Requirement |
|---------|-------------|
| Runtime | **Final acceptance on FlightSim** only |
| Immich | Required endpoint to **media-server** for photo acceptance; libraries stay there |
| Degradation test | Ability to take Immich offline (or misconfigure) without destroying non-photo Ask |
| Evidence | Existing PG email/calendar Evidence; re-ingest from media-server Sources only if needed for demos |
| Secrets | Gitignored env only |
| Reports | Evidence IDs / pass-fail / opaque counts only — **no** family message/photo content in Git docs |

---

## 8. Constraints & risks

| Risk | Mitigation |
|------|------------|
| Context bugs → wrong person/time | Breadcrumb + clear/change; stale-context acceptance cases |
| Invented family facts | Citation rule + I4-B/H; inventing = fail |
| Demo hardcoding (Peggy/Florida) | **I4-K** unseen variation; planner must be entity-agnostic |
| Leaky Immich IDs as Person PK | Enforce `external_id` / `provider_identities` only |
| Photo down hides mail answers | **I4-G** deliberate Immich-off path; modality isolation |
| Premature generalization / multi-agent | Planner v0 only |
| POC SQLite creep | Read Evidence from PG only |
| Over-citing UI/status text | Citation rule explicitly excludes system-status, counts, UI language, missing disclosures |

---

## 9. Build plan (sequence — only after authorization)

1. Session context model + clear contract + clear/change API (in-memory for I4).  
2. Query Planner v0 + orchestrator over PG/Qdrant + PhotoProvider + LlmProvider (generalized; no demo hardcoding).  
3. Thin Ask UX: Ask Bar, results, evidence/citation view, breadcrumb, clear/change controls.  
4. FlightSim acceptance for I4-A–K: illustrative EF-02 conversation, **I4-K** unseen variation, **I4-G** Immich-unavailable then communications Ask, EVS-005/006.  
5. Decision log + living-spec updates; **stop** (no Inc 5).

---

## 10. Change-impact check (pre-build)

| Layer | Expected impact |
|-------|-----------------|
| EVS | 005/006 demonstrated on FlightSim |
| UX | Thin Ask shell + context patterns (no polish) |
| Domain | Process-session context; clean contract for later persistence; no new SoT tables required beyond thin session/store if needed |
| Experience Flow | EF-01, EF-02 basic, EF-04 thin |
| Architecture | Planner + orchestrator modules; provider failure surfacing |
| Build Spec | Inc 4 status after acceptance |
| Locked decisions | Aligns D2/D3/D6/D7; POC earn-in; generalized Ask |

---

## 11. Authorization gate

Increment 4 is **ACCEPTED**. Do **not** begin Increment 5 until Tom explicitly authorizes *Build Increment 5 only* (or the next authorized slice).
