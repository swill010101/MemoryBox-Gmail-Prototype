# MBBS-001 Increment 5 — Definition (for review)

**Status:** **REVIEW ONLY — NOT AUTHORIZED TO BUILD**  
**Date:** 2026-08-09  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**Depends on:** Increment 1 (domain + relationships) · Increment 4 Ask (accepted; multimodal exploratory retrieval)  
**Prior increment:** [MBBS-001_INCREMENT_4_ACCEPTANCE.md](MBBS-001_INCREMENT_4_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization gate:** Do **not** implement until Tom explicitly authorizes *Build Increment 5 only*.

---

## 0. Locked review decisions

| Topic | Decision |
|-------|----------|
| Product slice | **Story service + EF-10** + **first-class Ask retrieval modality** (no Story silo) |
| STT / voice capture into Story draft | **OUT** — preserve for later capture / Guided Capture |
| Journal | **OUT of I5** — remains distinct domain type in **Increment 5A** |
| Ask integration | Saved Stories are a **retrievable MemoryBox knowledge source/modality**. Broad exploratory Ask (e.g. “What do you know about \<subject\>?”) must be able to retrieve the **current** Story alongside other applicable I4/I5 modalities |
| Acceptance corpus | **Synthetic** Stories for deterministic automated acceptance **and** ≥1 **real owner-saved** Story via FlightSim Story UX |
| Acceptance reports | **Opaque IDs / counts / status only** — never real Story text |
| Schema policy | Inspect I1 domain/relationship model **before** any Story-specific columns. Prefer generalized `relationships`. If required associations cannot be supported cleanly → **STOP and report domain gap** (no workaround) |
| AI | Never silently become owner Story evidence; **never auto-save** |
| Out of I5 | Journal, STT, Guided Capture, SMS, HVRT/video build, Person teach/merge, multi-user, visual polish |

---

## 1. Problem / why now

Ask (I4) retrieves email/calendar Evidence and Immich stills, but the owner still cannot **compose, version, and explicitly save** durable Stories that participate in the same multimodal Ask graph. Increment 5 delivers owner-controlled Stories so recollection is preserved with provenance and is **findable in Ask**, not trapped in a silo.

---

## 2. Objective

Deliver **owner-saved Stories with immutable versions** and make the **current** Story a **first-class Ask modality** alongside Evidence and photos.

| Field | Content |
|-------|---------|
| **Modules** | Story Service; thin Story UX (no polish); Ask retrieval/attribution integration |
| **Reuse** | I1 `stories` / `story_versions`; I1 generalized `relationships`; POC `memories.py` versioning as earn-in only |
| **Dependencies** | 1 (schema + relationships exist); 4 (Ask exploratory multimodal) |
| **Flows** | **EF-10** (+ Ask retrieval of saved Stories) |
| **EVSs** | **012** (Story versions) — single-owner P1 path |
| **Risk** | “Memory” naming — use **Story** in APIs/UX; collapsing Journal into Story — **forbidden** |

---

## 3. Success criteria (acceptance)

Final acceptance is on **FlightSim**. Desktop may develop; it does not satisfy final I5 acceptance.

| ID | Criterion | How we will prove it |
|----|-----------|----------------------|
| **I5-A** | Create / explicit Save | Synthetic + owner path: Story + version 1 persisted |
| **I5-B** | Edit / Save → version 2 | Version 2 created; version 1 remains immutable |
| **I5-C** | Retrieve current + prior | Get current by default; explicitly retrieve prior version |
| **I5-D** | Associations | Story associated with ≥1 **Person** and ≥1 **Evidence** via domain model; narrator/person provenance present |
| **I5-E** | Provenance semantics | Owner/narrator recollection may be saved **without** independent corroborating archive Evidence; Ask attribution distinguishes recollection vs independently corroborated Evidence vs AI |
| **I5-F** | Ask retrieves Story | After save, broad exploratory Ask about a relevant subject retrieves the **current** Story with other applicable modalities (no silo) |
| **I5-G** | Ask attribution | When Ask uses a Story, response exposes Story/narrator provenance (e.g. owner recollection), not as silent independent fact |
| **I5-H** | No AI persist / auto-save | Unsupported AI-generated / inferred content is **not** persisted as Story; no auto-save |
| **I5-I** | Naming | Public APIs/CLI/docs say Story, not Memory |
| **I5-J** | Generalized + real | Automated suite uses **subjects different from** the real owner Story; real owner Story exercised on FlightSim UX (opaque IDs only in reports) |
| **I5-K** | Keep runnable + portable | Prior I1–I4 health/proves still pass; D7 config-only |
| **I5-L** | Living specs | Decision log + acceptance report updated |

Acceptance reports: opaque Story/version/person/evidence IDs, counts, statuses — **never** Story body text.

---

## 4. Scope

### In

- Story Service over I1 `stories` / `story_versions`  
- Explicit create / edit / **Save** / list / get-current / get-version  
- Thin functional Story UX on FlightSim (no visual polish)  
- Associate Story with subjects using **generalized domain relationships** (and `narrator_person_id`)  
- Ask integration: current Story is a **retrievable modality** in multimodal / exploratory Ask (alongside communication, calendar, stills as applicable)  
- Attribution/provenance on Ask results that use Stories  
- Deterministic synthetic acceptance + real owner-saved Story path  
- FlightSim prove + opaque acceptance report  

### Out (locked)

| Out | Deferred to |
|-----|-------------|
| STT / voice capture into Story draft | Later capture / Guided Capture |
| Journal Entry | **Increment 5A** (distinct type) |
| Collapsing Journal into Story | **Forbidden** (MBDM) |
| Guided Capture email + in-app | Later Guided Capture increment |
| SMS ingest | Later communications / Inc 9 |
| HVRT / video processing / Review & Learn | Inc 7 |
| Person teach/merge productization | Inc 6 |
| Rich EF-13 AI Story Composition as product | Later / out of I5 |
| Multi-user, tone dial, visual polish | P2 / later |
| Ask language edge-case polish from normal use | Defect backlog / future increments (unless trust failure) |

---

## 5. Domain mapping & association policy

### 5.1 I1 inspection result (pre-build; no new columns assumed)

| Need | Existing support | Notes |
|------|------------------|-------|
| Story entity | `stories` | `title`, `status`, `current_version`, timestamps |
| Versions | `story_versions` | `version`, `body_text`, `actor_key`, `created_at`, optional `audio_uri` / `note` / `confidence_at_save` |
| Narrator / person provenance | `stories.narrator_person_id` → `people` | Required for I5-E/G attribution |
| Story ↔ Person (about) | `relationships` | I1 synthetic already uses `relationship_kind=about_person`, `from_type=story`, `to_type=person` |
| Story ↔ Evidence | `relationships` | I1 synthetic already uses `relationship_kind=cites_evidence`, `from_type=story`, `to_type=evidence` |
| Place / Event / media associations | Same `relationships` graph | Prefer `from_type=story` + appropriate `to_type` / `relationship_kind` rather than ad-hoc Story columns |
| Assertions (optional) | `assertions` + `assertion_evidence` | Available when a claim needs structured assertion status; **not** required to “validate” owner recollection before save |

**I5 minimum proof:** narrator provenance + Story↔Person + Story↔Evidence using the above.  
**No Story-specific association columns** unless a clean gap is proven. If the generalized model cannot support a required association cleanly → **STOP and report the domain gap** before any workaround.

### 5.2 Version semantics (locked)

1. Explicit **Save** persists.  
2. Prior versions are **immutable**.  
3. **Current** version is used by default (Ask + APIs).  
4. Prior versions remain **explicitly retrievable**.  
5. **No AI auto-save.**  
6. Edit + Save creates a **new version** (does not overwrite history).

---

## 6. Evidence First / provenance semantics (I5-E refined)

Owner-authored Story content is **itself provenance-bearing narrative evidence**. It does **not** require independent corroborating photo/email/calendar/document Evidence before MemoryBox may **preserve** or **retrieve** it.

MemoryBox **must distinguish**:

| Kind | Meaning |
|------|---------|
| Owner / narrator recollection or testimony | Explicitly saved Story (narrator, timestamp, version, provenance) |
| Independently corroborating archive Evidence | Email, calendar, photo/provider hits, etc. |
| AI-generated / inferred claims | Never silently become owner Story evidence; never auto-save |

An owner may explicitly save a recollection with **no** independent archive support. When Ask uses that Story for a family-history statement, **attribution must remain available** so MemoryBox can distinguish e.g. “Tom recalled…” from independently corroborated facts.

AI-generated narrative or inferred family facts must **never** silently become owner Story evidence and must **never** auto-save.

---

## 7. Ask integration (no silo)

- After explicit Save, the **current** Story participates in Ask retrieval for relevant subjects (person/place/event/trip/topic associations and/or content match as designed).  
- Broad exploratory intents from I4 (know-about / tell-me-about / what-do-I-have-about) must be able to return Story hits **together with** other applicable modalities.  
- Explicitly narrowed intents still win (e.g. emails-only does not dump Stories unless also relevant under that narrowing — follow I4 narrowing rules; do not invent a Story-only bypass).  
- Do **not** build a separate “Story search product” that Ask cannot see.

---

## 8. Architecture notes

- PostgreSQL is authoritative for Story content and relationships.  
- No dual-write Story SoT to SQLite or provider-native memories.  
- Providers (Immich/Ollama) are not Story storage.  
- POC earn-in only; product code lives under MemoryBox packages.  
- D7: FlightSim = P1 app/services; config-only hosts; no hard-coded hosts/credentials.

---

## 9. Build plan (rough — only after authorization)

1. Confirm association kinds (`about_person`, `cites_evidence`, narrator) against I1; STOP only if gap found.  
2. Story Service: create/save/edit-version/get-current/get-version + associations.  
3. Thin FlightSim Story UX (explicit Save).  
4. Ask: register Story as retrievable modality + attribution in results.  
5. Synthetic prove suite (generalized subjects ≠ real owner Story).  
6. FlightSim: automated prove + one real owner-saved Story (opaque report).  
7. Decision log + acceptance; **stop** (no 5A / Inc 6 without auth).

---

## 10. Open questions remaining

1. Exact Ask ranking/blend when Story + Evidence + photos all hit — default proposal: return all applicable modalities with clear provenance labels (I4-style multimodal presentation). Confirm or adjust at build lock.  
2. Whether `evidence_kind` / derived index should materialize `story_passage` rows for retrieval, vs querying `stories`/`story_versions` directly in Ask — choose at build lock without creating a silo either way.  
3. Optional Place/Event association kinds for I5 demo beyond Person+Evidence — nice-to-have if relationship kinds already clear; not a substitute for I5-D minimum.

---

## 11. Authorization gate

**Status: REVIEW ONLY.**

Do **not** write Increment 5 product code, Story UX implementation, Ask Story modality wiring, or I5 migrations until Tom explicitly says **Build Increment 5 only**.

Unauthorized increments must not start.
