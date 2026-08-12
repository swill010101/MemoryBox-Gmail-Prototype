-- MBBS-001 Increment 1 — MemoryBox domain schema v0
-- Conceptual mapping from MBDM-001. Minimal physical columns; expand in later increments.
-- Rule: no provider-native schemas (no Immich/HVRT tables as product model).

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Layer 3 — Source / Media / Evidence
-- ---------------------------------------------------------------------------

CREATE TABLE sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_kind     TEXT NOT NULL,
    -- e.g. mbox_import | immich_library | filesystem | capture_channel | manual
    label           TEXT,
    uri             TEXT,
    -- path, URL, or logical locator; not a provider schema dump
    content_hash    TEXT,
    authoritative_original_mode TEXT NOT NULL DEFAULT 'referenced'
        CHECK (authoritative_original_mode IN ('referenced', 'memorybox_managed')),
    metadata_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sources_kind ON sources (source_kind);

CREATE TABLE media_objects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID REFERENCES sources (id) ON DELETE SET NULL,
    media_kind      TEXT NOT NULL,
    -- photo | video | audio | document | scan | other
    storage_mode    TEXT NOT NULL DEFAULT 'referenced'
        CHECK (storage_mode IN ('referenced', 'memorybox_managed')),
    uri             TEXT,
    content_hash    TEXT,
    mime_type       TEXT,
    captured_at     TIMESTAMPTZ,
    metadata_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_media_source ON media_objects (source_id);
CREATE INDEX idx_media_kind ON media_objects (media_kind);

-- Optional stable handle for external systems (provider id lives here, not as Person PK)
CREATE TABLE media_refs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_object_id UUID NOT NULL REFERENCES media_objects (id) ON DELETE CASCADE,
    provider_key    TEXT NOT NULL,
    -- e.g. immich | hvrt | filesystem
    external_id     TEXT NOT NULL,
    metadata_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_key, external_id)
);

CREATE INDEX idx_media_refs_media ON media_refs (media_object_id);

CREATE TABLE evidence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_kind   TEXT NOT NULL,
    -- communication | media_span | transcript_span | ocr_span | story_passage | journal_passage | annotation | other
    source_id       UUID REFERENCES sources (id) ON DELETE SET NULL,
    media_object_id UUID REFERENCES media_objects (id) ON DELETE SET NULL,
    span_start      TEXT,
    span_end        TEXT,
    -- opaque span markers (byte offset, time sec, etc.) interpreted by evidence_kind
    summary         TEXT,
    payload_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_kind ON evidence (evidence_kind);
CREATE INDEX idx_evidence_source ON evidence (source_id);
CREATE INDEX idx_evidence_media ON evidence (media_object_id);

-- ---------------------------------------------------------------------------
-- Layer 1 — Person (Identity mappings are not Immich people tables)
-- ---------------------------------------------------------------------------

CREATE TABLE people (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT,
    status          TEXT NOT NULL DEFAULT 'unresolved'
        CHECK (status IN ('unresolved', 'confirmed', 'merged_away')),
    merged_into_id  UUID REFERENCES people (id) ON DELETE SET NULL,
    notes           TEXT,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_people_status ON people (status);
CREATE INDEX idx_people_display_name ON people (display_name);

CREATE TABLE provider_identities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       UUID REFERENCES people (id) ON DELETE SET NULL,
    provider_key    TEXT NOT NULL,
    -- immich | hvrt | email | phone | other — mapping only
    identity_kind   TEXT NOT NULL,
    -- face | voice | email | phone | external_person | other
    external_id     TEXT NOT NULL,
    label           TEXT,
    metadata_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_key, identity_kind, external_id)
);

CREATE INDEX idx_provider_identities_person ON provider_identities (person_id);

-- ---------------------------------------------------------------------------
-- Layer 4 — Assertions / Relationships
-- ---------------------------------------------------------------------------

CREATE TABLE assertions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assertion_kind  TEXT NOT NULL,
    subject_type    TEXT NOT NULL,
    subject_id      UUID NOT NULL,
    predicate       TEXT NOT NULL,
    object_type     TEXT,
    object_id       UUID,
    statement       TEXT,
    confidence      REAL,
    authority       TEXT NOT NULL DEFAULT 'system'
        CHECK (authority IN ('owner', 'contributor', 'system')),
    status          TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'confirmed', 'rejected', 'superseded')),
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_assertions_subject ON assertions (subject_type, subject_id);
CREATE INDEX idx_assertions_status ON assertions (status);

CREATE TABLE assertion_evidence (
    assertion_id    UUID NOT NULL REFERENCES assertions (id) ON DELETE CASCADE,
    evidence_id     UUID NOT NULL REFERENCES evidence (id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'supports'
        CHECK (role IN ('supports', 'contradicts')),
    PRIMARY KEY (assertion_id, evidence_id, role)
);

CREATE TABLE relationships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_kind TEXT NOT NULL,
    from_type       TEXT NOT NULL,
    from_id         UUID NOT NULL,
    to_type         TEXT NOT NULL,
    to_id           UUID NOT NULL,
    label           TEXT,
    status          TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'confirmed', 'rejected', 'superseded')),
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_relationships_from ON relationships (from_type, from_id);
CREATE INDEX idx_relationships_to ON relationships (to_type, to_id);

-- ---------------------------------------------------------------------------
-- Layer 2 — Story / Journal
-- ---------------------------------------------------------------------------

CREATE TABLE stories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    narrator_person_id UUID REFERENCES people (id) ON DELETE SET NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE story_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id        UUID NOT NULL REFERENCES stories (id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    body_text       TEXT NOT NULL,
    audio_uri       TEXT,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    confidence_at_save REAL,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, version)
);

CREATE INDEX idx_story_versions_story ON story_versions (story_id);

CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT,
    body_text       TEXT NOT NULL DEFAULT '',
    recorded_at     TIMESTAMPTZ,
    channel         TEXT,
    -- ui | email | voice | import | other
    audio_uri       TEXT,
    source_id       UUID REFERENCES sources (id) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_journal_recorded ON journal_entries (recorded_at);

-- ---------------------------------------------------------------------------
-- Platform — Jobs / processing
-- ---------------------------------------------------------------------------

CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_kind        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'done', 'error', 'cancelled')),
    subject_type    TEXT,
    subject_id      UUID,
    progress_pct    REAL,
    message         TEXT,
    error_message   TEXT,
    payload_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_jobs_status ON jobs (status);
CREATE INDEX idx_jobs_kind ON jobs (job_kind);

CREATE TABLE processing_states (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type    TEXT NOT NULL,
    subject_id      UUID NOT NULL,
    stage           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'done', 'error', 'skipped')),
    provider_key    TEXT,
    detail_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (subject_type, subject_id, stage)
);

CREATE INDEX idx_processing_states_subject ON processing_states (subject_type, subject_id);
