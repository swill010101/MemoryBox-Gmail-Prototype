-- P2-I10C Journal: drafts vs Ask-current, visibility, place, described time, versioned memories.

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private';
ALTER TABLE journal_entries
    DROP CONSTRAINT IF EXISTS journal_entries_visibility_check;
ALTER TABLE journal_entries
    ADD CONSTRAINT journal_entries_visibility_check
    CHECK (visibility IN ('private', 'shared_with_family'));

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS place_id UUID REFERENCES places (id) ON DELETE SET NULL;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS described_time TIME;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS current_saved_version INTEGER;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS working_version INTEGER;

ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS lifecycle TEXT NOT NULL DEFAULT 'saved';
ALTER TABLE journal_versions
    DROP CONSTRAINT IF EXISTS journal_versions_lifecycle_check;
ALTER TABLE journal_versions
    ADD CONSTRAINT journal_versions_lifecycle_check
    CHECK (lifecycle IN ('working', 'saved'));

ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS described_start_date DATE;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS described_end_date DATE;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS described_precision TEXT;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS described_time TIME;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS place_id UUID REFERENCES places (id) ON DELETE SET NULL;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS visibility TEXT;
ALTER TABLE journal_versions
    ADD COLUMN IF NOT EXISTS frozen_at TIMESTAMPTZ;

UPDATE journal_entries
SET current_saved_version = COALESCE(current_saved_version, current_version)
WHERE current_saved_version IS NULL
  AND COALESCE(current_version, 0) >= 1;

UPDATE journal_versions
SET lifecycle = 'saved',
    frozen_at = COALESCE(frozen_at, created_at, now())
WHERE lifecycle IS NULL OR lifecycle = 'saved';

CREATE TABLE IF NOT EXISTS journal_version_memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id      UUID NOT NULL REFERENCES journal_versions (id) ON DELETE CASCADE,
    position        INTEGER NOT NULL,
    source_kind     TEXT NOT NULL
        CHECK (source_kind IN (
            'photo', 'video', 'email_thread', 'sms_conversation',
            'calendar_event', 'artifact', 'audio', 'evidence'
        )),
    source_id       TEXT NOT NULL,
    label_snapshot  TEXT,
    occurred_on     DATE,
    thumb_url       TEXT,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (version_id, source_kind, source_id)
);

CREATE INDEX IF NOT EXISTS idx_journal_version_memories_version
    ON journal_version_memories (version_id);

CREATE TABLE IF NOT EXISTS journal_version_people (
    version_id  UUID NOT NULL REFERENCES journal_versions (id) ON DELETE CASCADE,
    person_id   UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (version_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_journal_saved ON journal_entries (current_saved_version);
CREATE INDEX IF NOT EXISTS idx_journal_visibility ON journal_entries (visibility);
CREATE INDEX IF NOT EXISTS idx_journal_place ON journal_entries (place_id);
