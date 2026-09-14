-- P2-I14 migration 038: household authored voice is authenticated From + clean quote.
-- Unverified To/Cc may leave identity_quality = uncertain; that must not forbid
-- voice_corpus. Unverified From still cannot be voice (authorship gate).
-- Additive CHECK replace only. Does not UPDATE existing prepared rows.
-- Do not apply on FlightSim until a reload is separately authorized.

DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT c.conname
      FROM pg_constraint c
     WHERE c.contype = 'c'
       AND c.conrelid = 'comms_prepared_messages'::regclass
       AND pg_get_constraintdef(c.oid) LIKE '%voice_corpus%'
       AND pg_get_constraintdef(c.oid) LIKE '%identity_quality%'
  LOOP
    EXECUTE format('ALTER TABLE comms_prepared_messages DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;

ALTER TABLE comms_prepared_messages
  ADD CONSTRAINT comms_prepared_messages_voice_corpus_ck
  CHECK (
    NOT voice_corpus
    OR (
      quote_quality = 'clean'
      AND authorship = 'authenticated_focal'
    )
  );
