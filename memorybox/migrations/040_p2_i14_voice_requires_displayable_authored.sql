-- P2-I14 migration 040: nullable prepared_text_disposition and algo_version
-- branching for comms_prepared_assert_generation_ready.
-- Does not UPDATE v1/v2 rows. Does not activate or publish.
-- Pre-v3 rows stay NULL (not 'uncertain'). Optional token 'legacy' is allowed
-- if a later authorized backfill marks them without inventing a six-way class.
-- v3 loads must write one of the six values on every row.
--
-- Assert branches on generations.algo_version:
--   i14-prepared-email-v1 → 036/038 historical (no blank-text, no disposition)
--   i14-prepared-email-v2 → 039 (blank voice forbidden, no disposition)
--   i14-prepared-email-v3 → six-way disposition required; voice only when
--                           authored_displayable + nonblank + clean quote +
--                           authenticated From. v3 is not weakened.
-- Do not apply unless pending is exactly this file.

ALTER TABLE comms_prepared_messages
    ADD COLUMN IF NOT EXISTS prepared_text_disposition TEXT;

ALTER TABLE comms_prepared_messages
    DROP CONSTRAINT IF EXISTS comms_prepared_messages_prepared_text_disposition_ck;

ALTER TABLE comms_prepared_messages
    ADD CONSTRAINT comms_prepared_messages_prepared_text_disposition_ck
    CHECK (
        prepared_text_disposition IS NULL
        OR prepared_text_disposition IN (
            'legacy',
            'authored_displayable',
            'non_substantive',
            'prepared_text_unavailable',
            'attachment_only',
            'correctly_empty',
            'uncertain'
        )
    );

COMMENT ON COLUMN comms_prepared_messages.prepared_text_disposition IS
    'Loader-assigned prepared-text disposition. NULL/legacy = pre-v3. v3 requires one of the six values. Voice on v3 requires authored_displayable.';

CREATE OR REPLACE FUNCTION comms_prepared_assert_generation_ready(p_id UUID)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    algo TEXT;
BEGIN
    SELECT g.algo_version INTO algo
      FROM comms_prepared_generations g
     WHERE g.id = p_id;
    IF algo IS NULL THEN
        RAISE EXCEPTION 'generation_not_found';
    END IF;

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

    IF algo = 'i14-prepared-email-v1' THEN
        RETURN;
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

    IF algo = 'i14-prepared-email-v2' THEN
        RETURN;
    END IF;

    IF algo IS DISTINCT FROM 'i14-prepared-email-v3' THEN
        RAISE EXCEPTION 'unsupported_prepared_algo_version';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND (
                m.prepared_text_disposition IS NULL
             OR m.prepared_text_disposition = 'legacy'
             OR m.prepared_text_disposition NOT IN (
                    'authored_displayable',
                    'non_substantive',
                    'prepared_text_unavailable',
                    'attachment_only',
                    'correctly_empty',
                    'uncertain'
                )
          )
    ) THEN
        RAISE EXCEPTION 'v3_requires_prepared_text_disposition';
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
          AND m.prepared_text_disposition IS DISTINCT FROM 'authored_displayable'
    ) THEN
        RAISE EXCEPTION 'voice_requires_authored_displayable_disposition';
    END IF;
END;
$$;
