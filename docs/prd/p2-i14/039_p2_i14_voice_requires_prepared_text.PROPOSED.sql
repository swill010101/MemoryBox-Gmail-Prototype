-- PROPOSED activation-function migration. Do not apply on FlightSim until
-- separately authorized. Do not copy into memorybox/migrations/ yet.
--
-- Identity: replaces comms_prepared_assert_generation_ready in place.
-- This is a function-only change. It does not ALTER comms_prepared_messages,
-- does not add a table CHECK, and does not UPDATE existing rows. The currently
-- active generation is therefore not rewritten.
--
-- Activation invariant: a candidate generation cannot become active while any
-- row has voice_corpus AND blank/whitespace cleaned_authored_text
-- (voice_requires_nonblank_prepared_text).
--
-- Failure mode: CREATE OR REPLACE FUNCTION is transactional with the session
-- that applies it. Activation still uses the existing
-- comms_prepared_activate_generation path, which only flips
-- comms_prepared_active_generations after assert succeeds. If assert raises,
-- the active generation pointer is unchanged.
--
-- Ledger remains 001–038 until this file is authorized as 039.

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
          AND length(btrim(COALESCE(m.cleaned_authored_text, ''))) = 0
    ) THEN
        RAISE EXCEPTION 'voice_requires_nonblank_prepared_text';
    END IF;
END;
$$;
