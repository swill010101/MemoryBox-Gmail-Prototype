-- P2-I10 Cross-Source Correlation: one Occurrence (Event or Trip) + membership.
-- Place is an anchor, not an Occurrence type. Do not mint a parallel graph.

CREATE TABLE IF NOT EXISTS occurrences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                TEXT NOT NULL CHECK (kind IN ('event', 'trip')),
    label               TEXT NOT NULL,
    normalized_label    TEXT NOT NULL,
    time_start          TIMESTAMPTZ,
    time_end            TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'owner_confirmed', 'rejected', 'withdrawn')),
    actor_key           TEXT,
    provenance_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_occurrences_kind_label_active
    ON occurrences (kind, normalized_label)
    WHERE status IS DISTINCT FROM 'withdrawn' AND status IS DISTINCT FROM 'rejected';

CREATE INDEX IF NOT EXISTS idx_occurrences_kind_status ON occurrences (kind, status);
CREATE INDEX IF NOT EXISTS idx_occurrences_time ON occurrences (time_start, time_end);

-- Place remains a first-class anchor linked to an Occurrence (not a third kind).
CREATE TABLE IF NOT EXISTS occurrence_places (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurrence_id       UUID NOT NULL REFERENCES occurrences (id) ON DELETE CASCADE,
    place_label         TEXT NOT NULL,
    place_key           TEXT NOT NULL,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    place_ref           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (occurrence_id, place_key)
);

CREATE TABLE IF NOT EXISTS occurrence_memberships (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurrence_id       UUID NOT NULL REFERENCES occurrences (id) ON DELETE CASCADE,
    evidence_kind       TEXT NOT NULL,
    evidence_key        TEXT NOT NULL,
    evidence_ref        JSONB NOT NULL,
    join_method         TEXT NOT NULL,
    confidence          DOUBLE PRECISION,
    status              TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'owner_confirmed', 'rejected', 'withdrawn')),
    actor_key           TEXT,
    provenance_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_occurrence_memberships_key
    ON occurrence_memberships (occurrence_id, evidence_kind, evidence_key);

CREATE INDEX IF NOT EXISTS idx_occurrence_memberships_occ_status
    ON occurrence_memberships (occurrence_id, status);

CREATE TABLE IF NOT EXISTS occurrence_membership_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    membership_id       UUID NOT NULL REFERENCES occurrence_memberships (id) ON DELETE CASCADE,
    occurrence_id       UUID NOT NULL REFERENCES occurrences (id) ON DELETE CASCADE,
    prior_status        TEXT,
    new_status          TEXT NOT NULL,
    actor_key           TEXT,
    reason              TEXT,
    join_method         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_occurrence_membership_history_member
    ON occurrence_membership_history (membership_id, created_at);
