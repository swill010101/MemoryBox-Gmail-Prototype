# N1 browser-normalization pilot proposal

## Status

This proposal was prepared after the successful N1 read-only preflight on 2026-09-07. It does not authorize or perform encoding, proxy publication, service changes, database writes, recognition, transcription, Learn, or queue work.

## What the preflight proved

The exact N1 source is present and unchanged:

| Field | Value |
|---|---|
| Source | `P:\Photos\Home Videos\second meals on wheels.mp4` |
| Source ID | `vid-c015e0fe07414fcc` |
| SHA-256 | `09e6dfb523724448888586183d9e265f3181f241ab37fa9d6d800ac1b6cf92b3` |
| Size | 6,249,411 bytes |
| Duration | 305.408 seconds |
| Stream layout | one H.264 video, 320x240, `yuvj420p`; one AAC audio stream |
| Existing proxy | absent |
| Derivative-volume free space | 1,210,296,193,024 bytes |
| Tools | FFmpeg/FFprobe 9.0 |

N1 already uses H.264, but it uses the older full-range `yuvj420p` pixel format and does not render in the browser viewer. The evidence supports a one-source normalization experiment to H.264 `yuv420p`; it does not prove that pixel format is the only cause or guarantee browser playback.

## Exact bounded operation proposed

[n1-playable-copy-pilot.py](n1-playable-copy-pilot.py) is an exact-source helper with a check-only default. If separately approved, `--execute` would perform one staging attempt only:

- preserve the full 305-second source timeline with no trim, seek, concatenation, moment export, overwrite, cleanup, retry, or source write;
- copy the AAC track unchanged;
- re-encode the single video stream to H.264 `yuv420p`, keeping 320x240 dimensions and zero-origin timing;
- use at most two encoder threads, a 600-second wall limit, 4 GiB output limit, and require at least 10 GiB free;
- stage only beneath the existing derivative root at `i13-playable-pilot-c015e0fe07414fcc-v01`;
- validate source hash before and after, stream metadata, full audio/video decode, and packet timestamps.

Publication is a separate later `--publish` operation. It would revalidate the stage and atomically hard-link it to only `browser_proxies/9eca7338d7a661aed03b02b9.mp4`, refusing an existing destination. It never replaces or deletes a proxy.

## Required decision gates

1. Approve exactly one staging/validation attempt for helper commit and N1 source/hash above. The helper stops with `published=false`.
2. Tom reviews the staged copy locally for moving picture, normal orientation, audible synchronized sound, and seeking at beginning, middle, and end.
3. Approve a separate publication only after that review. Then verify N1 in MemoryBox. If it remains black, preserve all artifacts and investigate serving/browser compatibility; do not retry or convert another source automatically.

## Limits

This is a media-compatibility proposal only. It does not use Q1/N1 as voice evidence, alter the archive, change the app/worker, or unlock any I13 processing.