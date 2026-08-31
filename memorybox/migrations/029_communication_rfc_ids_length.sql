-- Drop btree-illegal RFC tokens if 028 applied before the length gate.
-- Idempotent. Safe when the table is empty or already constrained.

DELETE FROM communication_rfc_ids
WHERE char_length(rfc_id) > 512
   OR char_length(rfc_id) < 3
   OR position('@' IN rfc_id) = 0;

DO $$
BEGIN
    ALTER TABLE communication_rfc_ids
        ADD CONSTRAINT communication_rfc_ids_rfc_id_len
        CHECK (char_length(rfc_id) BETWEEN 3 AND 512);
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
    WHEN undefined_table THEN
        NULL;
END $$;
