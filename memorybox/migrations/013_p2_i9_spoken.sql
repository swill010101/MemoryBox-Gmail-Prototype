-- P2-I9 Spoken Moments: words, anonymous turns, Spoken Moments, voice exemplars.
-- Transcription queue is per video. Do not cartesian people × files.

CREATE TABLE IF NOT EXISTS speech_processing_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_provider_key TEXT,
    video_external_id TEXT,
    run_kind        TEXT NOT NULL,
    trigger         TEXT,
    status          TEXT NOT NULL DEFAULT 'running',
    detail          TEXT,
    word_count      INT NOT NULL DEFAULT 0,
    turn_count      INT NOT NULL DEFAULT 0,
    moment_count    INT NOT NULL DEFAULT 0,
    meta_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS speech_transcript_words (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    t_start             DOUBLE PRECISION NOT NULL,
    t_end               DOUBLE PRECISION NOT NULL,
    token               TEXT NOT NULL,
    confidence          DOUBLE PRECISION,
    model_version       TEXT NOT NULL,
    processing_run_id   UUID REFERENCES speech_processing_runs (id) ON DELETE SET NULL,
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_speech_words_video
    ON speech_transcript_words (video_provider_key, video_external_id, t_start);

CREATE TABLE IF NOT EXISTS speech_speaker_turns (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    t_start             DOUBLE PRECISION NOT NULL,
    t_end               DOUBLE PRECISION NOT NULL,
    anonymous_speaker_key TEXT NOT NULL,
    person_id           UUID REFERENCES people (id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'anonymous',
    confidence          DOUBLE PRECISION,
    diarization_model   TEXT NOT NULL,
    processing_run_id   UUID REFERENCES speech_processing_runs (id) ON DELETE SET NULL,
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_speech_turns_video
    ON speech_speaker_turns (video_provider_key, video_external_id, t_start);

CREATE TABLE IF NOT EXISTS speech_spoken_moments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    t_start             DOUBLE PRECISION NOT NULL,
    t_end               DOUBLE PRECISION NOT NULL,
    text                TEXT NOT NULL,
    text_original       TEXT,
    turn_id             UUID REFERENCES speech_speaker_turns (id) ON DELETE SET NULL,
    person_id           UUID REFERENCES people (id) ON DELETE SET NULL,
    speaker_state       TEXT NOT NULL DEFAULT 'anonymous',
    confidence          DOUBLE PRECISION,
    model_version       TEXT NOT NULL,
    qdrant_point_id     TEXT,
    status              TEXT NOT NULL DEFAULT 'accepted',
    processing_run_id   UUID REFERENCES speech_processing_runs (id) ON DELETE SET NULL,
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_speech_moments_video
    ON speech_spoken_moments (video_provider_key, video_external_id, t_start);
CREATE INDEX IF NOT EXISTS idx_speech_moments_person
    ON speech_spoken_moments (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_speech_moments_text
    ON speech_spoken_moments USING gin (to_tsvector('simple', text));

CREATE TABLE IF NOT EXISTS speech_voice_exemplars (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    t_start             DOUBLE PRECISION NOT NULL,
    t_end               DOUBLE PRECISION NOT NULL,
    embedding_json      JSONB,
    embedding_model     TEXT NOT NULL,
    withdrawn           BOOLEAN NOT NULL DEFAULT false,
    authority           TEXT NOT NULL DEFAULT 'owner_confirmed',
    confirmation_state  TEXT NOT NULL DEFAULT 'owner',
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS speech_identity_withdrawals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    t_start             DOUBLE PRECISION NOT NULL,
    t_end               DOUBLE PRECISION,
    reason              TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS speech_queue_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_provider_key  TEXT NOT NULL,
    video_external_id   TEXT NOT NULL,
    person_id           UUID REFERENCES people (id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'queued',
    reason              TEXT,
    priority            INT NOT NULL DEFAULT 100,
    enqueue_reason      TEXT NOT NULL,
    attempt_count       INT NOT NULL DEFAULT 0,
    result_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_speech_queue_transcribe
    ON speech_queue_items (video_provider_key, video_external_id, enqueue_reason)
    WHERE person_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_speech_queue_learn
    ON speech_queue_items (video_provider_key, video_external_id, enqueue_reason, person_id)
    WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_speech_queue_status
    ON speech_queue_items (status, priority, created_at);
