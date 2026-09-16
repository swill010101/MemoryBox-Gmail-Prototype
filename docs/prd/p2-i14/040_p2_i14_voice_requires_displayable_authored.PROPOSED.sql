-- PROPOSED P2-I14 migration 040. Do not copy into memorybox/migrations
-- and do not apply on FlightSim until founder authorizes.
-- Function-only replacement of comms_prepared_assert_generation_ready.
-- Does not ALTER tables, UPDATE rows, or add a CHECK.
-- Stronger than 039: voice requires displayable authored prepared text,
-- not merely non-whitespace. Signoffs, debris, device output, and
-- confirmed fragments cannot activate as voice even when nonblank.

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
    IF EXISTS (
        SELECT 1
        FROM comms_prepared_messages m
        WHERE m.generation_id = p_id
          AND m.voice_corpus
          AND (
                btrim(COALESCE(m.cleaned_authored_text, '')) ~ '^[_[:space:]—\-]+$'
             OR btrim(COALESCE(m.cleaned_authored_text, '')) ~ '^[A-Za-z][A-Za-z''.\-]{0,40},$'
             OR btrim(COALESCE(m.cleaned_authored_text, '')) ~* '^\+?\s*Link\s*-?\s*$'
             OR COALESCE(m.cleaned_authored_text, '') ~* '\[([0-9a-f]{2}:){5}[0-9a-f]{2}\]'
             OR COALESCE(m.cleaned_authored_text, '') ~* '\yKM-[0-9]{3,6}\y'
             OR btrim(COALESCE(m.cleaned_authored_text, '')) = E'\uFEFF'
             OR btrim(COALESCE(m.cleaned_authored_text, '')) ~* '^A[[:space:]]+a[[:space:]]+ml'
          )
    ) THEN
        RAISE EXCEPTION 'voice_requires_displayable_authored_prepared_text';
    END IF;
END;
$$;
