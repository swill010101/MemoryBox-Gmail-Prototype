# MBRM-001 — MemoryBox P2 Roadmap

**Status:** Historical shell-first draft · **Superseded for sequencing by** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) · I1 definition: [MBBS-P2_INCREMENT_1_DEFINITION.md](MBBS-P2_INCREMENT_1_DEFINITION.md)  
**Inserted later (001A only):** **P2-I8.5** Face Evidence Ownership & Immich Decoupling — after I8 Richer Email, before I9 Spoken Moments. Not I7.5. See [I8.5 PRD](MBBS-P2_I8.5_FACE_EVIDENCE_OWNERSHIP_PRD.md). Do not map I8.5 onto this file’s older I6=Email / I8=Video Moments numbering.  
**ID:** MBRM-001  
**Owner:** Tom  
**Gate:** **No build** — see MBRM-001A + P2-I1 definition.

## 1. Purpose

This roadmap is the Cursor-ready P2 sequencing authority. It clusters MBPS-002 product requirement areas and MBEVS-001 scenarios into coherent increments with dependencies, IN/OUT, acceptance intent, and EVS traceability.

It does **not** prescribe schemas, model choices, or service internals. It does **not** authorize implementation.

## 2. P2 objective (from MBPS-002)

P2 is **product maturation** and **capability expansion** together:

- Maturation: coherent shell, high-volume exploration, Archive Health, Settings, saved views, summaries, consistent correction, mature family-facing experience.
- Expansion: SMS/text, richer email, face/voice learning, video timeslots/searchable moments, STT, speaker linking, cross-source correlation, relationship inference, evidence-backed narrative.
- Experience completion: an EVS passes only when the intended outcome is complete (drill-down, correction, provenance, return to context where required).

## 3. Principles and boundaries that do not change

Preserve MBPS-002 §§3 and 6, including:

- Evidence First · Create No False Memories · Original Evidence Is Sacred · Import Don’t Replace · Local First / exportability.
- Do not replace canonical MB People with provider IDs; improve mapping/sync.
- Do not make confidence-first or provider-first UX the default family experience.
- Do not treat AI narrative/recognition/external web context as original family evidence.
- Do not silently invent identities, relationships, dates, or stories under uncertainty.
- Do not require full multi-user before the primary owner P2 experience is mature.
- Synthetic/imagined media (EVS-253, 257–260) stay **P3 / out**.

## 4. Locked planning defaults (MBPS-002 §10)

| Topic | Locked default for this roadmap |
|-------|----------------------------------|
| Family contribution | **Owner-mediated** through most of P2; independent accounts = **Late-P2 / P2.5** |
| External history EVS-254–256 | **Late narrative wave** after core P2-I11 family narratives |
| Immich Person sync cadence | Scheduled job + on People/Status refresh; conflicts → review; **no silent destructive merge** |
| Recognition confidence | Product defaults first; owner-adjustable in **P2-I13 Settings** |
| First Experience Flows to formalize | The six MBPS-002 §5 patterns |
| First real-family demo acceptance set | After **I1 shell + I2 Archive Health + I3 high-volume explore + I4 identity sync** |
| Explicit deferrals | Tone dial **EVS-019**; synthetic P3; full multi-user until Late |

## 5. Backlog absorption (P1 parked → P2 increments)

Prior planning note: [MBBS_P2_BACKLOG_PLANNING.md](MBBS_P2_BACKLOG_PLANNING.md). Sequencing authority is **this roadmap**.

| Parked item | Absorbed into |
|-------------|---------------|
| **TASK-P1P2-004** Immich Status Photos inventory | **P2-I2** |
| **TASK-P1P2-001** Universal Immich lazy-teach | **P2-I4** |
| **TASK-P1P2-002** Kinship inference graph | **P2-I7** |
| Ops: SMS ingest | **P2-I5** |
| Ops: full mbox → Evidence / richer email | **P2-I6** |
| Ops: HVRT serve env for video counts | **P2-I2** (Status/Health honesty) + **P2-I8** (moments) |
| **TASK-P1P2-003** Export import-back | **P2-I16** |

## 6. Increment sequence

```text
P2-I1 Product Shell
  → P2-I2 Archive Health (+004)
    → P2-I3 Timeline-first Explore
      → P2-I4 Identity Sync (+001)
        → P2-I5 SMS
          → P2-I6 Richer Email
        → P2-I7 Kinship (+002)
      → P2-I8 Video Moments → P2-I9 Audio/Speaker
        → P2-I10 Cross-Source → P2-I11 Narrative → P2-I12 Dynamic Views
    → P2-I13 Settings (also depends on I2 health signals)
  → P2-I14 Capture deepen (after narrative/gaps useful)
  → P2-I15 Trust/correction consistency (starts earning in with I4; formalize by I15)
  → P2-I16 Portability + import-back (+003)
  → Late-P2/P2.5 Multi-user + Tone dial
```

**Named first definition after roadmap approval:** **P2-I1 — Product Shell & Coherent Navigation** (definition doc only; no code until that definition is approved).

---

### P2-I1 — Product Shell & Coherent Navigation

| Field | Content |
|-------|---------|
| **MBPS** | P2-UX-01, P2-UX-04 |
| **IN** | One coherent product shell over Ask, Library/Timeline, People, Stories, Journal, Artifacts, Review & Learn, Settings entry, Archive Health entry; open→inspect→act→return preserves context; progressive disclosure |
| **OUT** | Full high-volume timeline redesign (I3); Archive Health redesign (I2); multi-user; tone dial; new providers |
| **Depends** | P1 baseline accepted |
| **Acceptance intent** | Owner navigates MemoryBox as one product, not a set of disconnected P1 tools; context survives drill-down/return |
| **Primary EVSs** | Enabling; dedicated: EVS-017, EVS-199, EVS-242 (see Appendix A) |

### P2-I2 — Archive Health + Immich Photos inventory

| Field | Content |
|-------|---------|
| **MBPS** | P2-AH-01..03; thin provider-health signals toward P2-SET-02 |
| **Absorbs** | **TASK-P1P2-004** |
| **IN** | Evolve P1 `/status` into owner-facing Archive Health; real Immich Photos totals when key/endpoints allow; small high-leverage “Work on these now” queues; unavailable ≠ 0 |
| **OUT** | Final Dashboard chrome as a separate polish program; inventing unsupported Immich metrics; IQ/blur engines |
| **Depends** | I1 shell entry points |
| **Acceptance intent** | FlightSim: Photos inventory available with real total when Immich healthy; actionable queues without thousands of deficiencies |

### P2-I3 — Timeline-first high-volume exploration

| Field | Content |
|-------|---------|
| **MBPS** | P2-UX-02, P2-UX-04 natural/structured refinement with P2-UX-03 |
| **IN** | Timeline-centered navigation, adaptive zoom/clustering/banding, preview, filters, drill-down/return for large photo/video sets |
| **OUT** | Provider-structure-first UI; confidence-score-first UX; video timeslot engine (I8) |
| **Depends** | I1, I2 (health/coverage honesty) |
| **Acceptance intent** | Real archive-scale photo/video explore is practical |

### P2-I4 — Continuous Immich → MB Person sync / lazy teach

| Field | Content |
|-------|---------|
| **MBPS** | P2-ID-01..03 (foundation for 04/05 later) |
| **Absorbs** | **TASK-P1P2-001** |
| **IN** | Canonical MB Person retained; named Immich people auto map/create when unambiguous; continuous sync on schedule + People/Status refresh; ambiguity → review; universal Person pickers use lazy teach |
| **OUT** | Bulk Immich Person import as a chore; Immich UUID as `people.id`; silent destructive merges; full face-evidence ownership epic (thin only if required for sync) |
| **Depends** | I1–I3 |
| **Acceptance intent** | No redundant `/people` enrollment when Immich already has the unique name; provider changes reconcile without silent damage |

### P2-I5 — SMS/text as first-class evidence

| Field | Content |
|-------|---------|
| **MBPS** | P2-COM-01 |
| **Absorbs** | Ops SMS ingest |
| **IN** | Ingest, preserve originals where available, participants, timestamps, search, Person/event correlation, narrative-usable evidence |
| **OUT** | Full multi-user SMS contribution; replacing carrier apps |
| **Depends** | I4 (Person linking) |
| **Acceptance intent** | SMS participates in Ask/Library with provenance |

### P2-I6 — Richer email understanding

| Field | Content |
|-------|---------|
| **MBPS** | P2-COM-02, P2-COM-03 |
| **Absorbs** | Ops full mbox → Evidence |
| **IN** | Thread awareness, participant identity, attachments, dates/events/places hooks, significant exchanges, provenance |
| **OUT** | Replacing email clients; inventing missing mailbox content |
| **Depends** | I5 recommended (shared comms patterns); I4 |
| **Acceptance intent** | Richer-than-P1 email retrieval/summary with disclosed coverage gaps |

### P2-I7 — Kinship / derived relationship reasoning

| Field | Content |
|-------|---------|
| **MBPS** | P2-GRAPH-01 |
| **Absorbs** | **TASK-P1P2-002** |
| **IN** | Derived kinship from canonical graph; disclosed inference paths; gendered resolve where safe; cousins/uncle/aunt/grandparent composition from minimal facts |
| **OUT** | Genealogy tree visualization; auto-genealogy from photos; overwriting SoT with inferred edges |
| **Depends** | I4 |
| **Acceptance intent** | Ask resolves relationship language with disclosure; ambiguity never silently picked |

### P2-I8 — Video timeslots & searchable moments

| Field | Content |
|-------|---------|
| **MBPS** | P2-VID-01..05 |
| **IN** | Source video immutable; derived timeslots rebuildable; person appearance start/end; searchable moments; face teach/correct in frame; reuse proven HVRT concepts |
| **OUT** | Synthetic video; replacing HVRT wholesale without earn-in |
| **Depends** | I3 explore; I4 identity |
| **Acceptance intent** | Results open at the relevant moment, not only containing files |

### P2-I9 — Audio, STT, speaker identity

| Field | Content |
|-------|---------|
| **MBPS** | P2-AUD-01..04 |
| **IN** | Time-aligned transcription; speaker↔Person association; spoken-moment retrieval; authentic voice only |
| **OUT** | Generated/reconstructed speech as evidence |
| **Depends** | I8 patterns; I4 |
| **Acceptance intent** | “Play X talking about Y” returns passages/ranges with provenance |

### P2-I10 — Cross-source correlation

| Field | Content |
|-------|---------|
| **MBPS** | P2-GRAPH-02, P2-GRAPH-03 |
| **IN** | Correlate People/Places/Events/Trips/Stories/evidence across modalities when supported; corrections propagate safely without erasing provenance |
| **OUT** | Forced KnowledgeLinks graph busywork; silent correlation under weak evidence |
| **Depends** | I6, I7, I8/I9 as available |
| **Acceptance intent** | Mixed-media asks complete with drill-down and safe correction propagation |

### P2-I11 — Evidence-backed narrative & summaries

| Field | Content |
|-------|---------|
| **MBPS** | P2-NAR-01..03 |
| **IN** | Multi-source narratives distinguishing fact / recollection / inference / gap; owner review before durable Story save; trip/year/Person summaries with drill-down |
| **OUT** | **EVS-254–256 external history** (see I11-later); narrative as authoritative evidence |
| **Depends** | I10 |
| **Acceptance intent** | Fluent answers never outrank evidence; save requires review |

### P2-I11-later — External historical context

| Field | Content |
|-------|---------|
| **MBPS** | P2-NAR-04 |
| **EVSs** | EVS-254, EVS-255, EVS-256 |
| **IN** | Dated media → cited U.S./world context; visually/semantically distinct from family evidence; no implied family impact without family evidence |
| **OUT** | Merging external facts into authentic evidence layer |
| **Depends** | I11 |
| **Acceptance intent** | External context cited and distinguishable |

### P2-I12 — Dynamic views, collections & persistence

| Field | Content |
|-------|---------|
| **MBPS** | P2-VIEW-01..03 |
| **IN** | Save intent (query + normalized filters/state); Live re-run; Curated; Snapshot/Frozen |
| **OUT** | Sharing packages as multi-user product |
| **Depends** | I11 (and I3 explore primitives) |
| **Acceptance intent** | Owner can reopen live vs frozen deliberately |

### P2-I13 — Settings, providers & processing controls

| Field | Content |
|-------|---------|
| **MBPS** | P2-SET-01, P2-SET-02 |
| **IN** | Mature Settings: providers, storage locations, processing, recognition services, archive config; provider health actionable; owner-adjustable confidence where product-ready |
| **OUT** | Leaking ops complexity into everyday explore |
| **Depends** | I2 health signals; identity/video processing realities from I4/I8 |
| **Acceptance intent** | Operate P2 without turning family UX into admin |

### P2-I14 — Capture deepen (owner-mediated)

| Field | Content |
|-------|---------|
| **MBPS** | P2-CAP-01..03 thin |
| **IN** | Gap-driven prompts; typed/voice/email channels; owner-mediated family contribution with provenance/review |
| **OUT** | Full independent multi-user participation |
| **Depends** | I11 gaps/summaries useful |
| **Acceptance intent** | Capture easier than organization; significant content reviewed before durable save |

### P2-I15 — Trust, correction, authority & provenance consistency

| Field | Content |
|-------|---------|
| **MBPS** | P2-TRUST-01..04 |
| **IN** | Consistent correct/merge/split/unlink/supersede/withdraw/restore across major objects; contributor/assertion authority; identity uncertainty never silent-confirm; authentic vs generated boundary |
| **OUT** | Destructive overwrite as normal path; synthetic media as evidence |
| **Depends** | Earns in from I4 onward; formal consistency gate by I15 |
| **Acceptance intent** | Correction lifecycle feels one product |

### P2-I16 — Portability deepen + import-back

| Field | Content |
|-------|---------|
| **MBPS** | Ownership/export completion; EVS-020 family |
| **Absorbs** | **TASK-P1P2-003** |
| **IN** | Strengthen export/retrieve; import `memorybox_export_format` `1` preserving MB knowledge/versions/GC context/MB-managed originals |
| **OUT** | Inventing full Immich/HVRT library restore |
| **Depends** | Mature P2 domain objects (after I11+) |
| **Acceptance intent** | Exit and round-trip MB-owned knowledge without vendor lock-in theater |

### Late-P2 / P2.5 — Multi-user + tone dial

| Field | Content |
|-------|---------|
| **MBPS** | P2-MU-01..04; EVS-019 |
| **IN** | One shared archive; account≠Person; relative relationship context; voice convenience≠sole auth; constrained/warm path tone policy |
| **OUT** | Starting P2 with multi-user architecture as prerequisite |
| **Depends** | Primary owner P2 experience mature (through I16 wave as needed) |

## 7. Validation framework (MBPS-002 §7)

- **P2-EVS-01 Traceability:** every active P2-relevant EVS has a primary increment (Appendix A).
- **P2-EVS-02 Regression:** phase-P1 EVSs remain regression requirements.
- **P2-EVS-03 Partial vs complete:** initial result without required drill-down/correct/save/evidence is only partial.
- **P2-EVS-04 Real family evidence:** prefer real-family material for acceptance where practical.

## 8. Completion criteria checkpoint

Track against MBPS-002 §8. Roadmap is complete for planning when:

1. Owner approves this document.
2. Appendix A has no unexplained unmapped **active** P2 / P1–P2 / P2–P3 EVS.
3. First authorized definition target is agreed: **P2-I1**.

## 9. Next step after approval

1. Owner marks **MBRM-001 approved**.  
2. Agent writes **`docs/product/MBBS-P2_INCREMENT_1_DEFINITION.md`** (Product Shell) for review.  
3. **No code / FlightSim build** until that definition is explicitly approved.

## 10. Document control

| Artifact | Role |
|----------|------|
| `docs/source/MBPS-002_*.docx` | Locked product WHAT master |
| `docs/source/MBEVS-001_EVS_Catalog_v1.0.docx` | Locked EVS master |
| `docs/product/MBPS-002_P2_PRODUCT_SPECIFICATION.md` | Readable extract |
| `docs/product/MBEVS-001_EVS_CATALOG_v1.0.md` | Readable extract |
| **This file** | P2 sequencing authority (pending approval) |
| `MBBS_P2_BACKLOG_PLANNING.md` | Historical parking → points here |

---
## Appendix A — EVS primary-increment map (P2-relevant + deferrals)

Primary home only. Multi-step EVSs may earn secondary coverage in later increments; unexplained unmapped active P2 EVSs are a roadmap defect.

| Primary increment | Count | EVS IDs |
|---|---:|---|
| P2-I1 Product Shell & Navigation | 3 | EVS-017, EVS-199, EVS-242 |
| P2-I2 Archive Health (+ TASK-004) | 0* | *Enabling / ops-maturity increment; validates via MBPS completion criteria and dependent EVSs |
| P2-I3 Timeline-first High-Volume Explore | 20 | EVS-002, EVS-009, EVS-081, EVS-082, EVS-085, EVS-086, EVS-090, EVS-095, EVS-105, EVS-110, EVS-111, EVS-116, EVS-119, EVS-126, EVS-128, EVS-184, EVS-191, EVS-227, EVS-229, EVS-249 |
| P2-I4 Continuous Identity Sync (+ TASK-001) | 20 | EVS-011, EVS-024, EVS-029, EVS-030, EVS-034, EVS-035, EVS-037, EVS-038, EVS-039, EVS-040, EVS-042, EVS-043, EVS-055, EVS-100, EVS-103, EVS-127, EVS-193, EVS-209, EVS-228, EVS-230 |
| P2-I5 SMS/Text Evidence | 7 | EVS-065, EVS-118, EVS-220, EVS-221, EVS-222, EVS-223, EVS-224 |
| P2-I6 Richer Email | 5 | EVS-047, EVS-070, EVS-106, EVS-107, EVS-108 |
| P2-I7 Kinship Inference (+ TASK-002) | 13 | EVS-045, EVS-069, EVS-083, EVS-084, EVS-087, EVS-088, EVS-089, EVS-204, EVS-205, EVS-206, EVS-207, EVS-208, EVS-210 |
| P2-I8 Video Timeslots & Moments | 3 | EVS-058, EVS-237, EVS-246 |
| P2-I9 Audio / STT / Speaker | 8 | EVS-026, EVS-033, EVS-064, EVS-098, EVS-123, EVS-232, EVS-233, EVS-243 |
| P2-I10 Cross-Source Correlation | 12 | EVS-004, EVS-010, EVS-147, EVS-149, EVS-152, EVS-157, EVS-158, EVS-159, EVS-161, EVS-186, EVS-192, EVS-244 |
| P2-I11 Evidence-Backed Narrative & Summaries | 18 | EVS-008, EVS-071, EVS-109, EVS-124, EVS-181, EVS-182, EVS-190, EVS-211, EVS-212, EVS-213, EVS-226, EVS-235, EVS-236, EVS-238, EVS-241, EVS-247, EVS-248, EVS-251 |
| P2-I11-later External Historical Context (EVS-254–256) | 3 | EVS-254, EVS-255, EVS-256 |
| P2-I12 Dynamic Views | 0* | *Enabling / ops-maturity increment; validates via MBPS completion criteria and dependent EVSs |
| P2-I13 Settings & Providers | 0* | *Enabling / ops-maturity increment; validates via MBPS completion criteria and dependent EVSs |
| P2-I14 Capture Deepen (owner-mediated) | 4 | EVS-129, EVS-136, EVS-140, EVS-239 |
| P2-I15 Trust & Correction Consistency | 18 | EVS-027, EVS-079, EVS-091, EVS-092, EVS-093, EVS-094, EVS-096, EVS-097, EVS-114, EVS-167, EVS-168, EVS-170, EVS-171, EVS-201, EVS-203, EVS-214, EVS-216, EVS-250 |
| P2-I16 Portability + Import-back (+ TASK-003) | 3 | EVS-020, EVS-202, EVS-217 |
| Late-P2 / P2.5 Multi-user + Tone Dial | 1 | EVS-019 |
| P3 / out of P2 build | 7 | EVS-018, EVS-200, EVS-253, EVS-257, EVS-258, EVS-259, EVS-260 |

**P1 regression pool:** 115 EVSs remain accepted-behavior regression requirements (phase P1). They are not re-scoped as new P2 features.

### A.1 Detail — active P2 / P1–P2 / P2–P3 rows

| EVS | Phase | Taxonomy | Primary increment |
|---|---|---|---|
| EVS-002 | P1–P2 | Events & Timeline | P2-I3 Timeline-first High-Volume Explore |
| EVS-004 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-008 | P1–P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-009 | P1–P2 | Photos | P2-I3 Timeline-first High-Volume Explore |
| EVS-010 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-011 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-017 | P2 | Sharing | P2-I1 Product Shell & Navigation |
| EVS-019 | P2 | Trust & Evidence | Late-P2 / P2.5 Multi-user + Tone Dial |
| EVS-020 | P2 | Ownership & Portability | P2-I16 Portability + Import-back (+ TASK-003) |
| EVS-024 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-026 | P1–P2 | People & Identity | P2-I9 Audio / STT / Speaker |
| EVS-027 | P2 | People & Identity | P2-I15 Trust & Correction Consistency |
| EVS-029 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-030 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-033 | P1–P2 | People & Identity | P2-I9 Audio / STT / Speaker |
| EVS-034 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-035 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-037 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-038 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-039 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-040 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-042 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-043 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-045 | P2 | People & Identity | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-047 | P1–P2 | Communications | P2-I6 Richer Email |
| EVS-055 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-058 | P2 | Video | P2-I8 Video Timeslots & Moments |
| EVS-064 | P2 | Audio & Voice | P2-I9 Audio / STT / Speaker |
| EVS-065 | P1–P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-069 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-070 | P2 | Communications | P2-I6 Richer Email |
| EVS-071 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-079 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-081 | P2 | Photos | P2-I3 Timeline-first High-Volume Explore |
| EVS-082 | P2 | Photos | P2-I3 Timeline-first High-Volume Explore |
| EVS-083 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-084 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-085 | P1–P2 | Events & Timeline | P2-I3 Timeline-first High-Volume Explore |
| EVS-086 | P1–P2 | Events & Timeline | P2-I3 Timeline-first High-Volume Explore |
| EVS-087 | P1–P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-088 | P1–P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-089 | P1–P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-090 | P1–P2 | Places | P2-I3 Timeline-first High-Volume Explore |
| EVS-091 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-092 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-093 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-094 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-095 | P2 | Photos | P2-I3 Timeline-first High-Volume Explore |
| EVS-096 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-097 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-098 | P2 | Corrections & Learning | P2-I9 Audio / STT / Speaker |
| EVS-100 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-103 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-105 | P1–P2 | Places | P2-I3 Timeline-first High-Volume Explore |
| EVS-106 | P1–P2 | Communications | P2-I6 Richer Email |
| EVS-107 | P1–P2 | Communications | P2-I6 Richer Email |
| EVS-108 | P1–P2 | Communications | P2-I6 Richer Email |
| EVS-109 | P2 | Photos | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-110 | P1–P2 | Events & Timeline | P2-I3 Timeline-first High-Volume Explore |
| EVS-111 | P1–P2 | Events & Timeline | P2-I3 Timeline-first High-Volume Explore |
| EVS-114 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-116 | P2 | Places | P2-I3 Timeline-first High-Volume Explore |
| EVS-118 | P1–P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-119 | P2 | Places | P2-I3 Timeline-first High-Volume Explore |
| EVS-123 | P2 | Audio & Voice | P2-I9 Audio / STT / Speaker |
| EVS-124 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-126 | P2 | Places | P2-I3 Timeline-first High-Volume Explore |
| EVS-127 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-128 | P2 | Places | P2-I3 Timeline-first High-Volume Explore |
| EVS-129 | P1–P2 | Family Contribution | P2-I14 Capture Deepen (owner-mediated) |
| EVS-136 | P1–P2 | Guided & Journal Capture | P2-I14 Capture Deepen (owner-mediated) |
| EVS-140 | P2 | Guided & Journal Capture | P2-I14 Capture Deepen (owner-mediated) |
| EVS-147 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-149 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-152 | P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-157 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-158 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-159 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-161 | P2 | Artifacts | P2-I10 Cross-Source Correlation |
| EVS-167 | P1–P2 | Trust & Evidence | P2-I15 Trust & Correction Consistency |
| EVS-168 | P2 | Trust & Evidence | P2-I15 Trust & Correction Consistency |
| EVS-170 | P1–P2 | Trust & Evidence | P2-I15 Trust & Correction Consistency |
| EVS-171 | P2 | Trust & Evidence | P2-I15 Trust & Correction Consistency |
| EVS-181 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-182 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-184 | P1–P2 | Events & Timeline | P2-I3 Timeline-first High-Volume Explore |
| EVS-186 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-190 | P1–P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-191 | P1–P2 | Photos | P2-I3 Timeline-first High-Volume Explore |
| EVS-192 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-193 | P1–P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-199 | P2 | Sharing | P2-I1 Product Shell & Navigation |
| EVS-201 | P2 | Trust & Evidence | P2-I15 Trust & Correction Consistency |
| EVS-202 | P2–P3 | Ownership & Portability | P2-I16 Portability + Import-back (+ TASK-003) |
| EVS-203 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-204 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-205 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-206 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-207 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-208 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-209 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-210 | P2 | Relationships | P2-I7 Kinship Inference (+ TASK-002) |
| EVS-211 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-212 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-213 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-214 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-216 | P2 | Trust & Evidence | P2-I15 Trust & Correction Consistency |
| EVS-217 | P2 | Ownership & Portability | P2-I16 Portability + Import-back (+ TASK-003) |
| EVS-220 | P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-221 | P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-222 | P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-223 | P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-224 | P2 | Communications | P2-I5 SMS/Text Evidence |
| EVS-226 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-227 | P2 | Discovery | P2-I3 Timeline-first High-Volume Explore |
| EVS-228 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-229 | P2 | Photos | P2-I3 Timeline-first High-Volume Explore |
| EVS-230 | P2 | People & Identity | P2-I4 Continuous Identity Sync (+ TASK-001) |
| EVS-232 | P2 | Audio & Voice | P2-I9 Audio / STT / Speaker |
| EVS-233 | P2 | Audio & Voice | P2-I9 Audio / STT / Speaker |
| EVS-235 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-236 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-237 | P2 | Video | P2-I8 Video Timeslots & Moments |
| EVS-238 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-239 | P2 | Family Contribution | P2-I14 Capture Deepen (owner-mediated) |
| EVS-241 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-242 | P2 | Sharing | P2-I1 Product Shell & Navigation |
| EVS-243 | P2 | Audio & Voice | P2-I9 Audio / STT / Speaker |
| EVS-244 | P2 | Recipes | P2-I10 Cross-Source Correlation |
| EVS-246 | P1–P2 | Video | P2-I8 Video Timeslots & Moments |
| EVS-247 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-248 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-249 | P2 | Discovery | P2-I3 Timeline-first High-Volume Explore |
| EVS-250 | P2 | Corrections & Learning | P2-I15 Trust & Correction Consistency |
| EVS-251 | P2 | Stories & Narrative | P2-I11 Evidence-Backed Narrative & Summaries |
| EVS-254 | P2 | Discovery | P2-I11-later External Historical Context (EVS-254–256) |
| EVS-255 | P2 | Discovery | P2-I11-later External Historical Context (EVS-254–256) |
| EVS-256 | P2 | Stories & Narrative | P2-I11-later External Historical Context (EVS-254–256) |
