# MBBS-001 Increment 5 — Definition (for review)

**Status:** **REVIEW ONLY — NOT AUTHORIZED TO BUILD**  
**Date:** 2026-08-09  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 5  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**Depends on:** Increment 1 (domain tables) · Increment 4 Ask (accepted; citation/integration)  
**Prior increment:** [MBBS-001_INCREMENT_4_ACCEPTANCE.md](MBBS-001_INCREMENT_4_ACCEPTANCE.md) — **ACCEPTED**  
**Authorization gate:** Do **not** implement until Tom explicitly authorizes *Build Increment 5 only*.

---

## 0. Purpose of this document

This is the **review draft** for Increment 5 so scope can be locked before any code.  
It is **not** a build authorization. Open questions below must be resolved (or explicitly deferred) before build.

---

## 1. Problem / why now

Ask (I4) can retrieve and cite Evidence and photos, but the owner still cannot **compose, version, and explicitly save** durable owner Stories that Ask (and later Journal/Guided Capture) can treat as first-class, provenance-bearing artifacts. Increment 5 delivers **Story service + EF-10** so saved narrative is owner-controlled, versioned, and never silently invented or auto-persisted from AI.

---

## 2. Objective (from MBBS)

Deliver **owner-saved Stories with versions**: explicit Save; prior versions retained; current version cited by default; **AI narrative never auto-saved as Story**.

| Field | Content |
|-------|---------|
| **Modules** | Story Service; thin Story UX; optional capture/STT (only if locked in) |
| **Reuse** | Domain tables `stories` / `story_versions` (I1); versioning patterns from POC `memories.py` as earn-in only |
| **Dependencies** | 1 (schema exists); Ask citation/integration after 4 |
| **Flows** | **EF-10** |
| **EVSs** | **012** (Story versions) — single-owner P1 path |
| **Risk** | “Memory” naming — use **Story** in APIs and UX labels |

**Explicitly not Increment 5:** Journal (→ **5A**), HVRT/video, SMS, Guided Capture, Person teach/merge productization, Ask polish, multi-user.

---

## 3. Success criteria (proposed — for review)

An increment is accepted only when demonstrated on **FlightSim** (P1 runtime). Desktop may develop; it does not satisfy final acceptance.

| ID | Criterion | How we will prove it |
|----|-----------|----------------------|
| **I5-A** | Create Story with explicit Save | Owner creates/saves a Story; row + current version persisted in PG |
| **I5-B** | Edit → new version | Edit + Save creates a new `story_versions` row; prior versions retained |
| **I5-C** | Current cited by default | Ask (or Story cite API) resolves to **current** version unless a prior version is explicitly selected |
| **I5-D** | No AI auto-save | Generated draft (if any) is not persisted as Story without explicit owner Save |
| **I5-E** | Evidence First on Story claims | Factual family-history claims in Story text that are presented as facts must be citable / disclose missing support per product rules (align EF-10 / EVS-012) |
| **I5-F** | Naming | Public APIs/CLI/docs say Story, not Memory |
| **I5-G** | Keep runnable + portable | Prior I1–I4 health/proves still pass; D7 config-only hosts |
| **I5-H** | Living specs | Decision log + this definition updated at acceptance |

Opaque metrics only in acceptance reports — **no** family Story bodies in Git or reports.

---

## 4. Scope

### In (proposed)

- Story Service over existing `stories` / `story_versions` (extend schema only if gaps are proven)  
- Explicit create / edit / save / list / get-current / get-version  
- Thin functional Story UX (no visual polish)  
- Wire so Ask can **cite** current Story version when product rules require (minimal integration; not Ask redesign)  
- Acceptance harness / prove path on FlightSim  
- Decision log entry at acceptance  

### Out

| Out | Deferred to |
|-----|-------------|
| Journal Entry as distinct type | **Increment 5A** |
| Collapsing Journal into Story | **Forbidden** (MBDM) |
| HVRT / video processing / Review & Learn | Inc 7 |
| SMS ingest | Later communications / Inc 9 |
| Guided Capture email + in-app | Inc 11 area |
| Person teach/merge productization | Inc 6 |
| Ask language edge-case polish from normal use | Defects / EVS refinements in future increments (unless trust failure) |
| Visual polish, multi-user, tone dial | P2 / later |

### Optional (must be locked before build)

| Option | Default for review | Note |
|--------|--------------------|------|
| Capture / STT into Story draft | **Out unless Tom locks in** | Can reuse Marvin/capture patterns later |
| Full rich EF-13 AI Story Composition | **Out of I5** | Draft assist only if explicitly scoped; never auto-save |
| Story search in Ask as first-class modality | **Minimal cite only** unless expanded in lock |

---

## 5. Domain mapping

| Concept | Storage |
|---------|---------|
| Story | `stories` |
| Version | `story_versions` (immutable versions; `stories.current_version` pointer) |
| Narrator | `narrator_person_id` → Person when available |
| Provenance | Version payload / metadata — original owner text retained; no silent rewrite of prior versions |

---

## 6. Architecture notes

- PostgreSQL remains authoritative for Story content.  
- Do not dual-write Story SoT to SQLite or provider-native “memories.”  
- POC `memories.py` is **earn-in**, not package layout.  
- Providers (Immich/Ollama) are not Story storage.  
- Evidence First / Create No False Memories apply to any Ask surface that presents Story-derived family facts.

---

## 7. Build plan (rough — only after authorization)

1. Lock open questions below; freeze §0/§3/§4.  
2. Story Service API + persistence against I1 tables; gap migrations if needed.  
3. Thin UX + explicit Save.  
4. Minimal Ask cite-current integration.  
5. FlightSim prove + acceptance report.  
6. Decision log; **stop** (no 5A / Inc 6 without auth).

---

## 8. Open questions for Tom

1. Is **STT / capture into Story draft** in I5, or deferred?  
2. Must I5 include a **thin Ask citation path** for Stories, or is service + UX enough with Ask citation in a follow-on slice?  
3. EVS-012 acceptance: what is the **minimum opaque demo** on FlightSim (synthetic Story only vs owner-saved real Story with opaque IDs)?  
4. Confirm **Journal remains 5A** and must not ship inside I5.  
5. Any Story fields beyond I1 schema required for EF-10 (tags, attachments, Evidence links)?

---

## 9. Authorization gate

**Status: REVIEW ONLY.**  

Do **not** write Increment 5 product code, migrations for I5 features, or Story UX implementation until Tom explicitly says **Build Increment 5 only** (or an explicitly named I5 slice).

Unauthorized increments must not start.
