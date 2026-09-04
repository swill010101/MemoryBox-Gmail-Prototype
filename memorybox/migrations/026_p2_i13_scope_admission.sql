-- Stage A: AUTHORED ONLY. Do not apply until founder deployment approval.
CREATE TABLE IF NOT EXISTS i13_processing_admissions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 plan_json JSONB NOT NULL,
 plan_sha256 TEXT NOT NULL,
 review_ref TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'registered' CHECK(state IN ('registered','unlocked','started','stopped')),
 acceptance_ref TEXT,
 unlock_ref TEXT,
 start_ref TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS i13_admission_events (
 id BIGSERIAL PRIMARY KEY,
 admission_id UUID NOT NULL REFERENCES i13_processing_admissions(id),
 action TEXT NOT NULL,
 actor TEXT NOT NULL,
 reference TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS i13_work_attempts (
 admission_id UUID NOT NULL REFERENCES i13_processing_admissions(id),
 lane TEXT NOT NULL CHECK(lane IN ('face','voice','transcribe')),
 provider_key TEXT NOT NULL,
 video_external_id TEXT NOT NULL,
 person_key TEXT NOT NULL,
 attempts INTEGER NOT NULL CHECK(attempts>0),
 PRIMARY KEY(admission_id,lane,provider_key,video_external_id,person_key)
);
-- Existing work is deliberately left unstamped and cannot be drained by I13.
ALTER TABLE recognition_queue_items ADD COLUMN IF NOT EXISTS i13_admission_id UUID REFERENCES i13_processing_admissions(id);
ALTER TABLE speech_queue_items ADD COLUMN IF NOT EXISTS i13_admission_id UUID REFERENCES i13_processing_admissions(id);
CREATE INDEX IF NOT EXISTS idx_i13_face_claim ON recognition_queue_items(i13_admission_id,status,priority,created_at);
CREATE INDEX IF NOT EXISTS idx_i13_speech_claim ON speech_queue_items(i13_admission_id,status,priority,created_at);

CREATE TABLE IF NOT EXISTS i13_queue_units (
 admission_id UUID NOT NULL REFERENCES i13_processing_admissions(id),
 lane TEXT NOT NULL CHECK(lane IN ('face','voice','transcribe')),
 provider_key TEXT NOT NULL,
 video_external_id TEXT NOT NULL,
 person_key TEXT NOT NULL,
 enqueue_reason TEXT NOT NULL,
 PRIMARY KEY(admission_id,lane,provider_key,video_external_id,person_key)
);

CREATE OR REPLACE FUNCTION i13_preserve_admission_plan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.plan_json IS DISTINCT FROM OLD.plan_json OR NEW.plan_sha256 IS DISTINCT FROM OLD.plan_sha256
    OR NEW.review_ref IS DISTINCT FROM OLD.review_ref THEN
   RAISE EXCEPTION 'I13 admission plan is immutable; register a new reviewed plan';
 END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS i13_immutable_plan ON i13_processing_admissions;
CREATE TRIGGER i13_immutable_plan BEFORE UPDATE ON i13_processing_admissions
 FOR EACH ROW EXECUTE FUNCTION i13_preserve_admission_plan();
