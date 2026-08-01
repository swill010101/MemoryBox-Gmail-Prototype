# Memory Box — Voice Annotate PRD

**Status:** Approved (Tom) — **parked** until Memory Box app work (no HVRT build)  
**Decisions (2026-08-01):** Memory Box feature (not HVRT POC now) · STT = **local faster-whisper**  
**UX defaults (signed off):** max note **10 min** · show transcript then one **Save** · mic **tap start / tap stop**  
**Related:** [ROADMAP_R3_VOICE_NOTES.md](ROADMAP_R3_VOICE_NOTES.md) · Memory Box ask/teach UI mockups

## Problem being solved

Memory Box answers are only as good as the evidence it holds. Gaps are normal (who is this, what place, what story). Typing every clarification is slow. Tom needs to **speak a note**, have it **transcribed with Whisper**, and have that text become **first-class searchable memory** — the same way email, texts, and video transcripts will be.

This is how the app fixes poor data: human voice → durable evidence → better next answers.

## Success criteria

- From the Memory Box teach surface (or while viewing any asset), Tom can **Record → Stop → Save**
- Audio artifact stored; **Whisper transcript** stored with provenance **owner**, confidence **1.0**
- Asking a natural question later can **hit that transcript** and cite it (open asset + play note)
- Works on assets with **no speech track** (still photos, Immich pics, emails, texts)
- Also supports a **free-standing memory note** (not tied to media) for “here’s the story…”
- Original media never modified; notes are additive

## Scope — In

| Piece | Approach |
|-------|----------|
| Capture | Browser `MediaRecorder` (default mic) in Memory Box UI |
| STT | **Local faster-whisper** (same family as HVRT video ASR) |
| Storage | `voice_notes`: audio path, transcript text, timestamps, optional `asset_id` / kind |
| Link targets | Photo (Immich or disk), video, email, text message, or **none** (standalone) |
| Search | Transcript indexed with other evidence modalities; appears in ask filmstrip as “Your story” / voice frame |
| Playback | Replay audio + show transcript beside cited asset |
| Provenance | Owner mark; never silently promoted from AI |

## Scope — Out (this feature)

- Building the full Memory Box ask shell (separate PRD)
- Immich connector details (voice notes attach once assets exist)
- Speaker diarization / “enroll this voiceprint” (HVRT span enroll stays separate)
- Web Speech live draft (rejected for v1 — Whisper only)
- Cloud STT
- Multi-user auth

## Constraints & dependencies

- Local-first; Whisper must run on Tom’s machine (GPU optional)
- Depends on Memory Box asset IDs once Immich/disk/email/texts are ingested
- Long notes: show progress while Whisper runs (background job pattern like HVRT Learn)
- Privacy: audio + transcript stay local unless Tom later chooses sync

## Edge cases

- Mic denied / no device → clear error, no silent fail
- Empty / noise-only recording → refuse save or flag “no speech detected”
- Very long monologue → chunk Whisper; one note ID, multiple segments OK
- Asset deleted later → note remains as standalone with broken-link warning
- Wrong transcript → Tom can edit text before save (and after, as owner edit)

## UX fit (Memory Box main screen)

Same two depths as the mockups:

1. **Ask** — voice notes show up in the evidence filmstrip and in the narrative citation  
2. **Teach** — mic control on the deepen panel: “Tell me about this” → record → transcript preview → Save to memory  

No separate “voice app.” One interface.

## Build plan (when Memory Box app work starts)

1. Schema: `voice_notes` + files under `working/voice_notes/`  
2. API: start/stop upload audio, enqueue Whisper job, status, save/edit transcript  
3. Teach UI: record control + transcript preview + link to current asset  
4. Index transcript into ask/search  
5. Citation playback from an answer  
6. Standalone note entry (no asset)  
7. Wire Immich/disk/email/text asset types as they land  

## Resolved defaults

1. Max note length before split: **10 minutes**  
2. After Whisper: **show transcript** (editable) → one **Save** tap  
3. Mic UX: **tap to start / tap to stop** (not hold-to-talk)

## Sign-off

- [x] Tom approves this PRD (2026-08-01) — parked; implement with Memory Box, not HVRT now
