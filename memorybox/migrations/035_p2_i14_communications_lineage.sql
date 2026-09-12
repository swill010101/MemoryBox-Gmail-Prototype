-- P2-I14 Phase B step 1: logical source lineage, extract instances, checkpoints,
-- canonical record mapping, and identity aliases. Additive only.
--
-- Do not apply until founder deployment authorization.
-- Do not apply on Desktop or FlightSim without that authorization.
-- Never apply repository file 025_historian_capture_i12.sql as version 025.
-- FlightSim ledger 025-029 (trusted retrieval + RFC ids) stay in place; this
-- file must not replay, renumber, retire, or CREATE those objects.
--
-- Prepared-generation tables are not created here. Checkpoint has no generation FKs.
-- Calendar RRULE expansion and prepared-calendar grain are not decided here.
--
-- Later ingest (not this file) must consult existing:
--   person_contact_points.retrieval_trust  -- fail-closed Person linkage
--   communication_rfc_ids                  -- RFC aliases / thread reconstruction
-- Do not duplicate those structures. RFC aliases are generated/resolved from
-- communication_rfc_ids, then stored here as identity_method email_rfc_message_id.
--
-- Committed mapping transaction (later ingest, not this file):
--   1. compute/check aliases against comms_record_identity_aliases
--   2. insert evidence
--   3. insert comms_record_identities + aliases
--   4. commit atomically
-- evidence_id is NOT NULL with FK ON DELETE RESTRICT and UNIQUE(evidence_id).
--
-- Duplicate-count audit of existing evidence remains mandatory before backfill,
-- canonical selection among duplicates, merge/delete, or constraints on evidence.
--
-- Rollback (derived objects only; never drop 001-034 or evidence):
--   1. comms_record_identity_aliases
--   2. comms_record_identities
--   3. comms_source_checkpoint
--   4. comms_extract_instances
--   5. comms_source_memberships
--   6. comms_logical_sources

CREATE TABLE IF NOT EXISTS comms_logical_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logical_key         TEXT NOT NULL
        CHECK (logical_key ~ '^[a-z][a-z0-9_]{1,62}$'),
    source_kind         TEXT NOT NULL
        CHECK (source_kind IN ('email', 'calendar', 'sms')),
    label               TEXT NOT NULL
        CHECK (char_length(btrim(label)) BETWEEN 1 AND 120),
    is_configured       BOOLEAN NOT NULL DEFAULT FALSE,
    is_enabled          BOOLEAN NOT NULL DEFAULT FALSE,
    timezone_name       TEXT NOT NULL DEFAULT 'America/Chicago'
        CHECK (char_length(btrim(timezone_name)) BETWEEN 1 AND 64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_kind, logical_key)
);

CREATE INDEX IF NOT EXISTS idx_comms_logical_sources_kind
    ON comms_logical_sources (source_kind);

COMMENT ON TABLE comms_logical_sources IS
    'One stable production stream, independent of export filename or import run. No production keys seeded.';
COMMENT ON COLUMN comms_logical_sources.logical_key IS
    'Key unique per source_kind. Never a private address or filesystem path.';
COMMENT ON COLUMN comms_logical_sources.timezone_name IS
    'Closed-day policy timezone. Production default America/Chicago.';

CREATE TABLE IF NOT EXISTS comms_source_memberships (
    source_id           UUID PRIMARY KEY
        REFERENCES sources (id) ON DELETE RESTRICT,
    logical_source_id   UUID NOT NULL
        REFERENCES comms_logical_sources (id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, logical_source_id)
);

CREATE INDEX IF NOT EXISTS idx_comms_source_memberships_logical
    ON comms_source_memberships (logical_source_id);

COMMENT ON TABLE comms_source_memberships IS
    'One sources.id belongs to exactly one logical source. Successive extract fingerprints reuse this membership.';
COMMENT ON COLUMN comms_source_memberships.source_id IS
    'Existing sources.id. PK so a landing file cannot join a second production stream.';

CREATE TABLE IF NOT EXISTS comms_extract_instances (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logical_source_id       UUID NOT NULL REFERENCES comms_logical_sources (id) ON DELETE RESTRICT,
    source_id               UUID NOT NULL REFERENCES sources (id) ON DELETE RESTRICT,
    fingerprint             TEXT NOT NULL
        CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
    landing_alias           TEXT NOT NULL
        CHECK (landing_alias ~ '^[a-z][a-z0-9_]{1,62}$'),
    landing_basename        TEXT NOT NULL
        CHECK (
            char_length(btrim(landing_basename)) BETWEEN 1 AND 255
            AND landing_basename !~ '[\\/]'
            AND landing_basename NOT LIKE '%..%'
        ),
    byte_size               BIGINT
        CHECK (byte_size IS NULL OR byte_size >= 0),
    source_modified_at      TIMESTAMPTZ,
    validation_status       TEXT NOT NULL DEFAULT 'pending'
        CHECK (validation_status IN ('pending', 'valid', 'invalid')),
    ingest_status           TEXT NOT NULL DEFAULT 'not_started'
        CHECK (ingest_status IN (
            'not_started', 'running', 'checked_unchanged', 'ingested', 'failed'
        )),
    started_at              TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    failure_category        TEXT
        CHECK (failure_category IS NULL OR char_length(failure_category) BETWEEN 1 AND 80),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (logical_source_id, fingerprint),
    UNIQUE (logical_source_id, id),
    FOREIGN KEY (source_id, logical_source_id)
        REFERENCES comms_source_memberships (source_id, logical_source_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_comms_extract_instances_source
    ON comms_extract_instances (source_id);

CREATE INDEX IF NOT EXISTS idx_comms_extract_instances_logical
    ON comms_extract_instances (logical_source_id, created_at DESC);

COMMENT ON TABLE comms_extract_instances IS
    'One full-extract run. Logical stream in comms_logical_sources; file provenance in sources.id. source_id is not unique: a replaced landing URI may yield successive fingerprints.';
COMMENT ON COLUMN comms_extract_instances.source_id IS
    'Existing sources.id for the landing file. The same sources.id may have many extract instances when a URI is replaced by successive full exports. Exact URI stays on sources.';
COMMENT ON COLUMN comms_extract_instances.landing_alias IS
    'Configured source alias for Admin/status. Not an absolute path.';
COMMENT ON COLUMN comms_extract_instances.landing_basename IS
    'Safe filename only. No directories.';
COMMENT ON COLUMN comms_extract_instances.fingerprint IS
    'SHA-256 hex of extract bytes. Not a record identity.';

CREATE TABLE IF NOT EXISTS comms_source_checkpoint (
    logical_source_id           UUID PRIMARY KEY
        REFERENCES comms_logical_sources (id) ON DELETE RESTRICT,
    last_success_at             TIMESTAMPTZ,
    last_closed_source_date     DATE,
    current_extract_instance_id UUID,
    last_failure_category       TEXT
        CHECK (last_failure_category IS NULL OR char_length(last_failure_category) BETWEEN 1 AND 80),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (logical_source_id, current_extract_instance_id)
        REFERENCES comms_extract_instances (logical_source_id, id)
        ON DELETE RESTRICT
);

COMMENT ON TABLE comms_source_checkpoint IS
    'Per-logical-source progress. current_extract_instance_id must share logical_source_id. Referenced extracts cannot be deleted.';
COMMENT ON COLUMN comms_source_checkpoint.last_closed_source_date IS
    'Progress marker only. Not the sole skip filter for late historical records.';

CREATE TABLE IF NOT EXISTS comms_record_identities (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logical_source_id           UUID NOT NULL
        REFERENCES comms_logical_sources (id) ON DELETE RESTRICT,
    evidence_id                 UUID NOT NULL
        REFERENCES evidence (id) ON DELETE RESTRICT,
    source_kind                 TEXT NOT NULL
        CHECK (source_kind IN ('email', 'calendar', 'sms')),
    first_extract_instance_id   UUID NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (evidence_id),
    UNIQUE (id, logical_source_id),
    FOREIGN KEY (logical_source_id, first_extract_instance_id)
        REFERENCES comms_extract_instances (logical_source_id, id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_comms_record_identities_logical
    ON comms_record_identities (logical_source_id, created_at);

COMMENT ON TABLE comms_record_identities IS
    'Canonical immutable record: one evidence row, one logical source. No backfill in I14-035.';
COMMENT ON COLUMN comms_record_identities.evidence_id IS
    'Mandatory. Real evidence(id). ON DELETE RESTRICT. UNIQUE so one evidence row cannot be two logical records.';
COMMENT ON COLUMN comms_record_identities.first_extract_instance_id IS
    'First-seen extract; must share logical_source_id (composite FK).';

CREATE TABLE IF NOT EXISTS comms_record_identity_aliases (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_record_id     UUID NOT NULL,
    logical_source_id       UUID NOT NULL,
    identity_method         TEXT NOT NULL
        CHECK (identity_method IN (
            'email_rfc_message_id',
            'email_vendor_message_id',
            'email_full_sha256',
            'calendar_uid_recurrence',
            'calendar_uid_dtstart',
            'calendar_full_sha256',
            'sms_provider_id',
            'sms_normalized_sha256'
        )),
    record_key              TEXT NOT NULL
        CHECK (char_length(record_key) BETWEEN 3 AND 700),
    native_id_class         TEXT
        CHECK (native_id_class IS NULL OR native_id_class IN (
            'rfc_message_id',
            'gmail_msgid',
            'calendar_uid',
            'sms_guid',
            'fallback_hash'
        )),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (logical_source_id, identity_method, record_key),
    FOREIGN KEY (canonical_record_id, logical_source_id)
        REFERENCES comms_record_identities (id, logical_source_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_comms_record_identity_aliases_canonical
    ON comms_record_identity_aliases (canonical_record_id);

COMMENT ON TABLE comms_record_identity_aliases IS
    'All known identifiers for one canonical record. Unique per logical source + method + key.';
COMMENT ON COLUMN comms_record_identity_aliases.record_key IS
    'RFC aliases come from communication_rfc_ids at ingest time, not by duplicating that table.';
