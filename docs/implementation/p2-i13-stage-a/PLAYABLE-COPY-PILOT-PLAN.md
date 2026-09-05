# Bounded playable-copy pilot - proposal

Tom requested proceeding with a plan after the unavailable-copy screenshot. This authorizes plan preparation, not media conversion. No source processing, application changes, runtime writes, deletion, or conversion occurred in preparing this plan.

## Exact first source

The screenshot identifies hvrt source `vid-c57dbd21f993f6d1`. The accepted 22-source manifest identifies it as `20111105_1532.MP4`, 1,251,525,801 bytes, 1,105.104 seconds (18:25.104), SHA256 `26f3646b4adbda7573ff19c02da3b11bafceff4ac5cd7d967d5b0053a2e10705`. Tom has now supplied live source size/hash/duration matching these recorded values. The helper revalidates them before each authorized operation.

This is distinct from the previously inspected `vid-8163a680131fd30a` / Grandpa sessions 003.MP4. Its mp4v codec finding must not be attributed to the screenshot source. Tom subsequently supplied ffprobe metadata for the screenshot source: MPEG-4 Part 2/mp4v, 1280x720/yuv420p, 33,120 frames at 30000/1001, with one AAC mono 24 kHz audio stream; both start at zero. He confirmed that the expected proxy does not exist. The unavailable UI confirms that the existing playback path did not produce a usable copy; it does not prove that all such files share a codec or are duplicates.

Machine-readable scope: [playable-copy-pilot-plan.json](playable-copy-pilot-plan.json). Exactly one full source and one conversion attempt are proposed. The 22-source membership does not authorize converting all 22 sources.

## Step 1 - Read-only FlightSim preflight

Use the deployed release and reviewed source/derived roots. Confirm the source exists and matches manifest size/hash. Inspect ffprobe stream metadata: video codec, pixel format, dimensions, rotation, duration, audio streams and timestamps. Record ffmpeg/ffprobe versions. Check the existing proxy destination and GET browser-proxy status. Inspect free space on the actual derivative volume, including a resolved junction/redirect target if present. Do not create a directory or generate a poster as a preflight step.

The ready check currently uses file size and mtime, not content hash/codec validation. An existing file, stale file, hash mismatch, changed path, absent source, or unexpected stream layout requires review; do not overwrite or remove it. If a validated compatible copy already exists, investigate serving/selection rather than converting again.

## Step 2 - Prepare and review the operator helper

Prepare a separate explicit single-source helper, with check-only default, before asking for execution approval. It must verify the plan's exact source ID/path/hash and destination containment; verify drains off and admission unset; and never use provider/model/recognition queues. This media-only operation is separate from a recognition/transcription admission. API and worker generation routes stay locked. Do not call the legacy manager's private _run method: it uses overwrite mode and has not implemented these preservation guarantees.

Review a concrete command/argument list and dry-run report. Proposed encoding is MP4, H.264/yuv420p, AAC if source audio exists, faststart; preserve aspect ratio/orientation, audio sync and the entire source timeline. No -ss/-t trimming, concatenation or per-moment exports. A source with multiple relevant tracks needs a reviewed track choice before encoding. One proxy must serve all moments referencing this source ID.

Proposed limits: one source, one job, one attempt, two encoder threads, two-hour wall limit, output at most 4 GiB, and at least 10 GiB free before starting. These are operator limits for review, not runtime measurements. The helper must enforce time/size limits and never publish a capped/truncated result. No automatic retries, parallel directory walk, wildcard, recursive source discovery or automatic next source.

## Step 3 - Approval then isolated generation

Execution approval must name the pilot plan/version, exact source hash, approved helper commit, destination and limits. Only then may Tom run the helper on FlightSim. The helper may create a uniquely named staging output and provenance/validation report outside Git in the approved derivative area. Encode with no overwrite; never open the original for writing. Preserve existing files, including failed/staged outputs. A failed attempt stops for review.

## Step 4 - Validate before making the copy visible

Recheck the original size/hash after generation. Probe the staged copy: expected codecs, nonzero dimensions, duration within 0.5 seconds of the recorded source after live metadata reconciliation, monotonic usable timestamps and preserved orientation/audio. Validate the full encoded video/audio decode for errors; spot-check beginning, middle and near end with moving frames and audible sync. Reject truncated output even if it exceeds the legacy ready-size threshold.

Record source/output hashes, stream metadata, sizes, tool versions, exact argument list, start/end times and validation results outside Git; commit only an authorized sanitized summary. Never commit media. Keep output hidden from the normal proxy path until validation passes. Publication must atomically refuse an existing destination (no replace). Use the existing browser_proxies key from the JSON plan and verify its mtime satisfies the current server check without altering source timestamps. Do not falsify timestamps to hide a stale copy. Runtime admission/recognition records remain unchanged.

## Step 5 - MB playback acceptance

1. GET status reports ready for this exact source; reopening the same Gallery item selects its existing proxy. No generation POST occurs.
2. Moving video, sound, controls and correct orientation are present. Source duration is about 18:25 after metadata validation, not the relevance interval's length.
3. Open multiple existing moments for this source. Each seeks to its evidence-backed start and continues naturally beyond the relevance interval without resetting or clamping.
4. Seek through beginning/middle/end, including a seek backward after natural source end; verify normal controls and audio sync.
5. Close the viewer and confirm Gallery query, chips, filter, scroll and item position remain intact. Existing transcript text/timestamps remain immutable; do not select Learn.
6. Source hash remains unchanged. No recognition/transcription queue work, admissions, cleanup, I12 changes, migration or archive processing was performed. Normal MB browsing is not a read-only application session; attribute proof to the helper and actual observed operations.

## Step 6 - Stop and review

Stop after this one-source proof. Do not automatically convert other Grandpa videos, the 22-source corpus or 63 Gallery moments. Additional sources require an explicit source-ID manifest and reviewed limits. Fragment Gallery presentation is separate from source playback and is not solved by deleting records/files. Full face/voice learning, off-camera voice recognition acceptance, and additive annotation overlays remain separate I13 work.

If validation or playback fails, retain the original, previous deployment and all outputs. Report the failure and keep processing locked. Do not delete/quarantine a copy or run a cleanup as a rollback shortcut; a published-file rollback needs a concrete reviewed action.

## Current deployment position

Gate 2 current Ask/Gallery and curator corrections have owner-reported passes on code 6d1bf63678d79bd021bc4803eca09f0211a35ca1. Full source playback remains open. This proposal does not advance Gate 3 recognition/transcription or Gate 4 archive release. No redeployment is needed to read this plan.

## Prepared helper and execution review - version 0.2

Owner preflight matches the manifest hash/size/duration. The exact proxy is absent. C: has 1,240,324,608,000 free bytes in the supplied report; FFmpeg and FFprobe 9.0 full builds are installed. The helper rechecks free space at the actual resolved derivative root and refuses redirected root/destination paths. No source decoding or media conversion was performed by the agent.

[playable-copy-pilot.py](playable-copy-pilot.py) is prepared. It imports only Python standard-library modules, never MB, database, provider, speech or recognition modules. It uses the pinned source and existing derivative root; no command-line source substitution or directory scan is supported. It requires explicit drain-off settings and admission unset in the operator shell. These checks do not independently inspect running child service environments; the existing deployed locked launcher provides their locks.

- Default mode: checks source hash, stream metadata, tool versions, destination and free space; prints the exact proposed argument list and helper hash. Creates nothing and does not decode/convert media.
- `--execute --expected-release ... --approval-ref ...`: requires a clean exact reviewed helper checkout. Reserves one persistent attempt directory; a repeated or concurrent attempt fails without deletion. Writes staged.mp4 and reports/logs only under `i13-playable-pilot-c57dbd21f993f6d1-v01` in the existing derivative root. Converts video to H.264 and copies existing AAC unchanged. Validates duration, frame count, pixel format, audio layout, zero start, full decode and strictly increasing per-stream decode timestamps, then rechecks original hash/size/mtime. Stops with published=false. All failures preserve their outputs for review.
- `--publish --expected-release ... --approval-ref ... --visual-review-ref ...`: a separate later operation, after owner beginning/middle/end moving-video and audio-sync review. Rechecks source and staged content, refuses an existing destination and creates an atomic same-volume hard link at the expected browser_proxies path. Keeps the staged link and validation reports; never copies over, renames over, removes or changes original files. Unsupported hard links stop without a fallback. The existing MB proxy GET can then serve the validated file; app code and generation locks are not changed.

The default conversion argument sequence is: no stdin, no overwrite, fail on decode errors, two decoder threads, exact source input, first video and first audio (exact two-stream layout checked), libx264 with two encoder threads, one filter thread, veryfast/CRF 23/yuv420p, audio copy, faststart, 4 GiB file cap, exact staged output. No seek/trim flags. Two threads is the encoder limit, not a guarantee that the whole FFmpeg process has only two threads. A wall-time monitor bounds encode/full-decode work; source hashing and preflight have additional read time. A size-capped or truncated result cannot pass publication checks.

Offline proof: `python -B -m unittest discover -s tests -p test_i13_playable_pilot.py -v` passes 14 tests using synthetic bytes and mocked tools. Covers read-only default, source mismatch, destination escape/collision, immutable staged publication, lock/approval gates, expired work budget, stream/frame/duration validation and timestamps. No real FFmpeg encode/decode or family-media tests were run. Existing app tests need not be rerun for these standalone helper/documentation additions.

Next decision: approve only one **staging and validation attempt** for plan 0.2 and this exact source. Publication remains a later decision after staged visual/audio review. No recognition/transcription admission, proxy-generation API unlock, migration, service restart, corpus pass or I12 work is part of either helper operation. Use a separate clean helper checkout; the running application can remain at 6d1bf63678d79bd021bc4803eca09f0211a35ca1. Complete copy-and-paste FlightSim commands will name the exact committed helper SHA after approval.

## Founder execution approval received

Tom explicitly approved one staging-and-validation attempt for the specified source; publication remains separate. Approval reference: `Tom-approved-single-source-staging-2026-09-05`. Approved helper code: `d3e7eff71c8a627bf1f712dfe5c99be493c38992`. Scope: hvrt `vid-c57dbd21f993f6d1`, `20111105_1532.MP4`, source SHA256 `26f3646b4adbda7573ff19c02da3b11bafceff4ac5cd7d967d5b0053a2e10705`, plan 0.2 limits. Tom operates FlightSim using a separate exact helper checkout; the app/worker release need not change. Default preflight and 14 offline tests precede --execute. The helper stops at validated=true, published=false. No automatic retry or publication is authorized. Execution results and staged visual/audio review are pending; this record does not claim conversion has run.

## Staging validation result received

Tom supplied the FlightSim validated.json output for the authorized attempt. Source vid-c57dbd21f993f6d1 retained SHA256 26f3646b4adbda7573ff19c02da3b11bafceff4ac5cd7d967d5b0053a2e10705; source_unchanged=true and full_decode_passed=true. Staged output: 229,993,314 bytes, SHA256 ca206513d69bb08f499df0b26a6646e438061dbbdce1579cae48aef643027f90, H.264 High/yuv420p 1280x720, 33,120 video frames, 1,105.104 seconds starting at zero. AAC mono 24 kHz audio has 25,900 packets and duration 1,105.066667 seconds. Packet validation completed. These are helper results supplied by the operator, not an independent agent runtime inspection.

Next: Tom opens the existing staged.mp4 in a local player and verifies moving picture, orientation and audio sync near beginning, middle (~09:12) and end (~18:00), plus normal seeking. Publication and MB playback proof remain pending and are not authorized by this validation report. Do not rerun encoding. No app redeployment is needed for this documentation update.

## Owner staged review passed

Tom reported "all passed" after the requested staged-copy checks for moving picture, orientation, sound/lip-sync at beginning, middle and near end, and backward/forward seeking. Visual review reference: `Tom-staged-visual-audio-seek-pass-2026-09-05`. This applies to the already validated staged output SHA256 ca206513d69bb08f499df0b26a6646e438061dbbdce1579cae48aef643027f90 for source vid-c57dbd21f993f6d1. No second encode is needed or authorized. Publication remains a separate decision: the prepared helper will revalidate and atomically link that existing copy at browser_proxies/edda398dc1204bb272364d87.mp4, refusing an existing destination. MB source seek, natural playback beyond relevance intervals and Gallery return must then be checked in the application. No publication occurred in recording this result.
