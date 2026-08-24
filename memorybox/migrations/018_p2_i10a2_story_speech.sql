-- P2-I10A.2 authored-memory provenance on saved Story versions.
-- Do not mutate prior version audio; new takes write a new saved version.

ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS speech_origin TEXT;

ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS speech_user_edited BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS speech_captured_at TIMESTAMPTZ;

ALTER TABLE story_versions
    ADD COLUMN IF NOT EXISTS speech_audio_id TEXT;
