-- Increment 11: Guided Capture campaigns (EF-11)
-- First-class Campaign / Question / Delivery / Response — not email-row flatten.

CREATE TABLE IF NOT EXISTS guided_capture_contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    people_id       UUID REFERENCES people (id) ON DELETE SET NULL,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gc_contacts_email
    ON guided_capture_contacts (lower(email));

CREATE TABLE IF NOT EXISTS guided_capture_campaigns (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_person_id         UUID REFERENCES people (id) ON DELETE SET NULL,
    respondent_contact_id   UUID NOT NULL REFERENCES guided_capture_contacts (id),
    title                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'paused', 'stopped', 'outbound_complete')),
    send_mode               TEXT NOT NULL DEFAULT 'time_driven'
        CHECK (send_mode IN ('time_driven', 'wait_for_response_before_next')),
    start_at                TIMESTAMPTZ,
    cadence_seconds         INTEGER NOT NULL DEFAULT 86400
        CHECK (cadence_seconds >= 1),
    timezone_name           TEXT NOT NULL DEFAULT 'UTC',
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gc_campaigns_status
    ON guided_capture_campaigns (status);

CREATE TABLE IF NOT EXISTS guided_capture_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID NOT NULL REFERENCES guided_capture_campaigns (id) ON DELETE CASCADE,
    body_text       TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'skipped', 'cancelled')),
    category        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gc_questions_campaign
    ON guided_capture_questions (campaign_id, sort_order);

CREATE TABLE IF NOT EXISTS guided_capture_deliveries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id             UUID NOT NULL REFERENCES guided_capture_campaigns (id) ON DELETE CASCADE,
    question_id             UUID NOT NULL REFERENCES guided_capture_questions (id),
    respondent_contact_id   UUID NOT NULL REFERENCES guided_capture_contacts (id),
    channel                 TEXT NOT NULL DEFAULT 'email',
    scheduled_for           TIMESTAMPTZ NOT NULL,
    sent_at                 TIMESTAMPTZ,
    status                  TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    correlation_token       TEXT NOT NULL,
    outbound_message_id     TEXT,
    thread_id               TEXT,
    fail_detail             TEXT,
    preserved_raw_uri       TEXT,
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (correlation_token)
);

CREATE INDEX IF NOT EXISTS idx_gc_deliveries_due
    ON guided_capture_deliveries (status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_gc_deliveries_campaign
    ON guided_capture_deliveries (campaign_id);

CREATE TABLE IF NOT EXISTS guided_capture_responses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id             UUID NOT NULL REFERENCES guided_capture_campaigns (id) ON DELETE CASCADE,
    question_id             UUID NOT NULL REFERENCES guided_capture_questions (id),
    delivery_id             UUID REFERENCES guided_capture_deliveries (id) ON DELETE SET NULL,
    respondent_contact_id   UUID NOT NULL REFERENCES guided_capture_contacts (id),
    channel                 TEXT NOT NULL
        CHECK (channel IN ('email_text', 'voice', 'other')),
    received_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    review_status           TEXT NOT NULL DEFAULT 'new'
        CHECK (review_status IN ('new', 'reviewed')),
    credibility             TEXT NOT NULL DEFAULT 'not_rated'
        CHECK (credibility IN (
            'not_rated', 'trust_strongly', 'generally_trust',
            'uncertain', 'doubt', 'believe_incorrect'
        )),
    credibility_set_at      TIMESTAMPTZ,
    credibility_set_by      TEXT,
    credibility_history     JSONB NOT NULL DEFAULT '[]'::jsonb,
    inbound_message_id      TEXT,
    preserved_raw_uri       TEXT,
    audio_uri               TEXT,
    extracted_text          TEXT,
    transcript_text         TEXT,
    transcript_versions     JSONB NOT NULL DEFAULT '[]'::jsonb,
    stt_status              TEXT NOT NULL DEFAULT 'none'
        CHECK (stt_status IN ('none', 'pending', 'ok', 'failed')),
    resulting_knowledge_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gc_responses_inbound_msg
    ON guided_capture_responses (inbound_message_id)
    WHERE inbound_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_gc_responses_review
    ON guided_capture_responses (review_status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_gc_responses_campaign
    ON guided_capture_responses (campaign_id);
