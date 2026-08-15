-- P2-I7A AI Model Trace — diagnostic only, not Evidence.

CREATE TABLE IF NOT EXISTS ai_traces (
    trace_id            UUID PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_kind        TEXT NOT NULL,
    originating_ask     TEXT,
    session_id          TEXT,
    purpose             TEXT,
    status              TEXT NOT NULL DEFAULT 'running',
    error_class         TEXT,
    model_call_count    INT NOT NULL DEFAULT 0,
    duration_ms         INT,
    initiator           JSONB NOT NULL DEFAULT '{}'::jsonb,
    assembled_context   JSONB,
    final_disposition   JSONB,
    error               JSONB
);

CREATE INDEX IF NOT EXISTS idx_ai_traces_created_at
    ON ai_traces (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_traces_updated_at
    ON ai_traces (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_traces_error_class
    ON ai_traces (error_class);

CREATE TABLE IF NOT EXISTS ai_spans (
    span_id             UUID PRIMARY KEY,
    trace_id            UUID NOT NULL REFERENCES ai_traces (trace_id) ON DELETE CASCADE,
    parent_span_id      UUID,
    seq                 INT NOT NULL,
    stage               TEXT NOT NULL,
    component           TEXT NOT NULL,
    operation           TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    duration_ms         INT,
    status              TEXT NOT NULL DEFAULT 'running',
    error_class         TEXT,
    assembled_context   JSONB,
    provider_payload    JSONB,
    raw_response        JSONB,
    parsed              JSONB,
    validation          JSONB,
    disposition         JSONB,
    model               JSONB,
    error               JSONB,
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ai_spans_trace_seq
    ON ai_spans (trace_id, seq);

INSERT INTO memorybox_runtime_settings (setting_key, value_text, actor_key)
VALUES
    ('ai_trace_max_traces', '500', 'system'),
    ('ai_trace_retention_days', '7', 'system')
ON CONFLICT (setting_key) DO NOTHING;
