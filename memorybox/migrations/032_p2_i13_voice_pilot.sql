-- AUTHORED ONLY. Requires reviewed clone rehearsal and production approval.
CREATE TABLE i13_voice_pilot_runs (
 admission_id uuid PRIMARY KEY REFERENCES i13_processing_admissions(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE i13_voice_pilot_attempts (
 admission_id uuid NOT NULL REFERENCES i13_voice_pilot_runs(admission_id),
 span_key text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(admission_id,span_key)
);
CREATE TABLE i13_voice_pilot_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 admission_id uuid NOT NULL REFERENCES i13_voice_pilot_runs(admission_id),
 kind text NOT NULL CHECK(kind IN ('reference','result','failed')),
 payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX i13_voice_pilot_one_publication ON i13_voice_pilot_events(admission_id,kind) WHERE kind IN ('reference','result');
CREATE TABLE i13_voice_pilot_retirements (
 annotation_id uuid PRIMARY KEY REFERENCES i13_transcript_annotations(id),
 reason text NOT NULL CHECK(length(btrim(reason))>0),
 actor text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER i13_pilot_runs_immutable BEFORE UPDATE OR DELETE ON i13_voice_pilot_runs FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE TRIGGER i13_pilot_attempts_immutable BEFORE UPDATE OR DELETE ON i13_voice_pilot_attempts FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE TRIGGER i13_pilot_events_immutable BEFORE UPDATE OR DELETE ON i13_voice_pilot_events FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE TRIGGER i13_pilot_retirements_immutable BEFORE UPDATE OR DELETE ON i13_voice_pilot_retirements FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE VIEW i13_voice_pilot_results AS
 SELECT e.*, EXISTS (
   SELECT 1 FROM jsonb_array_elements(a.plan_json->'spans') s
   WHERE NOT EXISTS (SELECT 1 FROM i13_active_annotations n JOIN i13_current_transcripts v ON v.id=n.version_id WHERE n.id=(s->>'annotation_id')::uuid)
   OR EXISTS (SELECT 1 FROM i13_voice_pilot_retirements r WHERE r.annotation_id=(s->>'annotation_id')::uuid)
 ) AS stale
 FROM i13_voice_pilot_events e JOIN i13_processing_admissions a ON a.id=e.admission_id
 WHERE e.kind='result';
