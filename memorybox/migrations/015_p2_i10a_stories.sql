-- P2-I10A Stories: Ask-current pointer, working drafts, versioned blocks and memories.
-- Existing stories are treated as already published (Ask-visible). Working version = 0.

ALTER TABLE stories
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private';
ALTER TABLE stories
    DROP CONSTRAINT IF EXISTS stories_visibility_check;
ALTER TABLE stories
    ADD CONSTRAINT stories_visibility_check
    CHECK (visibility IN ('private', 'shared_with_family'));

ALTER TABLE stories
    ADD COLUMN IF NOT EXISTS current_saved_version_id UUID;
ALTER TABLE stories
    ADD COLUMN IF NOT EXISTS working_version_id UUID;

ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS lifecycle TEXT NOT NULL DEFAULT 'saved';
ALTER TABLE story_versions
    DROP CONSTRAINT IF EXISTS story_versions_lifecycle_check;
ALTER TABLE story_versions
    ADD CONSTRAINT story_versions_lifecycle_check
    CHECK (lifecycle IN ('working', 'saved'));

ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS narrator_person_id UUID REFERENCES people (id) ON DELETE SET NULL;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS editor_person_id UUID REFERENCES people (id) ON DELETE SET NULL;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS described_start_date DATE;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS described_end_date DATE;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS described_precision TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE story_versions
    DROP CONSTRAINT IF EXISTS story_versions_described_precision_check;
ALTER TABLE story_versions
    ADD CONSTRAINT story_versions_described_precision_check
    CHECK (described_precision IN ('day', 'month', 'year', 'range', 'approximate', 'unknown'));
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS place_id UUID REFERENCES places (id) ON DELETE SET NULL;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS place_label TEXT;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS frozen_at TIMESTAMPTZ;
ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Existing rows are saved versions.
UPDATE story_versions
SET lifecycle = 'saved',
    frozen_at = COALESCE(frozen_at, created_at, now()),
    title = COALESCE(title, (SELECT s.title FROM stories s WHERE s.id = story_versions.story_id)),
    narrator_person_id = COALESCE(
        narrator_person_id,
        (SELECT s.narrator_person_id FROM stories s WHERE s.id = story_versions.story_id)
    )
WHERE lifecycle = 'saved' OR lifecycle IS NULL OR frozen_at IS NULL;

UPDATE stories s
SET current_saved_version_id = sv.id
FROM story_versions sv
WHERE sv.story_id = s.id
  AND sv.version = s.current_version
  AND s.current_saved_version_id IS NULL;

CREATE TABLE IF NOT EXISTS story_version_blocks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id  UUID NOT NULL REFERENCES story_versions (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    kind        TEXT NOT NULL
        CHECK (kind IN ('heading', 'paragraph', 'memory_ref')),
    text        TEXT,
    memory_id   UUID,
    UNIQUE (version_id, position)
);

CREATE INDEX IF NOT EXISTS idx_story_version_blocks_version
    ON story_version_blocks (version_id);

CREATE TABLE IF NOT EXISTS story_version_memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id      UUID NOT NULL REFERENCES story_versions (id) ON DELETE CASCADE,
    position        INTEGER NOT NULL,
    source_kind     TEXT NOT NULL
        CHECK (source_kind IN (
            'photo', 'video', 'email_thread', 'sms_conversation',
            'calendar_event', 'artifact', 'journal', 'audio', 'evidence'
        )),
    source_id       TEXT NOT NULL,
    label_snapshot  TEXT,
    occurred_on     DATE,
    thumb_url       TEXT,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (version_id, source_kind, source_id)
);

CREATE INDEX IF NOT EXISTS idx_story_version_memories_version
    ON story_version_memories (version_id);
CREATE INDEX IF NOT EXISTS idx_story_version_memories_source
    ON story_version_memories (source_kind, source_id);

CREATE TABLE IF NOT EXISTS story_version_people (
    version_id  UUID NOT NULL REFERENCES story_versions (id) ON DELETE CASCADE,
    person_id   UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (version_id, person_id)
);

-- One paragraph block from legacy body_text when none exist.
INSERT INTO story_version_blocks (id, version_id, position, kind, text)
SELECT gen_random_uuid(), sv.id, 0, 'paragraph', sv.body_text
FROM story_versions sv
WHERE COALESCE(sv.body_text, '') <> ''
  AND NOT EXISTS (
      SELECT 1 FROM story_version_blocks b WHERE b.version_id = sv.id
  );

-- People from unversioned relationships → current saved version.
INSERT INTO story_version_people (version_id, person_id, position)
SELECT s.current_saved_version_id, r.to_id, 0
FROM stories s
JOIN relationships r
  ON r.from_type = 'story' AND r.from_id = s.id
 AND r.to_type = 'person'
 AND r.status IN ('candidate', 'confirmed')
WHERE s.current_saved_version_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Evidence UUID links.
INSERT INTO story_version_memories (
    id, version_id, position, source_kind, source_id, label_snapshot
)
SELECT gen_random_uuid(), s.current_saved_version_id, 0, 'evidence', r.to_id::text, 'Evidence'
FROM stories s
JOIN relationships r
  ON r.from_type = 'story' AND r.from_id = s.id
 AND r.relationship_kind = 'cites_evidence'
 AND r.to_type = 'evidence'
 AND r.status IN ('candidate', 'confirmed')
WHERE s.current_saved_version_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Artifact links.
INSERT INTO story_version_memories (
    id, version_id, position, source_kind, source_id, label_snapshot
)
SELECT gen_random_uuid(), s.current_saved_version_id, 0, 'artifact', r.to_id::text,
       COALESCE(a.label, 'Artifact')
FROM stories s
JOIN relationships r
  ON r.from_type = 'story' AND r.from_id = s.id
 AND r.to_type = 'artifact'
 AND r.status IN ('candidate', 'confirmed')
LEFT JOIN artifacts a ON a.id = r.to_id
WHERE s.current_saved_version_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Note-bus Immich photos (mb_source_photo=).
INSERT INTO story_version_memories (
    id, version_id, position, source_kind, source_id, thumb_url, occurred_on
)
SELECT gen_random_uuid(),
       sv.id,
       0,
       'photo',
       substring(sv.note from 'mb_source_photo=(\S+)'),
       substring(sv.note from 'mb_thumb=(\S+)'),
       CASE
         WHEN substring(sv.note from 'mb_taken_at=(\S+)') ~ '^\d{4}-\d{2}-\d{2}'
         THEN left(substring(sv.note from 'mb_taken_at=(\S+)'), 10)::date
         ELSE NULL
       END
FROM story_versions sv
WHERE sv.note IS NOT NULL
  AND sv.note LIKE '%mb_source_photo=%'
  AND substring(sv.note from 'mb_source_photo=(\S+)') IS NOT NULL
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'stories_current_saved_version_fk'
    ) THEN
        ALTER TABLE stories
            ADD CONSTRAINT stories_current_saved_version_fk
            FOREIGN KEY (current_saved_version_id) REFERENCES story_versions (id)
            ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'stories_working_version_fk'
    ) THEN
        ALTER TABLE stories
            ADD CONSTRAINT stories_working_version_fk
            FOREIGN KEY (working_version_id) REFERENCES story_versions (id)
            ON DELETE SET NULL;
    END IF;
END $$;
