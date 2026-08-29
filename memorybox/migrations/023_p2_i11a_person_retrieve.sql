-- Person-scoped communication retrieve: identity GIN, not body ILIKE paging.
CREATE INDEX IF NOT EXISTS evidence_comm_person_ids_gin
    ON evidence USING GIN ((payload_json->'person_ids'))
    WHERE evidence_kind = 'communication';

CREATE INDEX IF NOT EXISTS evidence_comm_from_lower
    ON evidence ((lower(coalesce(payload_json->>'from', ''))))
    WHERE evidence_kind = 'communication';

CREATE INDEX IF NOT EXISTS evidence_comm_sender_name_lower
    ON evidence ((lower(coalesce(payload_json->>'sender_name', ''))))
    WHERE evidence_kind = 'communication';
