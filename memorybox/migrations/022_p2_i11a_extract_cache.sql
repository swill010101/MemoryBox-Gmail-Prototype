-- Deterministic observation_id upsert for Ask-independent extract cache.
-- Existing PK is observation_id; application writes fingerprint-derived ids.

CREATE INDEX IF NOT EXISTS idx_semantic_obs_extract_hash
    ON semantic_observations (method, method_version, source_hash)
    WHERE invalidated_at IS NULL;
