-- Increment 6: Person & Identity — negatives + merge history (non-destructive)

CREATE TABLE IF NOT EXISTS identity_negatives (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key    TEXT NOT NULL,
    identity_kind   TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    person_id       UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_key, identity_kind, external_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_identity_negatives_external
    ON identity_negatives (provider_key, identity_kind, external_id);
CREATE INDEX IF NOT EXISTS idx_identity_negatives_person
    ON identity_negatives (person_id);

CREATE TABLE IF NOT EXISTS person_merges (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survivor_person_id  UUID NOT NULL REFERENCES people (id) ON DELETE RESTRICT,
    loser_person_id     UUID NOT NULL REFERENCES people (id) ON DELETE RESTRICT,
    actor_key           TEXT NOT NULL DEFAULT 'owner',
    note                TEXT,
    snapshot_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_person_merges_survivor ON person_merges (survivor_person_id);
CREATE INDEX IF NOT EXISTS idx_person_merges_loser ON person_merges (loser_person_id);

-- Optional teaching / confirmation stamp on mappings (non-destructive)
ALTER TABLE provider_identities
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;

ALTER TABLE provider_identities
    ADD COLUMN IF NOT EXISTS confirmed_by TEXT;
