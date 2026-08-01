# HVRT / Memory Box — R3 roadmap note

## Voice annotate → Whisper → searchable (Memory Box)

**Status:** Spec’d in [MEMORYBOX_VOICE_ANNOTATE_PRD.md](MEMORYBOX_VOICE_ANNOTATE_PRD.md)  
**Tom decisions (2026-08-01):** Plan for **Memory Box** (not HVRT build now) · STT = **local faster-whisper**

**Idea:** If Memory Box doesn’t know something, Tom **voice-annotates**. System transcribes with Whisper, stores **audio + transcript**, and that text is searchable like email, texts, and video speech.

HVRT today only has **enroll voice span** (label who is speaking on an existing video transcript). That is *not* this feature.

| Piece | Approach |
|-------|----------|
| Capture | Browser `MediaRecorder` / mic |
| STT | Local faster-whisper (same stack as video ASR) |
| Storage | `voice_notes` linked to asset **or** standalone |
| Search | Index transcript; provenance `owner` conf 1.0 |
| Playback | Audio under working/ + citation in ask UI |

**Fit:** Poor data is what the app fixes — voice annotate is a primary teach path.
