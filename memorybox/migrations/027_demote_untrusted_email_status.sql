-- 026 stamped retrieval_trust but left status=confirmed on auto-expand rows.
-- FlightSim still has ~700 confirmed emails on Peggy. Demote status/ledger.
-- Keep the rows. Trusted People-card / attest contacts stay confirmed.

UPDATE person_contact_points
SET status = 'candidate',
    updated_at = now()
WHERE contact_kind = 'email'
  AND retrieval_trust = 'untrusted'
  AND status = 'confirmed';

UPDATE communication_identities AS ci
SET resolution_status = 'observed',
    updated_at = now()
WHERE identity_kind = 'email'
  AND resolution_status = 'confirmed'
  AND NOT EXISTS (
        SELECT 1
        FROM person_contact_points AS p
        WHERE p.contact_kind = 'email'
          AND p.retrieval_trust = 'trusted'
          AND p.status IN ('confirmed', 'candidate', 'observed')
          AND lower(p.value_text) = ci.address_normalized
    );
