# N1 browser-playback preflight

## Purpose

Tom could not play N1 in MemoryBox. The viewer showed **Playable copy unavailable** for `second meals on wheels.mp4` / `vid-c015e0fe07414fcc`; the original remains preserved. This plan prepares one read-only preflight only. It is unrelated to recognition evidence and does not change Q1 or N1 annotations.

## Exact source and boundary

| Field | Value |
|---|---|
| Source ID | `vid-c015e0fe07414fcc` |
| Source path | `P:\Photos\Home Videos\second meals on wheels.mp4` |
| Manifest SHA-256 | `09e6dfb523724448888586183d9e265f3181f241ab37fa9d6d800ac1b6cf92b3` |
| Manifest size | 6,249,411 bytes |
| Manifest duration | 305.4066667 seconds |
| Expected proxy path | `C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived\browser_proxies\9eca7338d7a661aed03b02b9.mp4` |

The source ID, path, hash, size, duration, and destination are fixed. This does not authorize proxy creation for any other video, including Q1's `vid-c57dbd21f993f6d1` source.

## Q1 listening result

Tom listened to Q1 (`vid-c57dbd21f993f6d1`, 02:18.720-02:23.180) and concluded that TV/background audio and Eugene speak together. This is a listening conclusion only: no annotation was saved, no Unknown label was created, and it is not training, hold-out, or recognition evidence. It remains excluded from future voice-run proposals unless Tom later saves exact truthful sub-spans.

## Check-only command

From a clean release checkout containing this helper, with drains set to `0` and no admission ID:

```powershell
& $i13Python -B docs/implementation/p2-i13-stage-a/n1-playback-preflight.py
```

The helper imports no MemoryBox modules. It verifies drain/admission locks, the exact source hash and size, ffprobe stream metadata and duration, installed FFmpeg/FFprobe versions, the derived-root free space, and the absent expected proxy. It creates no directory, file, poster, copy, database row, admission, queue item, transcript, recognition result, or network request. An existing proxy or redirected destination stops for review.

## Decision after the report

If the report passes, the next gate is a new source-specific staging proposal: one source, one H.264/AAC-compatible derived copy, no overwrite, no auto-retry, full-decode validation, and later separate visual review plus publication approval. This preflight does not authorize that work. If it fails, preserve the error report and source; do not use the worker POST endpoint or legacy conversion path as a workaround.