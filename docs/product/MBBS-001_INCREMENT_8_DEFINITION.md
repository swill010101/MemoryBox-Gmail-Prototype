# MBBS-001 Increment 8 — Definition (review only — no build)

**Status:** **LOCKED FOR REVIEW** — decisions proposed; **NOT BUILD AUTHORIZED**  
**Date:** 2026-08-10  
**Owner acceptance gate (proposed):** On FlightSim, Tom can open a thin **Library / Timeline** client **without developer intervention**, browse a **unified** chronological (or filterable) view across **at least three** real evidence modalities already available from I1–I7 (e.g. email Evidence, Immich photo refs, HVRT/video hits, Story, Journal), open a card to see **honest provenance / modality / identity trust**, and return to Ask/Review without a separate “second app.” Synthetic harnesses prove the unified Library API + empty/provider-down disclosure.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 8  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx)  
**Depends on:** Increment 3 (email/calendar Evidence) · Increment 4 Ask · Increment 5 / 5A (Story / Journal) · Increment 6 Person · **Increment 7 Video / Review (ACCEPTED)** · D7 (FlightSim app; media-server providers)  
**Prior:** [MBBS-001_INCREMENT_7_ACCEPTANCE.md](MBBS-001_INCREMENT_7_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization:** *Do not build Increment 8 until Tom explicitly says so.*

---

## 0. Locked decisions (proposed for Tom review)

| Topic | Decision |
|-------|----------|
| Product slice | **Library / Gallery / Timeline** as **one** browse surface over a **unified evidence read API** — explore **without** requiring a full Ask question (EF-03) |
| Primary EVS | **EVS-015** thin — browse timeline/library across modalities |
| One Gallery pattern | **One** MBUX-aligned pattern (risk lock from MBBS). Not three competing UIs. **Timeline-first** mixed feed with optional modality filters; visual “Gallery” mode is a **view of the same cards**, not a second product |
| Unified evidence | Cards normalize **email**, **calendar** (if present), **photo refs** (Immich via PhotoProvider), **video hits** (VideoIntelligenceProvider), **Story**, **Journal**. Each card carries modality + provenance + identity trust when applicable |
| SMS | **Earn-in only** if SMS Evidence already exists in PG from prior ingest. I3 staged SMS without ingest → Library discloses “SMS not ingested” — **not** an I8-OWNER blocker to add SMS ingest |
| Ask vs Library | Ask = question → retrieve. Library = **browse / filter / scroll** without a question. Shared citation/card shape where practical; do **not** fork a second evidence model |
| Identity trust | Reuse I6/I7 rules: owner-confirmed vs trusted-provider vs candidate. Library must **not** present provider-seeded or AI candidates as owner-confirmed |
| Person / teach | Deep Person teach stays in `/people/ui` and `/review/ui`. Library may **link** to Person / open Ask with person context — **full teach UX OUT** of I8 |
| Review / HVRT | Review remains the video teach surface. Library may deep-link to a video hit / Review when worker healthy — **does not** re-implement Review |
| Immich / video originals | Still **referenced**; originals untouched; Immich write-back **OUT** |
| Settings / multi-user / polish | **OUT** of I8 |
| EVS-014 full cross-provider | **OUT** → Increment 10 |
| Artifacts / Guided Capture / Export | **OUT** → Inc 9 / 11 / 12 |
| Hosts (D7) | FlightSim app + PG; Immich/video libraries on media-server via existing providers; config-only paths |
| Prove command | Primary: **`prove-library`** with named API / UX / provider-down / modality subchecks + `--flightsim` owner path |
| Acceptance | Synthetic harness + real FlightSim owner browse; opaque IDs/counts/status only |

---

## 1. Problem / why now

Ask (I4–I7), Story/Journal (I5/5A), People (I6), and Review/video (I7) work as **directed** surfaces. The family still cannot **browse** the archive without inventing a question.

Without I8:

- EVS-015 stays unmet.  
- Demonstrator “Library/Timeline” remains a parallel prototype, not MB-domain PG.  
- Risk of bolting a second evidence model or a photo-only Gallery that ignores email/Story/video trust rules.

I8 productizes **one** browse path over the **same** MemoryBox domain + providers already proven.

---

## 2. Objective

1. **Unified Library read API** — paginated, filterable evidence cards from PG + photo/video providers (read-only).  
2. **Thin Library / Timeline UX** — browse without Ask; open card detail with provenance; modality filters.  
3. **Shared trust labels** — reuse Person / Ask attribution semantics.  
4. Prove via **`prove-library`** (synthetic + FlightSim owner browse).

| Field | Content |
|-------|---------|
| **Modules** | Library / Context read API; Gallery/Timeline thin UX; card DTO shared with Ask citations where practical |
| **Flows** | **EF-03**; **EF-04** thin (browse visual refs already available — not a new Ask rewrite) |
| **EVSs in** | **EVS-015** thin |

---

## 3. Success criteria (acceptance)

Final acceptance on **FlightSim** for **I8-OWNER**; harness for the rest via **`prove-library`**.

| ID | Criterion | Proof |
|----|-----------|-------|
| **I8-A** | Unified Library API returns mixed-modality cards (synthetic: ≥3 modalities) | `prove-library` |
| **I8-B** | Timeline/chronological ordering (or explicit “undated” bucket with disclosure) | Harness |
| **I8-C** | Modality filter (e.g. photos / video / email / story / journal) works without silent drop of other types from the product | Harness |
| **I8-D** | Card provenance honest: modality + source/provider + identity trust when person-linked | Harness |
| **I8-E** | Photo/video provider down → Library remains up; affected modalities show **visible degradation** (not empty success) | Harness |
| **I8-F** | Does not invent evidence; empty filters disclose “no items” | Harness |
| **I8-G** | Reuses I6/I7 trust — no silent promotion of candidates to confirmed | Harness |
| **I8-H** | Thin UX: browse → open card → return; nav to Ask / Review / People exists | FlightSim |
| **I8-OWNER** | FlightSim: browse real family archive across **≥3** live modalities without developer intervention / SQL | Tom on FlightSim |
| **I8-I** | No Immich/HVRT native schemas as MB domain tables; originals untouched | Health / policy |
| **I8-J** | I1–I7 proves remain runnable | Prior prove commands |
| **I8-K** | Living specs | Decision log + acceptance report |
| **I8-L** | SMS: if not ingested, disclosed and **not** required for owner gate | Note / optional |

---

## 4. Scope

### In

- Library read API over MB Evidence + Story + Journal + photo/video provider refs  
- Thin `/library/ui` (or equivalent) Timeline-first browse + optional Gallery layout of **same** cards  
- Filters: modality; optional person (via I6 resolver); optional coarse time range  
- Card detail: provenance, trust, deep-link to Ask / Review / People when relevant  
- Provider-down degrade per modality  
- **`prove-library`** + FlightSim owner path  
- Quiet consistency with existing chrome (Ask / Review / People nav)

### Out

| Out | Notes |
|-----|--------|
| Full MBUX pixel polish / multi-theme | Later polish |
| Second evidence database / demonstrator dual-store | Rewrite over PG + providers only |
| Immich write-back | Locked OUT |
| EVS-014 full cross-provider enroll loop | **Increment 10** |
| Artifact boxing / keepsake product | **Increment 9** |
| Guided Capture | **Increment 11** |
| Export package | **Increment 12** |
| SMS ingest as I8 requirement | Earn-in only |
| Rich Person teach inside Library | Use People / Review |
| Multi-user, sharing, invite relatives | Out |
| Settings UI | Out |
| Auto-curated “highlights” / AI story invent | Forbidden (Create No False Memories) |
| Replacing Ask | Ask unchanged except optional deep-links |

---

## 5. Domain / provider intent

### 5.0 Library card (illustrative)

Each card is a **read model**, not a new SoT:

| Field (illustrative) | Rule |
|----------------------|------|
| `modality` | email \| calendar \| photo \| video \| story \| journal \| (sms if present) |
| `external_id` / domain ids | Provider IDs remain external; MB UUIDs for Story/Journal/Evidence/Person |
| `occurred_at` / `undated` | Prefer evidence timestamps; undated disclosed |
| `identity_trust` | confirmed \| trusted_provider \| candidate \| n/a |
| `attribution` / `provenance` | Honest; never invent |

### 5.1 Providers

- Photos: existing PhotoProvider (Immich)  
- Video: existing VideoIntelligenceProvider (worker URL / media root unchanged)  
- Email/calendar/Story/Journal: PostgreSQL domain  
- Do **not** embed Immich/HVRT schemas in MB domain

### 5.2 Ask / Review coexistence

```
Ask     = question → retrieve
Review  = teach video faces
People  = teach / map identity
Library = browse / filter without a question
```

Same FlightSim monolith; config-driven providers (D7).

---

## 6. UX (thin)

Locked thin Library surface:

- Timeline (default) of unified cards  
- Optional Gallery layout for visual modalities **using the same card API**  
- Modality chips / filters  
- Open card → provenance + trust  
- Nav: Ask · Review · People · Library  

No dashboard chrome, no multi-column knowledge graph, no Settings.

Owner FlightSim gate uses this UI without SQL/API babysitting.

---

## 7. Architecture notes

```
memorybox serve (FlightSim)
    ├─ /ask/ui
    ├─ /review/ui
    ├─ /people/ui
    └─ /library/ui  ← I8
         │
         ▼
    Library read API
         ├─ PG Evidence / Story / Journal / People
         ├─ PhotoProvider (Immich on media-server)
         └─ VideoIntelligenceProvider (worker → \\media-server\photos\home videos)
```

Demonstrator `application/` Library concepts may be **mined for UX ideas** only — not packaged as the P1 SoT (same D2 spirit as HVRT).

---

## 8. EVS scope (MBEVS-001 v0.8)

### 8.1 In (thin)

| EVS ID | Role in I8 |
|--------|------------|
| **EVS-015** | Browse a timeline/library across available modalities — **not Ask-only** |

### 8.2 Improves / related (not full acceptance bars)

| EVS ID | Note |
|--------|------|
| EVS-002-class | Browse may surface mixed Christmas-like clusters later; full narrative Ask remains I4+ |
| EVS-016 | Soft “related” suggestions **OUT** of I8 unless free earn-in |

### 8.3 Out (later)

| Slice | Increment / track |
|-------|-------------------|
| EVS-014 | 10 |
| EVS-013 Artifact | 9 |
| Guided Capture | 11 |
| Export | 12 |

---

## 9. Build plan (only after *Build Increment 8 only*)

1. Library card DTO + read API (Fake-friendly).  
2. Wire PG modalities + photo/video provider refs.  
3. Thin `/library/ui` Timeline + filters + card detail.  
4. Provider-down degrade paths.  
5. **`prove-library`** subchecks + `--flightsim`.  
6. Confirm I1–I7 proves.  
7. Acceptance report; **stop**.

---

## 10. Risks

| Risk | Mitigation |
|------|------------|
| UX scope creep (three Galleries) | One pattern; Gallery = view mode of same cards |
| Second evidence model | Single read API over existing domain/providers |
| Trust dilution in browse | Reuse I6/I7 labels; no silent confirm |
| Performance on large archives | Pagination; coarse filters; no full Immich mirror |
| SMS gap | Earn-in / disclose; not owner blocker |

---

## 11. Authorization gate

**Status: NOT BUILD AUTHORIZED.**

This document is for **Tom review / lock**. Do **not** begin Increment 8 implementation until Tom explicitly authorizes: *Build Increment 8 only*.

---

## 12. Stop line

After definition lock: wait for build authorization. Do **not** begin Increment 9 / 10 / Guided Capture / Export from this document alone.

---

## 13. Open questions for Tom (answer before build authorize)

1. **Default view:** Timeline-first (proposed) vs Gallery-first for first paint?  
2. **Person filter on owner gate:** required, or modality browse alone enough?  
3. **Calendar:** include as first-class modality on owner gate, or email+photo+video+story sufficient?  
4. **Deep-link to Review:** required for video cards in I8, or “open video hit in Ask/citation” enough?  
5. Any modality that must be **hard-required** among the ≥3 for I8-OWNER?

---

*End of Increment 8 definition — review only. No build.*
