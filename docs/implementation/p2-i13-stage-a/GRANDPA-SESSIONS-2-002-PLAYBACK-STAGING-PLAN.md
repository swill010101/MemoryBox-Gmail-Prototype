# Grandpa sessions 2 002 browser-copy staging proposal

## What you are seeing

`vid-34df63e61b949890` / `2011-03-21 grandpa sessions 2/grandpa sessions 2 002.MP4` is in the accepted 22-source manifest. MemoryBox Review/Explore serves browser video only through a derived H.264 proxy under the worker derived root. **This source never received a published proxy.** Only `20111105_1532.MP4` completed the earlier one-source playable-copy pilot.

The UI message **Playable copy unavailable. This video cannot play here yet. The original is preserved.** is therefore expected for this source. It is not evidence that Codex removed playback or damaged the original on `P:\Photos\Home Videos`.

Proxy generation through the application API remains locked (`playable_copy_generation_requires_separate_authorization`). A separate bounded helper operation is required, same class as [PATIO-003-PLAYBACK-STAGING-PLAN.md](PATIO-003-PLAYBACK-STAGING-PLAN.md) and [PLAYABLE-COPY-PILOT-PLAN.md](PLAYABLE-COPY-PILOT-PLAN.md).

## Pinned source

| Field | Value |
|---|---|
| Source ID | `vid-34df63e61b949890` |
| Relative path | `2011-03-21 grandpa sessions 2/grandpa sessions 2 002.MP4` |
| SHA-256 | `61505855a1220985482c415238bd4622278bf4eff053687dffad5e02a1b77a32` |
| Size | 361,851,720 bytes |
| Duration | 319.8195 seconds (~5:20) |
| Expected proxy | `browser_proxies/7cb205f4b99419be11e3d3f5.mp4` |
| Staging attempt dir | `i13-playable-pilot-34df63e61b949890-v01` |

## Why this matters for Eugene reprocessing

Tom identified this source as a good candidate for a **new clear Eugene training reference** after the inspector returned `fresh_reference_count: 0`. Owner annotation requires in-browser playback to select transcript text and verify audio. Until a validated browser proxy exists, annotation work on this source is blocked in the UI even though the original file is intact.

This playable-copy operation is **separate** from voice-pilot admission, Eugene reprocessing, Learn, drains, and archive processing.

## Step 1 — Read-only preflight (FlightSim)

```powershell
$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue

cd C:\MemoryBox
python -B docs\implementation\p2-i13-stage-a\grandpa-sessions-2-002-playback-preflight.py
```

Confirm `destination_exists: false`, manifest hash/size match, and stream layout (expected one MPEG-4 video + one AAC audio stream). Stop if the proxy already exists.

## Step 2 — Helper check-only

After pulling the helper commit to FlightSim:

```powershell
python -B docs\implementation\p2-i13-stage-a\grandpa-sessions-2-002-playable-copy-pilot.py
```

Review proposed encode args, free space, and helper hash. No media is written in default mode.

## Step 3 — Staging approval then execute

Tom approved **one** staging-and-validation attempt on 2026-09-08. Approval reference: `Tom-approved-grandpa-sessions-2-002-staging-2026-09-08`. Helper release: `032a113c43de8eae3117b9ae64ebcda1b3229eb2`. Check-only helper SHA-256: `60b73d15db51110e7602c29eb034fb94a2c04fbc212826aaac154cd921351e21`. Execution uses the pinned helper with `--execute --expected-release 032a113c43de8eae3117b9ae64ebcda1b3229eb2 --approval-ref Tom-approved-grandpa-sessions-2-002-staging-2026-09-08`. The helper stops at `published=false`.

## Step 4 — Owner staged review

Tom opens `staged.mp4` locally and verifies moving picture, orientation, audible speech, and seeking at beginning, middle (~02:40), and end (~05:10).

## Step 5 — Separate publication approval

Only after staged review passes: `--publish --visual-review-ref <ref>`. This atomically hard-links the validated stage to `browser_proxies/7cb205f4b99419be11e3d3f5.mp4`. Then verify playback in MemoryBox for this source.

## Step 6 — Resume Eugene annotation

After in-MB playback works:

1. Save one new clear Eugene assignment on a distinct interval (not reused pilot spans).
2. Rerun [inspect-eugene-reprocessing-candidates.py](inspect-eugene-reprocessing-candidates.py).
3. Finalize [EUGENE-AFFECTED-REPROCESSING-PROPOSAL.md](EUGENE-AFFECTED-REPROCESSING-PROPOSAL.md) when `fresh_reference_count = 1`.

## Interim workaround

If annotation cannot wait for this proxy pilot, use a source that already plays in Review/Explore, for example `20111105_1530.MP4` or `Grandpa sessions 003.MP4` if its proxy is published — on a **new** interval not used in prior pilots.

## Explicit prohibitions

- No automatic conversion of other manifest sources
- No overwrite of an existing proxy destination
- No recognition, transcription, Learn, drain, database write, or voice-pilot admission as part of proxy staging
- No inference that Codex damaged the original; verify with preflight hash only
