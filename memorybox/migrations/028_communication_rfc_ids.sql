-- Indexed RFC Message-ID lookup for email communications.
-- Runtime neighbor walking must use this table, not payload_json regex scans.
-- One-time backfill is applied from memorybox.ingest.rfc_lookup after this file.

CREATE TABLE IF NOT EXISTS communication_rfc_ids (
    evidence_id UUID NOT NULL REFERENCES evidence (id) ON DELETE CASCADE,
    rfc_id      TEXT NOT NULL
        CHECK (char_length(rfc_id) BETWEEN 3 AND 512),
    role        TEXT NOT NULL
        CHECK (role IN ('own', 'in_reply_to', 'references')),
    PRIMARY KEY (evidence_id, rfc_id, role)
);

CREATE INDEX IF NOT EXISTS idx_communication_rfc_ids_rfc_id
    ON communication_rfc_ids (rfc_id);

CREATE INDEX IF NOT EXISTS idx_communication_rfc_ids_evidence_id
    ON communication_rfc_ids (evidence_id);

COMMENT ON TABLE communication_rfc_ids IS
    'Normalized RFC Message-IDs for email evidence. Equality lookups only.';
COMMENT ON COLUMN communication_rfc_ids.rfc_id IS
    'Canonical lowercased <local@host> Message-ID';
COMMENT ON COLUMN communication_rfc_ids.role IS
    'own = this message; in_reply_to / references = parent/thread ids';
