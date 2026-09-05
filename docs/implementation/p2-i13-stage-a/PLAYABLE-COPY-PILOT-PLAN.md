# Bounded playable-copy pilot - proposal

Tom requested proceeding with a plan after the unavailable-copy screenshot. This authorizes plan preparation, not media conversion. No source processing, application changes, runtime writes, deletion, or conversion occurred in preparing this plan.

## Exact first source

The screenshot identifies hvrt source `vid-c57dbd21f993f6d1`. The accepted 22-source manifest identifies it as `20111105_1532.MP4`, 1,251,525,801 bytes, 1,105.104 seconds (18:25.104), SHA256 `26f3646b4adbda7573ff19c02da3b11bafceff4ac5cd7d967d5b0053a2e10705`. These are recorded inventory values, pending live revalidation.

This is distinct from the previously inspected `vid-8163a680131fd30a` / Grandpa sessions 003.MP4. Its mp4v codec finding must not be attributed to the screenshot source. No codec or current cache failure cause is asserted for the screenshot source yet. The unavailable UI confirms that the existing playback path did not produce a usable copy; it does not prove that all such files share a codec or are duplicates.

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
