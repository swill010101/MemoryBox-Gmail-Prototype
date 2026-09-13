-- P2-I14 Phase B migration 036: prepared household-email generations, threads,
-- messages, participants, and attachment metadata. Additive derived store only.
--
-- Do not apply on Desktop or FlightSim until founder apply authorization.
-- Do not INSERT production or family rows. New generations start unpublished
-- and inactive. Do not CREATE or alter evidence, 035 tables,
-- person_contact_points, or communication_rfc_ids. Do not replay 025-029.
-- Do not modify 035 SQL bytes.
--
-- Production grain: one prepared corpus per household_email logical source.
-- Peggy/Sue were validation pilots only. There is no Person-scoped generation.
-- Messages are stored once. People retrieve them through participants.
-- canonical_record_id is 035 communication identity, not Person identity.
-- person_id is optional known-participant linkage. Unknown addresses stay.
--
-- Calendar prepared grain and SMS episodes are out of this file.
--
-- Publication is generation-atomic. Child rows have no published flag.
-- Gallery consumers must use comms_prepared_active_generations (is_active).
-- Direct published/is_active writes are rejected unless
-- comms_prepared_activate_generation() is running.
-- Activation validates first; failure does not supersede a prior generation.
--
-- Rollback (derived objects only; never drop 001-035 or evidence):
--   1. VIEW comms_prepared_active_generations
--   2. FUNCTION comms_prepared_activate_generation
--   3. FUNCTION comms_prepared_assert_generation_ready
--   4. TRIGGER/FUNCTION comms_prepared_guard_activation
--   5. TRIGGER/FUNCTION comms_prepared_generation_scope_guard
--   6. TRIGGER/FUNCTION comms_prepared_message_generation_guard
--   7. TRIGGER/FUNCTION comms_prepared_participant_normalize
--   8. TRIGGER/FUNCTION comms_prepared_attachment_parent_guard
--   9. comms_prepared_attachments
--  10. comms_prepared_participants
--  11. comms_prepared_messages
--  12. comms_prepared_threads
--  13. comms_prepared_generations

CREATE TABLE IF NOT EXISTS comms_prepared_generations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    algo_version        TEXT NOT NULL
        CHECK (char_length(btrim(algo_version)) BETWEEN 1 AND 80),
    logical_source_id   UUID
        REFERENCES comms_logical_sources (id) ON DELETE RESTRICT,
    scope_key           TEXT NOT NULL DEFAULT 'household_email'
        CHECK (scope_key = 'household_email'),
    source_kind         TEXT NOT NULL DEFAULT 'email'
        CHECK (source_kind IN ('email')),
    published           BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
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
        (
            status = 'published'
            AND published
            AND is_active
            AND logical_source_id IS NOT NULL
            AND checksum IS NOT NULL
            AND scope_key = 'household_email'
        )
        OR (
            status <> 'published'
            AND NOT published
            AND NOT is_active
        )
    ),
    CHECK (status <> 'failed' OR (NOT published AND NOT is_active))
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_generations_logical
    ON comms_prepared_generations (logical_source_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_comms_prepared_one_active
    ON comms_prepared_generations (logical_source_id)
    WHERE is_active;

COMMENT ON TABLE comms_prepared_generations IS
    'Source-wide household email prepared build. Not a Person corpus. No person_id.';
COMMENT ON COLUMN comms_prepared_generations.scope_key IS
    'Stream grain inside a logical source. Locked to household_email so a Person name or UUID cannot open a second prepared corpus.';
COMMENT ON COLUMN comms_prepared_generations.is_active IS
    'Exactly one active generation per household_email logical source. Unpublished rows cannot be active.';
COMMENT ON COLUMN comms_prepared_generations.published IS
    'True only for the atomically activated generation. Child rows are not published separately.';

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
    suppression_reason      TEXT NOT NULL DEFAULT ''
        CHECK (suppression_reason IN (
            '',
            'commercial_suppress_default',
            'identity_uncertain',
            'quote_contamination',
            'founder_hold'
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
    provenance              JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings                JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (generation_id, display_id),
    UNIQUE (generation_id, thread_key),
    CHECK (
        gallery_eligibility <> 'suppress_default'
        OR suppression_reason <> ''
    )
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_threads_generation
    ON comms_prepared_threads (generation_id, earliest_at);

COMMENT ON TABLE comms_prepared_threads IS
    'Canonical household-email thread. People attach through participants, not duplicated messages.';
COMMENT ON COLUMN comms_prepared_threads.gallery_eligibility IS
    'Default Person-Ask retrieval only, via trusted participant person_id links. Never deletes evidence.';
COMMENT ON COLUMN comms_prepared_threads.provenance IS
    'Structured reconstruction provenance. Not message bodies.';

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
    canonical_record_id     UUID
        REFERENCES comms_record_identities (id) ON DELETE RESTRICT,
    evidence_ref            TEXT NOT NULL
        CHECK (evidence_ref ~ '^T-[0-9]{4}-M-[0-9]{2}$'),
    sent_at                 TIMESTAMPTZ NOT NULL,
    subject                 TEXT NOT NULL DEFAULT '',
    cleaned_authored_text   TEXT NOT NULL DEFAULT '',
    forward_block           TEXT NOT NULL DEFAULT '',
    forward_status          TEXT NOT NULL DEFAULT 'none'
        CHECK (forward_status IN (
            'none', 'new_forward', 'relay', 'omitted_duplicate'
        )),
    forward_omitted         TEXT NOT NULL DEFAULT ''
        CHECK (forward_omitted IN (
            '',
            'duplicate_of_thread_message',
            'commercial_body_omitted',
            'relay_history_omitted'
        )),
    urls_stripped           BOOLEAN NOT NULL DEFAULT FALSE,
    quote_quality           TEXT NOT NULL DEFAULT 'clean'
        CHECK (quote_quality IN (
            'clean', 'suspected_contamination', 'unresolved_contamination'
        )),
    identity_quality        TEXT NOT NULL DEFAULT 'resolved'
        CHECK (identity_quality IN ('resolved', 'unverified', 'uncertain')),
    quote_contamination_flagged BOOLEAN GENERATED ALWAYS AS (
        quote_quality <> 'clean'
    ) STORED,
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
            'retain_life_evidence',
            'suppress_default',
            'uncertain'
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
    UNIQUE (generation_id, evidence_id),
    CHECK (
        (forward_status = 'omitted_duplicate' AND forward_omitted <> '' AND forward_block = '')
        OR (forward_status = 'relay' AND forward_omitted = 'relay_history_omitted' AND forward_block = '')
        OR (forward_status = 'new_forward' AND forward_omitted = '')
        OR (forward_status = 'none' AND forward_omitted = '' AND forward_block = '')
    ),
    CHECK (
        NOT voice_corpus
        OR (
            quote_quality = 'clean'
            AND identity_quality = 'resolved'
            AND authorship = 'authenticated_focal'
        )
    ),
    CHECK (
        cleaned_authored_text !~* 'https?://'
        AND forward_block !~* 'https?://'
    )
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_messages_thread
    ON comms_prepared_messages (thread_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_comms_prepared_messages_sent
    ON comms_prepared_messages (generation_id, sent_at, evidence_id);
CREATE INDEX IF NOT EXISTS idx_comms_prepared_messages_canonical
    ON comms_prepared_messages (canonical_record_id);

COMMENT ON TABLE comms_prepared_messages IS
    'One communication once per household-email generation. Not stored per Person.';
COMMENT ON COLUMN comms_prepared_messages.sent_at IS
    'Authoritative payload sent_at as timestamptz after UTC-instant normalization. Tie-break is evidence_id.';
COMMENT ON COLUMN comms_prepared_messages.canonical_record_id IS
    '035 communication identity. Nullable while building. Required on every message before activation. Not a Person id.';
COMMENT ON COLUMN comms_prepared_messages.quote_contamination_flagged IS
    'Distinguishable remaining quote risk. Never voice-eligible.';
COMMENT ON COLUMN comms_prepared_messages.cleaned_authored_text IS
    'New contribution only. Tracking, login, unsubscribe, and marketing URLs are not stored.';

CREATE TABLE IF NOT EXISTS comms_prepared_participants (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id              UUID NOT NULL
        REFERENCES comms_prepared_messages (id) ON DELETE CASCADE,
    role                    TEXT NOT NULL
        CHECK (role IN ('from', 'to', 'cc')),
    display_name            TEXT NOT NULL DEFAULT '',
    address_normalized      TEXT NOT NULL DEFAULT '',
    identity_confidence     TEXT NOT NULL
        CHECK (identity_confidence IN (
            'authenticated_focal',
            'authenticated_other',
            'unverified'
        )),
    person_id               UUID
        REFERENCES people (id) ON DELETE RESTRICT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (
            identity_confidence = 'unverified'
            AND person_id IS NULL
        )
        OR (
            identity_confidence <> 'unverified'
            AND person_id IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_comms_prepared_one_from
    ON comms_prepared_participants (message_id)
    WHERE role = 'from';

CREATE UNIQUE INDEX IF NOT EXISTS uq_comms_prepared_participant_addr
    ON comms_prepared_participants (
        message_id,
        role,
        lower(btrim(address_normalized))
    );

CREATE INDEX IF NOT EXISTS idx_comms_prepared_participants_message
    ON comms_prepared_participants (message_id);
CREATE INDEX IF NOT EXISTS idx_comms_prepared_participants_person
    ON comms_prepared_participants (person_id)
    WHERE person_id IS NOT NULL;

COMMENT ON TABLE comms_prepared_participants IS
    'From/To/Cc for one prepared message. Unknown addresses keep person_id NULL. Several People share one message.';
COMMENT ON COLUMN comms_prepared_participants.person_id IS
    'Optional known MemoryBox Person. Not required to prepare or publish. Ask/Gallery Person retrieval uses trusted links only.';

CREATE TABLE IF NOT EXISTS comms_prepared_attachments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id              UUID NOT NULL
        REFERENCES comms_prepared_messages (id) ON DELETE CASCADE,
    parent_evidence_id      UUID NOT NULL
        REFERENCES evidence (id) ON DELETE RESTRICT,
    attachment_evidence_id  UUID
        REFERENCES evidence (id) ON DELETE RESTRICT,
    attachment_ordinal      INTEGER NOT NULL
        CHECK (attachment_ordinal >= 1),
    filename                TEXT NOT NULL DEFAULT '',
    mime_type               TEXT NOT NULL DEFAULT '',
    disposition             TEXT NOT NULL DEFAULT 'attachment'
        CHECK (disposition IN ('inline', 'attachment', 'unknown')),
    byte_size               BIGINT
        CHECK (byte_size IS NULL OR byte_size >= 0),
    source_locator          TEXT NOT NULL DEFAULT '',
    gallery_action          TEXT NOT NULL
        CHECK (gallery_action IN (
            'view_image', 'open_pdf', 'open_document', 'record_only'
        )),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (message_id, attachment_ordinal),
    CHECK (
        attachment_evidence_id IS NULL
        OR attachment_evidence_id IS DISTINCT FROM parent_evidence_id
    )
);

CREATE INDEX IF NOT EXISTS idx_comms_prepared_attachments_message
    ON comms_prepared_attachments (message_id);

COMMENT ON TABLE comms_prepared_attachments IS
    'Attachment metadata. parent_evidence_id is the message original. attachment_evidence_id is set only when a distinct attachment evidence row exists.';
COMMENT ON COLUMN comms_prepared_attachments.parent_evidence_id IS
    'Immutable parent communication evidence. Required. Does not claim the attachment is its own evidence row.';
COMMENT ON COLUMN comms_prepared_attachments.attachment_evidence_id IS
    'Optional distinct evidence row for the bytes. Null when the archive is reached only via source_locator.';
COMMENT ON COLUMN comms_prepared_attachments.source_locator IS
    'Pointer into the archive. The archive remains authoritative.';
COMMENT ON COLUMN comms_prepared_attachments.gallery_action IS
    'record_only keeps unsupported or unsafe attachments visible as records.';

CREATE OR REPLACE VIEW comms_prepared_active_generations AS
SELECT *
FROM comms_prepared_generations
WHERE is_active
  AND published
  AND status = 'published'
  AND scope_key = 'household_email';

COMMENT ON VIEW comms_prepared_active_generations IS
    'The only generation Gallery may treat as current household email. Empty while unpublished.';

CREATE OR REPLACE FUNCTION comms_prepared_guard_activation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.published OR NEW.is_active OR NEW.status = 'published' THEN
        IF current_setting('memorybox.comms_prepared_activate', true) IS DISTINCT FROM '1' THEN
            RAISE EXCEPTION 'row_by_row_publication_forbidden';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_comms_prepared_guard_activation
    BEFORE INSERT OR UPDATE ON comms_prepared_generations
    FOR EACH ROW
    EXECUTE PROCEDURE comms_prepared_guard_activation();

CREATE OR REPLACE FUNCTION comms_prepared_generation_scope_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    src_kind TEXT;
    src_key TEXT;
BEGIN
    IF NEW.scope_key IS DISTINCT FROM 'household_email' THEN
        RAISE EXCEPTION 'prepared_scope_must_be_household_email';
    END IF;
    IF NEW.logical_source_id IS NOT NULL THEN
        SELECT source_kind, logical_key
          INTO src_kind, src_key
          FROM comms_logical_sources
         WHERE id = NEW.logical_source_id;
        IF src_kind IS DISTINCT FROM 'email'
           OR src_key IS DISTINCT FROM 'household_email' THEN
            RAISE EXCEPTION 'prepared_generation_must_use_household_email_source';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_comms_prepared_generation_scope_guard
    BEFORE INSERT OR UPDATE ON comms_prepared_generations
    FOR EACH ROW
    EXECUTE PROCEDURE comms_prepared_generation_scope_guard();

CREATE OR REPLACE FUNCTION comms_prepared_message_generation_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    thread_gen UUID;
BEGIN
    SELECT generation_id INTO thread_gen
    FROM comms_prepared_threads
    WHERE id = NEW.thread_id;
    IF thread_gen IS NULL OR thread_gen IS DISTINCT FROM NEW.generation_id THEN
        RAISE EXCEPTION 'thread_generation_mismatch';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_comms_prepared_message_generation_guard
    BEFORE INSERT OR UPDATE ON comms_prepared_messages
    FOR EACH ROW
    EXECUTE PROCEDURE comms_prepared_message_generation_guard();

CREATE OR REPLACE FUNCTION comms_prepared_participant_normalize()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.address_normalized := lower(btrim(NEW.address_normalized));
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_comms_prepared_participant_normalize
    BEFORE INSERT OR UPDATE ON comms_prepared_participants
    FOR EACH ROW
    EXECUTE PROCEDURE comms_prepared_participant_normalize();

CREATE OR REPLACE FUNCTION comms_prepared_attachment_parent_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    msg_evidence UUID;
BEGIN
    SELECT evidence_id INTO msg_evidence
    FROM comms_prepared_messages
    WHERE id = NEW.message_id;
    IF msg_evidence IS NULL OR msg_evidence IS DISTINCT FROM NEW.parent_evidence_id THEN
        RAISE EXCEPTION 'attachment_parent_must_match_message_evidence';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_comms_prepared_attachment_parent_guard
    BEFORE INSERT OR UPDATE ON comms_prepared_attachments
    FOR EACH ROW
    EXECUTE PROCEDURE comms_prepared_attachment_parent_guard();

CREATE OR REPLACE FUNCTION comms_prepared_assert_generation_ready(p_id UUID)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.canonical_record_id IS NULL
    ) THEN
        RAISE EXCEPTION 'canonical_record_required_for_activation';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        JOIN comms_prepared_generations g ON g.id = m.generation_id
        LEFT JOIN comms_record_identities c ON c.id = m.canonical_record_id
        WHERE m.generation_id = p_id
          AND (
                c.id IS NULL
                OR c.evidence_id IS DISTINCT FROM m.evidence_id
                OR c.logical_source_id IS DISTINCT FROM g.logical_source_id
                OR c.source_kind IS DISTINCT FROM 'email'
          )
    ) THEN
        RAISE EXCEPTION 'canonical_record_must_match_evidence_and_source';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND NOT EXISTS (
              SELECT 1
              FROM comms_prepared_participants p
              WHERE p.message_id = m.id
                AND p.role = 'from'
          )
    ) THEN
        RAISE EXCEPTION 'exactly_one_from_required_for_activation';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.voice_corpus
          AND NOT EXISTS (
              SELECT 1
              FROM comms_prepared_participants p
              WHERE p.message_id = m.id
                AND p.role = 'from'
                AND p.identity_confidence = 'authenticated_focal'
                AND p.person_id IS NOT NULL
          )
    ) THEN
        RAISE EXCEPTION 'voice_requires_authenticated_from_person';
    END IF;
END;
$$;

COMMENT ON FUNCTION comms_prepared_assert_generation_ready(UUID) IS
    'Activation-time communication-identity and From/voice checks. Does not require person_id on every participant.';

CREATE OR REPLACE FUNCTION comms_prepared_activate_generation(p_id UUID)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    rec comms_prepared_generations%ROWTYPE;
    src_kind TEXT;
    src_key TEXT;
BEGIN
    SELECT * INTO rec
    FROM comms_prepared_generations
    WHERE id = p_id
    FOR UPDATE;
    IF rec.id IS NULL THEN
        RAISE EXCEPTION 'generation_not_found';
    END IF;
    IF rec.status <> 'validated' THEN
        RAISE EXCEPTION 'generation_not_validated';
    END IF;
    IF rec.logical_source_id IS NULL THEN
        RAISE EXCEPTION 'logical_source_required';
    END IF;
    IF rec.checksum IS NULL THEN
        RAISE EXCEPTION 'checksum_required';
    END IF;
    IF rec.scope_key IS DISTINCT FROM 'household_email' THEN
        RAISE EXCEPTION 'prepared_scope_must_be_household_email';
    END IF;
    SELECT source_kind, logical_key
      INTO src_kind, src_key
      FROM comms_logical_sources
     WHERE id = rec.logical_source_id
     FOR UPDATE;
    IF src_kind IS DISTINCT FROM 'email'
       OR src_key IS DISTINCT FROM 'household_email' THEN
        RAISE EXCEPTION 'prepared_generation_must_use_household_email_source';
    END IF;
    PERFORM comms_prepared_assert_generation_ready(p_id);
    PERFORM set_config('memorybox.comms_prepared_activate', '1', true);
    UPDATE comms_prepared_generations
    SET is_active = FALSE,
        published = FALSE,
        status = CASE WHEN is_active THEN 'superseded' ELSE status END,
        updated_at = now()
    WHERE logical_source_id = rec.logical_source_id
      AND id <> p_id
      AND is_active;
    UPDATE comms_prepared_generations
    SET is_active = TRUE,
        published = TRUE,
        status = 'published',
        updated_at = now()
    WHERE id = p_id;
END;
$$;

COMMENT ON FUNCTION comms_prepared_activate_generation(UUID) IS
    'Validate communication identity and participants, then atomically replace the active household_email generation. Prior active generation is unchanged if validation fails.';
