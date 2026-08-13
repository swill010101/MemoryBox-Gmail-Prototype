-- Increment 5A: Journal versions, author SoT, capture vs described temporal range
-- Parallel in principle to Story versioning; author is first-class FK only (no authored_by dual-write).

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS author_person_id UUID REFERENCES people (id) ON DELETE RESTRICT;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS current_version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS captured_at TIMESTAMPTZ;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS described_start_date DATE;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS described_end_date DATE;

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS described_precision TEXT NOT NULL DEFAULT 'unknown';

-- Backfill captured_at from created_at where null
UPDATE journal_entries
SET captured_at = COALESCE(captured_at, created_at, now())
WHERE captured_at IS NULL;

ALTER TABLE journal_entries
    ALTER COLUMN captured_at SET DEFAULT now();

ALTER TABLE journal_entries
    ALTER COLUMN captured_at SET NOT NULL;

-- Soft-check precision vocabulary via constraint (drop/recreate if re-run)
ALTER TABLE journal_entries DROP CONSTRAINT IF EXISTS journal_entries_described_precision_check;
ALTER TABLE journal_entries
    ADD CONSTRAINT journal_entries_described_precision_check
    CHECK (described_precision IN ('day', 'month', 'year', 'range', 'approximate', 'unknown'));

-- Ensure every existing journal row has an author Person (SoT NOT NULL)
INSERT INTO people (id, display_name, status)
SELECT gen_random_uuid(), 'MemoryBox Owner', 'confirmed'
WHERE NOT EXISTS (
    SELECT 1 FROM people WHERE lower(display_name) = lower('MemoryBox Owner')
)
AND EXISTS (
    SELECT 1 FROM journal_entries WHERE author_person_id IS NULL
);

UPDATE journal_entries j
SET author_person_id = (
    SELECT p.id FROM people p
    WHERE lower(p.display_name) = lower('MemoryBox Owner')
    ORDER BY p.created_at ASC
    LIMIT 1
)
WHERE j.author_person_id IS NULL;

-- Only enforce NOT NULL when all rows are filled (empty table or backfilled)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM journal_entries WHERE author_person_id IS NULL) THEN
        ALTER TABLE journal_entries
            ALTER COLUMN author_person_id SET NOT NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS journal_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_id      UUID NOT NULL REFERENCES journal_entries (id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    body_text       TEXT NOT NULL,
    audio_uri       TEXT,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (journal_id, version)
);

CREATE INDEX IF NOT EXISTS idx_journal_versions_journal ON journal_versions (journal_id);
CREATE INDEX IF NOT EXISTS idx_journal_author ON journal_entries (author_person_id);
CREATE INDEX IF NOT EXISTS idx_journal_captured ON journal_entries (captured_at);
CREATE INDEX IF NOT EXISTS idx_journal_described_start ON journal_entries (described_start_date);

-- Seed v1 rows for legacy journals that have body but no version row
INSERT INTO journal_versions (id, journal_id, version, body_text, audio_uri, actor_key)
SELECT gen_random_uuid(), j.id, COALESCE(j.current_version, 1), COALESCE(j.body_text, ''), j.audio_uri, 'owner'
FROM journal_entries j
WHERE NOT EXISTS (
    SELECT 1 FROM journal_versions v WHERE v.journal_id = j.id AND v.version = COALESCE(j.current_version, 1)
);
