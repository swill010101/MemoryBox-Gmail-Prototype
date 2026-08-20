-- P2-I8B Person-seeded video recognition & owner Learn
-- Extends I1 tables; does not drop or merge legacy face_appearance_moments.

ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS source_type TEXT;
ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS crop_path TEXT;
ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS embedding_json JSONB;
ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS quality_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS capture_at TIMESTAMPTZ;
ALTER TABLE face_evidence
    ADD COLUMN IF NOT EXISTS withdrawn BOOLEAN NOT NULL DEFAULT false;

UPDATE face_evidence
SET source_type = COALESCE(source_type,
    CASE
        WHEN method IN ('immich_face_asset') THEN 'immich_face'
        WHEN method IN ('owner_confirm', 'owner_correct', 'owner_learn') THEN 'owner_video'
        ELSE 'immich_face'
    END
)
WHERE source_type IS NULL;

ALTER TABLE face_appearance_moments
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'accepted';
ALTER TABLE face_appearance_moments
    ADD COLUMN IF NOT EXISTS model_version TEXT;
ALTER TABLE face_appearance_moments
    ADD COLUMN IF NOT EXISTS observation_ids UUID[] NOT NULL DEFAULT '{}';
ALTER TABLE face_appearance_moments
    ADD COLUMN IF NOT EXISTS processing_run_id UUID;
ALTER TABLE face_appearance_moments
    ADD COLUMN IF NOT EXISTS evidence_lineage TEXT;

-- Legacy I1/HVRT rows stay visible and distinguishable.
UPDATE face_appearance_moments
SET evidence_lineage = COALESCE(evidence_lineage,
    CASE
        WHEN method IN ('mb_native_i8b', 'owner_learn') THEN 'mb_native_i8b'
        ELSE 'i1_hvrt'
    END
)
WHERE evidence_lineage IS NULL;

ALTER TABLE recognition_queue_items
    ADD COLUMN IF NOT EXISTS run_kind TEXT NOT NULL DEFAULT 'provider_seeded';

CREATE TABLE IF NOT EXISTS recognition_processing_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       UUID REFERENCES people (id) ON DELETE SET NULL,
    run_kind        TEXT NOT NULL,
    -- provider_seeded | owner_learned | incremental | correction
    trigger         TEXT,
    status          TEXT NOT NULL DEFAULT 'running',
    detail          TEXT,
    candidate_count INT NOT NULL DEFAULT 0,
    accepted_count  INT NOT NULL DEFAULT 0,
    uncertain_count INT NOT NULL DEFAULT 0,
    range_count     INT NOT NULL DEFAULT 0,
    meta_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_recognition_runs_person
    ON recognition_processing_runs (person_id, started_at DESC);

CREATE TABLE IF NOT EXISTS video_face_observations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    t_sec               DOUBLE PRECISION NOT NULL,
    bbox_json           JSONB,
    person_id           UUID REFERENCES people (id) ON DELETE SET NULL,
    confidence          DOUBLE PRECISION,
    match_score         DOUBLE PRECISION,
    review_state        TEXT NOT NULL DEFAULT 'candidate',
    -- candidate | assigned | uncertain | withdrawn
    embedding_model     TEXT,
    exemplar_id         UUID REFERENCES face_evidence (id) ON DELETE SET NULL,
    processing_run_id   UUID REFERENCES recognition_processing_runs (id) ON DELETE SET NULL,
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_video_face_obs_video
    ON video_face_observations (video_provider_key, video_external_id, t_sec);
CREATE INDEX IF NOT EXISTS idx_video_face_obs_person
    ON video_face_observations (person_id);

CREATE TABLE IF NOT EXISTS identity_withdrawals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    start_sec           DOUBLE PRECISION NOT NULL,
    end_sec             DOUBLE PRECISION NOT NULL,
    observation_id      UUID,
    appearance_id       UUID,
    reason              TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_identity_withdrawals_lookup
    ON identity_withdrawals (person_id, video_provider_key, video_external_id);

CREATE TABLE IF NOT EXISTS pending_review_face_crops (
    face_external_id    TEXT PRIMARY KEY,
    video_external_id   TEXT,
    t_sec               DOUBLE PRECISION,
    bbox_json           JSONB,
    crop_jpeg_base64    TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
