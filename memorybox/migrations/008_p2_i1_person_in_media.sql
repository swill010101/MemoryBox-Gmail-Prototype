-- P2-I1 Show me Peggy — Person-in-Media Vertical

-- Immich → MB Person sync cursor / last run
CREATE TABLE IF NOT EXISTS provider_person_sync_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key    TEXT NOT NULL,
    trigger         TEXT NOT NULL, -- nightly | sync_now | harness
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running', -- running | completed | failed
    detail          TEXT,
    created_count   INT NOT NULL DEFAULT 0,
    mapped_count    INT NOT NULL DEFAULT 0,
    skipped_count   INT NOT NULL DEFAULT 0,
    conflict_count  INT NOT NULL DEFAULT 0,
    meta_json       JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_provider_person_sync_runs_provider
    ON provider_person_sync_runs (provider_key, started_at DESC);

-- Provenance-preserved face evidence (Immich assets + owner confirms)
CREATE TABLE IF NOT EXISTS face_evidence (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    provider_key        TEXT NOT NULL,
    external_face_id    TEXT,
    external_person_id  TEXT,
    source_asset_id     TEXT,
    bbox_json           JSONB,
    method              TEXT NOT NULL, -- immich_face_asset | owner_confirm | owner_correct | auto_associate
    confidence          DOUBLE PRECISION,
    confirmation_state  TEXT NOT NULL DEFAULT 'unconfirmed',
    -- unconfirmed | system_associated | owner_confirmed | owner_corrected
    authority           TEXT NOT NULL DEFAULT 'ai_inferred',
    -- owner_confirmed | trusted_provider | ai_inferred
    exemplar_meta_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_face_evidence_person ON face_evidence (person_id);
CREATE INDEX IF NOT EXISTS idx_face_evidence_provider
    ON face_evidence (provider_key, external_face_id);
CREATE INDEX IF NOT EXISTS idx_face_evidence_authority ON face_evidence (authority);

-- Durable recognition work queue (full eligible archive; exclusions visible)
CREATE TABLE IF NOT EXISTS recognition_queue_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'queued',
    -- queued | running | completed | failed | excluded
    reason              TEXT,
    priority            INT NOT NULL DEFAULT 100,
    enqueue_reason      TEXT NOT NULL DEFAULT 'newly_known_person',
    -- newly_known_person | exemplar_change | harness
    attempt_count       INT NOT NULL DEFAULT 0,
    result_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    UNIQUE (person_id, video_provider_key, video_external_id, enqueue_reason)
);

CREATE INDEX IF NOT EXISTS idx_recognition_queue_person_status
    ON recognition_queue_items (person_id, status);
CREATE INDEX IF NOT EXISTS idx_recognition_queue_status
    ON recognition_queue_items (status, priority, created_at);

-- Derived face-appearance moments (rebuildable)
CREATE TABLE IF NOT EXISTS face_appearance_moments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    start_sec           DOUBLE PRECISION NOT NULL,
    end_sec             DOUBLE PRECISION NOT NULL,
    face_external_id    TEXT,
    method              TEXT NOT NULL,
    confidence          DOUBLE PRECISION,
    confirmation_state  TEXT NOT NULL DEFAULT 'system_associated',
    authority           TEXT NOT NULL DEFAULT 'ai_inferred',
    source_exemplar_ids UUID[] NOT NULL DEFAULT '{}',
    play_url            TEXT,
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_face_appearance_person
    ON face_appearance_moments (person_id);
CREATE INDEX IF NOT EXISTS idx_face_appearance_video
    ON face_appearance_moments (video_provider_key, video_external_id);
