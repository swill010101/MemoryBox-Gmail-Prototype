-- Increment 9: Artifact (conceptual object) + Representations + metadata revisions
-- Artifact ≠ file: one Artifact may have many representations.
-- MB-managed originals: durable storage URI + content_hash; never silently overwrite.

CREATE TABLE IF NOT EXISTS artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            TEXT NOT NULL
        CHECK (kind IN (
            'keepsake_object',
            'letter',
            'document',
            'recipe_card',
            'clipping',
            'photograph_of_object',
            'other'
        )),
    label           TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    current_metadata_revision INTEGER NOT NULL DEFAULT 1,
    unresolved_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- e.g. {"person": true, "place": true, "event": true} when unknown
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts (status);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts (kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_label ON artifacts (label);

-- Immutable prior owner metadata (Story/Journal pattern for text fields)
CREATE TABLE IF NOT EXISTS artifact_metadata_revisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id     UUID NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
    revision        INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    label           TEXT NOT NULL,
    description     TEXT,
    unresolved_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_artifact_meta_rev_artifact
    ON artifact_metadata_revisions (artifact_id);

-- Immutable original representations (bytes not duplicated on metadata edit)
CREATE TABLE IF NOT EXISTS artifact_representations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id     UUID NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
    representation_kind TEXT NOT NULL DEFAULT 'mb_managed'
        CHECK (representation_kind IN ('mb_managed', 'evidence_ref')),
    -- mb_managed: uri under MEMORYBOX_ARTIFACT_MEDIA_ROOT + content_hash
    -- evidence_ref: evidence_id points at existing Evidence (provider originals untouched)
    evidence_id     UUID REFERENCES evidence (id) ON DELETE SET NULL,
    media_object_id UUID REFERENCES media_objects (id) ON DELETE SET NULL,
    uri             TEXT,
    content_hash    TEXT,
    mime_type       TEXT,
    original_filename TEXT,
    byte_size       BIGINT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    label           TEXT,
    -- optional caption for this representation (front/back/engraving)
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (representation_kind = 'mb_managed' AND uri IS NOT NULL AND content_hash IS NOT NULL)
        OR (representation_kind = 'evidence_ref' AND evidence_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_artifact_reps_artifact
    ON artifact_representations (artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_reps_hash
    ON artifact_representations (content_hash);
