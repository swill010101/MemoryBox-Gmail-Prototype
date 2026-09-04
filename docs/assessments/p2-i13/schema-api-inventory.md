# Schema and API inventory

Generated from baseline source; declarations are not proof of deployed schema.

## memorybox/migrations/008_p2_i1_person_in_media.sql

- L4: `CREATE TABLE IF NOT EXISTS provider_person_sync_runs (`
- L19: `CREATE INDEX IF NOT EXISTS idx_provider_person_sync_runs_provider`
- L23: `CREATE TABLE IF NOT EXISTS face_evidence (`
- L42: `CREATE INDEX IF NOT EXISTS idx_face_evidence_person ON face_evidence (person_id);`
- L43: `CREATE INDEX IF NOT EXISTS idx_face_evidence_provider`
- L45: `CREATE INDEX IF NOT EXISTS idx_face_evidence_authority ON face_evidence (authority);`
- L48: `CREATE TABLE IF NOT EXISTS recognition_queue_items (`
- L68: `CREATE INDEX IF NOT EXISTS idx_recognition_queue_person_status`
- L70: `CREATE INDEX IF NOT EXISTS idx_recognition_queue_status`
- L74: `CREATE TABLE IF NOT EXISTS face_appearance_moments (`
- L93: `CREATE INDEX IF NOT EXISTS idx_face_appearance_person`
- L95: `CREATE INDEX IF NOT EXISTS idx_face_appearance_video`

## memorybox/migrations/011_p2_i8b_video_face.sql

- L4: `ALTER TABLE face_evidence`
- L6: `ALTER TABLE face_evidence`
- L8: `ALTER TABLE face_evidence`
- L10: `ALTER TABLE face_evidence`
- L12: `ALTER TABLE face_evidence`
- L14: `ALTER TABLE face_evidence`
- L16: `ALTER TABLE face_evidence`
- L29: `ALTER TABLE face_appearance_moments`
- L31: `ALTER TABLE face_appearance_moments`
- L33: `ALTER TABLE face_appearance_moments`
- L35: `ALTER TABLE face_appearance_moments`
- L37: `ALTER TABLE face_appearance_moments`
- L50: `ALTER TABLE recognition_queue_items`
- L53: `CREATE TABLE IF NOT EXISTS recognition_processing_runs (`
- L70: `CREATE INDEX IF NOT EXISTS idx_recognition_runs_person`
- L73: `CREATE TABLE IF NOT EXISTS video_face_observations (`
- L91: `CREATE INDEX IF NOT EXISTS idx_video_face_obs_video`
- L93: `CREATE INDEX IF NOT EXISTS idx_video_face_obs_person`
- L96: `CREATE TABLE IF NOT EXISTS identity_withdrawals (`
- L109: `CREATE INDEX IF NOT EXISTS idx_identity_withdrawals_lookup`
- L112: `CREATE TABLE IF NOT EXISTS pending_review_face_crops (`

## memorybox/migrations/012_p2_i8b_person_watermark.sql

- L2: `CREATE TABLE IF NOT EXISTS recognition_person_watermark (`

## memorybox/migrations/013_p2_i9_spoken.sql

- L4: `CREATE TABLE IF NOT EXISTS speech_processing_runs (`
- L20: `CREATE TABLE IF NOT EXISTS speech_transcript_words (`
- L32: `CREATE INDEX IF NOT EXISTS idx_speech_words_video`
- L35: `CREATE TABLE IF NOT EXISTS speech_speaker_turns (`
- L49: `CREATE INDEX IF NOT EXISTS idx_speech_turns_video`
- L52: `CREATE TABLE IF NOT EXISTS speech_spoken_moments (`
- L70: `CREATE INDEX IF NOT EXISTS idx_speech_moments_video`
- L72: `CREATE INDEX IF NOT EXISTS idx_speech_moments_person`
- L74: `CREATE INDEX IF NOT EXISTS idx_speech_moments_text`
- L77: `CREATE TABLE IF NOT EXISTS speech_voice_exemplars (`
- L94: `CREATE TABLE IF NOT EXISTS speech_identity_withdrawals (`
- L105: `CREATE TABLE IF NOT EXISTS speech_queue_items (`
- L121: `CREATE UNIQUE INDEX IF NOT EXISTS idx_speech_queue_transcribe`
- L124: `CREATE UNIQUE INDEX IF NOT EXISTS idx_speech_queue_learn`
- L127: `CREATE INDEX IF NOT EXISTS idx_speech_queue_status`

## memorybox/migrations/018_p2_i10a2_story_speech.sql

- L4: `ALTER TABLE story_versions`
- L7: `ALTER TABLE story_versions`
- L10: `ALTER TABLE story_versions`
- L13: `ALTER TABLE story_versions`

## Pipeline API routes

- L1080: `@app.get("/review/ui")`
- L1290: `@app.get("/library/media/photo/{external_id}")`
- L1360: `@app.get("/library/media/immich-video/{external_id}")`
- L1412: `@app.get("/library/media/immich-person/{external_id}")`
- L1434: `@app.get("/library/media/video-poster")`
- L2528: `@app.post("/people/sync/immich")`
- L2588: `@app.get("/people/sync/immich/latest")`
- L2596: `@app.get("/recognition/queue")`
- L2611: `@app.post("/recognition/queue/process")`
- L2622: `@app.post("/recognition/archive-pass")`
- L2655: `@app.post("/recognition/appearances/correct")`
- L2688: `@app.get("/recognition/status")`
- L2705: `@app.post("/recognition/seed")`
- L2745: `@app.post("/recognition/learn")`
- L2767: `@app.get("/recognition/video-people")`
- L2778: `@app.get("/speech/transcript")`
- L2785: `@app.get("/speech/status")`
- L2792: `@app.post("/speech/archive-pass")`
- L2810: `@app.post("/speech/transcribe-now")`
- L2827: `@app.post("/speech/queue/process")`
- L2844: `@app.post("/speech/learn")`
- L2874: `@app.post("/speech/moments/correct")`
- L3798: `@app.get("/review/videos")`
- L3832: `@app.get("/review/faces")`
- L3881: `@app.post("/review/faces")`
- L3928: `@app.patch("/review/faces/{face_external_id}")`
- L4026: `@app.post("/review/videos/{video_external_id}/browser-proxy")`
- L4032: `@app.get("/review/videos/{video_external_id}/browser-proxy")`
- L4072: `@app.get("/review/media/{video_external_id}")`
