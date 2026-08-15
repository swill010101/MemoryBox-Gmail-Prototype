# MBRM-001 v0.2 — AI Trace insertion (ingested)

**Status:** Ingested planning note · I7A definition **LOCKED** 2026-08-15 · **no I7A build**  
**Source:** `MBRM-001_MemoryBox_Roadmap_and_P2_Backlog_Notes_v0.2_AI_Trace_Insertion.docx` · 2026-08-15  
**Supersedes:** any earlier sequence that placed **MBQL-001 immediately after I7**  
**Does not rewrite:** the rest of the historical MBRM-001 / P2 backlog notes (P1 path, post-P1 validation loop, UX stubs, Late-P2 multi-user, P3 boundary)

---

## New decision (2026-08-15)

Insert **P2-I7A — AI Model Trace & Observability** immediately after **P2-I7 SMS/Text acceptance** and **before MBQL-001** implementation/handoff.

Before MBQL implementation begins, MemoryBox must be able to trace a user request from orchestrator/planner state through each model call and back to the parsed/validated MemoryBox result. The trace must make orchestrator/Python, provider/model, parser/schema, trust-validation, and downstream application failures distinguishable.

Detailed requirements: [MBPRD-P2-I7A](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md).  
Increment definition (**locked**): [MBBS-P2_INCREMENT_7A_DEFINITION.md](MBBS-P2_INCREMENT_7A_DEFINITION.md).

## Sequence (authoritative for this insertion)

| Sequence | Increment / artifact | Status / reason |
|----------|----------------------|-----------------|
| 1 | P2-I6 — Relationships | **ACCEPTED** |
| 2 | P2-I7 — SMS/Text | **ACCEPTED** 2026-08-15. Attachment bytes **P2-BL-I7-01**. |
| 3 | **P2-I7A — AI Model Trace & Observability** | **DEFINITION LOCKED.** No build until explicit I7A authorization. |
| 4 | MBQL-001 — Ask, Query & Command Language | Implement/adopt **after I7A**; MBQL remains the semantic contract for Query Planner / Experience Orchestrator |
| 5 | P2-I8 — Richer Email | Apply shared MBQL communication semantics |
| 6 | P2-I8.5 — MB Face Evidence Ownership & Immich Decoupling | Existing inserted increment; **unchanged** |
| 7 | P2-I9 — Spoken Moments | Same query state and model trace infrastructure |
| 8 | P2-I10 — Correlation | Evidence scope / cross-source reasoning |
| 9 | P2-I11 — Narrative | Evidence-backed synthesis; increased model importance |

## Historical notes preserved (not reopened)

The uploaded v0.2 file also restates: keep Cursor on the current P1/P2 increment path; post-P1 validation loop with real people; P2 UX stubs (timeline-first, live views, highlights, source video vs searchable moments); Late-P2/P2.5 multi-user; P3 only when genuinely blocked; EVS catalog merge note (MBEVS-001 v0.8 + EVS-183–200 addendum). Those remain background. **This ingest does not authorize I8–I11, multi-user, or MBQL.**
