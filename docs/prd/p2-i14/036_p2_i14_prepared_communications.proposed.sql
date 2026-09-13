-- P2-I14 Phase B candidate 036: prepared email generations, threads, messages,
-- participants, and attachment metadata. Additive derived store only.
--
-- THIS FILE IS NOT A MIGRATION. Do not copy into memorybox/migrations/ and
-- do not apply on Desktop or FlightSim until founder promotion + apply
-- authorization. 035 lineage tables must already exist.
--
-- Do not INSERT production or family rows here. published defaults false.
-- Do not CREATE or alter evidence, person_contact_points, or
-- communication_rfc_ids. Do not replay 025-029.
--
-- Calendar prepared grain and SMS episodes are out of this file.
--
-- Rollback (derived objects only; never drop 001-035 or evidence):
--   1. comms_prepared_attachments
--   2. comms_prepared_participants
--   3. comms_prepared_messages
--   4. comms_prepared_threads
--   5. comms_prepared_generations

CREATE TABLE IF NOT EXISTS comms_prepared_generations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    algo_version        TEXT NOT NULL
        CHECK (char_length(btrim(algo_version)) BETWEEN 1 AND 80),
    logical_source_id   UUID
        REFERENCES comms_logical_sources (id) ON DELETE RESTRICT,
    source_kind         TEXT NOT NULL
        CHECK (source_kind IN ('email')),
    published           BOOLEAN NOT NULL DEFAULT FALSE,
    status              TEXT NOT NULL DEFAULT 'building'
        CHECK (status IN (
            'building', 'validated', 'published', 'superseded', 'failed'
        )),
    item_count          INTEGER NOT NULL DEFAULT 0
        CHECK (item_count >= 0),
    checksum            TEXT
        CHECK (checksum IS NULL OR checksum ~ '^[a-f0-9]{64}$'),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (published = FALSE AND status <> 'published')
        OR (published = TRUE AND status = 'published')
    )
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_generations_logical
    ON comms_prepared_generations (logical_source_id, created_at DESC);

COMMENT ON TABLE comms_prepared_generations IS
    'One prepared-email build. published stays false until a separate load/publication authorization.';
COMMENT ON COLUMN comms_prepared_generations.logical_source_id IS
    'Nullable until comms_logical_sources is seeded. 035 membership, not an extract filename.';
COMMENT ON COLUMN comms_prepared_generations.published IS
    'Gallery may consume only published generations. Default false.';

CREATE TABLE IF NOT EXISTS comms_prepared_threads (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id           UUID NOT NULL
        REFERENCES comms_prepared_generations (id) ON DELETE CASCADE,
    thread_key              TEXT NOT NULL
        CHECK (char_length(btrim(thread_key)) BETWEEN 1 AND 700),
    display_id              TEXT NOT NULL
        CHECK (display_id ~ '^T-[0-9]{4}$'),
    earliest_at             TIMESTAMPTZ,
    latest_at               TIMESTAMPTZ,
    message_count           INTEGER NOT NULL DEFAULT 0
        CHECK (message_count >= 0),
    evidence_count          INTEGER NOT NULL DEFAULT 0
        CHECK (evidence_count >= 0),
    duplicate_omitted_count INTEGER NOT NULL DEFAULT 0
        CHECK (duplicate_omitted_count >= 0),
    threading_confidence    TEXT NOT NULL
        CHECK (threading_confidence IN (
            'vendor+rfc', 'rfc', 'vendor', 'mixed_unthreaded', 'unknown'
        )),
    identity_confidence     TEXT NOT NULL
        CHECK (identity_confidence IN (
            'all_authenticated', 'unverified_present', 'mixed'
        )),
    gallery_eligibility     TEXT NOT NULL
        CHECK (gallery_eligibility IN (
            'show_by_default', 'suppress_default', 'hold_uncertain'
        )),
    founder_review_state    TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK (founder_review_state IN (
            'unreviewed',
            'accept_thread',
            'split_here',
            'merge_with_another',
            'incorrect_participant',
            'incorrect_ordering',
            'quoted_text_removed_incorrectly',
            'missing_message',
            'needs_investigation'
        )),
    warnings                JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (generation_id, display_id),
    UNIQUE (generation_id, thread_key)
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_threads_generation
    ON comms_prepared_threads (generation_id, earliest_at);

COMMENT ON TABLE comms_prepared_threads IS
    'Canonical email thread for one prepared generation. Display ids are assigned after UTC sort at load time.';
COMMENT ON COLUMN comms_prepared_threads.gallery_eligibility IS
    'Default Gallery retrieval only. Never deletes immutable evidence.';

CREATE TABLE IF NOT EXISTS comms_prepared_messages (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id               UUID NOT NULL
        REFERENCES comms_prepared_threads (id) ON DELETE CASCADE,
    generation_id           UUID NOT NULL
        REFERENCES comms_prepared_generations (id) ON DELETE CASCADE,
    ordinal                 INTEGER NOT NULL
        CHECK (ordinal >= 1),
    evidence_id             UUID NOT NULL
        REFERENCES evidence (id) ON DELETE RESTRICT,
    evidence_ref            TEXT NOT NULL
        CHECK (evidence_ref ~ '^T-[0-9]{4}-M-[0-9]{2}$'),
    sent_at                 TIMESTAMPTZ NOT NULL,
    subject                 TEXT NOT NULL DEFAULT '',
    cleaned_authored_text   TEXT NOT NULL DEFAULT '',
    forward_block           TEXT NOT NULL DEFAULT '',
    forward_omitted         TEXT NOT NULL DEFAULT ''
        CHECK (forward_omitted IN (
            '',
            'duplicate_of_thread_message',
            'commercial_body_omitted'
        )),
    urls_stripped           BOOLEAN NOT NULL DEFAULT FALSE,
    authorship              TEXT NOT NULL
        CHECK (authorship IN (
            'authenticated_focal',
            'authenticated_other',
            'unverified'
        )),
    voice_corpus            BOOLEAN NOT NULL DEFAULT FALSE,
    commercial_class        TEXT NOT NULL
        CHECK (commercial_class IN (
            'not_commercial',
            'commercial_retain',
            'commercial_suppress',
            'commercial_uncertain'
        )),
    direction               TEXT NOT NULL
        CHECK (direction IN (
            'sent_by_focal',
            'sent_to_focal_other_author',
            'no_focal',
            'unresolved'
        )),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (thread_id, ordinal),
    UNIQUE (generation_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_messages_thread
    ON comms_prepared_messages (thread_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_comms_prepared_messages_sent
    ON comms_prepared_messages (generation_id, sent_at);

COMMENT ON TABLE comms_prepared_messages IS
    'One canonical evidence message once per generation. cleaned_authored_text is the sender new contribution only.';
COMMENT ON COLUMN comms_prepared_messages.sent_at IS
    'Authoritative payload sent_at as timestamptz. Not a lexicographic ISO string.';
COMMENT ON COLUMN comms_prepared_messages.ordinal IS
    'Display number assigned after sorting by sent_at, then evidence_id.';
COMMENT ON COLUMN comms_prepared_messages.forward_block IS
    'Genuinely new forwarded content not otherwise in this thread. Empty when omitted.';
COMMENT ON COLUMN comms_prepared_messages.cleaned_authored_text IS
    'Must not store tracking, account, unsubscribe, or legal marketing URLs.';

CREATE TABLE IF NOT EXISTS comms_prepared_participants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID NOT NULL
        REFERENCES comms_prepared_messages (id) ON DELETE CASCADE,
    role                TEXT NOT NULL
        CHECK (role IN ('from', 'to', 'cc', 'bcc')),
    display_name        TEXT NOT NULL DEFAULT '',
    address_normalized  TEXT NOT NULL DEFAULT '',
    identity_status     TEXT NOT NULL
        CHECK (identity_status IN (
            'authenticated_focal',
            'authenticated_other',
            'unverified'
        )),
    person_id           UUID
        REFERENCES people (id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_participants_message
    ON comms_prepared_participants (message_id);
CREATE INDEX IF NOT EXISTS idx_comms_prepared_participants_person
    ON comms_prepared_participants (person_id);

COMMENT ON TABLE comms_prepared_participants IS
    'Header roles for a prepared message. person_id is set only when authenticated unique.';

CREATE TABLE IF NOT EXISTS comms_prepared_attachments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID NOT NULL
        REFERENCES comms_prepared_messages (id) ON DELETE CASCADE,
    evidence_id         UUID NOT NULL
        REFERENCES evidence (id) ON DELETE RESTRICT,
    filename            TEXT NOT NULL DEFAULT '',
    mime_type           TEXT NOT NULL DEFAULT '',
    byte_size           BIGINT
        CHECK (byte_size IS NULL OR byte_size >= 0),
    source_locator      TEXT NOT NULL DEFAULT '',
    gallery_action      TEXT NOT NULL
        CHECK (gallery_action IN (
            'view_image', 'open_pdf', 'open_document', 'record_only'
        )),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_attachments_message
    ON comms_prepared_attachments (message_id);

COMMENT ON TABLE comms_prepared_attachments IS
    'Attachment metadata only. Do not copy bytes into this table.';
COMMENT ON COLUMN comms_prepared_attachments.source_locator IS
    'Pointer into the archive. Not file contents.';
