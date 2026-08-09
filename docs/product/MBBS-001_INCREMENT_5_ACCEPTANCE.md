# MBBS-001 Increment 5 — Acceptance Report

**Status:** **ACCEPTED**  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_5_DEFINITION.md](MBBS-001_INCREMENT_5_DEFINITION.md)  
**Charter:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5 (Story service + EF-10)  
**Authorization:** *Build Increment 5 only*  
**Final acceptance host:** P1 runtime (**FlightSim**)  
**Depends on:** Increment 1 (domain + relationships) · Increment 4 Ask (accepted)

---

## 1. Verdict

| Gate | Result |
|------|--------|
| Story Service (explicit Save, immutable versions, associations) | **COMPLETE** |
| First-class Ask Story modality + narrator attribution (no silo) | **COMPLETE** |
| Thin Story UX (`/story/ui`) | **COMPLETE** |
| Desktop `prove-story` | **PASS** |
| FlightSim `prove-story --flightsim` | **PASS** (`ok: true`, `problems: []`) |
| Real owner-saved Story via FlightSim Story UX | **PASS** (opaque id; `v=1`) |
| Living specs / decision log updated | **PASS** |

**Increment 5 is ACCEPTED.**

**Do not begin Increment 5A (Journal), Increment 6, or any later slice without explicit authorization.**  
**Out of I5 (confirmed unused):** STT/voice capture, Journal, Guided Capture, SMS, HVRT/video build, Person teach/merge productization, multi-user, visual polish.

This report contains **opaque IDs, counts, and statuses only**. It does **not** contain Story body text, family narrative content, or credentials.

---

## 2. Scope accepted

### In

- Owner-saved **Stories** with **explicit Save**
- **Immutable** prior versions; edit+Save → new version; **current** used by default; prior versions explicitly retrievable
- Associations via I1 domain model: `narrator_person_id`, `relationships` (`about_person`, `cites_evidence`)
- **Ask** retrieves current Story as a first-class modality alongside other applicable modalities (exploratory / know-about)
- Ask **attribution** distinguishes owner/narrator recollection from archive Evidence
- AI-generated content **cannot** be persisted as owner Story (`actor_key=ai` rejected); **no auto-save**
- Thin functional Story UX; synthetic automated acceptance + ≥1 real owner Story on FlightSim

### Out (locked exclusions honored)

| Exclusion | Deferred to |
|-----------|-------------|
| Journal Entry | Increment **5A** |
| STT / voice into Story draft | Later capture / Guided Capture |
| Guided Capture, SMS, HVRT/video, Person teach/merge | Later increments |
| Multi-user, tone dial, visual polish | P2 / later |

---

## 3. Success criteria map

| ID | Criterion | Result | Opaque proof |
|----|-----------|--------|--------------|
| **I5-A** | Create / explicit Save | **PASS** | Harness `i5_a_create_save`; synthetic `story_id` + `v=1` + narrator id |
| **I5-B** | Edit / Save → version 2; v1 retained | **PASS** | Harness `i5_b_edit_new_version`; `current=2` |
| **I5-C** | Retrieve current + prior version | **PASS** | Harness `i5_c_retrieve_current_and_prior` |
| **I5-D** | Story ↔ narrator/Person + Evidence | **PASS** | Harness `i5_d_associations`; `people=1` `evidence=1` |
| **I5-E** | Recollection without corroborating archive Evidence | **PASS** | Harness `i5_e_recollection_without_corroboration` |
| **I5-F** | Broad Ask retrieves current Story | **PASS** | Harness `i5_f_ask_retrieves_story`; `want_story=True` `story_hits=4` `kind=mixed` |
| **I5-G** | Ask attribution / provenance | **PASS** | Harness `i5_g_ask_attribution` |
| **I5-H** | No AI persist / auto-save | **PASS** | Harness `i5_h_no_ai_persist` |
| **I5-I** | Naming = Story (not Memory) | **PASS** | Harness `i5_i_naming_story` |
| **I5-J** | Generalized synthetic + real owner Story | **PASS** | Synthetic tag `Harborwick-3c6503c4`; owner `3a51e7ba-…` |
| **I5-K** | Keep runnable; health increment ≥5 | **PASS** | Harness `i5_k_health`; `increment=5` |
| **I5-L** | Living specs | **PASS** | This report + definition + decision log |

**Additional harness:** `i5_narrowed_email_no_story` **PASS** (emails-only does not request Story modality).

---

## 4. Provenance semantics verified

| Kind | Behavior demonstrated |
|------|------------------------|
| Owner / narrator recollection | May be saved and retrieved without independent photo/email/calendar support |
| Independently corroborating archive Evidence | Remains separate; Story may optionally `cites_evidence` |
| AI-generated / inferred | Rejected on persist (`actor_key=ai`); never auto-saved as Story |

When Ask uses a Story, citations expose `kind=story`, `provenance_kind=owner_narrator_recollection`, and attribution text (e.g. narrator recalled) — not as silent independent archive fact.

---

## 5. FlightSim final (opaque)

| Field | Value |
|-------|-------|
| Date | 2026-08-09 |
| Host | FlightSim (P1 runtime) |
| Command | `python -m memorybox prove-story --flightsim` |
| Env | `MEMORYBOX_P1_RUNTIME_HOST=1`; `MEMORYBOX_I5_OWNER_STORY_ID=<owner uuid>` |
| Result | `"ok": true` |
| Problems | `[]` |
| `p1_runtime_final` | `true` |
| Health | `increment=5` |
| Synthetic story id | `43ed1e95-9808-4026-ba41-4b7abd470070` |
| Synthetic tag | `Harborwick-3c6503c4` |
| Owner story id | `3a51e7ba-7341-4823-b311-f485a161ccc6` |
| Owner story version | `1` |
| Ask opaque | `want_story=True`, `story_hits=4`, `kind=mixed` |

### Harness check roll-up (FlightSim)

All listed checks `ok: true`:  
`i5_a_create_save`, `i5_b_edit_new_version`, `i5_c_retrieve_current_and_prior`, `i5_d_associations`, `i5_e_recollection_without_corroboration`, `i5_h_no_ai_persist`, `i5_f_ask_retrieves_story`, `i5_g_ask_attribution`, `i5_narrowed_email_no_story`, `i5_i_naming_story`, `i5_j_generalized_subjects`, `i5_k_health`, `i5_j_real_owner_story`, `i5_l_living_specs`.

---

## 6. Owner UX checkpoint

| Step | Result |
|------|--------|
| Save Story via `/story/ui` on FlightSim | **PASS** |
| Opaque `story.id` obtained | `3a51e7ba-7341-4823-b311-f485a161ccc6` |
| Bound into FlightSim prove via `MEMORYBOX_I5_OWNER_STORY_ID` | **PASS** (`i5_j_real_owner_story`) |

UX hardening during acceptance (blank optional UUID fields; clear errors) shipped before final prove (`5c46e77`).

---

## 7. What shipped

| Area | Location |
|------|----------|
| Story Service | `memorybox/story/__init__.py` |
| I5 acceptance harness | `memorybox/story/acceptance.py` |
| Thin Story UX | `memorybox/story/static/story.html` → `GET /story/ui` |
| Planner `want_story` | `memorybox/planner/` |
| Ask Story retrieval | `memorybox/ask/retrieve.py` (`search_stories`) |
| Ask orchestration + attribution | `memorybox/ask/orchestrator.py` |
| HTTP API | `POST/GET /story`, versions, person/evidence associate |
| CLI | `python -m memorybox prove-story [--flightsim]` |
| Health | `increment: 5` |

**Notable commits (examples):** `ad7a4a5` (I5 build), `3d197eb` / `5c46e77` (FlightSim/UX harden), `6ae6d7a` (acceptance record).

---

## 8. Post-acceptance policy

- Further Story/Ask edge cases from normal use → **defects / EVS refinements** in a **future increment**, unless they expose a **fundamental trust or architecture failure** (Evidence First / No False Memories / inventing / silent AI-as-Story).  
- Do **not** continue polishing Increment 5 ad hoc.  
- **Journal remains Increment 5A** and must not be collapsed into Story.

---

## 9. Stop

- Increment 5 **ACCEPTED** on FlightSim with owner Story UX proof.  
- **Do not** start **5A**, **6**, Guided Capture, SMS, HVRT/video, or polish without explicit authorization.
