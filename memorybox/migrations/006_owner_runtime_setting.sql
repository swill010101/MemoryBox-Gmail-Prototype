-- Increment 9A+: durable runtime settings (canonical owner Person)
-- Env MEMORYBOX_OWNER_PERSON_ID still overrides when set (ops/deploy).

CREATE TABLE IF NOT EXISTS memorybox_runtime_settings (
    setting_key     TEXT PRIMARY KEY,
    value_text      TEXT,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed key reserved: owner_person_id → MB people.id
