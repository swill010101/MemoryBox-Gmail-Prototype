# Playback availability correction

Tom authorized the bounded code correction after a deployed source displayed no moving video. Browser evidence for vid-8163a680131fd30a: duration 931.931, currentTime 0.5, paused true, ended false, dimensions 0x0, no media error, and no proxy query parameter. Existing inventory identifies Grandpa sessions 003.MP4 with the same full duration. Read-only container-header inspection found mp4v video and mp4a audio. Codec compatibility is the leading explanation; the original proxy-request error was not captured. This is not proof of duplicated fragments or a forced stop.

## Changes

Opening native video now checks existing proxy status with GET. Initial video markup contains no source URL, so media does not load before that check. Only ready copies are selected. Missing, stale, failed or unreadable copies produce clear unavailable/error feedback, with no silent fallback to the original. Immich's existing stream path is retained with explicit media-error feedback. Source seek and natural playback remain; Gallery return functions remain unchanged.

Proxy status/path inspection no longer creates derivative/cache directories. Proxy serving requires an existing source and a ready copy according to the existing size/mtime criterion; this is not a new codec/content verification claim. Generation requests are denied through the MB API, worker POST route and proxy manager start method. There is no newly introduced switch that unlocks generation; a future single-source operation needs its own authorization and reviewed implementation/command. Existing files and records are preserved.

The feedback is placed outside the video frame to remain visible with existing flex/overflow styles. Existing Learn/transcript selection is not converted into an annotation-save workflow by this correction. No I12 files or migrations changed.

## Proof and limits

33 offline tests pass, including ready/missing/request-failure cases, delayed responses after navigation, initial markup without a source, read-only status when no cache exists, stale proxy detection and generation denial before body/provider access. JavaScript syntax and Git whitespace checks pass. browser-proxy-hold-proof.json/png show the actual binder rendered in offline Chromium with synthetic missing-copy status, one GET and no source load. It is isolated component proof, not full live Gallery acceptance. Earlier natural-playback proof remains applicable to unchanged appearance-seek logic.

No runtime migration, source decoding, conversion, deletion, cleanup or deployment was performed in this correction. No family media was processed. Proxy generation before this change was possible despite recognition/transcription locks; the observed request outcome remains unknown.

## Locked deployment and next gate

This code-only correction requires no new migration; FlightSim already applied 030. Prepare the exact correction commit in a new unused worktree, run the 33 tests and launch check, then coordinate both app and worker replacement using the existing locked launcher with the correction SHA. Do not use startmb or rerun migrations. Retain Capture code/config and media/derived paths, drains off, admission unset. Refresh the browser after both services use the correction; native missing-copy entries should show the explicit unavailable state and make no generation POST. Existing compatible copies should seek and play naturally. Recognition/speech and proxy-generation POSTs must remain denied.

A separately authorized single-source playable copy for Grandpa sessions 003.MP4 remains the next media operation. Its path, codec, duration, source hash and preservation proof must be reviewed; this correction grants no processing authority. Full voice recognition and annotation-only overlays remain later I13 requirements.
