-- P2-I12: Historian Collection & Campaigns V1 (S1–S4 schema)

CREATE TABLE IF NOT EXISTS historian_capture_campaigns (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_person_id         UUID REFERENCES people (id) ON DELETE SET NULL,
    title                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'paused', 'stopped', 'completed')),
    cadence_config_json     JSONB NOT NULL DEFAULT '{"pattern":"weekly","send_time_local":"09:00"}'::jsonb,
    follow_up_interval_seconds INTEGER NOT NULL DEFAULT 259200
        CHECK (follow_up_interval_seconds >= 1),
    send_thank_you_ack      BOOLEAN NOT NULL DEFAULT TRUE,
    timezone_name           TEXT NOT NULL DEFAULT 'UTC',
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hc_campaigns_status
    ON historian_capture_campaigns (status);

CREATE TABLE IF NOT EXISTS historian_capture_campaign_respondents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id             UUID NOT NULL REFERENCES historian_capture_campaigns (id) ON DELETE CASCADE,
    people_id               UUID NOT NULL REFERENCES people (id) ON DELETE RESTRICT,
    display_name_snapshot   TEXT NOT NULL,
    contact_route_kind      TEXT NOT NULL DEFAULT 'email',
    contact_route_value     TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'removed', 'opted_out')),
    opted_out_at            TIMESTAMPTZ,
    opt_out_inbound_message_id TEXT,
    opt_out_source          TEXT CHECK (opt_out_source IS NULL OR opt_out_source IN ('respondent_stop', 'owner_manual')),
    progress_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, people_id)
);

CREATE INDEX IF NOT EXISTS idx_hc_respondents_campaign
    ON historian_capture_campaign_respondents (campaign_id);

CREATE TABLE IF NOT EXISTS historian_capture_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID NOT NULL REFERENCES historian_capture_campaigns (id) ON DELETE CASCADE,
    body_text       TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'skipped', 'cancelled')),
    source          TEXT NOT NULL DEFAULT 'owner_authored',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hc_questions_campaign
    ON historian_capture_questions (campaign_id, sort_order);

CREATE TABLE IF NOT EXISTS historian_capture_deliveries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id             UUID NOT NULL REFERENCES historian_capture_campaigns (id) ON DELETE CASCADE,
    question_id             UUID NOT NULL REFERENCES historian_capture_questions (id),
    campaign_respondent_id  UUID NOT NULL REFERENCES historian_capture_campaign_respondents (id),
    channel                 TEXT NOT NULL DEFAULT 'email',
    scheduled_for           TIMESTAMPTZ NOT NULL,
    sent_at                 TIMESTAMPTZ,
    status                  TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'sent', 'waiting', 'reminder_sent', 'answered',
            'no_response', 'exhausted', 'failed', 'cancelled'
        )),
    waiting_started_at        TIMESTAMPTZ,
    reminder_sent_at        TIMESTAMPTZ,
    reminder_outbound_message_id TEXT,
    no_response_at          TIMESTAMPTZ,
    follow_up_deadline_at   TIMESTAMPTZ,
    correlation_token       TEXT NOT NULL,
    question_snapshot_text  TEXT,
    question_snapshot_hash  TEXT,
    outbound_message_id     TEXT,
    thread_id               TEXT,
    preserved_outbound_raw_uri TEXT,
    fail_detail             TEXT,
    retry_count             INTEGER NOT NULL DEFAULT 0,
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (correlation_token)
);

CREATE INDEX IF NOT EXISTS idx_hc_deliveries_due
    ON historian_capture_deliveries (status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_hc_deliveries_followup
    ON historian_capture_deliveries (status, follow_up_deadline_at);
CREATE INDEX IF NOT EXISTS idx_hc_deliveries_token
    ON historian_capture_deliveries (correlation_token);

CREATE TABLE IF NOT EXISTS historian_capture_items (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id             UUID REFERENCES historian_capture_campaigns (id) ON DELETE SET NULL,
    question_id             UUID REFERENCES historian_capture_questions (id) ON DELETE SET NULL,
    delivery_id             UUID REFERENCES historian_capture_deliveries (id) ON DELETE SET NULL,
    campaign_respondent_id  UUID REFERENCES historian_capture_campaign_respondents (id) ON DELETE SET NULL,
    channel                 TEXT NOT NULL DEFAULT 'email_text'
        CHECK (channel IN ('email_text', 'other')),
    received_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    inbound_message_id      TEXT,
    from_address            TEXT NOT NULL DEFAULT '',
    subject                 TEXT NOT NULL DEFAULT '',
    preserved_raw_uri       TEXT NOT NULL DEFAULT '',
    content_hash            TEXT NOT NULL DEFAULT '',
    header_json             JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_text          TEXT NOT NULL DEFAULT '',
    match_status            TEXT NOT NULL DEFAULT 'matched'
        CHECK (match_status IN ('matched', 'unmatched', 'ambiguous', 'resolved')),
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_hc_items_inbound_msg
    ON historian_capture_items (inbound_message_id)
    WHERE inbound_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_hc_items_match
    ON historian_capture_items (match_status, received_at DESC);

CREATE TABLE IF NOT EXISTS historian_capture_attachments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_item_id UUID NOT NULL REFERENCES historian_capture_items (id) ON DELETE CASCADE,
    filename        TEXT NOT NULL DEFAULT '',
    mime_type       TEXT NOT NULL DEFAULT '',
    storage_uri     TEXT NOT NULL DEFAULT '',
    sha256          TEXT NOT NULL DEFAULT '',
    size_bytes      BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS historian_capture_review_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_item_id     UUID NOT NULL REFERENCES historian_capture_items (id) ON DELETE CASCADE,
    version             INTEGER NOT NULL,
    is_current          BOOLEAN NOT NULL DEFAULT TRUE,
    body_text           TEXT NOT NULL DEFAULT '',
    notes_private       TEXT,
    proposed_links_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by          TEXT NOT NULL DEFAULT 'owner',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_draft_id UUID REFERENCES historian_capture_review_drafts (id) ON DELETE SET NULL,
    UNIQUE (capture_item_id, version)
);

CREATE INDEX IF NOT EXISTS idx_hc_drafts_item
    ON historian_capture_review_drafts (capture_item_id, version);

CREATE TABLE IF NOT EXISTS historian_capture_verdicts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_item_id     UUID NOT NULL REFERENCES historian_capture_items (id) ON DELETE CASCADE,
    review_draft_id     UUID NOT NULL REFERENCES historian_capture_review_drafts (id) ON DELETE CASCADE,
    verdict             TEXT NOT NULL
        CHECK (verdict IN ('retained', 'rejected', 'promotion_authorized')),
    decided_by          TEXT NOT NULL DEFAULT 'owner',
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_verdict_id UUID REFERENCES historian_capture_verdicts (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_hc_verdicts_item
    ON historian_capture_verdicts (capture_item_id, decided_at DESC);

CREATE TABLE IF NOT EXISTS historian_capture_owner_assessments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_item_id         UUID NOT NULL REFERENCES historian_capture_items (id) ON DELETE CASCADE,
    assessment_code         TEXT NOT NULL
        CHECK (assessment_code IN (
            'high_confidence', 'moderate_confidence', 'low_confidence', 'uncertain'
        )),
    note_private            TEXT,
    set_by                  TEXT NOT NULL DEFAULT 'owner',
    set_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_assessment_id UUID REFERENCES historian_capture_owner_assessments (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS historian_capture_respondent_opt_outs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_respondent_id  UUID NOT NULL REFERENCES historian_capture_campaign_respondents (id) ON DELETE CASCADE,
    capture_item_id         UUID REFERENCES historian_capture_items (id) ON DELETE SET NULL,
    keyword_matched         TEXT,
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    source                  TEXT NOT NULL
        CHECK (source IN ('respondent_stop', 'owner_manual')),
    provenance_json         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS historian_capture_thank_you_acknowledgments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_item_id         UUID NOT NULL REFERENCES historian_capture_items (id) ON DELETE CASCADE,
    verdict_id              UUID NOT NULL REFERENCES historian_capture_verdicts (id) ON DELETE CASCADE,
    campaign_respondent_id  UUID NOT NULL REFERENCES historian_capture_campaign_respondents (id) ON DELETE CASCADE,
    sent_at                 TIMESTAMPTZ,
    outbound_message_id     TEXT,
    body_snapshot           TEXT,
    preserved_outbound_raw_uri TEXT,
    skipped_reason          TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS historian_capture_promotions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capture_item_id     UUID NOT NULL REFERENCES historian_capture_items (id) ON DELETE CASCADE,
    review_draft_id     UUID NOT NULL REFERENCES historian_capture_review_drafts (id) ON DELETE CASCADE,
    verdict_id          UUID NOT NULL REFERENCES historian_capture_verdicts (id) ON DELETE CASCADE,
    promoted_type       TEXT NOT NULL
        CHECK (promoted_type IN ('story', 'artifact', 'accepted_evidence')),
    promoted_id         UUID NOT NULL,
    promoted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    promoted_by         TEXT NOT NULL DEFAULT 'owner',
    provenance_json     JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_hc_promotions_target
    ON historian_capture_promotions (promoted_type, promoted_id);
