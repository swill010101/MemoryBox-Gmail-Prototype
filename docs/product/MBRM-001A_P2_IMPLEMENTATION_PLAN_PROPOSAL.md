# MBRM-001A — P2 Implementation Plan

**Status:** Planning direction **approved** · P2-I1 definition **LOCKED** · **Date:** 2026-08-12  
**Locked inputs:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) · [MBEVS-001 v1.0](MBEVS-001_EVS_CATALOG_v1.0.md) · [`docs/source/`](../source/)  
**Supporting catalogs (ingested 2026-08-13; do not silently resequence this plan):** [MBUX-001 v0.4](MBUX-001_v0.4.md) · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) · [planning delta](MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md)  
**Supersedes sequencing in:** [MBRM-001_P2_ROADMAP.md](MBRM-001_P2_ROADMAP.md)  
**P2-I1 definition (locked):** [MBBS-P2_INCREMENT_1_DEFINITION.md](MBBS-P2_INCREMENT_1_DEFINITION.md)  
**Gate:** Increment builds require explicit definition + build authorization (I1–I7 **ACCEPTED** including **I4** 2026-08-18; **P2-I7A ACCEPTED** 2026-08-15; **MBQL-001 ACCEPTED** 2026-08-18). SMS attachment bytes = **P2-BL-I7-01**. I8 email attachment files up front = **P2-BL-I8-01**. Explore visual polish = **P2-BL-I4-01** (does not reopen I4).  
**Owner-pass order:** **P2-I4 ACCEPTED** 2026-08-18 (Tom: functional and UX satisfactory). **MBQL-001 ACCEPTED** 2026-08-18. Do not start I8 until Tom authorizes I8. Do not reopen I4 for aesthetic polish.  
**I7A insertion (2026-08-15):** [MBRM-001 v0.2](MBRM-001_v0.2_AI_TRACE_INSERTION.md) · [I7A definition](MBBS-P2_INCREMENT_7A_DEFINITION.md) · [MBPRD-P2-I7A](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md). **MBQL-001** is [ACCEPTED](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) 2026-08-18.

## 0. First-increment verdict (confirmed)

**Do not start P2 with Product Shell / High-Volume UX / Settings / Archive Health.**

First authorized build candidate remains **P2-I1 — Show me Peggy (Person-in-Media Vertical)**: Immich→canonical Person → photos + **face-appearance** timeslots → jump-to-moment → correct → reusable evidence → retrieval update, with thin open/detail/correct/return context.

Shell, Archive Health, Settings, and high-volume timeline stay in P2 but **after** this vertical (or only as a minimal I1 slice if required to expose sync/reprocessing status).

---

## 1. Founder decisions locked into this plan (2026-08-12)

| # | Topic | Locked decision |
|---|--------|-----------------|
| 1 | Duplicate EVSs | **Lower-number EVS is canonical.** Higher duplicate (EVS-183..202) is a **historical alias**, not a separate acceptance scenario. |
| 2 | EVS-020 vs 202 | **EVS-020 governs** → phase **P2**. EVS-202 is alias only. |
| 3 | I1 “moment” | **Face-appearance timeslot only** (not speech passages). |
| 4 | New-Person video reprocessing | **Full eligible-archive** durable queue; excluded/failed videos visible with reason; later exemplar changes may be targeted/incremental only if equivalent coverage is provable; not flag-only |
| 4a | Eligible video | Configured/healthy source + technically processable by supported pipeline |
| 4b | Recognition authority | Auto-associate at system confidence; **owner-confirmed/corrected outranks**; preserve method, confidence, exemplars, confirmation state |
| 4c | I1 acceptance corpus | Clear Peggy appearance; no-Peggy video; ideally ambiguous; correction case; enough videos for full-library queue demo |
| 5 | Immich face assets | **Required in I1** as usable, provenance-preserved face evidence. |
| 6 | HVRT readiness | **Real timeslot recognition required** for I1 acceptance. Degraded-provider UX alone **does not pass**. |
| 7 | TASK-004 inventory | Keep in **P2-I3**, unless a **minimal** piece is technically necessary to expose I1 sync/reprocessing status. |
| 8 | Confidence thresholds | **System-managed through P2** unless deliberately reopened. |

Also still locked from prior planning: owner-run campaigns (not multi-user); Late-P2/P2.5 multi-user; nightly Immich sync + Sync/Poll now; auto create/map; private owner trust ratings; EVS-254–256 in **P2-I12** (after core narrative); formal Experience Flows only where multi-step reuse needs them.

---

## 2. Major dependency chains

### Chain A — Person-in-media (I1 critical path)

```text
Immich named Person
  → nightly sync / Sync now
  → canonical MB Person (map or create; conflict → review)
  → Immich face assets as provenance-preserved exemplars
  → enqueue FULL eligible-archive into durable recognition queue
     (excluded/failed videos visible with reason — never silent omit)
  → observable processing state
  → face-appearance timeslot (method, confidence, exemplars, confirmation state)
  → searchable moment (owner-confirmed outranks auto-associate)
  → Ask “Show me Peggy” (photos + moments, not file-only)
  → open jumps to timeslot
  → correct miss/wrong association
  → reusable higher-authority identity evidence
  → subsequent retrieval reflects correction
  → return to original result context
```

### Chain B — Spoken moments (P2-I9)

Source AV → STT → diarization → speaker↔Person → passage → searchable spoken moment → correct/reuse.

### Chain C — Provider identity sync

Provider change → nightly/Sync now → reconcile → review on ambiguity → **enqueue** video recognition work (not flag-only).

### Chain D — Evidence → narrative

Ingest → correlate → narrative/summary → drill-down → review before durable Story save.

### Chain E — Gap → propagate

Archive gap → Review task → owner correction → propagate → preserve provenance.

---

## 3. Normalized increment sequence

| ID | Name | Kinds | Notes |
|----|------|-------|-------|
| **P2-I1** | Show me Peggy (Person-in-Media Vertical) | F+E | **ACCEPTED** (2026-08-13) |
| **P2-I2** | Product Shell & Context Maturation | U | **ACCEPTED** (2026-08-13) |
| **P2-I3** | Archive Health & Provider Honesty | U+A | **ACCEPTED** (2026-08-13) |
| **P2-I4** | Mixed-Media Find / Explore (Timeline-first) | U | **ACCEPTED** (2026-08-18 — Tom: functional and UX satisfactory; remaining visual defects **P2-BL-I4-01**) — [I4 definition](MBBS-P2_INCREMENT_4_DEFINITION.md) |
| **P2-I5** | Universal Person Surfaces | F+U | **ACCEPTED** (2026-08-14) — rest of TASK-001 |
| **P2-I6** | Kinship Inference | A | **ACCEPTED** (2026-08-14) — TASK-002 |
| **P2-I7** | SMS/Text Evidence | A | **ACCEPTED** (2026-08-15) — [I7 definition](MBBS-P2_INCREMENT_7_DEFINITION.md); attachment bytes **P2-BL-I7-01** |
| **P2-I7A** | AI Model Trace & Observability | F | **ACCEPTED** (2026-08-15) — after I7 ACCEPTED, before MBQL-001 — [I7A definition](MBBS-P2_INCREMENT_7A_DEFINITION.md) · [schema](MBBS-P2_I7A_TRACE_SCHEMA.md) |
| **MBQL-001** | Ask, Query & Command Language | F | **ACCEPTED** (2026-08-18 — Tom: “MBQL is accepted”) — [definition](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) · [PRD](MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md). After I7A ACCEPTED, before I8. |
| **P2-I8** | Richer Email | A | **BUILD AUTHORIZED** 2026-08-18 (definition locked; not yet ACCEPTED) — [I8 definition](MBBS-P2_INCREMENT_8_DEFINITION.md) · [PRD](MBPRD-P2-I8_RICHER_EMAIL.md) |
| **P2-I8.5** | Face Evidence Ownership & Immich Decoupling | F | Existing inserted increment; unchanged by I7A |
| **P2-I9** | Spoken Moments (STT/Speaker) | F+A | |
| **P2-I10** | Cross-Source Correlation | A | |
| **P2-I11** | Narrative & Summaries | E+A | Family evidence only |
| **P2-I12** | External Historical Context | E | EVS-254–256 only |
| **P2-I13** | Dynamic Views | U | |
| **P2-I14** | Settings & Processing Controls | U | No confidence dials |
| **P2-I15** | Owner-run Capture Campaigns | E | Not multi-user |
| **P2-I16** | Trust Consistency & Private Owner Trust | F | |
| **P2-I17** | Portability & Import-back | A | TASK-003; **EVS-020** |
| **Late** | Multi-user + Tone Dial | E | EVS-019 (EVS-201 alias) |

Kinds: **F** foundational · **U** UX maturation · **A** archive understanding · **E** family experience.

```text
I1 Show me Peggy
 → I2 Shell → I3 Archive Health (+004) → I4 Timeline explore
 → I5 Universal Person → I6 Kinship
 → I7 SMS → I7A Model Trace → MBQL-001 → I8 Email → I8.5 Face SoT → I9 Spoken → I10 Correlate
 → I11 Narrative → I12 External history → I13 Views
 → I14 Settings → I15 Campaigns → I16 Trust → I17 Portability
 → Late multi-user / tone
```

---

## 4. Increment sheets (normalized)

### P2-I1 — Show me Peggy (Person-in-Media Vertical) · F+E

| Field | Content |
|-------|---------|
| **Primary outcome** | “Show me Peggy” returns Immich-backed canonical Person results with photos and **face-appearance** video moments; jump-to-timeslot; correct→reuse; observable recognition queue; context return |
| **MBPS** | P2-ID-01..04; P2-VID-01..04 (+ VID-05 earn-in); thin UX context/progressive disclosure |
| **EVSs (canonical)** | Primary homes in Appendix A.1 under I1; P1 teach/person video basics remain regression but must **earn in** to moment-complete behavior |
| **Capabilities** | Nightly sync + Sync now; auto map/create; Immich face assets as evidence; durable video recognition queue (full eligible archive); timeslot index; Ask person+moments; correction→relearn; context stack |
| **Prerequisites** | P1 baseline; **working HVRT/timeslot recognition** |
| **Domain/services** | Person/Identity; Provider sync; Face evidence; Video recognition queue/worker; Ask; Provenance; thin Review |
| **UX / Flows** | Formalize Show-me-Peggy result→open→correct→return; Recognize→Confirm→Reuse |
| **Acceptance** | See [I1 definition](MBBS-P2_INCREMENT_1_DEFINITION.md) |
| **OUT** | Speech moments; full shell; Archive Health redesign; Settings; SMS; kinship; narrative; multi-user; TASK-004 unless minimal status needed |
| **Risks** | Queue backlog UX; Immich face API/rights; FlightSim HVRT must be real for pass |

### P2-I2 — Product Shell & Context Maturation · U

Wrap I1 in coherent navigation (P2-UX-01/04). OUT: high-volume timeline engine (I4).

### P2-I3 — Archive Health & Provider Honesty · U+A

P2-AH-01..03; **TASK-004** Immich Photos inventory. Minimal sync/reprocess status may already appear in I1; full inventory honesty here.

### P2-I4 — Timeline-first High-Volume Explore · U

P2-UX-02/03. Depends on I2; improved by I1 moments. **ACCEPTED** 2026-08-18 (Tom: functional and UX satisfactory; remaining visual defects parked **P2-BL-I4-01**). [I4 definition](MBBS-P2_INCREMENT_4_DEFINITION.md). Do not reopen I4 for aesthetic polish.

### P2-I5 — Universal Person Surfaces · F+U

Remainder of TASK-001 across Story/Journal/Library/Artifact/etc.

### P2-I6 — Kinship Inference · A

P2-GRAPH-01; TASK-002. Disclosed inference; no tree viz. **ACCEPTED** 2026-08-14 — [I6 definition](MBBS-P2_INCREMENT_6_DEFINITION.md).

### P2-I7 — SMS/Text Evidence · A

P2-COM-01 · CAP-P2-018. **ACCEPTED** 2026-08-15 (Tom). Attachment bytes parked **P2-BL-I7-01**. [I7 definition](MBBS-P2_INCREMENT_7_DEFINITION.md).

### P2-I7A — AI Model Trace & Observability · F

Developer-only request→model→disposition traces. **ACCEPTED** 2026-08-15 (Tom FlightSim owner pass). [I7A definition](MBBS-P2_INCREMENT_7A_DEFINITION.md) · [schema](MBBS-P2_I7A_TRACE_SCHEMA.md). **No MBQL in I7A.**

### MBQL-001 — Ask, Query & Command Language · F

Shared typed intent for Planner / Orchestrator / Explore commands. **ACCEPTED** 2026-08-18 (Tom: “MBQL is accepted”). [definition](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) · [PRD](MBPRD-P2-MBQL-001_ASK_QUERY_COMMAND_LANGUAGE.md). Q1 residual model only. I9 stays after I8.5. **P2-I8 is BUILD AUTHORIZED** (2026-08-18).

### P2-I8 — Richer Email · A

P2-COM-02/03. **P2-BL-I8-01:** ingest **attachment files up front** (do not repeat the I7 CSV-only gap). [I8 definition](MBBS-P2_INCREMENT_8_DEFINITION.md) **LOCKED + BUILD AUTHORIZED** 2026-08-18. Do not start I8.5 / I9 / I10 / I11.

### P2-I8.5 — Face Evidence Ownership · F

Existing inserted increment (Immich decoupling). Unchanged by I7A.

### P2-I9 — Spoken Moments · F+A

P2-AUD-01..04; Chain B. Authentic voice only.

### P2-I10 — Cross-Source Correlation · A

P2-GRAPH-02/03.

### P2-I11 — Narrative & Summaries · E+A

P2-NAR-01..03. Review before durable save.

### P2-I12 — External Historical Context · E

P2-NAR-04; **EVS-254, 255, 256 only**. After I11.

### P2-I13 — Dynamic Views · U

P2-VIEW-01..03.

### P2-I14 — Settings & Processing Controls · U

P2-SET-01/02. Sync controls may exist earlier; confidence stays system-managed.

### P2-I15 — Owner-run Capture Campaigns · E

P2-CAP thin; owner-mediated only.

### P2-I16 — Trust Consistency & Private Owner Trust · F

P2-TRUST-*; owner-private trust never in family UX.

### P2-I17 — Portability & Import-back · A

**EVS-020**; TASK-003. EVS-202 is alias only.

### Late — Multi-user + Tone

P2-MU-*; **EVS-019** (EVS-201 alias).

---

## 5. Traceability summary

| Pool | Count | Rule |
|------|------:|------|
| Canonical active acceptance EVSs (P2 + P1–P2; EVS-020 for export) | **129** | Each has one primary increment (Appendix A.1) |
| Historical aliases EVS-183..202 | **20** | Not separate acceptance; inherit canonical home (Appendix A.2) |
| P1-only | 115 | Regression; selected earn-ins under I1 |
| P3 synthetic / deferred invite | out | EVS-253, 257–260, EVS-018 (+ alias 200) |

---

## 6. Finish block

### A. Sequence

See §3 normalized table (I1→I17 + Late).

### B. EVS traceability

Appendix A — canonical homes + alias table.

### C. Top dependency chains

§2 Chains A–E.

### D. Remaining open questions (non-blocking for I1 draft)

1. Owner-visible recognition-queue UX density (per-video vs aggregate progress) — detail in I1 definition defaults; refine at acceptance if needed.  
2. Exact Immich API surface for face assets on FlightSim — validate during I1 definition review / pre-build spike **without** expanding product scope.  
3. Whether any **minimal** TASK-004 probe must ship inside I1 for sync/queue observability — default **no**; only if technically necessary.

### E. First authorized build

**P2-I1 Show me Peggy** — definition **LOCKED**: [MBBS-P2_INCREMENT_1_DEFINITION.md](MBBS-P2_INCREMENT_1_DEFINITION.md). **No code** until explicit **“Build P2-I1”**.

---

## Appendix A — EVS homes

*Do not renumber or delete EVSs. Aliases are not independent acceptance scenarios.*

### A.1 Canonical acceptance homes (active P2 / P1–P2; EVS-020 governs export)

| EVS | Phase | Taxonomy | Primary increment |
|---|---|---|---|
| EVS-002 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |
| EVS-004 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-008 | P1–P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-009 | P1–P2 | Photos | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-010 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-011 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-017 | P2 | Sharing | P2-I2 Product Shell & Context Maturation |
| EVS-019 | P2 | Trust & Evidence | Late-P2/P2.5 Multi-user + Tone |
| EVS-020 | P2 | Ownership & Portability | P2-I17 Portability & Import-back |
| EVS-024 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-026 | P1–P2 | People & Identity | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-027 | P2 | People & Identity | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-029 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-030 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-033 | P1–P2 | People & Identity | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-034 | P1–P2 | People & Identity | P2-I5 Universal Person Surfaces |
| EVS-035 | P1–P2 | People & Identity | P2-I5 Universal Person Surfaces |
| EVS-037 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-038 | P2 | People & Identity | P2-I5 Universal Person Surfaces |
| EVS-039 | P2 | People & Identity | P2-I5 Universal Person Surfaces |
| EVS-040 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-042 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-043 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-045 | P2 | People & Identity | P2-I6 Kinship Inference |
| EVS-047 | P1–P2 | Communications | P2-I8 Richer Email |
| EVS-055 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-058 | P2 | Video | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-064 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-065 | P1–P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-069 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-070 | P2 | Communications | P2-I8 Richer Email |
| EVS-071 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-079 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-081 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |
| EVS-082 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |
| EVS-083 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-084 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-085 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |
| EVS-086 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |
| EVS-087 | P1–P2 | Relationships | P2-I6 Kinship Inference |
| EVS-088 | P1–P2 | Relationships | P2-I6 Kinship Inference |
| EVS-089 | P1–P2 | Relationships | P2-I6 Kinship Inference |
| EVS-090 | P1–P2 | Places | P2-I4 Timeline-first High-Volume Explore |
| EVS-091 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-092 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-093 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-094 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-095 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |
| EVS-096 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-097 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-098 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-100 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-103 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-105 | P1–P2 | Places | P2-I4 Timeline-first High-Volume Explore |
| EVS-106 | P1–P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-107 | P1–P2 | Communications | P2-I8 Richer Email |
| EVS-108 | P1–P2 | Communications | P2-I8 Richer Email |
| EVS-109 | P2 | Photos | P2-I8 Richer Email |
| EVS-110 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |
| EVS-111 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |
| EVS-114 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-116 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |
| EVS-118 | P1–P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-119 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |
| EVS-123 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-124 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-126 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |
| EVS-127 | P2 | People & Identity | P2-I5 Universal Person Surfaces |
| EVS-128 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |
| EVS-129 | P1–P2 | Family Contribution | P2-I15 Owner-run Capture Campaigns |
| EVS-136 | P1–P2 | Guided & Journal Capture | P2-I15 Owner-run Capture Campaigns |
| EVS-140 | P2 | Guided & Journal Capture | P2-I15 Owner-run Capture Campaigns |
| EVS-147 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-149 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-152 | P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-157 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-158 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-159 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-161 | P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-167 | P1–P2 | Trust & Evidence | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-168 | P2 | Trust & Evidence | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-170 | P1–P2 | Trust & Evidence | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-171 | P2 | Trust & Evidence | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-181 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-182 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-203 | P2 | Corrections & Learning | P2-I3 Archive Health & Provider Honesty |
| EVS-204 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-205 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-206 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-207 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-208 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-209 | P2 | People & Identity | P2-I6 Kinship Inference |
| EVS-210 | P2 | Relationships | P2-I6 Kinship Inference |
| EVS-211 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-212 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-213 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-214 | P2 | Corrections & Learning | P2-I16 Trust Consistency & Private Owner Trust |
| EVS-216 | P2 | Trust & Evidence | P2-I3 Archive Health & Provider Honesty |
| EVS-217 | P2 | Ownership & Portability | P2-I17 Portability & Import-back |
| EVS-220 | P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-221 | P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-222 | P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-223 | P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-224 | P2 | Communications | P2-I7 SMS/Text Evidence |
| EVS-226 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-227 | P2 | Discovery | P2-I4 Timeline-first High-Volume Explore |
| EVS-228 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-229 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |
| EVS-230 | P2 | People & Identity | P2-I5 Universal Person Surfaces |
| EVS-232 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-233 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-235 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-236 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-237 | P2 | Video | P2-I4 Timeline-first High-Volume Explore |
| EVS-238 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-239 | P2 | Family Contribution | P2-I15 Owner-run Capture Campaigns |
| EVS-241 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-242 | P2 | Sharing | P2-I2 Product Shell & Context Maturation |
| EVS-243 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |
| EVS-244 | P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-246 | P1–P2 | Video | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-247 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-248 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-249 | P2 | Discovery | P2-I4 Timeline-first High-Volume Explore |
| EVS-250 | P2 | Corrections & Learning | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-251 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |
| EVS-254 | P2 | Discovery | P2-I12 External Historical Context |
| EVS-255 | P2 | Discovery | P2-I12 External Historical Context |
| EVS-256 | P2 | Stories & Narrative | P2-I12 External Historical Context |

### A.2 Historical aliases (not separate acceptance)

| Alias EVS | Canonical EVS | Phase on alias row | Inherits increment |
|---|---|---|---|
| EVS-183 | EVS-001 | P1 | P1 regression |
| EVS-184 | EVS-002 | P1–P2 | P2-I4 Timeline-first High-Volume Explore |
| EVS-185 | EVS-003 | P1 | P1 regression |
| EVS-186 | EVS-004 | P1–P2 | P2-I10 Cross-Source Correlation |
| EVS-187 | EVS-005 | P1 | P1 regression |
| EVS-188 | EVS-006 | P1 | P1 regression |
| EVS-189 | EVS-007 | P1 | P1 regression |
| EVS-190 | EVS-008 | P1–P2 | P2-I11 Narrative & Summaries |
| EVS-191 | EVS-009 | P1–P2 | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-192 | EVS-010 | P1–P2 | P2-I10 Cross-Source Correlation |
| EVS-193 | EVS-011 | P1–P2 | P2-I1 Show me Peggy (Person-in-Media Vertical) |
| EVS-194 | EVS-012 | P1 | P1 regression |
| EVS-195 | EVS-013 | P1 | P1 regression |
| EVS-196 | EVS-014 | P1 | P1 regression |
| EVS-197 | EVS-015 | P1 | P1 regression |
| EVS-198 | EVS-016 | P1 | P1 regression |
| EVS-199 | EVS-017 | P2 | P2-I2 Product Shell & Context Maturation |
| EVS-200 | EVS-018 | P3 | P3 out |
| EVS-201 | EVS-019 | P2 | Late-P2/P2.5 Multi-user + Tone |
| EVS-202 | EVS-020 | P2–P3 | P2-I17 Portability & Import-back |
