-- Address-centric communication identity (email/phone handles).
-- Person contacts remain the confirmed Person attachment; this table is the
-- archive-wide address ledger (observed display names → optional person).

CREATE TABLE IF NOT EXISTS communication_identities (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address_normalized    TEXT NOT NULL,
    identity_kind         TEXT NOT NULL DEFAULT 'email'
        CHECK (identity_kind IN ('email', 'phone')),
    observed_display_names JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- { "peggy george": {"header_count": N, "quoted_body_count": M, "header_fields": ["from","cc"]}, ... }
    evidence_ids_sample   JSONB NOT NULL DEFAULT '[]'::jsonb,
    header_occurrence_count INTEGER NOT NULL DEFAULT 0,
    quoted_body_occurrence_count INTEGER NOT NULL DEFAULT 0,
    resolved_person_id    UUID NULL REFERENCES people (id) ON DELETE SET NULL,
    resolution_status     TEXT NOT NULL DEFAULT 'observed'
        CHECK (resolution_status IN (
            'observed', 'candidate', 'confirmed', 'ambiguous', 'rejected'
        )),
    provenance_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (identity_kind, address_normalized)
);

CREATE INDEX IF NOT EXISTS communication_identities_person_idx
    ON communication_identities (resolved_person_id)
    WHERE resolved_person_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS communication_identities_status_idx
    ON communication_identities (resolution_status);

CREATE INDEX IF NOT EXISTS communication_identities_display_names_gin
    ON communication_identities USING GIN (observed_display_names);
