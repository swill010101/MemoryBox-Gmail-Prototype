-- Reusable I11A derived observations (Person media/place history, etc.).
-- Invalidated when source evidence IDs or owner corrections change.

CREATE TABLE IF NOT EXISTS semantic_observations (
    observation_id TEXT PRIMARY KEY,
    person_id TEXT,
    method TEXT NOT NULL,
    method_version TEXT NOT NULL,
    model TEXT,
    source_evidence_ids TEXT[] NOT NULL DEFAULT '{}',
    source_hash TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence TEXT,
    uncertainty TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    invalidated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_semantic_obs_lookup
    ON semantic_observations (person_id, method, source_hash)
    WHERE invalidated_at IS NULL;
