-- I13 annotation-only persistence. Authoring does not authorize runtime application.
CREATE TABLE i13_transcript_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 provider_key text NOT NULL, source_id text NOT NULL,
 run_id uuid REFERENCES speech_processing_runs(id),
 machine jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(provider_key, source_id, run_id)
);
CREATE INDEX ON i13_transcript_versions(provider_key, source_id, sequence DESC);
-- Preserve the surviving legacy state as-is. Previously overwritten text cannot
-- be reconstructed; this is explicitly a legacy snapshot, not pristine STT.
INSERT INTO i13_transcript_versions(provider_key,source_id,machine)
SELECT s.video_provider_key,s.video_external_id,jsonb_build_object(
 'provenance','legacy_surviving_state',
 'words',COALESCE((SELECT jsonb_agg(to_jsonb(w) ORDER BY w.t_start,w.t_end,w.id)
 FROM speech_transcript_words w WHERE w.video_provider_key=s.video_provider_key AND w.video_external_id=s.video_external_id),'[]'::jsonb),
 'turns',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY t.t_start,t.id)
 FROM speech_speaker_turns t WHERE t.video_provider_key=s.video_provider_key AND t.video_external_id=s.video_external_id),'[]'::jsonb),
 'moments',COALESCE((SELECT jsonb_agg(to_jsonb(m) ORDER BY m.t_start,m.id)
 FROM speech_spoken_moments m WHERE m.video_provider_key=s.video_provider_key AND m.video_external_id=s.video_external_id),'[]'::jsonb))
FROM (SELECT DISTINCT video_provider_key,video_external_id FROM speech_transcript_words) s;
CREATE VIEW i13_current_transcripts AS
 SELECT DISTINCT ON(provider_key,source_id) * FROM i13_transcript_versions
 ORDER BY provider_key,source_id,sequence DESC;
CREATE TABLE i13_transcript_annotations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 version_id uuid NOT NULL REFERENCES i13_transcript_versions(id),
 word_ids uuid[] NOT NULL CHECK(cardinality(word_ids) BETWEEN 1 AND 500),
 t_start double precision NOT NULL CHECK(t_start>=0), t_end double precision NOT NULL CHECK(t_end>=t_start),
 action text NOT NULL CHECK(action IN ('assign','withdraw')),
 speaker_state text NOT NULL CHECK(speaker_state IN ('person','unknown','no_match')),
 person_id uuid REFERENCES people(id), correction text CHECK(length(correction)<=8000),
 actor_id uuid NOT NULL REFERENCES people(id), reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000),
 supersedes uuid UNIQUE REFERENCES i13_transcript_annotations(id),
 request_id uuid NOT NULL UNIQUE, request_digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK((speaker_state='person')=(person_id IS NOT NULL))
);
CREATE INDEX ON i13_transcript_annotations(version_id,sequence);
CREATE FUNCTION i13_reject_evidence_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable I13 evidence; append a revision'; END $$;
CREATE TRIGGER i13_version_immutable BEFORE UPDATE OR DELETE ON i13_transcript_versions
 FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE TRIGGER i13_annotation_immutable BEFORE UPDATE OR DELETE ON i13_transcript_annotations
 FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE TRIGGER i13_words_immutable BEFORE UPDATE OR DELETE ON speech_transcript_words
 FOR EACH ROW EXECUTE FUNCTION i13_reject_evidence_mutation();
CREATE VIEW i13_active_annotations AS SELECT a.* FROM i13_transcript_annotations a
 WHERE a.action='assign' AND NOT EXISTS(SELECT 1 FROM i13_transcript_annotations n WHERE n.supersedes=a.id);
-- Shared effective word projection for both display and search. Replacement text
-- occupies the first selected word; the remaining selected words retain timing.
CREATE VIEW i13_effective_words AS
SELECT v.id AS version_id,v.provider_key,v.source_id,w.ordinality AS word_index,
 (w.word->>'id')::uuid AS id,(w.word->>'t_start')::float8 AS t_start,
 (w.word->>'t_end')::float8 AS t_end,w.word->>'token' AS machine_token,
 CASE WHEN a.correction IS NULL THEN w.word->>'token'
 WHEN a.word_ids[1]=(w.word->>'id')::uuid THEN a.correction ELSE '' END AS token,
 CASE WHEN a.id IS NOT NULL THEN a.person_id ELSE CASE WHEN live.id IS NOT NULL THEN live.person_id ELSE (m.moment->>'person_id')::uuid END END AS person_id,
 CASE WHEN a.id IS NOT NULL THEN CASE WHEN a.speaker_state='person' THEN 'owner_confirmed' ELSE a.speaker_state END
 ELSE COALESCE(live.speaker_state,m.moment->>'speaker_state','anonymous') END AS speaker_state,
 a.id AS annotation_id,COALESCE(a.id,(m.moment->>'id')::uuid,(w.word->>'id')::uuid) AS group_id,
 m.moment AS machine_moment,COALESCE(live.status,m.moment->>'status','accepted') AS status
FROM i13_current_transcripts v
CROSS JOIN LATERAL jsonb_array_elements(v.machine->'words') WITH ORDINALITY w(word,ordinality)
LEFT JOIN LATERAL (SELECT x AS moment FROM jsonb_array_elements(v.machine->'moments') x
 WHERE (x->>'t_start')::float8 <= (w.word->>'t_start')::float8
 AND (x->>'t_end')::float8 >= (w.word->>'t_end')::float8
 ORDER BY (x->>'t_end')::float8-(x->>'t_start')::float8,x->>'id' LIMIT 1) m ON true
LEFT JOIN speech_spoken_moments live ON live.id=(m.moment->>'id')::uuid
LEFT JOIN i13_active_annotations a ON a.version_id=v.id AND (w.word->>'id')::uuid=ANY(a.word_ids);
CREATE VIEW i13_effective_moments AS
SELECT group_id AS id,provider_key AS video_provider_key,source_id AS video_external_id,
 min(t_start) AS t_start,max(t_end) AS t_end,
 string_agg(token,' ' ORDER BY word_index) FILTER(WHERE token<>'') AS text,
 person_id,speaker_state,NULL::float8 AS confidence,'accepted'::text AS status,
 version_id,annotation_id
FROM i13_effective_words
WHERE annotation_id IS NOT NULL OR status<>'withdrawn'
GROUP BY group_id,provider_key,source_id,person_id,speaker_state,version_id,annotation_id;
