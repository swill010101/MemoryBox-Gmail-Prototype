# MBBS-001 Increment 5A — Definition (build authorized)

**Status:** **LOCKED — BUILD AUTHORIZED** (*Build Increment 5A only*)  
**Date:** 2026-08-09  
**Owner acceptance gate:** Tom can open the FlightSim Journal client, create **one typed** and **one spoken** entry **without developer intervention**, save both, and subsequently retrieve them through MemoryBox Ask.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5A  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 1 · Increment 4 Ask (accepted) · Increment 5 Story (accepted — patterns earn-in only; **Journal ≠ Story**)  
**Prior:** [MBBS-001_INCREMENT_5_ACCEPTANCE.md](MBBS-001_INCREMENT_5_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization:** *Build Increment 5A only* — authorized.

---

## 0. Locked decisions (final)

| Topic | Decision |
|-------|----------|
| Product slice | **Journal service + EF-12** + reusable **Capture/STT** + Ask Journal modality |
| Journal vs Story | **Distinct types** — collapsing Journal into Story is **forbidden** (MBDM) |
| Versioning | **Immutable Journal versions** (parallel in principle to Story). Edit + explicit Save → new version; priors retrievable; **no silent overwrite**. Explicit schema migration |
| STT / voice | **IN 5A** — reusable Capture/STT; Journal is first P1 consumer |
| STT provider (FlightSim) | **Existing/local Whisper** behind Capture/STT provider boundary — **replaceable/configurable**; **not** embedded in Journal code |
| Voice flow | “I want to journal” → type **or** speak → if voice: **preserve original audio** → STT → **review/edit transcript** → **explicit Save** → Journal Entry |
| No silent STT save | Transcript remains **draft** until explicit owner Save |
| Ask retrieval | **Direct PG Journal query** (parallel to Story). Do **not** materialize `journal_passage` Evidence as the required path |
| Author (SoT) | **`journal_entries.author_person_id UUID NOT NULL REFERENCES people(id)` only** — **no** dual-write `authored_by` relationship for author |
| About / other associations | Generalized `relationships` for people the Journal is **about**, Place/Event/Evidence — optional; **not** for authoritative author |
| Evidence association | **Not required** — Journal is provenance-bearing |
| Temporal | `captured_at` + `described_start_date` / `described_end_date` + `described_precision` (see §5.4). `created_at` = system insert. No full temporal algebra |
| EVS-136 | Retrieve via text, explicit relationships, and Ask context — **do not** require artificial Place relationships for acceptance |
| Guided Capture (EF-11) | **OUT** |
| Intent | “I want to journal” / “Journal” / equivalents enter thin Journal capture without taxonomy navigation |
| Acceptance | Synthetic + real FlightSim; opaque IDs/counts/status only |
| Out | SMS, HVRT/video, Person teach/merge, multi-user, polish |

---

## 1. Problem / why now

I5 delivered Stories. The owner still needs **owner-initiated Journal** (EF-12) with typed or spoken capture, immutable versions, single-source authorship, clear capture vs described time, and Ask retrieval — without Guided Capture and without treating Journal as Story.

---

## 2. Objective

1. **Journal Service** — versioned, authored (FK SoT), temporally clear, Ask-retrievable.  
2. **Reusable Capture/STT** — Whisper adapter behind provider boundary for FlightSim; Journal first consumer.  
3. **Thin Journal UX** + first-class journal intent.  
4. Prove on **FlightSim** (synthetic + real owner Journal).

| Field | Content |
|-------|---------|
| **Modules** | Journal Service; Capture/STT provider + Whisper adapter; thin Journal UX; Ask Journal modality |
| **Flows** | **EF-12** only (**not** EF-11) |
| **EVSs in** | **EVS-012**, **EVS-072**, **EVS-136** (see §8) |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I5A-A** | Typed Journal create / explicit Save | Harness |
| **I5A-OWNER** | FlightSim owner path (no developer intervention) | Tom opens Journal client → saves **one typed** + **one spoken** entry → retrieves both via Ask |
| **I5A-B** | Voice: preserve audio → STT → review/edit → explicit Save | Harness + FlightSim; opaque audio id; no Journal persist before Save |
| **I5A-C** | Immutable edit/version history | Edit+Save → v2; v1 unchanged/retrievable |
| **I5A-D** | Author SoT on `author_person_id` | Every entry NOT NULL author; API/Ask expose author; **no** authored_by dual-write |
| **I5A-E** | Capture ≠ described range | “About yesterday” today: `captured_at` today, `described_start=end=yesterday` |
| **I5A-F** | Range / month / year / approximate / unknown | Per §5.4 cases |
| **I5A-G** | Ask retrieves Journal with Journal attribution | Provenance ≠ Story; ≠ silent archive fact |
| **I5A-H** | No STT/AI auto-persist as Journal truth | Draft until Save |
| **I5A-I** | First-class journal intent | Enters capture UX without taxonomy chrome |
| **I5A-J** | Real owner Journal on FlightSim | Opaque id in prove |
| **I5A-K** | Generalized synthetic subjects | Opaque; ≠ real owner content in reports |
| **I5A-L** | I1–I5 proves remain runnable | health + prior prove commands |
| **I5A-M** | Capture/STT reusable | Whisper only behind provider; Journal does not import Whisper directly |
| **I5A-N** | Living specs | Decision log + acceptance report |
| **I5A-O** | EVS-012 / 072 / 136 | Opaque pass on single-owner P1 path |
| **I5A-P** | EVS-136 without artificial Place link | Relevant Journal found via text/context/optional real relationships — no forced Place row for the test |

---

## 4. Scope

### In

- Migration: `journal_versions`, `current_version`, `author_person_id`, temporal fields (§5)  
- Typed + voice Journal via Capture/STT (Whisper adapter on FlightSim)  
- Preserve original audio  
- Direct PG Ask retrieval + Journal provenance  
- First-class journal intent  
- FlightSim synthetic + real owner acceptance  

### Out

| Out | Notes |
|-----|--------|
| Guided Capture EF-11 | EVS-130–135, 137–140; scheduled/outbound/MB-initiated |
| Dual-write author to `relationships` | Forbidden for authoritative author |
| Required Evidence / artificial Place for EVS-136 | Forbidden as acceptance crutches |
| `journal_passage` Evidence materialization as required path | Deferred |
| Collapsing Journal into Story | Forbidden |
| SMS, HVRT, Person teach/merge, multi-user, polish | Out |
| Full temporal algebra | Out |

---

## 5. Domain (locked schema intent)

### 5.1 Versioning — explicit migration

I1 has no `journal_versions`. **Add:**

- `journal_entries.current_version INTEGER NOT NULL`  
- `journal_versions (id, journal_id, version, body_text, audio_uri, …, actor_key, note, created_at)` UNIQUE `(journal_id, version)`  
- Edit + Save → insert next version; **never** UPDATE prior version body  

### 5.2 Associations

| Fact | Mechanism |
|------|-----------|
| **Author (required, SoT)** | `journal_entries.author_person_id` only (§5.3) |
| People the entry is **about** (optional) | `relationships` (e.g. `about_person`) — **not** author |
| Place / Event / Evidence (optional) | `relationships` — no ad-hoc columns |
| Corroborating Evidence | **Not required** |

### 5.3 Authorship — single source of truth

**Locked:**

- Authoritative author = **`journal_entries.author_person_id UUID NOT NULL REFERENCES people(id)`**  
- Parallel in principle to Story’s first-class `narrator_person_id`  
- **Do not** also write an `authored_by` (or equivalent) `relationships` row for the author — avoids conflicting authorship records  
- **Do not** store authoritative author only in `attributes_json`  

Optional `relationships` may still associate **other** people the Journal discusses.

P1 single-owner path: resolve/create owner Person; Journals set `author_person_id` to that Person unless UI supplies another known Person (still required NOT NULL).

### 5.4 Temporal model — range-capable P1

I1 `recorded_at` alone is insufficient. **Locked fields:**

| Field | Type | Role |
|-------|------|------|
| `created_at` | TIMESTAMPTZ | System row creation (existing) |
| `captured_at` | TIMESTAMPTZ NOT NULL | When the owner captured/saved this journaling act |
| `described_start_date` | DATE NULL | Start of period the entry is **about** |
| `described_end_date` | DATE NULL | End of period the entry is **about** |
| `described_precision` | TEXT NOT NULL (check) | Vocabulary below |

**`described_precision` vocabulary (locked):**  
`day` | `month` | `year` | `range` | `approximate` | `unknown`

**Case mapping:**

| Case | `captured_at` | `described_start_date` / `described_end_date` | `described_precision` |
|------|---------------|-----------------------------------------------|------------------------|
| About today | now | start=end=today | `day` |
| About yesterday (created today) | now | start=end=yesterday | `day` |
| Known prior date | now | start=end=that date | `day` |
| Known range / trip | now | start and end of range | `range` |
| Month / year | now | bounded representative range (e.g. month first–last; year Jan 1–Dec 31) | `month` or `year` |
| Approximate period | now | approximate start/end where known | `approximate` |
| Unknown | now | both NULL | `unknown` |

**Constraints (P1):** if either described date is non-NULL, both should be set (start ≤ end); if precision=`unknown`, both dates NULL.  

**Legacy:** stop dual-use of `recorded_at`; optional backfill into described dates then deprecate writes to `recorded_at`.  

**Out of 5A:** full temporal algebra, recurrence, rich timezone productization beyond timestamptz + dates.

---

## 6. Capture / STT (reusable)

### 6.1 Owner-initiated flow

1. Journal intent → thin Journal capture.  
2. Type **or** speak.  
3. Voice → **preserve original audio** → STT → transcript **draft**.  
4. Owner review/edit (text + temporal fields).  
5. **Explicit Save** → Journal Entry v1 (+ author + temporal).  

### 6.2 Provider boundary (FlightSim)

- **Capture/STT protocol** in `memorybox` (replaceable).  
- **FlightSim P1 acceptance adapter:** existing/local **Whisper** behind that boundary.  
- Journal **must not** import or call Whisper directly.  
- Config-only endpoint/model/paths (D7).  
- Future Story / Guided Capture / others reuse the same capability.

### 6.3 Failure

- STT down → disclose; typed path works; do not invent transcript.  
- Audio preserve failure → do not claim voice Journal saved.

---

## 7. Ask integration

- Direct query of current Journal version + `author_person_id` + temporal + text/constraints.  
- Exploratory multimodal may include Journal with other modalities.  
- Attribution: **Journal** + author Person (+ temporal as needed).  
- Narrowed intents still win; no Journal silo.  
- No required `journal_passage` Evidence materialization.

---

## 8. EVS scope (MBEVS-001 v0.8)

### 8.1 In scope for 5A

| EVS ID | Role in 5A |
|--------|------------|
| **EVS-012** | Voice → preserve → transcript → Save → edit next day with **immutable versions** (Journal) |
| **EVS-072** | Ask: journal content by described date (“five years ago today”) |
| **EVS-136** | Ask: journals in trip/place context via **text, existing Ask context, and any real relationships** — **not** via artificial Place links invented for the test |

### 8.2 Out (Guided Capture / EF-11)

**EVS-130, 131, 132, 133, 134, 135, 137, 138, 139, 140** — MemoryBox-initiated prompting / email journal prompts / question queues.

**Distinction:** 5A = owner initiated (“I want to journal now”). Guided Capture = MB initiated.

---

## 9. Architecture notes

- PG authoritative for Journal + versions + author FK.  
- Capture/STT replaceable; Whisper = FlightSim default adapter.  
- D7 config-only.  
- Earn-in from I5 patterns; never merge Journal into Story.

---

## 10. Build plan (only after *Build Increment 5A only*)

1. Migration: versions, `author_person_id`, `captured_at`, `described_start_date`, `described_end_date`, `described_precision`.  
2. Capture/STT protocol + Whisper adapter + audio preserve.  
3. Journal Service (typed/voice, versions, author SoT, temporal).  
4. Thin `/journal/ui` + journal intent.  
5. Ask Journal modality + attribution.  
6. `prove-journal` + FlightSim owner path; EVS-012/072/136 (no fake Place for 136).  
7. Confirm I1–I5 proves.  
8. Acceptance report; **stop**.

---

## 11. Authorization gate

**Status: BUILD AUTHORIZED** (*Build Increment 5A only*).

Owner gate **I5A-OWNER** is mandatory for FlightSim acceptance. Do **not** begin 5A polish beyond scope, EF-11, or Increment 6 without explicit authorization.
