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
| Container duration | 305.408 seconds |
| Video duration | 300.368378 seconds (2,578 frames) |
| Audio duration | 305.408 seconds (2,386 AAC frames) |
| Stream layout | one H.264 video, 320x240, `yuvj420p`; one AAC audio stream |
| Existing proxy | absent |
| Derivative-volume free space | 1,210,296,193,024 bytes |
| Tools | FFmpeg/FFprobe 9.0 |

N1 already uses H.264, but it uses the older full-range `yuvj420p` pixel format and does not render in the browser viewer. Its 5.040-second AAC-only tail is an existing source property; it is not treated as corruption. The evidence supports a one-source normalization experiment to H.264 `yuv420p`; it does not prove that pixel format is the only cause or guarantee browser playback.

## Exact bounded operation proposed

[n1-playable-copy-pilot.py](n1-playable-copy-pilot.py) is an exact-source helper with a check-only default. If separately approved, `--execute` would perform one staging attempt only:

- preserve the source timeline with no trim, seek, concatenation, moment export, overwrite, cleanup, retry, or source write; the 5.040-second AAC-only tail remains intact and video is not padded;
- copy the AAC track unchanged;
- re-encode the single video stream to H.264 `yuv420p`, keeping 320x240 dimensions and zero-origin timing;
- use at most two encoder threads, a 600-second wall limit, 4 GiB output limit, and require at least 10 GiB free;
- stage only beneath the existing derivative root at `i13-playable-pilot-c015e0fe07414fcc-v01`;
- validate source hash before and after, stream metadata, full audio/video decode, and packet timestamps.

Publication is a separate later `--publish` operation. It would revalidate the stage and atomically hard-link it to only `browser_proxies/9eca7338d7a661aed03b02b9.mp4`, refusing an existing destination. It never replaces or deletes a proxy.

## Staged playback evidence

Tom opened the existing staged file locally in Chrome and confirmed moving video and audible audio. FFprobe reports H.264 High, 320x240, 2,578 frames, 300.333367 seconds; AAC duration and container duration remain 305.408 seconds. FFmpeg reported `yuv420p(pc)`, while FFprobe labels the full-range output `yuvj420p`. The direct browser result is the acceptance evidence for this staged file; the helper requires its distinct High profile and accepts either FFprobe pixel-format label only for output validation. This does not establish that every `yuvj420p` file is browser-playable.

The first encode attempt is consumed and will not be repeated. `--validate-staged` is a recovery-only mode: it can validate this exact existing stage once, without invoking an encoder, and records `validated.json` only after full decode, packet checks and a repeat source-hash check. It requires an explicit recovery approval reference and stops before publication.
## Required decision gates

1. Approve exactly one staging/validation attempt for helper commit and N1 source/hash above. The helper stops with `published=false`.
2. Tom reviews the staged copy locally for moving picture, normal orientation, audible synchronized sound, and seeking at beginning, middle, and end.
3. Approve a separate publication only after that review. Then verify N1 in MemoryBox. If it remains black, preserve all artifacts and investigate serving/browser compatibility; do not retry or convert another source automatically.

## Limits

This is a media-compatibility proposal only. It does not use Q1/N1 as voice evidence, alter the archive, change the app/worker, or unlock any I13 processing.

## Publication and MemoryBox acceptance

On 2026-09-07, the validated staged copy was atomically published at `browser_proxies/9eca7338d7a661aed03b02b9.mp4`. The worker status endpoint returned `ready` with the expected stream URL. Tom then validated playback in MemoryBox. This closes the N1 browser-playback gap for this exact source only. The original remains unchanged, and no database, queue, recognition, transcription, Learn, migration, service restart, or additional media conversion occurred.