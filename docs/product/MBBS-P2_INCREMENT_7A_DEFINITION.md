# MBBS-P2 Increment 7A — AI Model Trace & Observability

**Status:** **ACCEPTED** (2026-08-15 — Tom FlightSim owner pass: history keys + real Ask + `/dev/ai-trace`)  
**Date:** 2026-08-15  
**Schema / live-update:** [MBBS-P2_I7A_TRACE_SCHEMA.md](MBBS-P2_I7A_TRACE_SCHEMA.md)  
**Authority:** Tom Word uploads 2026-08-15 — [MBPRD-P2-I7A](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md) (v0.1 ingest) · [MBRM-001 v0.2 insertion](MBRM-001_v0.2_AI_TRACE_INSERTION.md) · **Q1–Q6 + extra rules locked 2026-08-15**  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) — inserted after **P2-I7 ACCEPTED** and **before MBQL-001**  
**Depends:** P2-I7 **ACCEPTED** (2026-08-15) · I1–I6 **ACCEPTED**  
**Does not reopen / does not absorb:** I7 SMS/text · SMS attachment bytes **P2-BL-I7-01** · I8 email **P2-BL-I8-01** · **MBQL-001 language** · I8 richer email · I8.5 face-evidence · I9 spoken · I10 correlation · I11 narrative · I13/I14 Settings product · family nav · multi-user

**I7A is ACCEPTED.** Schema/live-update contract is in [MBBS-P2_I7A_TRACE_SCHEMA.md](MBBS-P2_I7A_TRACE_SCHEMA.md). **No MBQL implementation starts as part of I7A.** [MBQL-001](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) is **ACCEPTED** 2026-08-18.

## What shipped (ACCEPTED)

- Provider-neutral wrap of shared `LlmProvider.chat` / `embed`
- Every Ask, including deterministic / zero-model paths, writes an end-to-end trace
- `/dev/ai-trace` (poll ~750 ms; not in family nav)
- Retention 500 traces or 7 days; redact before persist; store failure never fails Ask
- T1–T10 harness via `prove-p2-i7a` and page buttons

---

## 0. Product intent

> **Before MemoryBox asks models to do more, a tester can see exactly what MemoryBox sent, what the model returned, and what MemoryBox did with it — and can tell a Python/orchestrator bug from a model/provider bug.**

I7A is **developer observability**, not a family AI dashboard, not MBQL, and not a change to Ask answers.

End-to-end (when built, after authorization):

1. Every model invocation used by MemoryBox emits the same provider-neutral trace lifecycle.  
2. Planner / Orchestrator can attach pre-model and post-model spans to the same Trace ID.  
3. A bookmarkable local **AI Trace** window at **`/dev/ai-trace`** follows live work and keeps recent traces.  
4. Failures are classified by stage (ORCHESTRATION, PROMPT_BUILD, PROVIDER_TRANSPORT, MODEL_EXECUTION, MODEL_OUTPUT, PARSE_SCHEMA, TRUST_VALIDATION, DOWNSTREAM_APP).  
5. Secrets are redacted **before persistence**. Trace-store failure never fails the user request.

A request trace may contain **zero, one, or many** model calls. Deterministic / no-model Ask paths **must** still produce an end-to-end trace showing planner/orchestrator and final disposition. That is the common P2 path today (`plan_ask` is rule-based; SMS/person retrieve does not call `llm.chat`).

---

## 1. Why now (sequence lock)

MBRM-001 v0.2 (2026-08-15) **supersedes** any earlier sequence that jumped from I7 to MBQL-001.

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15. Attachment bytes parked **P2-BL-I7-01**. |
| 2 | **P2-I7A** AI Model Trace | **ACCEPTED** 2026-08-15. Observability **before** model workload grows |
| 3 | **MBQL-001** | Ask / query / command language — [ACCEPTED](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) 2026-08-18 |
| 4 | **P2-I8** Richer Email | Shared MBQL communication semantics + existing trace. Attachment files up front = **P2-BL-I8-01**. |
| 5 | **P2-I8.5** Face Evidence Ownership | Already inserted; **unchanged** by I7A |
| 6 | **P2-I9** Spoken Moments | Same trace contract |
| 7+ | I10 / I11 / later VLM | Trace becomes more valuable; do not pull them into I7A |

**Build rule (historical):** I7A code started only after I7 ACCEPTED and explicit I7A build authorization. Both gates passed. Runtime shipped and ACCEPTED.

---

## 2. Locked decisions (Tom, 2026-08-15)

| # | Topic | Locked answer |
|---|--------|---------------|
| **Q1** | Sequence | **Confirm.** I7 ACCEPTED → I7A → MBQL-001. **I8.5 remains after I8.** |
| **Q2** | Build gate | **Confirm.** Definition may be finalized now. **No runtime implementation** until I7 is ACCEPTED **and** explicit I7A build authorization is given. I7 is now ACCEPTED; the second gate is still open. |
| **Q3** | First-wave calls | **Trace all** shared `LlmProvider.chat` and `LlmProvider.embed` at the **provider-neutral** boundary. Embeddings: capture **input / purpose / model / timing / dimensions / error** metadata. **Full vector persistence is not required by default.** `/api/tags` and other non-chat/non-embed health probes are not chat/embed spans. VLM uses the same contract when a VLM provider exists; I7A does not add a VLM product. |
| **Q4** | Route | Canonical bookmarkable developer route: **`/dev/ai-trace`**. Settings may link to it later. **Must not** appear in family primary navigation. I7A does not build Settings (I13/I14). |
| **Q5** | Live Follow | **Polling is acceptable for P2**, approximately **500 ms–1 second**. SSE/WebSocket may be added later **only if needed**. No OpenTelemetry collector, no SaaS. |
| **Q6** | Retention | Default: **500 traces or 7 days**, whichever limit is reached first; **configurable**; **automatic cleanup** and **manual clear**. Diagnostic only — not family evidence. |

### Additional locked rules (same day)

1. A request trace may contain **zero, one, or many** model calls.
2. Deterministic / no-model Ask paths **must** still produce an end-to-end trace showing planner/orchestrator and final disposition.
3. The UI **must distinguish assembled MemoryBox context** from the **exact provider payload actually sent**.
4. **Secret redaction occurs before trace persistence**, not only at display time.
5. **Trace-store failure must never fail** the MemoryBox user request.
6. **No MBQL implementation starts as part of I7A.**

---

## 3. Current code (inspect only — do not implement)

Today most Asks never call a model. `plan_ask` is deterministic. The orchestrator **holds** an `LlmProvider` for health/snapshot; SMS/person retrieve does not go through `llm.chat`. **T3 (zero model spans) is the common path until MBQL.**

| Boundary | Path | I7A role |
|----------|------|----------|
| Protocol | `memorybox/providers/llm/protocol.py` — `chat`, `embed` | **Shared emit point.** Do not instrument only Ollama. Provider-neutral wrapper required. |
| Ollama | `providers/llm/ollama.py` + `_ollama_http.py` | Current local provider; must emit the same lifecycle as Fake. |
| Fake | `providers/llm/fake.py` | Harness must still produce traces (T1/T3/T10). |
| Wiring | `ask/deps.py` `build_llm()` | Choose provider; wrapper sits here or on the protocol. |
| Planner | `planner/__init__.py` `plan_ask` | Pre-model span: normalized intent. Today this is often the **whole** path (T3). |
| Orchestrator | `ask/orchestrator.py` | Parent Trace ID; post-model disposition / final user result. |
| Health | `status/summary.py` `_ollama_status` | Not a model invocation; do not pretend `/api/tags` is a chat span. |

**Embeddings (when `embed` is called):** persist input text (redacted), purpose, model, timing, returned dimensions, and error metadata. Do **not** persist the full embedding vector by default.

Handoff after build auth (from the PRD): propose schema + live-update **before coding**; wrap shared boundaries; add `/dev/ai-trace`; prove T1–T10 with at least one orchestrator failure and one model-output failure visibly distinct; **stop** — do not start MBQL.

---

## 4. Scope

### IN

- Provider-neutral trace contract (Trace + Span/Event; parent/child).  
- Stages 1–8 and field catalog in the [PRD](MBPRD-P2-I7A_AI_MODEL_TRACE_AND_OBSERVABILITY.md) §§5–6.  
- Developer-only AI Trace window at **`/dev/ai-trace`**: list, detail panes that separate **assembled MemoryBox context** from **exact provider payload sent**, plus Raw / Parsed / MB Result, Live Follow (poll ~500 ms–1 s), filter, copy/export JSON, clear, retention.  
- Local PostgreSQL (or equivalent local) store; default **500 traces or 7 days**; configurable; automatic cleanup + manual clear.  
- Secret redaction **before write**.  
- Passive emission: UI closed still works; store down does not fail Ask.  
- Harness T1–T10 (forced-model hook is allowed for T1/T4/T6/T7/T8 because production Ask is still mostly deterministic).

### OUT

- MBQL grammar, planner rewrite, or “the model interprets every Ask.”  
- Family-facing AI / Settings product (I13/I14). Family primary nav link.  
- I8 email richness, I8.5 face SoT, I9 STT, I10 Alaska inference, I11 narrative generation.  
- SMS attachment bytes (**P2-BL-I7-01**) or I8 email attachment ingest (**P2-BL-I8-01**).  
- External Jaeger/OTLP/SaaS as a requirement.  
- SSE/WebSocket as a P2 requirement.  
- Persisting full embedding vectors by default.  
- Asking the model to explain its hidden reasoning.  
- Changing I7 SMS retrieve or attachment ingest.

---

## 5. Acceptance (passed)

Pass the PRD §10 list and T1–T10. Visual polish may be thin. **Gating:** request → raw response → parsed/validated → MB disposition, plus error class that does not say “AI error” for a Python bug. Zero-model Asks must still appear as complete request traces.

`prove-p2-i7a` is a harness / regression check. **ACCEPTED** is the FlightSim owner pass (2026-08-15): Explore history keys, real Ask results, `/dev/ai-trace` on a second display.

**Ask-path persist overhead (measured, warm store):** about **80 ms** for a zero-model Ask (median 78 ms; 75–83 ms). One extra chat/embed span is about **+20 ms**. Closing `/dev/ai-trace` stops poll traffic; it does **not** remove this persist cost. That ~80 ms is ~1% of a 6 s warm SMS Ask and is not the 60 s first-Ask cold start.

---

## 6. Privacy

Traces may contain the most sensitive prompt material in MemoryBox. They are **diagnostic**, not Evidence. Local only. API keys, credentials, authorization headers, and connection tokens are stripped **before the row is written**. Family nav must not link here.

---

## 7. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001 v0.2 insertion + MBPRD-P2-I7A v0.1 | **INGESTED** 2026-08-15 |
| I7A increment definition | **LOCKED** 2026-08-15 (Q1–Q6 + extra rules) |
| I7 SMS/Text | **ACCEPTED** 2026-08-15 — attachment bytes **P2-BL-I7-01** |
| I7A build | **AUTHORIZED** 2026-08-15 |
| I7A ACCEPTED | **Yes** (2026-08-15 — Tom FlightSim owner pass) |
| MBQL-001 | **ACCEPTED** 2026-08-18 — [definition](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) |

**I7A ACCEPTED.** Keep `/dev/ai-trace` off when not diagnosing; emission stays on for later increments. MBQL-001 **ACCEPTED** 2026-08-18. **P2-I8 ACCEPTED** 2026-08-18. **P2-I8A is DRAFT** (not build-authorized).

## 8. FlightSim deploy (this branch)

```powershell
cd C:\memorybox
git fetch origin
git checkout cursor/p2-i7a-model-trace-definition-3061
git pull origin cursor/p2-i7a-model-trace-definition-3061
python -m memorybox migrate
# restart Ask/serve (required — old serve will keep polling a missing table)
#   http://127.0.0.1:8790/dev/ai-trace
python -m memorybox prove-p2-i7a
```

`serve` now applies pending migrations and `ensure_schema()` on startup. If `/dev/ai-trace` still shows an empty list after a restart, the old process was not recycled.

Bookmark `/dev/ai-trace`. It is not in family nav. Run a normal Ask (T3 path) and the T1–T10 buttons on the page. T2 (ORCHESTRATION) and T4 (MODEL_OUTPUT) must look different.
