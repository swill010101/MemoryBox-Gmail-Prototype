# HVRT / Memory Box — R3 roadmap note

## Voice note on a picture / email (approved for R3, not R2)

**Idea:** While viewing a photo (or email), Tom records a voice note via webcam mic (e.g. Logitech). System runs speech-to-text, stores the **transcript + audio artifact** linked to that asset, searchable later.

**Feasibility:** **Yes.** Not bleeding edge.

| Piece | Approach |
|-------|----------|
| Capture | Browser `MediaRecorder` / Web Audio from default mic |
| STT | Local faster-whisper (same stack as video ASR) or Web Speech API for draft |
| Storage | `voice_notes` linked to `photo_id` / `message_id` / future MB asset id |
| Search | Index transcript text like other evidence; provenance `owner` conf 1.0 |
| Playback | Keep audio file under working/ for replay |

**Fit with end product:** “Point at pile of stuff → explore → teach → recall.” Voice notes are high-value human evidence on assets that have no speech track.

**R3 acceptance sketch:** Add note on an Immich photo → transcript searchable → citation opens photo + note.
