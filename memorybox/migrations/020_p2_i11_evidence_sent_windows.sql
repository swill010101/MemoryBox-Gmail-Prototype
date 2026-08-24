-- I11 tell retrieve: date-window SMS/email/calendar without a full-export scan.
CREATE INDEX IF NOT EXISTS evidence_comm_channel_sent_day
    ON evidence (
        (lower(coalesce(payload_json->>'evidence_channel', ''))),
        (left(coalesce(payload_json->>'sent_at', ''), 10))
    )
    WHERE evidence_kind = 'communication';

CREATE INDEX IF NOT EXISTS evidence_calendar_start_day
    ON evidence ((left(coalesce(payload_json->>'start', ''), 10)))
    WHERE evidence_kind = 'calendar_event';
