# P2-I7A — Trace persistence schema and live-update (build proposal)

**Status:** BUILD AUTHORIZED 2026-08-15 · this is the pre-code contract  
**Authority:** Locked [I7A definition](MBBS-P2_INCREMENT_7A_DEFINITION.md) §2  
**Not:** MBQL · family nav · SSE/WebSocket · full embedding vectors

---

## 1. Persistence (local PostgreSQL)

Two tables. Diagnostic only — not Evidence. Writes are fail-open (never fail Ask).

### `ai_traces` — one user request / job / harness run

| Column | Type | Notes |
|--------|------|-------|
| `trace_id` | UUID PK | Parent id for all spans |
| `created_at` / `updated_at` | timestamptz | List + Live Follow cursor |
| `request_kind` | text | `ask` · `job` · `harness` |
| `originating_ask` | text | Ask text or job name |
| `session_id` | text | Nullable |
| `purpose` | text | Short label (planner+retrieve, chat, embed, scenario id) |
| `status` | text | `running` · `ok` · `error` |
| `error_class` | text | PRD §6 class or null |
| `model_call_count` | int | `chat` + `embed` spans |
| `duration_ms` | int | End-to-end |
| `initiator` | jsonb | Ask text, session, timestamp |
| `assembled_context` | jsonb | MemoryBox plan/context **before** provider payload |
| `final_disposition` | jsonb | answer_kind, answer preview, hit counts, inventing |
| `error` | jsonb | stage, class, message, stack (MB/Python) |

### `ai_spans` — ordered stages (zero, one, or many model calls)

| Column | Type | Notes |
|--------|------|-------|
| `span_id` | UUID PK | |
| `trace_id` | UUID FK | ON DELETE CASCADE |
| `parent_span_id` | UUID | Nullable |
| `seq` | int | Chronological within the trace |
| `stage` | text | `initiation` · `planner` · `prompt_build` · `provider_call` · `raw_response` · `parse_validate` · `disposition` · `final_result` |
| `component` | text | `planner` · `orchestrator` · `llm_wrapper` · `retrieve` · `harness` |
| `operation` | text | `plan_ask` · `chat` · `embed` · … |
| `started_at` / `ended_at` / `duration_ms` | | |
| `status` / `error_class` | text | |
| `assembled_context` | jsonb | What MB assembled (may differ from payload) |
| `provider_payload` | jsonb | **Exact** messages/options/text sent (redacted) |
| `raw_response` | jsonb | Unmodified provider return. Embeddings: model / dimensions / error — **no vector by default** |
| `parsed` / `validation` / `disposition` | jsonb | Post-model interpretation |
| `model` | jsonb | provider_key, model, host (credentials stripped), capability `llm`/`embedding` |
| `error` / `meta` | jsonb | |

Indexes: `ai_traces(created_at DESC)`, `ai_traces(updated_at DESC)`, `ai_spans(trace_id, seq)`.

### Settings (configurable)

Stored in `memorybox_runtime_settings`:

| Key | Default |
|-----|---------|
| `ai_trace_max_traces` | `500` |
| `ai_trace_retention_days` | `7` |

Env overrides (optional): `MEMORYBOX_AI_TRACE_MAX`, `MEMORYBOX_AI_TRACE_DAYS`.  
Cleanup: delete older than N days, then if count still exceeds max, delete oldest. Runs after each successful write and on manual clear. Manual clear empties both tables.

---

## 2. Live-update (P2)

- **Mechanism:** HTTP polling. No SSE/WebSocket in I7A.
- **Interval:** 750 ms (inside the locked 500 ms–1 s band). UI may expose 500 / 750 / 1000.
- **List:** `GET /dev/api/ai-trace?updated_after=<iso>&q=&error_class=`
- **Detail:** `GET /dev/api/ai-trace/{trace_id}`
- **Clear:** `POST /dev/api/ai-trace/clear`
- **Settings:** `GET` / `PATCH /dev/api/ai-trace/settings`
- **Harness (developer only):** `POST /dev/api/ai-trace/scenario` for T1–T10 forced-model hooks

Live Follow ON keeps the newest `updated_at` trace selected and refreshes its detail. Closed UI does not affect emission.

---

## 3. Emission boundary

- `TracedLlmProvider` wraps any `LlmProvider` at `build_llm()` / `_llm_embedder()` / orchestrator inject. **Not** Ollama-only. `health()` / `/api/tags` are not spans.
- `contextvars` bind the current `trace_id` so Ask retrieve embeds attach to the Ask trace. No current trace → wrapper opens a short standalone/job trace.
- Orchestrator starts an Ask trace for **every** Ask, including deterministic paths with **zero** model spans (planner + disposition + final result).
- Secret redaction runs **before INSERT**. Trace-store exceptions are logged and swallowed.

---

## 4. UI

Canonical bookmarkable route: **`/dev/ai-trace`**. Standalone developer page (no family shell inject). Not in FAMILY or SYSTEM nav. Settings may link later (not this increment).
