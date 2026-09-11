-- HC-2: singleton tick heartbeat (FlightSim apply via `python -m memorybox migrate`)
-- Do not apply on desktop unless HC schema is already present.

CREATE TABLE IF NOT EXISTS historian_capture_tick_heartbeat (
    id                  SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    result              TEXT NOT NULL DEFAULT 'never',
    duration_ms         INTEGER,
    replies_found       INTEGER,
    replies_imported    INTEGER,
    outbound_attempted  INTEGER,
    outbound_sent       INTEGER,
    deferred            INTEGER,
    failure_category    TEXT,
    payload_json        JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO historian_capture_tick_heartbeat (id, result)
VALUES (1, 'never')
ON CONFLICT (id) DO NOTHING;
