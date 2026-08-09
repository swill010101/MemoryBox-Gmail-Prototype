# MBBS-001 — MemoryBox Build Specification

**Status:** Approved P1 build charter (**v0.3**) · **Date:** 2026-08-09  
**ID:** MBBS-001  
**Owner:** Tom  
**Depends on:** Controlled specs in [`docs/source/`](../source/README.md) · Locked decisions [`MB_LOCKED_DECISIONS_P1.md`](../source/MB_LOCKED_DECISIONS_P1.md) · Standing rules [`MB_P1_ENGINEERING_RULES.md`](../source/MB_P1_ENGINEERING_RULES.md)  
**Based on:** Build-Readiness Assessment of the existing POC codebase  
**Decision log:** [`MBBS_DECISION_LOG.md`](MBBS_DECISION_LOG.md)

**Build only the authorized increment.** Do not begin the next increment without explicit owner authorization.  
**Increment 1:** Authorized and **accepted** (synthetic persistence gate) — see [MBBS-001_INCREMENT_1_ACCEPTANCE.md](MBBS-001_INCREMENT_1_ACCEPTANCE.md) · tag `increment-1-accepted`.  
**Increment 2:** Authorized and **accepted** — see [MBBS-001_INCREMENT_2_ACCEPTANCE.md](MBBS-001_INCREMENT_2_ACCEPTANCE.md).  
**Increment 3:** Authorized and **accepted** — [definition](MBBS-001_INCREMENT_3_DEFINITION.md) · [acceptance](MBBS-001_INCREMENT_3_ACCEPTANCE.md).  
**FlightSim I1–I3 checkpoint:** **PASSED** — [MBBS-001_FLIGHTSIM_I1_I3_CHECKPOINT.md](MBBS-001_FLIGHTSIM_I1_I3_CHECKPOINT.md).  
**Media-Server Sources checkpoint:** **PASSED** — [MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md](MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md).  
**Increment 4:** **CORRECTIVE reopen** — [definition](MBBS-001_INCREMENT_4_DEFINITION.md) §0.2 · [corrective acceptance](MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md) (desktop PASS; FlightSim re-prove pending). Prior tag `increment-4-accepted` retained historically. SMS deferred.


### Revision note (v0.3)

Standing **P1 Engineering Rules** (Living Specifications, one-increment-at-a-time, acceptance-before-advancement, change-impact check, no silent architecture changes, provenance/rebuildability/no false memories, durable human teaching, visible provider failure, decision log, stop on expensive ambiguity, etc.) are now governing for every increment. See [`MB_P1_ENGINEERING_RULES.md`](../source/MB_P1_ENGINEERING_RULES.md).

### Revision note (v0.2)

Founder-directed changes vs v0.1:

1. **Journal (EF-12)** is explicit **P1** — Increment **5A**.  
2. **Guided Capture (EF-11)** email + in-app is explicit **P1** — Increment **11**.  
3. **Basic contextual follow-up (EF-02)** moves into **Increment 4** (with Ask).  
4. **Minimum viable Export (EF-16)** is **P1** — Increment **12** (not deferred to P2).  
5. **Rebuildability** of every derived index is a **global P1 acceptance criterion**.

---

## 1. Purpose

MBBS-001 converts MemoryBox product and architecture specifications into an incremental build plan for the **first production MemoryBox application**.

It does **not** redefine product philosophy. It sequences work so Cursor (and humans) implement against stable boundaries rather than inventing architecture.

Traceability (from MBAA-001):

`EVS → Experience Flow → UX → Domain objects → Application module → Build increment → Acceptance`

---

## 2. Authority and locked decisions

### 2.1 Authority order

1. MBPS-001  
2. MBEVS-001 v0.8  
3. MBUX-001 v0.2  
4. MBDM-001  
5. MBEF-001  
6. MBAA-001  
7. **This Build Specification** (execution sequencing only)  

Supporting: Founder's Book, MBBC, MBX-A-*, MBD-001, feature PRDs.  
On conflict with controlled specs: **flag**, do not silently choose.

### 2.2 Locked decisions (D1–D7)

| ID | Lock |
|----|------|
| D1 | Authoritative specs in `docs/source/`; 20-EVS markdown **deprecated** |
| D2 | **New modular monolith**; POCs → adapters/engines |
| D3 | **PostgreSQL** authoritative domain store from increment 1 |
| D4 | HVRT = **sibling background worker** behind Video Intelligence Provider |
| D5 | P1-first EVS gate; **EVS-014 stays P1**, sequenced **later within P1** |
| D6 | **Single-owner** P1 |
| D7 | **FlightSim** = P1 app + MB-owned services (PG, Qdrant, Ollama where practical); **media-server** = media host (Immich/Plex/libraries) via remote providers; Inc 3+ deployable without source changes; config-only locations; Git = code only |

### 2.3 Non-goals

- Do not become a photo manager, generic RAG app, genealogy app, chatbot, or Immich replacement.  
- Do not preserve multi-SQLite federation as the product model.  
- Do not push archive takeout/mbox or `hvrt/sample` media via git.  
- Do not hard-code FlightSim, media-server, localhost, drive letters, IP addresses, credentials, or machine-specific paths into application logic (**D7**).  
- Do not move or duplicate media libraries from media-server onto FlightSim as part of P1 (**D7**).  
- Do not implement multi-user or tone dial in P1.  
- Do not require beautiful comprehensive export of every Immich-referenced original in P1 — **do** require minimum viable export (Increment 12).

### 2.4 Standing P1 engineering rules (every increment)

Full text: [`MB_P1_ENGINEERING_RULES.md`](../source/MB_P1_ENGINEERING_RULES.md). Summary:

- **One increment at a time**; **acceptance before advancement** (demonstrate MBBS criteria).  
- **Living specifications** — propagate product decisions to all affected controlled specs **before** increment acceptance; no end-of-P1 doc cleanup; no silent supersede.  
- **Change-impact check:** EVS → UX → Domain → Experience Flow → Architecture → Build Spec.  
- **No silent architecture changes**; **stop on expensive ambiguity**.  
- POC must **earn** reuse; **no premature generalization**; **no migration-debt shortcuts** (IDs, provenance, providers, PostgreSQL, relationships).  
- **Originals/provenance sacred**; **derived data rebuildable**; **no false memories**; **human teaching durable**; **provider failure visible**.  
- **Don't optimize before measuring**; **test user outcomes**; maintain **decision/deviation log**; **keep the app runnable**.  
- **Host-portable (D7)** — FlightSim hosts app + PG/Qdrant/Ollama; media-server hosts Immich/media; Inc 3+ config-only deploy; Git excludes secrets and runtime data.  
- Working software gets a vote — **not** the final vote: fix specs deliberately when wrong.  

---

## 3. Target architecture (summary)

Per MBAA-001 + D2–D4:

```text
MemoryBox modular monolith (one deployable app/API + UX)
  ├── Experience Orchestrator (MBEF flows) + conversation/context state
  ├── Query Planner / Retrieval
  ├── Domain services (Person, Place, Event, Artifact, Story, Journal,
  │     Relationship/Assertion, Evidence/Provenance, Review & Learn)
  ├── Provider adapters (Photo, VideoIntelligence, Speech, OCR, LLM,
  │     Email, Calendar, SMS, Capture)
  ├── PostgreSQL (authoritative domain)
  ├── Derived indexes (FTS, Qdrant/vectors) — must be rebuildable
  ├── Export packaging (MV export)
  └── Platform (config, jobs client, audit, health)

Sibling process:
  HVRT Video Intelligence Worker  ←→  VideoIntelligence Provider API
```

**POC disposition:** Existing Ask/RAG, Immich client, import scripts, HVRT engines, Marvin Capture, and memory versioning are **mines for adapters** — not the long-term package layout.

---

## 4. P1 sequencing principles

1. **Vertical slices** that produce usable MemoryBox behavior.  
2. **Foundation first** where otherwise every slice rewrites storage (PG + domain + providers).  
3. **Evidence First / Create No False Memories** on every Ask / Story / Journal acceptance test.  
4. **Conversational continuity** — Ask must support basic follow-ups without restating full context (EF-02 basic in Increment 4).  
5. **EVS-014** (unified person across Ask/Immich/video) is P1 but **not** early increments — see Increment 10.  
6. Prefer completing an Experience Flow’s completion condition over displaying a first partial result (MBEF).  
7. **Ownership / no lock-in** — P1 ships a way out (Increment 12), consistent with MBBC trust philosophy.  
8. **Rebuildability** — every derived index is reproducible from authoritative MemoryBox data plus preserved/referenced source evidence (global acceptance).

### 4.1 P1 sequence (locked)

| Inc | Focus |
|-----|--------|
| 0 | Specs — **done** |
| 1 | Modular monolith + PostgreSQL |
| 2 | Provider interfaces |
| 3 | Communications → Evidence |
| 4 | Ask + Query Planner + **basic contextual follow-up** |
| 5 | Story |
| **5A** | **Journal** |
| 6 | Person & Identity |
| 7 | HVRT + Review & Learn |
| 8 | Library / Gallery / Timeline |
| 9 | Artifact |
| 10 | Cross-provider Person |
| **11** | **Guided Capture — email + in-app** |
| **12** | **Minimum viable Export** |

### 4.2 P1-first EVS gate

| Priority | EVSs | Notes |
|----------|------|-------|
| A (first) | 005, 006 | Email phrase / Christmas |
| A | 001, 028-class photo-by-person | After Photo adapter + Person mapping |
| A | 012 | Story versions |
| A | Journal-related EVSs in MBEVS v0.8 | Covered by Increment 5A |
| B | 003, 007 | Video via Review / Video worker |
| B | 015 | Unified library/timeline |
| B | 022, 023 | Teach identity |
| C (later P1) | **014**, 009 | Increment 10 |
| C (later P1) | 013 thin, 004/010 thin | Artifact / recipe |
| C (later P1) | Guided-capture EVSs | Increment 11 |
| C (later P1) | Ownership / exit path | Increment 12 (MV export) |

**P2 remains P2:** multi-user sharing (017), tone dial (019), beautiful/full Immich mirror export, handwriting (027), rich era/age EVSs needing attributes not yet in domain, rich EF-13 AI Story Composition as a polished product (owner-save composition may appear earlier only if Evidence First).

---

## 5. Build increments

### Increment 0 — Spec control (docs only) — DONE

| Field | Content |
|-------|---------|
| **Objective** | Controlled specs in repo; decisions locked; obsolete EVS markdown deprecated |
| **Modules** | `docs/source/*`, hierarchy, `.gitignore`, this MBBS |
| **Acceptance** | Specs under `docs/source/`; deprecated banner on old EVS md; archives/media gitignored |
| **Risk** | Spec drift — `docs/source` is master after ingest |

### Increment 1 — Monolith skeleton + PostgreSQL domain v0 — **ACCEPTED**

| Field | Content |
|-------|---------|
| **Objective** | Production app package with migrations for core MBDM concepts (minimal physical schema) |
| **Modules** | `memorybox/` (or agreed root): app entry, config, DB migrations, health |
| **Domain (v0)** | Source, MediaObject/MediaRef, Evidence, Person, ProviderIdentity, Assertion, Relationship, Story, StoryVersion, **JournalEntry**, Job, ProcessingState |
| **Dependencies** | Increment 0; D2, D3 |
| **Flows / EVSs** | None user-facing |
| **Acceptance** | App boots; migrates empty PG; health OK; no provider schemas as domain tables — **demonstrated** ([report](MBBS-001_INCREMENT_1_ACCEPTANCE.md)) |
| **Decision log** | [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 1 |
| **Risk** | Over-modeling — keep v0 minimal |

### Increment 2 — Provider interfaces + first adapters — **ACCEPTED**

| Field | Content |
|-------|---------|
| **Objective** | Stable capability interfaces; Immich, LLM (Ollama), Email-read adapters → MemoryBox DTOs |
| **Modules** | `memorybox/providers/` + immich, llm, email adapters |
| **Reuse** | `immich_client.py`, `ollama_client.py`, mbox parse helpers — behind adapters |
| **Dependencies** | 1 |
| **Acceptance** | Domain code never uses Immich UUID as Person PK; all calls via interfaces — **demonstrated** ([report](MBBS-001_INCREMENT_2_ACCEPTANCE.md)) |
| **Risk** | Leaky DTOs — mitigated via `external_id` / `provider_key` only on person refs |

### Increment 3 — Communications → Evidence — **ACCEPTED** (email + calendar; SMS deferred)

| Field | Content |
|-------|---------|
| **Objective** | Import **email** and **calendar** into Source/Evidence; Qdrant as **derived** index; SMS deferred |
| **Modules** | `memorybox/ingest/` + calendar provider; rebuild hooks |
| **Reuse** | mbox/ICS parse earn-in; embed path behind LlmProvider |
| **Dependencies** | 1–2 |
| **Flows** | EF-05 thin; EF-14 thin |
| **Acceptance** | Email + calendar Evidence with provenance; originals untouched; Qdrant rebuildable from PG — **demonstrated** ([report](MBBS-001_INCREMENT_3_ACCEPTANCE.md)) |
| **Risk** | Dual-write to POC SQLite — avoided |
| **Deferred** | **SMS** → later communications increment / Inc 9 (must not drop from P1 plan) |

### Increment 4 — Ask + Query Planner + basic contextual follow-up

| Field | Content |
|-------|---------|
| **Objective** | Evidence-backed Ask **and** conversational continuity without restating full context |
| **Modules** | Query Planner v0; thin Experience Orchestrator; **conversation/UX context state**; Ask UX (Ask Bar, results, evidence) |
| **Reuse** | `rag.py` / `retrieve.py` behind planner |
| **Dependencies** | 3 |
| **Flows** | **EF-01**; **EF-02 basic**; EF-04 thin |
| **EVSs** | **005, 006** must pass; follow-up examples below must work on the same session context |
| **Acceptance** | Citations for facts; missing disclosed; inventing = fail. **EF-02 basic:** after a result set or entity context is active, follow-ups such as “Just the ones with Peggy,” “What happened right after that?,” “What else do I have from that trip?” resolve using inherited context (person/place/event/time/gallery selection) without requiring the user to restate the prior ask. Clearing/changing context must be possible. |
| **Risk** | Context bugs → wrong person/time answers — prefer explicit context breadcrumb + “clear context” |

**Illustrative conversation (must feel natural):**

1. “Show me pictures from Florida.”  
2. “Just the ones with Peggy.”  
3. “What happened right after that?”  
4. “What else do I have from that trip?”  

(Photo steps need Photo adapter; communications/temporal follow-ups must work even when photo provider is degraded.)

### Increment 5 — Story service + EF-10

| Field | Content |
|-------|---------|
| **Objective** | Owner-saved Stories with versions; explicit Save; prior versions retained |
| **Modules** | Story Service; optional capture/STT |
| **Reuse** | `memories.py` versioning |
| **Dependencies** | 1 (can parallelize after 1; Ask integration after 4) |
| **Flows** | EF-10 |
| **EVSs** | **012** |
| **Acceptance** | Edit → new version; current cited by default; AI narrative never auto-saved as Story |
| **Risk** | “Memory” naming — use Story in APIs |

### Increment 5A — Journal service + EF-12

| Field | Content |
|-------|---------|
| **Objective** | First-class **Journal Entry** as distinct from Story (MBDM); capture, version, search, cite as Evidence |
| **Modules** | Journal Service; journal UX; indexing into Evidence/FTS |
| **Reuse** | Capture/STT patterns from Story/Marvin where applicable — **Journal is not Story** |
| **Dependencies** | 1; ideally after 5 for shared versioning patterns; Ask citation after 4 |
| **Flows** | **EF-12** |
| **EVSs** | Journal EVSs in MBEVS-001 v0.8 applicable to single-owner P1 |
| **Acceptance** | Owner can create/edit journal entries with provenance; searchable; citable in Ask without inventing content; explicit Save for substantive entries per MBEF |
| **Risk** | Collapsing Journal into Story — forbidden by MBDM |

### Increment 6 — Person & Identity + teach (EF-07 / EF-08 thin)

| Field | Content |
|-------|---------|
| **Objective** | MemoryBox-owned Person; provider identities mapped; owner teach/confirm |
| **Modules** | Person & Identity Service; provider identity map; reindex triggers |
| **Reuse** | `people_memory` concepts; Immich/HVRT IDs as mappings only |
| **Dependencies** | 1–2 |
| **Flows** | EF-07, EF-08 thin |
| **EVSs** | **022, 023**; improves 001/028 |
| **Acceptance** | Owner teach → MB Person; merge preserves provenance; negatives retained |
| **Risk** | Merge UX — owner-led merge before ranked candidate loops |

### Increment 7 — Video Intelligence worker + Review & Learn

| Field | Content |
|-------|---------|
| **Objective** | HVRT sibling worker; Review & Learn via Video Intelligence Provider; assertions in MB domain |
| **Modules** | Provider client; HVRT worker process; Review UX |
| **Reuse** | HVRT engines/pipeline/annotations/learning behind worker API |
| **Dependencies** | 2, 6; D4 |
| **Flows** | EF-15; EF-04 video |
| **EVSs** | **003, 007** |
| **Acceptance** | Worker down → monolith degraded, not dead; teach writes MB assertions |
| **Risk** | Process boundary / contract versioning |

### Increment 8 — Library / Gallery / Timeline (EF-03)

| Field | Content |
|-------|---------|
| **Objective** | Explore without a full question; unified evidence |
| **Modules** | Context/Library APIs; Gallery/Timeline UX |
| **Reuse** | Demonstrator library concepts rewritten over PG |
| **Dependencies** | 3–7 |
| **Flows** | EF-03, EF-04 |
| **EVSs** | **015** |
| **Acceptance** | One library/timeline over MB Evidence (email, SMS, photo ref, video hit, story, journal) |
| **Risk** | UX scope creep — one Gallery pattern (MBUX) |

### Increment 9 — Artifact thin + import jobs (EF-05/06)

| Field | Content |
|-------|---------|
| **Objective** | First-class Artifact with label/story; searchable |
| **Modules** | Artifact Service; association thin |
| **Reuse** | artifact_label concept |
| **Dependencies** | 5 |
| **Flows** | EF-06; EF-05 continued |
| **EVSs** | **013** thin; foundation for 004/010 |
| **Acceptance** | Artifact with representation + label; unresolved context allowed |
| **Risk** | Premature breadth |

### Increment 10 — Cross-provider Person in Ask (EVS-014)

| Field | Content |
|-------|---------|
| **Objective** | Teach in Review → same Person in Immich photo Ask and video hits |
| **Modules** | Reindex jobs; Ask media retrieval via Person |
| **Dependencies** | 6–8 |
| **Flows** | EF-01, EF-07 (EF-02 uses Person context) |
| **EVSs** | **014**, **009** |
| **Acceptance** | Single MB Person resolves photo + video evidence with provider provenance |
| **Risk** | Hardest P1 consistency problem — do not pull earlier |

### Increment 11 — Guided Capture (EF-11) — email + in-app

| Field | Content |
|-------|---------|
| **Objective** | Guided / prompted memory capture via **email channel and in-app**; originals never lost; answers land as Journal and/or Story/Evidence per product rules |
| **Modules** | Capture channel provider; Guided Capture orchestration; email adapter (Marvin lineage); in-app prompt/reply UX |
| **Reuse** | `application/marvin_capture/*`, MBC PRDs — behind Capture provider; never lose originals |
| **Dependencies** | 5, 5A, 2 (email); preferably after 4 for discoverability |
| **Flows** | **EF-11** (may invoke EF-10 / EF-12 on save) |
| **EVSs** | Guided-capture EVSs in MBEVS v0.8 for single-owner P1 |
| **Acceptance** | Scheduled or on-demand prompt → owner reply (email and in-app) → original preserved → extracted response stored with provenance → searchable/citable; AI must not discard originals |
| **Risk** | Dual channel complexity — shared domain write path; channel-specific adapters only |

### Increment 12 — Minimum viable Export (EF-16)

| Field | Content |
|-------|---------|
| **Objective** | A real **way out** from v1: export MemoryBox-created knowledge and MemoryBox-managed originals in documented, human-readable/open formats — consistent with No Vendor Lock-In / family ownership (MBBC / MBAA) |
| **Modules** | Export service; packaging job; documented export layout |
| **What P1 MV export includes** | MemoryBox-managed original files (e.g. Story/Journal audio, uploaded/scanned artifacts MB stores); Story and Journal text; relationship / assertion / provenance **manifest** (JSON and/or CSV); enough metadata to understand Sources and Evidence refs |
| **What P1 MV export does *not* require** | Reconstructing Immich; copying every externally **referenced** original; pretty multi-format publishing |
| **Dependencies** | Domain services through 9+ (practical after meaningful knowledge exists; contract designed earlier) |
| **Flows** | **EF-16** minimum |
| **Acceptance** | Owner can produce an export package; documented README in package; MemoryBox-created knowledge + MB-managed originals present; manifest covers relationships/provenance; **no subscription required to obtain this export** of the family’s own MB data |
| **Risk** | Scope creep into full Immich mirror — reject; keep MV boundary |

---

## 6. Cross-cutting acceptance (global P1)

Applies to every relevant increment. **Also governed by** [`MB_P1_ENGINEERING_RULES.md`](../source/MB_P1_ENGINEERING_RULES.md).

1. **Evidence First** — factual statements cite Evidence.  
2. **Create No False Memories** — no invented quotes, events, or relationships as fact.  
3. **Originals sacred** — archive / Immich / video files not overwritten; derived layers additive.  
4. **Owner authority** — confirmed knowledge outranks inference; **human teaching is durable** across provider reprocessing.  
5. **Provider replaceability** — domain tests must not require Immich/HVRT schemas.  
6. **Provider failure visible** — unavailable ≠ empty results.  
7. **Local-first** — core archive + domain readable without cloud SaaS.  
8. **Jobs** — expensive work async; UX shows processing state.  
9. **Rebuildability (P1 mandatory)** — every derived index (FTS, vector/Qdrant, media search caches, etc.) **must be reproducible** from authoritative MemoryBox (PostgreSQL) data plus preserved and/or referenced source evidence. Losing an index is an operational incident, not data loss. Increments that write derived indexes must ship or demonstrate a rebuild path.  
10. **Ownership / exit** — by Increment 12, MV export exists; retention must not depend on withholding the family’s own MB-created knowledge or MB-managed originals.  
11. **Living specs** — material product decisions this increment are reflected in controlled documents before acceptance.  
12. **Runnable** — `memorybox` remains startable after the increment.  

---

## 7. Package / repo conventions (for implementers)

| Item | Convention |
|------|------------|
| New app root | Prefer `memorybox/` package (name finalized at Increment 1) |
| POC code | Remain until adapters extract value; then delete or quarantine under `poc/` |
| Secrets | Never commit; `.env` gitignored |
| Media / takeout | `.gitignore` + LAN sync only |
| Migrations | Versioned migrations against PostgreSQL |
| Derived indexes | Document rebuild commands; no index is source of truth |

---

## 8. Conflict register (known)

| Conflict | Resolution for P1 |
|----------|-------------------|
| MBD-001 “keep POC databases” vs MBAA one PG domain | Demonstrator may keep POC DBs; **production follows MBAA + D3** |
| Deprecated 20-EVS markdown vs MBEVS v0.8 | **v0.8 wins** (D1) |
| MBPS “Moment” vs MBDM Event granularity | Treat Moment as Event granularity (MBDM) |
| HVRT embedded UI vs sibling worker | **D4** sibling worker |
| Earlier MBBS draft deferred Journal / Guided Capture / Export | **Superseded by v0.2** — all three are P1 per founder revision |

---

## 9. Definition of done for “P1 application”

P1 application is done when:

- Increments **1–12** (including **5A**) acceptance criteria pass on a single-owner deployment.  
- EVS **005, 006, 012, 003, 007, 015, 022/023, 014** demonstrably pass (**014** at Increment 10).  
- **Journal (EF-12)** and **Guided Capture email + in-app (EF-11)** pass their increment acceptance.  
- **Basic EF-02** conversational follow-up works in Ask sessions (Increment 4).  
- **Minimum viable Export (EF-16)** produces a documented package of MB-created knowledge + MB-managed originals + manifest — **without** requiring a full Immich mirror.  
- **Derived indexes are rebuildable** from authoritative data + preserved/referenced sources.  
- No factual Ask answer invents unsupported memories.  
- Immich and HVRT remain replaceable behind providers.

---

## 10. Next action

1. **Increment 4 — ACCEPTED** (corrective + owner manual validation). No further I4 polish.  
2. **Increment 5 definition** — [MBBS-001_INCREMENT_5_DEFINITION.md](MBBS-001_INCREMENT_5_DEFINITION.md) is **REVIEW ONLY**.  
3. **Do not begin Increment 5** until Tom explicitly authorizes *Build Increment 5 only*.  
4. SMS remains deferred — keep on P1 roadmap.  
5. Ask-language edge cases from normal use → defect/EVS backlog for future increments (unless fundamental trust failure).

**Unauthorized increments must not start.**
