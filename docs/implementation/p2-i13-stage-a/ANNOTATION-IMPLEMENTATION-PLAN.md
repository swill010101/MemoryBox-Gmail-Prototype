# Next I13 slice: annotation without processing

## Current decision

Tom accepted the modal correction at 33eff43d34ecf1d4314509519bd4549a66f1befe and directed moving to the next step. Record acceptance of that correction by owner report, not independent runtime measurement or full I13 acceptance. The two-source playback/presentation pilot is complete for its reviewed scope. Other sources remain outside that projection.

The next preparation step is an annotation-only implementation slice. Existing timestamped transcripts allow owner review without a new recognition run. Do not require Tom to watch videos and manually write timestamp/name worksheets. The exact 22-source membership remains the corpus boundary; do not substitute a local directory.

## Confirmed blockers from code inspection

- explore.js exposes highlighted transcript selection and Person choice, but its save path is /speech/learn.
- speech/learn.py owner_learn_voice embeds audio, persists an exemplar, assigns turns, recognizes the current source and queues other sources. It cannot serve as an annotation-only save.
- speech/store.py assign_turn_person updates machine turn and moment identity fields.
- speech/store.py replace_video_transcript deletes existing words/turns and eligible moments before inserting replacements. A new transcription run would conflict with the accepted immutable-machine-transcript requirement.

Do not start the historical 22-item transcription preview unchanged merely because the locked deployment passed. First reconcile this persistence behavior. Selection working in the browser does not prove annotation was saved.

## Concrete implementation sequence for review

1. Add an append-only owner annotation model referencing provider/source, machine transcript version/run and exact word IDs. Derive interval boundaries on the server from those words; validate source membership, canonical Person and owner authority. Represent unknown/no-match explicitly. Record actor, timestamp, request identity and superseded annotation; retain revisions and withdrawals. Reject stale/conflicting revisions rather than silently overwriting them.
2. Add a separate annotation API and explicit Save assignment action using the existing highlighted-text/Choose Person workflow. Saving must neither embed audio nor create exemplars, enqueue work, invoke recognition/transcription or enable drains. Keep Learn separate and locked. Preserve selection, source playback and Gallery return.
3. Return immutable machine text/attribution alongside an effective owner-overlay view for display and search. Text corrections must be additive, distinguishable and auditable. Resolve overlapping active revisions deterministically; no partial silent assignment of neighboring words/turns. Owner speaker assignment is truth, not proof of model recognition.
4. Preserve transcript versions before exposing any later transcription start. New machine runs append versions; historical transcript rows are not rewritten/deleted. Existing version identity must remain addressable by annotations. Specify explicit current-version selection and stale annotation behavior rather than automatically carrying truth to different words.
5. Export reviewed truth and coverage for the exact corpus from MB. Include provenance, unknown/no-match and unreviewed coverage. Do not claim completeness merely because an annotation exists for a source. Prepare a read-only coverage inventory before deciding whether any new transcript evidence is needed.
6. Validate migration and integration on a disposable database and synthetic fixtures. Author an additive migration only after checking current repository numbering and FlightSim schema history; do not apply it to runtime as part of development. Preserve I12 Capture.
7. Submit exact code SHA, test/browser evidence and complete detached-release deployment commands for review. Tom operates FlightSim. Migration/deployment and any later bounded processing require their own concrete run instructions; this proposal executes none.

## Acceptance for this slice

- Highlight existing timed words, choose a Person, Save assignment, reopen and observe the saved effective attribution.
- Correct text/Person, withdraw and inspect history; original machine words and timestamps remain unchanged.
- API rejects off-manifest sources, mismatched word/source/version, invalid Person, stale revision and unauthorized requests. Repeated request is idempotent.
- Saving produces zero embedding, recognition, transcription, queue or exemplar writes; processing locks remain enforced.
- Search and display consistently use effective overlays with traceable machine provenance.
- Transcript bottom remains reachable, selection works, source seek continues naturally, and Gallery context returns unchanged.
- Export represents reviewed and unreviewed coverage honestly.

Voice acceptance remains mandatory in a later separately bounded learning/recognition proof: actual audio-based suggestions, off-camera speech without face presence, uncertain/no-match cases, independent face/voice evidence and model/threshold provenance. Exemplar retirement must stop future use, preserve history, stale dependent suggestions and constrain separately authorized reprocessing. This annotation slice alone does not satisfy those requirements.

## Review boundary

Prepared from repository inspection only; no runtime query, migration, processing, media change or application edit was performed for this plan. Request implementation approval for steps 1-6 before expanding beyond Stage A's existing implementation scope. Existing ANNOTATION-WORKFLOW.md explicitly reserves this workflow for a subsequent authorized stage. Keep the accepted locked release running meanwhile.
