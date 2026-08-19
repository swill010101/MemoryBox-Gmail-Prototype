-- Incremental overnight watermark: only rescan a Person when exemplars change.
CREATE TABLE IF NOT EXISTS recognition_person_watermark (
    person_id              UUID PRIMARY KEY REFERENCES people (id) ON DELETE CASCADE,
    exemplar_fingerprint   TEXT NOT NULL DEFAULT '',
    last_video_count       INT NOT NULL DEFAULT 0,
    last_pass_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_reason            TEXT,
    meta_json              JSONB NOT NULL DEFAULT '{}'::jsonb
);
