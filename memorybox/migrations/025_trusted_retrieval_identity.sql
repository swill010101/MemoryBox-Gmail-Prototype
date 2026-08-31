-- Trusted-for-retrieval vs auto-confirmed identity.
-- Demote unsupported contacts to candidate/observed; do not delete rows.

ALTER TABLE person_contact_points
    DROP CONSTRAINT IF EXISTS person_contact_points_status_check;

ALTER TABLE person_contact_points
    ADD CONSTRAINT person_contact_points_status_check
    CHECK (status IN ('confirmed', 'candidate', 'observed', 'withdrawn', 'superseded'));

ALTER TABLE person_contact_points
    ADD COLUMN IF NOT EXISTS retrieval_trust TEXT;

ALTER TABLE person_contact_points
    DROP CONSTRAINT IF EXISTS person_contact_points_retrieval_trust_check;

ALTER TABLE person_contact_points
    ADD CONSTRAINT person_contact_points_retrieval_trust_check
    CHECK (retrieval_trust IS NULL OR retrieval_trust IN ('trusted', 'untrusted'));

CREATE INDEX IF NOT EXISTS idx_person_contacts_retrieval_trust
    ON person_contact_points (person_id, contact_kind, retrieval_trust)
    WHERE contact_kind = 'email';

COMMENT ON COLUMN person_contact_points.retrieval_trust IS
    'trusted = allowed in Ask/Gallery retrieve; untrusted = observed/candidate only';
