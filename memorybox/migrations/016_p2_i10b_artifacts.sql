-- P2-I10B Artifacts: visibility, one optional date, place_id, representation
-- lifecycle, supporting memories. No described_end_date.

ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private';
ALTER TABLE artifacts
    DROP CONSTRAINT IF EXISTS artifacts_visibility_check;
ALTER TABLE artifacts
    ADD CONSTRAINT artifacts_visibility_check
    CHECK (visibility IN ('private', 'shared_with_family'));

ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS described_start_date DATE;
ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS described_precision TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE artifacts
    DROP CONSTRAINT IF EXISTS artifacts_described_precision_check;
ALTER TABLE artifacts
    ADD CONSTRAINT artifacts_described_precision_check
    CHECK (described_precision IN ('day', 'month', 'year', 'approximate', 'unknown'));

ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS place_id UUID REFERENCES places (id) ON DELETE SET NULL;

ALTER TABLE artifact_metadata_revisions
    ADD COLUMN IF NOT EXISTS visibility TEXT;
ALTER TABLE artifact_metadata_revisions
    ADD COLUMN IF NOT EXISTS described_start_date DATE;
ALTER TABLE artifact_metadata_revisions
    ADD COLUMN IF NOT EXISTS described_precision TEXT;
ALTER TABLE artifact_metadata_revisions
    ADD COLUMN IF NOT EXISTS place_id UUID;

ALTER TABLE artifact_representations
    ADD COLUMN IF NOT EXISTS view_kind TEXT NOT NULL DEFAULT 'other';
ALTER TABLE artifact_representations
    DROP CONSTRAINT IF EXISTS artifact_representations_view_kind_check;
ALTER TABLE artifact_representations
    ADD CONSTRAINT artifact_representations_view_kind_check
    CHECK (view_kind IN (
        'front', 'back', 'detail', 'engraving', 'document', 'other'
    ));

ALTER TABLE artifact_representations
    ADD COLUMN IF NOT EXISTS caption TEXT;
ALTER TABLE artifact_representations
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE artifact_representations
    DROP CONSTRAINT IF EXISTS artifact_representations_status_check;
ALTER TABLE artifact_representations
    ADD CONSTRAINT artifact_representations_status_check
    CHECK (status IN ('active', 'removed'));

UPDATE artifact_representations
SET view_kind = CASE lower(COALESCE(label, ''))
    WHEN 'front' THEN 'front'
    WHEN 'back' THEN 'back'
    WHEN 'detail' THEN 'detail'
    WHEN 'engraving' THEN 'engraving'
    WHEN 'document' THEN 'document'
    ELSE view_kind
END
WHERE view_kind = 'other';

CREATE TABLE IF NOT EXISTS artifact_memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id     UUID NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
    position        INTEGER NOT NULL DEFAULT 0,
    source_kind     TEXT NOT NULL
        CHECK (source_kind IN (
            'photo', 'video', 'email_thread', 'sms_conversation',
            'calendar_event', 'journal', 'audio'
        )),
    source_id       TEXT NOT NULL,
    label_snapshot  TEXT,
    occurred_on     DATE,
    thumb_url       TEXT,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, source_kind, source_id)
);

CREATE INDEX IF NOT EXISTS idx_artifact_memories_artifact
    ON artifact_memories (artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_memories_source
    ON artifact_memories (source_kind, source_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_place ON artifacts (place_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_visibility ON artifacts (visibility);

-- Compat: about_artifact → story_version_memories on Ask-current saved
-- version, or working if draft_only.
INSERT INTO story_version_memories (
    id, version_id, position, source_kind, source_id, label_snapshot
)
SELECT
    gen_random_uuid(),
    COALESCE(s.current_saved_version_id, s.working_version_id),
    COALESCE((
        SELECT MAX(m.position) + 1
        FROM story_version_memories m
        WHERE m.version_id = COALESCE(s.current_saved_version_id, s.working_version_id)
    ), 0),
    'artifact',
    r.to_id::text,
    COALESCE(a.label, 'Artifact')
FROM relationships r
JOIN stories s ON s.id = r.from_id AND s.status = 'active'
JOIN artifacts a ON a.id = r.to_id
WHERE r.relationship_kind = 'about_artifact'
  AND r.from_type = 'story'
  AND r.to_type = 'artifact'
  AND r.status IN ('candidate', 'confirmed')
  AND COALESCE(s.current_saved_version_id, s.working_version_id) IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM story_version_memories m
      WHERE m.version_id = COALESCE(s.current_saved_version_id, s.working_version_id)
        AND m.source_kind = 'artifact'
        AND m.source_id = r.to_id::text
  );
