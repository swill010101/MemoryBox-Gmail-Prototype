# Patio 003 browser-copy staging proposal

## Scope

One source only: `vid-8163a680131fd30a`, `Grandpa sessions 003.MP4`, source SHA-256 `ccda7f166a780c512fa9dc72b366ad20b314003aa6cc2f3869a0cf5396dc37e1`, 1,055,204,616 bytes, 931.931 seconds. The original has one MPEG-4 video stream and one AAC audio stream; no browser proxy exists.

## Proposed bounded operation

A future source-specific helper will require a clean exact release, both drains set to `0`, no admission, at least 10 GiB free in FlightSim's C: derivative root, and an explicit execution reference. It will hash the original before and after, create one new staged MP4 only, map one video and one audio stream, encode video to H.264/yuv420p and copy AAC audio, enforce a single 20-minute attempt and 4 GiB output ceiling, then validate stream layout and full decode.

It stops with `published=false`. Tom must review picture, audible synchronized speech, and seeking at beginning/middle/end. A separate publication approval is required to hard-link the validated stage to `browser_proxies/28fafdd904eda5f82617c328.mp4`. No overwrite, retry, media deletion, database write, recognition, transcription, Learn, drain, or reprocessing is allowed.
