-- Increment 9A: Person Profile — layered facts, aliases, contacts,
-- Person↔Person relationship assertions (SoT), shared life events.
-- Identity SoT remains people / provider_identities (I6).

-- ---------------------------------------------------------------------------
-- Aliases (nickname / alternate name) — not display_name
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_aliases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    alias_kind      TEXT NOT NULL
        CHECK (alias_kind IN ('nickname', 'alternate_name')),
    alias_text      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'withdrawn', 'superseded')),
    superseded_by_id UUID REFERENCES person_aliases (id) ON DELETE SET NULL,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_person_aliases_person
    ON person_aliases (person_id);
CREATE INDEX IF NOT EXISTS idx_person_aliases_status
    ON person_aliases (person_id, status);

-- ---------------------------------------------------------------------------
-- Person facts (birth / death / free-form notes) — not a junk drawer for
-- contacts, relationships, or shared life events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_facts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    fact_kind       TEXT NOT NULL
        CHECK (fact_kind IN ('birth_date', 'death_date', 'note')),
    value_text      TEXT,
    value_date      DATE,
    status          TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'withdrawn', 'superseded')),
    superseded_by_id UUID REFERENCES person_facts (id) ON DELETE SET NULL,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (fact_kind IN ('birth_date', 'death_date') AND value_date IS NOT NULL)
        OR (fact_kind = 'note' AND value_text IS NOT NULL AND length(trim(value_text)) > 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_person_facts_person
    ON person_facts (person_id);
CREATE INDEX IF NOT EXISTS idx_person_facts_kind
    ON person_facts (person_id, fact_kind, status);

-- ---------------------------------------------------------------------------
-- Contact points (email / phone) — provenance + correction; NOT login /
-- provider identity (I6 mappings remain SoT for Immich etc.)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_contact_points (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    contact_kind    TEXT NOT NULL
        CHECK (contact_kind IN ('email', 'phone')),
    value_text      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'withdrawn', 'superseded')),
    superseded_by_id UUID REFERENCES person_contact_points (id) ON DELETE SET NULL,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_person_contacts_person
    ON person_contact_points (person_id);
CREATE INDEX IF NOT EXISTS idx_person_contacts_kind
    ON person_contact_points (person_id, contact_kind, status);

-- ---------------------------------------------------------------------------
-- Person↔Person relationship assertions (single SoT edge).
-- Inverse wording is DERIVED in the Relationship service — do not store a
-- second independently editable inverse row.
-- Semantics: from_person_id has role_kind toward to_person_id
--   e.g. Eugene father_of Tom  →  from=Eugene, role=father_of, to=Tom
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_relationship_assertions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_person_id  UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    to_person_id    UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    role_kind       TEXT NOT NULL,
    -- Controlled thin P1 vocabulary enforced in service layer
    status          TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'withdrawn', 'superseded')),
    superseded_by_id UUID REFERENCES person_relationship_assertions (id)
        ON DELETE SET NULL,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (from_person_id <> to_person_id)
);

CREATE INDEX IF NOT EXISTS idx_person_rel_from
    ON person_relationship_assertions (from_person_id, status);
CREATE INDEX IF NOT EXISTS idx_person_rel_to
    ON person_relationship_assertions (to_person_id, status);
CREATE INDEX IF NOT EXISTS idx_person_rel_role
    ON person_relationship_assertions (role_kind, status);

-- ---------------------------------------------------------------------------
-- Shared life events (marriage / anniversary class) — both participants
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shared_life_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_kind      TEXT NOT NULL
        CHECK (event_kind IN ('marriage')),
    event_date      DATE,
    label           TEXT,
    status          TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'withdrawn', 'superseded')),
    superseded_by_id UUID REFERENCES shared_life_events (id) ON DELETE SET NULL,
    actor_key       TEXT NOT NULL DEFAULT 'owner',
    note            TEXT,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shared_life_events_kind
    ON shared_life_events (event_kind, status);

CREATE TABLE IF NOT EXISTS shared_life_event_participants (
    event_id        UUID NOT NULL REFERENCES shared_life_events (id) ON DELETE CASCADE,
    person_id       UUID NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    participant_role TEXT NOT NULL DEFAULT 'spouse'
        CHECK (participant_role IN ('spouse', 'partner')),
    PRIMARY KEY (event_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_shared_life_event_participants_person
    ON shared_life_event_participants (person_id);
