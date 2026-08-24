# P2-I10A.2 — Reusable Speech Input for Text Entry

**Status:** Definition **DRAFT** 2026-08-24 · planning only · **not locked** · **not build-authorized**  
**PRD:** [MBPRD-P2-I10A2_SPEECH_INPUT.md](MBPRD-P2-I10A2_SPEECH_INPUT.md)  
**Assessment:** [MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md)  
**Surface map:** [MBAS-P2-I10A2_SURFACE_MAP.md](MBAS-P2-I10A2_SURFACE_MAP.md)  
**Depends:** I10A Stories **ACCEPTED** · I10A.1 **ACCEPTED** · I10B Artifacts **ACCEPTED** (consume Story dictation later for Tell its story; do not reopen I10B)  
**Does not start:** I10C Journal product · I11 · I9 archive STT · spoken Ask · TTS · voice-as-evidence recorder · three independent mics

## Intent

Users speak into the **same** substantial text they could type. Speech is an input method. It does not change Save/Cancel. It does not create audio evidence by default.

Story, Journal, Artifact, and Person notes must **share one narrative field**, then one speech lifecycle. They do **not** share that field today.

## Build locks (from PRD + assessment)

1. **Required:** consolidate multiline/narrative entry into one reusable control **before** microphone UX on each screen.
2. Speech attaches as `speech input allowed` on that control only.
3. Insert at cursor; do not replace the field because the mic started; do not silently overwrite a selection in v1.
4. Containing Save/Cancel unchanged. Speech does not Save.
5. No mic on names, emails, phones, dates, pickers, Ask, titles (v1).
6. Failure: typing still works; family-facing error only.
7. Do not confuse with I9 video transcription.
8. Dictation does not imply preserved Voice Memory / `audio_uri` unless a later increment says so.

## Out

General voice navigation · spoken Ask · TTS · diarization · speaker id · historical media STT · voice enrollment · AI rewrite of dictation · Artifact-private `MediaRecorder` · finishing I10C.

## Prove (when built)

Owner AT-01–AT-12. Harness must assert **one** speech module and **one** narrative control adopted on Story, Journal, Artifact description, and Person notes — not three copies of Record/Stop.

**Not locked until Tom accepts the PRD and authorizes build.**
