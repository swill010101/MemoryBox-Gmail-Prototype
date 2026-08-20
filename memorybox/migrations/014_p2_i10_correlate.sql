-- P2-I10 Cross-Source Correlation
-- Places, correlatable events (event|trip|theme), and owner-correctable links.
-- Links never rewrite source files. Rejected rows stay for GRAPH-03.

CREATE TABLE IF NOT EXISTS places (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    aliases_json    JSONB NOT NULL DEFAULT '[]'::jsonb,
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_places_name_lower
    ON places (lower(display_name))
    WHERE status <> 'removed';

CREATE TABLE IF NOT EXISTS correlatable_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_kind      TEXT NOT NULL
        CHECK (event_kind IN ('event', 'trip', 'theme')),
    display_name    TEXT NOT NULL,
    start_date      DATE,
    end_date        DATE,
    place_id        UUID REFERENCES places (id) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed')),
    attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_correlatable_events_kind
    ON correlatable_events (event_kind);
CREATE INDEX IF NOT EXISTS idx_correlatable_events_name
    ON correlatable_events (lower(display_name));

CREATE TABLE IF NOT EXISTS correlation_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type    TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    object_type     TEXT NOT NULL,
    object_id       UUID NOT NULL,
    predicate       TEXT NOT NULL,
    evidence_id     UUID REFERENCES evidence (id) ON DELETE SET NULL,
    authority       TEXT NOT NULL DEFAULT 'system'
        CHECK (authority IN ('owner', 'contributor', 'system')),
    status          TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'confirmed', 'rejected', 'superseded')),
    observed_date   DATE,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_correlation_links_object
    ON correlation_links (object_type, object_id, status);
CREATE INDEX IF NOT EXISTS idx_correlation_links_subject
    ON correlation_links (subject_type, subject_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_correlation_links_identity
    ON correlation_links (
        subject_type, subject_id, object_type, object_id, predicate
    )
    WHERE status <> 'superseded';
