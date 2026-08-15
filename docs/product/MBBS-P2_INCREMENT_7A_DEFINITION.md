# MBBS-P2 Increment 7A — AI Model Trace & Observability

**Status:** **DRAFTED FOR REVIEW** · **NO BUILD**  
**Date:** 2026-08-15  
**Authority:** Tom Word uploads 2026-08-15 — [MBPRD-P2-I7A](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md) (v0.1 ingest) · [MBRM-001 v0.2 insertion](MBRM-001_v0.2_AI_TRACE_INSERTION.md)  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) — inserted after **P2-I7** and **before MBQL-001**  
**Depends:** P2-I7 **ACCEPTED** (build gate) · I1–I6 **ACCEPTED**  
**Does not reopen / does not absorb:** I7 SMS/text · I7 attachment export · **MBQL-001 language** · I8 richer email · I8.5 face-evidence · I9 spoken · I10 correlation · I11 narrative · I13/I14 Settings product · family nav · multi-user

This document is the increment definition for founder review. It does **not** authorize implementation.

---

## 0. Product intent

> **Before MemoryBox asks models to do more, a tester can see exactly what MemoryBox sent, what the model returned, and what MemoryBox did with it — and can tell a Python/orchestrator bug from a model/provider bug.**

I7A is **developer observability**, not a family AI dashboard, not MBQL, and not a change to Ask answers.

End-to-end (when built, after authorization):

1. Every model invocation used by MemoryBox emits the same provider-neutral trace lifecycle.  
2. Planner / Orchestrator can attach pre-model and post-model spans to the same Trace ID.  
3. A bookmarkable local **AI Trace** window follows live work and keeps recent traces.  
4. Failures are classified by stage (ORCHESTRATION, PROMPT_BUILD, PROVIDER_TRANSPORT, MODEL_EXECUTION, MODEL_OUTPUT, PARSE_SCHEMA, TRUST_VALIDATION, DOWNSTREAM_APP).  
5. Secrets never land in the trace store. Trace-store failure never fails the user request.

---

## 1. Why now (sequence lock)

MBRM-001 v0.2 (2026-08-15) **supersedes** any earlier sequence that jumped from I7 to MBQL-001.

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | Finish and **ACCEPT** current increment (Tom is still exporting iMazing attachments) |
| 2 | **P2-I7A** AI Model Trace | This definition. Observability **before** model workload grows |
| 3 | **MBQL-001** | Ask / query / command language — **not started until I7A is accepted enough to trace end-to-end** |
| 4 | **P2-I8** Richer Email | Shared MBQL communication semantics + existing trace |
| 5 | **P2-I8.5** Face Evidence Ownership | Already inserted; **unchanged** by I7A |
| 6 | **P2-I9** Spoken Moments | Same trace contract |
| 7+ | I10 / I11 / later VLM | Trace becomes more valuable; do not pull them into I7A |

**Build rule:** I7A code starts only after (a) I7 is **ACCEPTED** and (b) Tom explicitly authorizes I7A build. Definition review can happen now while I7 attachments are still being exported.

---

## 2. Questions for Tom

| # | Topic | Proposed lock | Needs |
|---|--------|---------------|-------|
| **Q1** | Sequence | I7 ACCEPTED → I7A → MBQL-001. I8.5 stays after I8. | **Confirm** |
| **Q2** | Build gate | Definition now; **no I7A runtime** until I7 ACCEPTED + “approved to build.” | **Confirm** |
| **Q3** | First-wave calls | Wrap **all** `LlmProvider.chat` and `LlmProvider.embed` at the shared protocol/wrapper. VLM uses the same contract when a VLM provider exists; I7A does not add a VLM product. | **Confirm or narrow to chat-only** |
| **Q4** | Route | Bookmarkable **`/dev/ai-trace`** (or `/settings/ui` developer child). **Not** in family primary nav. Settings may link. | **Confirm URL** |
| **Q5** | Live Follow | Local poll ≤1s is enough for P2. No OpenTelemetry collector, no SaaS. SSE allowed later if poll is insufficient. | Accept unless you want SSE first |
| **Q6** | Retention | Last **200** traces **or 7 days**, whichever first; configurable; manual clear. Diagnostic only — not family evidence. | **Confirm numbers** |

PRD already locks: no chain-of-thought reconstruction; no family AI dashboard; no external telemetry requirement; no MBQL implementation in this increment.

---

## 3. Current code (inspect only — do not implement)

Today most Asks never call a model. `plan_ask` is deterministic. The orchestrator **holds** an `LlmProvider` for health/snapshot; SMS/person retrieve does not go through `llm.chat`.

| Boundary | Path | I7A role |
|----------|------|----------|
| Protocol | `memorybox/providers/llm/protocol.py` — `chat`, `embed` | **Shared emit point.** Do not instrument only Ollama. |
| Ollama | `providers/llm/ollama.py` + `_ollama_http.py` | Current local provider; must emit the same lifecycle as Fake. |
| Fake | `providers/llm/fake.py` | Harness must still produce traces (T1/T3/T10). |
| Wiring | `ask/deps.py` `build_llm()` | Choose provider; wrapper sits here or on the protocol. |
| Planner | `planner/__init__.py` `plan_ask` | Pre-model span: normalized intent. Today this is often the **whole** path (T3). |
| Orchestrator | `ask/orchestrator.py` | Parent Trace ID; post-model disposition / final user result. |
| Health | `status/summary.py` `_ollama_status` | Not a model invocation; do not pretend `/api/tags` is a chat span. |

Handoff after build auth (from the PRD): propose schema + live-update **before coding**; wrap shared boundaries; add the window; prove T1–T10 with at least one orchestrator failure and one model-output failure visibly distinct; **stop** — do not start MBQL.

---

## 4. Scope

### IN

- Provider-neutral trace contract (Trace + Span/Event; parent/child).  
- Stages 1–8 and field catalog in the [PRD](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md) §§5–6.  
- Developer-only AI Trace window: list, detail panes (Sent / Raw / Parsed / MB Result), Live Follow, filter, copy/export JSON, clear, retention.  
- Local PostgreSQL (or equivalent local) store; bounded retention; secret scrubbing.  
- Passive emission: UI closed still works; store down does not fail Ask.  
- Harness T1–T10 (forced-model hook is allowed for T1/T4/T6/T7/T8 because production Ask is still mostly deterministic).

### OUT

- MBQL grammar, planner rewrite, or “the model interprets every Ask.”  
- Family-facing AI / Settings product (I13/I14).  
- I8 email richness, I8.5 face SoT, I9 STT, I10 Alaska inference, I11 narrative generation.  
- External Jaeger/OTLP/SaaS as a requirement.  
- Asking the model to explain its hidden reasoning.  
- Changing I7 SMS retrieve or attachment ingest.

---

## 5. Acceptance intent (after build — not now)

Pass the PRD §10 list and T1–T10. Visual polish may be thin. **Gating:** request → raw response → parsed/validated → MB disposition, plus error class that does not say “AI error” for a Python bug.

`prove-p2-i7a` (when it exists) is a harness, not ACCEPTED. ACCEPTED is a FlightSim owner pass with the window open on a second display.

---

## 6. Privacy

Traces may contain the most sensitive prompt material in MemoryBox. They are **diagnostic**, not Evidence. Local only. No API keys/headers in payloads. Family nav must not link here.

---

## 7. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001 v0.2 insertion + MBPRD-P2-I7A v0.1 | **INGESTED** 2026-08-15 |
| I7A increment definition | **THIS DOC — review** |
| I7 SMS/Text | **BUILD AUTHORIZED** / **not ACCEPTED** (attachment bytes still being exported) |
| I7A build | **NOT AUTHORIZED** |
| MBQL-001 | **NOT STARTED** — blocked on I7A acceptance |

**Please answer Q1–Q6.** Do not authorize I7A build in this review. Finish I7 (including iMazing attachment export) first.
