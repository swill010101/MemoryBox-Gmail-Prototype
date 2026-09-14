-- P2-I14 Phase B migration 037: scale prepared evidence_ref / display_id CHECKs.
-- Additive. Does not INSERT rows. Does not alter evidence or 035/036 table shapes
-- except CHECK predicates on empty prepared identifier columns.
--
-- 036 locked T-NNNN and M-NN (max 99 messages / thread, max 9999 threads).
-- Existing values such as T-0001 and T-0001-M-01 remain valid. Wider ordinals
-- use M-100 (not M-0100) and T-10000 when needed. Meaning of T/M tokens is
-- unchanged: thread sequence then chronological message ordinal.
--
-- Do not modify 035 or 036 SQL bytes. Apply on FlightSim only when a later
-- production-load authorization includes schema apply; empty tables make this
-- CHECK-only change safe.

DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT DISTINCT c.conname, c.conrelid
      FROM pg_constraint c
      JOIN pg_attribute a
        ON a.attrelid = c.conrelid
       AND a.attnum = ANY (c.conkey)
     WHERE c.contype = 'c'
       AND pg_get_constraintdef(c.oid) LIKE '%T-[0-9]%'
       AND a.attname IN ('display_id', 'evidence_ref')
       AND c.conrelid IN (
             'comms_prepared_threads'::regclass,
             'comms_prepared_messages'::regclass
           )
  LOOP
    EXECUTE format(
      'ALTER TABLE %s DROP CONSTRAINT %I',
      r.conrelid::regclass,
      r.conname
    );
  END LOOP;

  ALTER TABLE comms_prepared_threads
    ADD CONSTRAINT comms_prepared_threads_display_id_scale_check
    CHECK (display_id ~ '^T-[0-9]{4,}$');

  ALTER TABLE comms_prepared_messages
    ADD CONSTRAINT comms_prepared_messages_evidence_ref_scale_check
    CHECK (evidence_ref ~ '^T-[0-9]{4,}-M-[0-9]{2,}$');
END $$;
