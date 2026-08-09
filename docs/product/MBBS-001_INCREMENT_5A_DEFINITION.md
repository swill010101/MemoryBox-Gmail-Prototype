# MBBS-001 Increment 5A — Definition (for review)

**Status:** **REVIEW ONLY — NOT AUTHORIZED TO BUILD**  
**Date:** 2026-08-09  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5A  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**Depends on:** Increment 1 (domain) · Increment 4 Ask (accepted) · Increment 5 Story (accepted — versioning/Ask patterns to earn from, **not** to merge types)  
**Prior increment:** [MBBS-001_INCREMENT_5_ACCEPTANCE.md](MBBS-001_INCREMENT_5_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization gate:** Do **not** implement until Tom explicitly authorizes *Build Increment 5A only*.

---

## 0. Purpose of this document

Review draft so Journal scope can be locked before any code.  
This is **not** a build authorization.

**Hard rule (MBDM):** Journal is a **distinct** domain type from Story. Collapsing Journal into Story is **forbidden**.

---

## 1. Problem / why now

Stories (I5) hold owner-saved narrative recollections that Ask can retrieve. The owner still needs a first-class **Journal** for day-to-day / dated personal entries (EF-12) that are searchable, provenance-bearing, and citable in Ask — without treating Journal as “just another Story.”

---

## 2. Objective (from MBBS)

Deliver a **Journal service + EF-12**: first-class **Journal Entry** distinct from Story; owner create/edit with provenance; searchable; citable in Ask without inventing content; explicit Save for substantive entries.

| Field | Content |
|-------|---------|
| **Modules** | Journal Service; thin Journal UX; Ask retrieval/citation integration; indexing path (PG and/or derived FTS/Evidence — lock in §10) |
| **Reuse** | I5 Story Service patterns (explicit Save, Ask modality, opaque acceptance) as **earn-in only**; I1 `journal_entries` table |
| **Dependencies** | 1; after 5 for shared patterns; Ask after 4 |
| **Flows** | **EF-12** |
| **EVSs** | Journal-related EVSs in MBEVS-001 v0.8 applicable to single-owner P1 |
| **Risk** | Collapsing Journal into Story — **forbidden** |

---

## 3. Proposed success criteria (for review)

Final acceptance on **FlightSim**. Desktop may develop; it does not satisfy final 5A acceptance.

| ID | Criterion | How we will prove it |
|----|-----------|----------------------|
| **I5A-A** | Create / explicit Save | Journal entry persisted with provenance (channel, timestamps) |
| **I5A-B** | Edit with history semantics | Locked edit model (see §5 / open Q1) proven: either versioned like Story or audited overwrite — **must be locked before build** |
| **I5A-C** | Retrieve by id + list/search | Get entry; search/list by text and/or `recorded_at` |
| **I5A-D** | Distinct from Story | Separate APIs/UX/types; Ask provenance labels Journal ≠ Story |
| **I5A-E** | Provenance-bearing owner entry | Owner Journal may be saved without independent archive corroboration; Ask attributes as journal/owner entry (parallel to I5-E for Story) |
| **I5A-F** | Ask retrieves Journal | After Save, relevant exploratory Ask can retrieve Journal alongside other modalities (no Journal silo) |
| **I5A-G** | Ask attribution | Citations expose Journal provenance (not silent archive fact; not Story label) |
| **I5A-H** | No AI auto-save | AI-generated text never silently becomes Journal; no auto-save |
| **I5A-I** | Naming | APIs/CLI/docs say Journal / Journal Entry — never “Story” or generic “Memory” for this type |
| **I5A-J** | Generalized + real | Synthetic automated subjects ≠ real owner Journal; ≥1 real owner Journal via FlightSim UX; opaque reports only |
| **I5A-K** | Keep runnable + portable | Prior I1–I5 health/proves still pass; D7 config-only |
| **I5A-L** | Living specs | Decision log + acceptance report |

Acceptance reports: opaque IDs/counts/status only — **never** Journal body text.

---

## 4. Scope

### In (proposed)

- Journal Service over I1 `journal_entries` (+ migrations **only if** a locked gap requires them — see §5)  
- Explicit create / edit / Save / get / list / search  
- Thin functional Journal UX (no visual polish)  
- Associations via generalized `relationships` where subjects are needed (Person/Evidence/Place/Event) — prefer I1 graph over ad-hoc columns  
- Ask: Journal as retrievable modality (parallel to Story; distinct provenance)  
- Synthetic prove + real FlightSim owner Journal path  
- Opaque acceptance report  

### Out (proposed defaults)

| Out | Deferred to |
|-----|-------------|
| Collapsing Journal into Story | **Forbidden** |
| STT / voice capture into Journal | Later capture / Guided Capture (**default OUT** unless Tom locks in) |
| Guided Capture email + in-app (EF-11) | Later Guided Capture increment |
| Story feature changes / I5 polish | Out of 5A |
| SMS, HVRT/video, Person teach/merge | Later increments |
| Multi-user, tone dial, visual polish | P2 / later |

---

## 5. Domain mapping & gap inspection (I1)

### 5.1 Existing `journal_entries` (I1)

| Column | Role |
|--------|------|
| `id` | Entry id |
| `title`, `body_text` | Content |
| `recorded_at` | Journal time (when the entry is about / was recorded) |
| `channel` | `ui` \| `email` \| `voice` \| `import` \| `other` |
| `audio_uri` | Optional media pointer (no STT pipeline required in 5A if voice OUT) |
| `source_id` | Optional link to `sources` |
| `status` | `active` \| `removed` |
| `attributes_json` | Extensible attributes |
| timestamps | `created_at` / `updated_at` |

Evidence kind vocabulary already contemplates `journal_passage` (migration comment on `evidence`).

### 5.2 Gap vs Story / MBBS “version”

| Need | Story (I5) | Journal (I1 today) | 5A implication |
|------|------------|--------------------|----------------|
| Immutable version history | `story_versions` + `current_version` | **No** `journal_versions` table | **Domain gap** if MBBS “version” means Story-like immutability |
| Narrator person FK | `narrator_person_id` | Not on journal row | Use `relationships` and/or attributes — prefer graph; STOP if unclean |
| Ask retrieval | Direct query + modality | Not wired | Build in 5A (direct query and/or Evidence materialization — lock in §10) |

**Policy (same as I5):** Prefer existing generalized domain. If required associations or versioning cannot be supported cleanly → **STOP and report the domain gap** before workarounds or silent schema invention.

**Open Q1 must be locked before build:** versioning model for Journal.

---

## 6. Journal vs Story (normative)

| | **Story (I5)** | **Journal (5A)** |
|--|----------------|------------------|
| Intent | Owner narrative recollection / testimony about subjects | Dated / personal journal entry (EF-12) |
| Type | `stories` + `story_versions` | `journal_entries` (+ versions only if locked) |
| Ask label | Owner/narrator recollection (Story) | Owner journal entry (Journal) |
| UX | `/story/ui` | Separate `/journal/ui` (proposed) |
| Forbidden | — | Implementing Journal as a Story subtype or shared table |

---

## 7. Evidence First / provenance (proposed, parallel to I5-E)

Owner-authored Journal content is **provenance-bearing**. It does **not** require independent corroborating archive Evidence before MemoryBox may preserve or retrieve it.

Distinguish:

1. Owner Journal entry (channel + timestamps + id)  
2. Independently corroborating archive Evidence  
3. AI-generated / inferred claims — never silently become Journal; never auto-save  

When Ask uses a Journal entry, attribution must remain available so MemoryBox does not present it as silent independent archive fact or as a Story.

---

## 8. Ask integration (no silo)

- After explicit Save, current Journal participates in Ask for relevant subjects/time/text.  
- Exploratory know-about may return Journal **with** other modalities.  
- Explicit narrowing still wins (e.g. emails-only does not dump Journals).  
- Do not build a Journal-only search product Ask cannot see.  
- Provenance labels must say **Journal**, not Story.

---

## 9. Architecture notes

- PostgreSQL authoritative for Journal content.  
- No dual-write Journal SoT to SQLite or provider “memories.”  
- D7: FlightSim = P1; config-only hosts.  
- Earn-in from I5 patterns; do not merge packages into a single “narrative” type.

---

## 10. Open questions for Tom (must answer before build)

1. **Versioning:** Story-like immutable `journal_versions`, or single-row edit with `updated_at` only for P1 5A? (I1 has no version table today — Story-like needs a migration; that is a deliberate schema add, not a silent workaround.)  
2. **STT / voice channel in 5A?** Default proposal: **OUT** (channel enum may still allow `voice` later).  
3. **Ask retrieval mechanism:** Direct `journal_entries` query (like I5 Stories) vs also materializing `evidence_kind=journal_passage`? Default proposal: **direct query first**; optional Evidence materialization only if needed for cite/index parity.  
4. **Minimum associations for acceptance:** Journal↔Person and/or Journal↔Evidence required like I5-D, or recorded_at + text search enough for 5A-A/C/F?  
5. **Author/narrator:** Required person association on every Journal, or optional?  
6. **EVS list:** Which specific Journal EVSs from MBEVS v0.8 are in-scope for single-owner P1 5A (IDs)?  
7. Confirm **Guided Capture (EF-11)** stays out of 5A.

---

## 11. Rough build plan (only after authorization + Q lock)

1. Lock §10 answers; freeze scope.  
2. Schema: only if Q1 requires `journal_versions` (or equivalent) — explicit migration.  
3. Journal Service + thin UX.  
4. Ask modality + attribution.  
5. Synthetic prove + FlightSim owner Journal.  
6. Acceptance report; **stop** (no Inc 6 / Guided Capture without auth).

---

## 12. Authorization gate

**Status: REVIEW ONLY.**

Do **not** write Increment 5A product code, Journal UX, Ask Journal wiring, or 5A migrations until Tom explicitly says **Build Increment 5A only**.

Unauthorized increments must not start.
