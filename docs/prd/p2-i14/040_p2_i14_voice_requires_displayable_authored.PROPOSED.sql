-- PROPOSED P2-I14 migration 040. Do not copy into memorybox/migrations
-- and do not apply on FlightSim until founder authorizes a v3 load.
-- Adds one stored prepared-text disposition. Replaces
-- comms_prepared_assert_generation_ready so activation checks that column
-- rather than re-implementing the Python classifier as SQL regexes.
-- Does not UPDATE v1/v2 rows. Does not activate or publish.
-- Existing voice rows stay valid because this does not add a table CHECK
-- tying voice_corpus to disposition (v1/v2 have no stored disposition).

ALTER TABLE comms_prepared_messages
    ADD COLUMN IF NOT EXISTS prepared_text_disposition TEXT NOT NULL DEFAULT 'uncertain';

ALTER TABLE comms_prepared_messages
    DROP CONSTRAINT IF EXISTS comms_prepared_messages_prepared_text_disposition_ck;

ALTER TABLE comms_prepared_messages
    ADD CONSTRAINT comms_prepared_messages_prepared_text_disposition_ck
    CHECK (prepared_text_disposition IN (
        'authored_displayable',
        'non_substantive',
        'prepared_text_unavailable',
        'attachment_only',
        'correctly_empty',
        'uncertain'
    ));

COMMENT ON COLUMN comms_prepared_messages.prepared_text_disposition IS
    'Loader-assigned mutually exclusive prepared-text disposition. Gallery and voice consume this value. Activation requires voice_corpus only when authored_displayable.';

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
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.voice_corpus
          AND m.quote_quality IS DISTINCT FROM 'clean'
    ) THEN
        RAISE EXCEPTION 'voice_requires_clean_quote_quality';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.voice_corpus
          AND length(btrim(COALESCE(m.cleaned_authored_text, ''))) = 0
    ) THEN
        RAISE EXCEPTION 'voice_requires_nonblank_prepared_text';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.voice_corpus
          AND m.prepared_text_disposition IS DISTINCT FROM 'authored_displayable'
    ) THEN
        RAISE EXCEPTION 'voice_requires_authored_displayable_disposition';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.voice_corpus
          AND m.prepared_text_disposition IN (
                'non_substantive',
                'prepared_text_unavailable',
                'attachment_only',
                'correctly_empty',
                'uncertain'
          )
    ) THEN
        RAISE EXCEPTION 'voice_forbidden_on_non_authored_disposition';
    END IF;
END;
$$;
