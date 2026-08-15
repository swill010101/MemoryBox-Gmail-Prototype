# MBPRD-P2-I7A — AI Model Trace & Observability

**Status:** Ingested. I7A **definition locked** · **BUILD AUTHORIZED** 2026-08-15.  
**ID:** MBPRD-P2-I7A · **Source file:** v0.1 · 2026-08-15 (Tom Word upload)  
**MBRM citation:** v0.2 insertion names this PRD as v0.2; this ingest is the v0.1 document Tom attached.  
**Increment definition (locked):** [MBBS-P2_INCREMENT_7A_DEFINITION.md](MBBS-P2_INCREMENT_7A_DEFINITION.md)

Ingested from `MBPRD-P2-I7A_AI_Model_Trace_and_Observability_v0.1.docx`. Wording below is Tom’s PRD, normalized to markdown. I7 is ACCEPTED; I7A code still waits for **explicit I7A build authorization**. No MBQL in I7A.

---

## 1. Decision and rationale

MemoryBox will add a dedicated AI Model Trace & Observability increment **before MBQL-001**. MBQL-001 is intended for post-I7 adoption and will expand model-assisted interpretation across the Query Planner, Experience Orchestrator, Ask, future speech, correlation, and narrative. Instrumentation should exist before that complexity arrives.

The model must not be asked to monitor or explain its own hidden reasoning. MemoryBox will observe model interactions **externally** at the provider boundary and across the surrounding application pipeline. The monitor records what MemoryBox asked the model to do, exactly what was sent, exactly what came back, and what MemoryBox did with the result.

**Governing diagnostic principle:** For any surprising result, the trace should make it possible to separate an orchestration/application error from a model/provider error.

## 2. Problem statement

A single user request can pass through context assembly, deterministic planning, model interpretation, retrieval, prompt construction, model response, parsing, trust validation, and final application behavior. Without structured traces, a tester may see only the final wrong answer.

- A Python/orchestrator bug can send the wrong person, time range, evidence scope, or task to the model.
- A prompt-builder bug can omit or distort context even when the Query Planner was correct.
- The model can misinterpret a correct prompt or return malformed/unsupported output.
- The response parser can incorrectly transform a valid model response.
- Trust/validation logic can accept something it should reject, or reject something valid.
- Downstream UI/application logic can display or execute something different from the accepted model result.
- Multiple model calls may occur in one user interaction.

## 3. Product goal

A persistent, local developer window that can follow every model interaction live and retain recent traces. From one trace a tester can answer:

1. What user action or background job caused the model call?
2. What MemoryBox component decided to call the model?
3. Which provider and exact model were used?
4. What task did MemoryBox ask the model to perform?
5. What context, prompt, evidence, schema, and parameters were actually sent?
6. What raw response did the provider/model return?
7. How did MemoryBox parse and validate that response?
8. What did MemoryBox accept, reject, modify, store, execute, or show?
9. Where did any error occur, and how should it be classified?

## 4. Scope

### 4.1 In

- Provider-neutral tracing contract around every LLM/VLM invocation used by MemoryBox.
- End-to-end correlation from initiating request/job through orchestration, model call, parsing/validation, and final MB disposition.
- Dedicated developer-only AI Trace window (separate browser tab; leave running during testing).
- Live Follow plus persistent history of recent traces.
- Full inspection of request metadata, model input, raw output, parsed output, validation, downstream action, timing, and errors.
- Failure-stage classification (model vs MemoryBox/Python).
- Filter/search and copy/export of a structured trace.
- Local retention and cleanup appropriate for sensitive family evidence.

### 4.2 Out

- Exposing private chain-of-thought or reconstructing hidden model reasoning.
- Changing MBQL semantics or implementing MBQL itself.
- A normal Family Historian-facing AI dashboard.
- External SaaS telemetry / cloud observability as a requirement.
- Model evaluation/scoring beyond basic trace comparison and error classification.
- Replacing existing application logging.

## 5. Trace model

One user interaction is a **Trace**. Each meaningful stage is a **Span/Event**. A Trace may contain zero, one, or many model calls. Every span shares a Trace ID; nested operations may carry parent/child Span IDs.

### Required stages

| Stage | What must be visible | Primary error class |
|-------|----------------------|---------------------|
| 1. Initiation | User Ask/action or background job; active context; request timestamp | Input/context |
| 2. Orchestrator / Planner | Normalized intent/state before the model; deterministic decisions; selected path | Orchestration/Python |
| 3. Prompt / Request Build | Task name, instructions, messages, evidence/context, expected schema, parameters | Prompt construction |
| 4. Provider Call | Provider, exact model, endpoint/host, start/end, duration, token/context metrics when available | Provider/transport/model |
| 5. Raw Response | Unmodified text/JSON/tool-style response and provider metadata | Model output |
| 6. Parse / Validate | Parsed structure, schema errors, trust checks, accepted/rejected fields, fallback | Parser/validation |
| 7. MB Disposition | What MB stored, executed, used for retrieval, rendered, or returned | Application/downstream |
| 8. Final User Result | Final answer/navigation/filter/state change shown to the user where applicable | Presentation/application |

### Required fields

| Category | Fields |
|----------|--------|
| Identity | `trace_id`, `span_id`, `parent_span_id`, request/job ID, timestamp, component, operation/purpose |
| Model | provider, model name, version/digest when available, host/endpoint, capability type (LLM/VLM/embedding if traced) |
| Request | task/purpose, exact messages/prompt payload, structured context, evidence references and included content, requested schema, temperature/options when used |
| Response | raw provider response, provider metadata, finish/stop status, usage/tokens when available, latency |
| Interpretation | parsed result, normalized state/object, parser warnings/errors, validation/trust decisions |
| Disposition | accepted/rejected/modified output, downstream MB action, persisted IDs if any, final user-facing result |
| Errors | stage, category, exception/error code, message, stack for MB/Python failures, retry/fallback status |
| Privacy/retention | trace enabled state, redaction mode if used, retention expiry/cleanup status |

## 6. Error classification

Do not collapse failures into “AI error.”

| Class | Example | What it tells us |
|-------|---------|------------------|
| ORCHESTRATION | Planner selected Email instead of SMS; wrong Person ID; wrong inherited context | MemoryBox/Python is wrong **before** the model call |
| PROMPT_BUILD | Correct plan, but Peggy evidence omitted from the prompt | Prompt assembly bug |
| PROVIDER_TRANSPORT | Ollama unreachable, timeout, HTTP failure | Infrastructure/provider boundary |
| MODEL_EXECUTION | Provider reports model load/inference failure | Model runtime/provider failure |
| MODEL_OUTPUT | Model returns incorrect intent or unsupported claim despite correct input | Model behavior/quality |
| PARSE_SCHEMA | Valid-looking response cannot be parsed into required structure | Response contract/parser |
| TRUST_VALIDATION | Unsupported assertion rejected or incorrectly accepted | MemoryBox trust gate |
| DOWNSTREAM_APP | Parsed/accepted result is correct but UI/query execution differs | Application/UI execution |

## 7. Developer window UX

Dedicated developer surface, not a transient console. Easy to leave open on a second display.

- Location: Settings / Developer / AI Trace (or equivalent developer-only route).
- Open in a separate browser tab; URL stable and locally bookmarkable.
- Live Follow ON/OFF. When ON, newest active trace stays selected and updates as spans arrive.
- Trace list columns: time, originating Ask/job, purpose, model, duration, status, error class.
- Expandable ordered stage timeline.
- Separate panes: Sent to Model · Raw Model Return · Parsed/Validated · MemoryBox Result.
- Search/filter by Trace ID, model, provider, component, purpose, status/error class, time.
- Copy Trace ID; copy raw request/response; export selected trace as structured JSON.
- Clear history and configure retention from the developer surface.
- Strong visual distinction between model output and MemoryBox-approved/committed output.

## 8. Persistence, security, privacy

Trace data may include private emails, texts, transcripts, and names. Same local-first and trust principles as the product.

- Local by default. No trace payload to an external analytics/telemetry service by this requirement.
- Diagnostic data, **not** authoritative family evidence.
- Structured local persistence compatible with existing architecture (e.g. dedicated PostgreSQL tables/JSONB).
- Bounded, configurable retention; automatic cleanup and immediate manual clear.
- Not exposed through normal family-facing navigation.
- Secrets, credentials, API keys, authorization headers, and connection tokens must **never** be written into trace payloads.
- A future redaction mode may mask evidence content; I7A must still make exact local debugging possible for an authorized developer.

## 9. Architecture requirements

- Instrument at the MemoryBox **model-provider abstraction**, not inside Ollama-specific business logic.
- All current and future model providers emit the same core trace lifecycle.
- Query Planner and Experience Orchestrator can add pre-model and post-model spans to the same Trace ID.
- Emission is lightweight and must not materially alter application behavior or model results.
- Model calls function when the trace UI is closed; observability is passive.
- Trace storage failure must not fail the user request; log the observability failure separately.
- Conceptually compatible with span/event tracing (e.g. OpenTelemetry) but **must not require** external infrastructure for P2.

## 10. Acceptance criteria

1. Every MemoryBox model invocation: initiating request/job, MB component, provider, exact model, purpose, timing.
2. Tester can view the exact payload/messages sent and the unmodified raw provider response.
3. Same trace shows parsed response, validation/trust result, and final MemoryBox disposition.
4. Orchestrator/Python exception before the model call: trace shows the failure and that **no model request was made**.
5. Correct input, bad/invalid model answer: classifiable as model/output, not orchestration.
6. Parse/schema failure after a successful model response: classified separately from model execution.
7. Multiple model calls in one user request: one parent trace, chronological order.
8. AI Trace window can stay open with Live Follow; updates without page refresh.
9. Recent traces survive close/reopen until retention cleanup or manual clear.
10. Filter traces; copy/export a selected structured trace.
11. Secrets/authentication material are not persisted.
12. Disabling or losing the trace store does not break normal model execution.

## 11. Required test scenarios

| Test | Condition | Expected diagnostic |
|------|-----------|---------------------|
| T1 Normal model call | Known Ask requiring model interpretation | Complete request → raw → parsed → MB disposition |
| T2 Orchestrator defect | Force wrong/missing normalized context before model call | Incorrect pre-model state; orchestration stage |
| T3 No model call | Deterministic query handled without LLM | Deterministic path; **zero** model spans |
| T4 Model bad output | Correct prompt, wrong intent or malformed JSON | Raw output preserved; MODEL_OUTPUT or PARSE_SCHEMA |
| T5 Provider unavailable | Stop Ollama or force timeout | PROVIDER_TRANSPORT; duration; retry/fallback |
| T6 Parser defect | Valid model response, parser mishandles | Raw differs from parsed; parser stage |
| T7 Trust rejection | Unsupported assertion | Raw assertion, validation rejection, no promotion to fact |
| T8 Multi-call | Planner + narrative or other two-call flow | One parent trace; parent/child order |
| T9 Retention | Close/reopen; age traces | Recent persist; cleanup at configured boundary |
| T10 Secret scrubbing | Auth configuration present on provider request | Credentials/headers absent from stored/displayed trace |

## 12. Roadmap placement

**Dependency rule:** MBQL implementation should not begin until I7A acceptance is complete enough to trace model calls end-to-end. Visual polish may be minimal; the request/response/disposition chain and error classification are gating.

| Order | Increment / artifact | Relationship |
|-------|----------------------|--------------|
| 1 | P2-I7 SMS/Text | Complete current build/test and **accept I7** |
| 2 | **P2-I7A** AI Model Trace | NEW. Observability before increasing model workload |
| 3 | MBQL-001 | Use AI Trace during Planner/Orchestrator expansion |
| 4 | P2-I8 Richer Email | Reuses MBQL + AI Trace |
| 5 | P2-I8.5 Face Evidence Ownership | Existing inserted increment; **unchanged** by I7A |
| 6 | P2-I9 Spoken Moments | Inherits the same tracing |
| 7+ | I10 / I11 / later VLM | Trace becomes more valuable as synthesis grows |

## 13. Cursor handoff (after build is authorized — not now)

1. Inspect the current LLM/Ollama provider abstraction and identify every model-call entry point.
2. Inspect Query Planner and Experience Orchestrator boundaries for pre- and post-model spans.
3. Propose minimal schema/storage and local live-update **before coding**.
4. Implement tracing at shared provider/orchestrator boundaries; do not instrument only the current Ollama call site.
5. Add the developer AI Trace window and Live Follow.
6. Add T1–T10; demonstrate at least one orchestrator failure and one model-output failure as visibly distinct.
7. **Stop after I7A acceptance.** Do not roll into MBQL without founder review.

## 14. Decision locked by this PRD

P2-I7A is inserted **after I7 and before MBQL**. It is provider-neutral, developer-facing, persistent, and intended to distinguish MemoryBox/orchestrator errors from model/provider errors.

| Field | Content |
|-------|---------|
| Roadmap placement | Immediately after P2-I7 SMS/Text **acceptance** and before MBQL-001 |
| Primary user | Founder/developer/tester; **not** a normal Family Historian surface |
| Core question | Was a bad result caused by orchestration/Python, the model call, parse/validation, or downstream application logic? |
| Provider scope | Provider-neutral. Ollama is the current local model provider; future providers use the same contract |
| Status | Definition **LOCKED** 2026-08-15. I7 is ACCEPTED. **No I7A build** until explicit authorization. See definition §2. |

## 15. Founder lock (2026-08-15) — does not rewrite §§1–14

Authoritative answers live in [I7A definition §2](MBBS-P2_INCREMENT_7A_DEFINITION.md). Summary:

- Sequence: I7 ACCEPTED → I7A → MBQL-001. I8.5 remains after I8.
- No I7A runtime until explicit I7A build authorization. No MBQL in I7A.
- Trace all shared `LlmProvider.chat` and `embed` at the provider-neutral boundary. Embeddings: input / purpose / model / timing / dimensions / error; full vectors not required by default.
- Canonical route: `/dev/ai-trace`. Not in family primary nav. Settings may link later.
- P2 live updates: poll ~500 ms–1 s. SSE/WebSocket later only if needed.
- Retention: 500 traces or 7 days, whichever first; configurable; automatic cleanup + manual clear.
- Zero / one / many model calls per request. Deterministic Asks still get an end-to-end trace.
- UI distinguishes assembled MemoryBox context from the exact provider payload sent.
- Redact secrets before persistence. Trace-store failure never fails the user request.
