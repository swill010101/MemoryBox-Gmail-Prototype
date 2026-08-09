# MBBS-001 Increment 5A — Definition (for review)

**Status:** **REVIEW ONLY — NOT AUTHORIZED TO BUILD**  
**Date:** 2026-08-09  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5A  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 1 · Increment 4 Ask (accepted) · Increment 5 Story (accepted — patterns earn-in only; **Journal ≠ Story**)  
**Prior:** [MBBS-001_INCREMENT_5_ACCEPTANCE.md](MBBS-001_INCREMENT_5_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization gate:** Do **not** implement until Tom explicitly authorizes *Build Increment 5A only*.

---

## 0. Locked review decisions

| Topic | Decision |
|-------|----------|
| Product slice | **Journal service + EF-12** + reusable **Capture/STT** + Ask Journal modality |
| Journal vs Story | **Distinct types** — collapsing Journal into Story is **forbidden** (MBDM) |
| Versioning | **Immutable Journal version history** (parallel in principle to Story). Edit + explicit Save → new version; priors retrievable; **no silent overwrite** of owner-authored text. Explicit schema migration required |
| STT / voice | **IN 5A** — reusable P1 Capture/STT capability; Journal is first consumer |
| Voice flow | “I want to journal” → type **or** speak → if voice: **preserve original audio** → STT → **review/edit transcript** → **explicit Save** → Journal Entry |
| No silent STT save | Raw transcription is **not** owner Journal truth until explicit Save |
| Ask retrieval | **Direct PG Journal query** (parallel to Story). Do **not** materialize `journal_passage` Evidence merely because vocabulary exists; leave room for derived indexing later |
| Associations | **Require** Journal ↔ **author/Person**. Do **not** require corroborating Evidence. Generalized `relationships` may link Place/Event/Evidence where useful — no ad-hoc columns |
| Author | Every Journal Entry has a **known author Person** on the P1 single-owner path (see §5.3) |
| Temporal | **Split** capture time vs described/effective date (see §5.4). Do not overload one field for both |
| Guided Capture (EF-11) | **OUT** — no scheduled prompts, outbound email prompting, reply correlation, or MB-initiated journaling |
| Intent | “I want to journal” / “Journal” / equivalents enter thin Journal capture **without** taxonomy navigation |
| Acceptance reports | Opaque IDs/counts/status only — **never** Journal body / transcript text |

---

## 1. Problem / why now

I5 delivered Stories. The owner still needs **owner-initiated Journal** (EF-12) with typed or spoken capture, immutable versions, clear authorship, and Ask retrieval — without Guided Capture and without treating Journal as Story.

---

## 2. Objective

1. **Journal Service** — first-class Journal Entry, versioned, authored, temporally clear, Ask-retrievable.  
2. **Reusable Capture/STT** — provider-shaped capability for voice → preserved audio → transcript; Journal is first P1 consumer; Story / Guided Capture / others reuse later.  
3. **Thin Journal UX** + first-class journal intent entry.  
4. Prove on **FlightSim** with synthetic + real owner Journal.

| Field | Content |
|-------|---------|
| **Modules** | Journal Service; Capture/STT service (reusable); thin Journal UX; Ask Journal modality |
| **Reuse** | I5 Save/version/Ask patterns (earn-in); I1 `journal_entries` + new version/temporal/author columns as locked |
| **Flows** | **EF-12** (owner-initiated). **Not** EF-11 |
| **Risk** | Journal≠Story; STT not Journal-only; no Guided Capture creep |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I5A-A** | Typed Journal create / explicit Save | Synthetic + harness |
| **I5A-B** | Voice path: preserve audio → STT → review/edit → explicit Save | Harness + FlightSim; audio artifact id opaque; no save before owner Save |
| **I5A-C** | Immutable edit/version history | Edit+Save → v2; v1 body unchanged/retrievable |
| **I5A-D** | Author provenance | Every entry has author Person; Ask/API expose author |
| **I5A-E** | Capture time ≠ described/effective date | Create “about yesterday” today; both timestamps distinct and queryable |
| **I5A-F** | Approximate/unknown described date supported | Save with unknown/approximate described date where appropriate |
| **I5A-G** | Ask retrieves relevant Journal with **Journal** attribution | Exploratory Ask; provenance ≠ Story, ≠ silent archive fact |
| **I5A-H** | No AI / STT auto-persist as Journal truth | Transcript draft only until Save; AI actor rejected if applicable |
| **I5A-I** | First-class journal intent | “I want to journal” / “Journal” enters capture UX without taxonomy chrome |
| **I5A-J** | Real owner Journal on FlightSim UX | Opaque id in prove |
| **I5A-K** | Generalized synthetic subjects | Subjects ≠ real owner Journal content/ids in reports |
| **I5A-L** | Prior I1–I5 proves remain runnable | health + prior prove commands still pass |
| **I5A-M** | Capture/STT reusable boundary | STT behind capture/transcription API/module — not Whisper calls embedded only in Journal |
| **I5A-N** | Living specs | Decision log + acceptance report |
| **I5A-O** | Named EVSs (below) demonstrated on single-owner P1 path | Opaque scenario pass/fail in report |

---

## 4. Scope

### In

- Immutable `journal_versions` (or equivalent) + explicit migration  
- Author Person requirement (clean domain representation — §5.3)  
- Temporal split: capture vs described/effective (§5.4)  
- Typed Journal UX + voice Journal via reusable Capture/STT  
- Preserve original audio (MediaObject/ref or version `audio_uri` + MB-managed bytes — config paths, D7)  
- Direct PG Ask retrieval + Journal provenance labels  
- First-class journal intent entry  
- FlightSim acceptance (synthetic + real owner)  

### Out

| Out | Notes |
|-----|--------|
| Guided Capture EF-11 | EVS-130–140 class; scheduled/outbound/MB-initiated prompts |
| Collapsing Journal into Story | Forbidden |
| Materializing `journal_passage` Evidence as required path | Deferred until corpus/quality needs it |
| Required Evidence association on Journal | Not required for save/retrieve |
| SMS, HVRT/video, Person teach/merge, multi-user, polish | Later / out |
| Story product changes | Out of 5A (Capture/STT may be *callable* by Story later without Story rebuild in 5A) |

---

## 5. Domain inspection

### 5.1 Versioning — **gap → explicit migration**

I1 has `journal_entries` only — **no** `journal_versions`.  
**Locked:** add Story-parallel versioning via **explicit migration**, e.g.:

- `journal_entries.current_version`  
- `journal_versions (journal_id, version, body_text, audio_uri, transcript_text?, actor_key, note, created_at, …)`  
- Edit + Save inserts next version; never UPDATE prior `body_text`

### 5.2 Associations

| Need | Mechanism |
|------|-----------|
| Author (required) | §5.3 |
| Place / Event / Evidence (optional) | Generalized `relationships` (`from_type=journal`, appropriate `to_type` / `relationship_kind`) — no ad-hoc Journal columns |
| Corroborating Evidence | **Not required** — Journal is itself provenance-bearing |

### 5.3 Author — representation

| Existing | Assessment |
|----------|------------|
| `stories.narrator_person_id` | Story has first-class FK |
| `journal_entries` | **No** author FK today |
| `relationships` | Can express `authored_by`: `from_type=journal` → `to_type=person` |

**Clean P1 choice (locked for review):**

1. **Required** `relationships` row `relationship_kind=authored_by` (or equivalent locked kind) journal→person on every Save — graph-native, matches I1 association policy.  
2. **Plus** explicit column `journal_entries.author_person_id UUID NOT NULL REFERENCES people(id)` in the same 5A migration — **parallel to Story narrator FK**, query-friendly for Ask, prevents “authorship only in attributes_json.”

This is an **intentional schema add**, not a workaround. If build discovers FK + relationship dual-write is unclean, **STOP** and report before inventing `attributes_json` authorship.

P1 single-owner path: resolve/create the owner Person once; all Journals author to that Person unless UI supplies another known Person (still required).

### 5.4 Temporal semantics — **gap → explicit small migration**

I1 `recorded_at` is a **single** timestamptz and is insufficient once capture time and described time must differ.

| Concept | Meaning | Proposed P1 fields |
|---------|---------|-------------------|
| System created | Row insert | existing `created_at` |
| **Captured** | When the owner captured/saved this journaling act | **`captured_at TIMESTAMPTZ NOT NULL`** (default now on Save; voice: time of accepted capture) |
| **Described / effective** | What day/period the entry is *about* | **`described_date DATE NULL`** + **`described_precision TEXT`** with check ∈ (`day`,`month`,`year`,`approximate`,`unknown`) |
| Legacy `recorded_at` | Ambiguous | **Do not use for both meanings.** Migration: stop writing dual-meaning into `recorded_at`; prefer new fields. Optionally backfill `described_date` from `recorded_at::date` where present, then treat `recorded_at` as deprecated |

**Supported cases:**

| Case | `captured_at` | `described_date` / precision |
|------|---------------|------------------------------|
| Journal about today | now | today / `day` |
| Created today about yesterday | now | yesterday / `day` |
| About a prior date | now | that date / `day` |
| Unknown when events occurred | now | NULL / `unknown` |
| Approximate (e.g. “summer 2019”) | now | representative date or month-start / `approximate` or `month`/`year` |

**Out of 5A:** full temporal algebra, recurring periods, timezone policy beyond storing timestamptz + date in host-local/config convention.

---

## 6. Capture / STT (reusable)

### 6.1 Required owner-initiated flow

1. Owner expresses journal intent (“I want to journal”, “Journal”, …) → thin Journal capture.  
2. Owner **types** or **speaks**.  
3. If voice: **preserve original audio** as first-class media (not discard after STT).  
4. STT produces transcript **draft**.  
5. Owner **reviews/edits** transcript (and described date, title, etc.).  
6. **Explicit Save** → Journal Entry (+ version 1) with author + temporal fields.  

No silent save of raw STT as Journal truth.

### 6.2 Reuse boundary

- Implement as **`memorybox` Capture/STT capability** (provider protocol + adapter, e.g. local Whisper/Ollama/http — config-only, D7).  
- Journal calls the capability; **must not** bury one-off Whisper code only inside Journal modules.  
- Future Story / Guided Capture / other experiences consume the same API.

### 6.3 Failure / disclosure

- STT unavailable → disclose; typed path still works; do not invent transcript.  
- Audio preserve failure → do not claim voice Journal saved.

---

## 7. Ask integration

- Direct query of current Journal versions + author + temporal + text/constraints (parallel to Story).  
- Exploratory multimodal may include Journal with Story/Evidence/photos.  
- Attribution: **Journal** / author Person / capture vs described dates as needed — never labeled as Story; never silent archive Evidence.  
- Narrowed intents still win.  
- No Journal silo.  
- **Do not** require `journal_passage` Evidence rows for I5A.

---

## 8. EVS scope (from MBEVS-001 v0.8)

Inspected authoritative workbook `docs/source/MBEVS-001_EVS_Catalog_v0.8.xlsx` (sheet **EVS Catalog**).

### 8.1 In scope for Increment 5A (single-owner P1)

| EVS ID | Scenario (short) | Why in 5A |
|--------|------------------|-----------|
| **EVS-012** | Record → Archive Updated → Edit next day (voice note, transcript, versions; never silent overwrite) | Owner voice capture + preserve + transcript + **immutable version edit** pattern applied to **Journal** (taxonomy lists Guided & Journal Capture; Guided *prompting* remains out — this EVS’s capture/version proof is in) |
| **EVS-072** | “What did I write in my journal? Five years ago today?” | Ask retrieves Journal by **described/effective** date semantics |
| **EVS-136** | “Show me my journal entries from our Alaska trip.” | Ask retrieves Journals with place/trip context (**P1 portion** via text/associations; full inferred trip-boundary intelligence may remain partial — disclose gaps; do not invent) |

### 8.2 Explicitly OUT of 5A (Guided Capture / EF-11)

| EVS ID | Why out |
|--------|---------|
| **EVS-130** | MB asks in-app; owner answers by voice — **MB-initiated** |
| **EVS-131** | MB emails question; reply save — **MB-initiated** |
| **EVS-132** | Channel preference for guided questions |
| **EVS-133** | MB sends journal prompt “what I did today” — **MB-initiated** |
| **EVS-134** | Journal **email** attachments to prompted entry |
| **EVS-135** | Answer MB question with audio — guided |
| **EVS-137** | “What did I say when MB asked…” — guided response retrieval |
| **EVS-138** | Unanswered MB questions queue |
| **EVS-139** | “Ask me another question” |
| **EVS-140** | Evidence-aware generated question (P2) |

**Distinction locked:**  
5A = owner initiated (“I want to journal now”).  
Guided Capture = MemoryBox initiated (“Tell me about your day / answer this question”).

### 8.3 Related but not 5A primary gate

Story-centric EVSs (e.g. EVS-025, 061, 173–180) remain Story/I5+ territory. Capsule/synthesis P2 items (EVS-071, 181, 182) out of 5A.

---

## 9. Architecture notes

- PG authoritative for Journal + versions.  
- Capture/STT behind replaceable provider; audio stored as MB-managed original.  
- D7 config-only hosts/paths/keys.  
- Earn-in from I5; do not merge Journal into Story packages/tables.

---

## 10. Rough build plan (only after *Build Increment 5A only*)

1. Migration: `journal_versions`, `current_version`, `author_person_id`, `captured_at`, `described_date`, `described_precision`; deprecate dual-use `recorded_at`.  
2. Capture/STT protocol + adapter + audio preserve.  
3. Journal Service (typed + voice Save paths, versions, author, temporal).  
4. Thin `/journal/ui` + journal intent entry.  
5. Ask `want_journal` / retrieval + attribution.  
6. `prove-journal` synthetic + FlightSim owner path; EVS-012/072/136 opaque checks.  
7. Confirm I1–I5 proves still runnable.  
8. Acceptance report; **stop** (no EF-11 / Inc 6 without auth).

---

## 11. Remaining open items (non-blocking if defaults accepted)

1. STT provider default on FlightSim (local Whisper vs remote) — config choice at build.  
2. Exact `relationship_kind` string for author (`authored_by` vs `author`) — freeze at build lock.  
3. EVS-136 depth: require explicit place relationship vs text match only for P1 prove.

---

## 12. Authorization gate

**Status: REVIEW ONLY.**

Do **not** write 5A product code, migrations, Capture/STT wiring, Journal UX, or Ask Journal modality until Tom explicitly says **Build Increment 5A only**.

Unauthorized increments must not start.
