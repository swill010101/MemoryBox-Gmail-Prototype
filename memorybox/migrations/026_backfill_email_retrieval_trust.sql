-- Stamp retrieval_trust on existing email contacts (FlightSim 700-key dump).
-- Fail closed: unknown provenance → untrusted. Do not delete rows.
-- Matches classify_contact_trust (actor + provenance), not status=confirmed.

ALTER TABLE person_contact_points
    ALTER COLUMN retrieval_trust SET DEFAULT 'untrusted';

UPDATE person_contact_points
SET retrieval_trust = CASE
    WHEN lower(coalesce(provenance_json->>'operator_attested', ''))
            IN ('true', 't', '1')
         OR lower(coalesce(provenance_json->>'owner_confirmed', ''))
            IN ('true', 't', '1')
        THEN 'trusted'
    WHEN coalesce(provenance_json->>'source', '') IN (
            'owner',
            'person_profile',
            'owner_confirmed',
            'owner_correction',
            'comm_identity_operator_attested',
            'operator_attest',
            'canonical_profile'
        )
        THEN 'trusted'
    WHEN actor_key IN ('owner', 'operator', 'owner_confirmed')
         AND coalesce(provenance_json->>'source', '') NOT IN (
            'comm_identity_expand',
            'sms_auto_map',
            'corroborated_header_identity',
            'address_centric',
            'confirmed_cache',
            'comm_address_index_resolve',
            'comm_identity_known_address',
            'ensure_confirmed_email_contact'
         )
        THEN 'trusted'
    ELSE 'untrusted'
END
WHERE contact_kind = 'email';

COMMENT ON COLUMN person_contact_points.retrieval_trust IS
    'trusted = Ask/Gallery retrieve key; default and unknown provenance = untrusted';
