# Pipeline inventory

All paths refer to the accepted baseline. Function names are searchable anchors; schema/index and API line references are in `schema-api-inventory.md`. Runtime deployment may differ.

## Source and provider boundaries

| Layer | Locations and behavior | Assessment |
|---|---|---|
| Source inventory | `memorybox/video_worker/__init__.py`: `_scan_videos`, `_stable_video_id`, `_alias_ids`; `recognition/inventory.py`; `recognition/archive_pass.py:combined_eligible_videos` | Owned-folder IDs hash relative paths, with historical aliases; rename/provider collision reconciliation needed. Worker inventory returns duration None. Reachable-file discovery is not corpus authorization. |
| Provider objects | `providers/video/dto.py`, `protocol.py`, `hvrt_http.py`, `fake.py`; Immich `_immich_http.py`; `recognition/origin.py` | Provider ID, source locator, date/filename and time links exist; no stable-source registry invariant across all derivative stores. Immich recognition hints are read into MB evidence; no I13 writeback should be added. |
| Playback/media | `app.py:/review/media`, `/library/media/immich-video`, video-poster and browser-proxy routes; `video_worker/browser_proxy.py`; `speech/media.py`; `recognition/frames.py` | Original/provider or full-source compatibility proxy paths. Poster extraction and proxy generation write caches; excluded from assessment execution. |
| Legacy HVRT | `hvrt/scripts/review_app.py`; `hvrt/hvrt/schema_r2.py`, `face_learn.py`, `voice_learn.py`, `annotations.py`, `rescoring.py`, `learning.py`, `process_jobs.py` | Separate SQLite evidence/learning system, including annotations and effective evidence. Do not conflate legacy integer IDs with MB UUIDs or native worker `vid-*` IDs. README refers to `scripts/process_videos.py`, absent from this baseline; original ingestion producer is not fully assessable. |

## Recognition data and execution

PostgreSQL migrations 008, 011, 012 supply provider-person sync history, face evidence, queue items, appearance moments, processing runs, frame observations, identity withdrawals, pending review crops, and person watermarks. The generated inventory lists all their declared indexes. Queue uniqueness is Person/provider/video/enqueue reason, not pipeline/model/parameter observation uniqueness. Observation/appearance tables have lookup indexes and UUID primary keys, not semantic uniqueness constraints.

`recognition/seed.py` selects Immich face candidates; `exemplars.py` selects diverse/nonduplicate evidence, stores vectors/model/quality and filters withdrawn evidence. `crops.py`, `embeddings.py`, and `frames.py` parse/quality-check crops and sample frames through InsightFace. `scan.py:scan_video_for_person` scores one Person's exemplars, applies withdrawals, persists observations, and groups assigned samples at an eight-second gap. It is sample grouping, not a proven track-continuity/occlusion system. Shared unknown observations are deleted during per-person rebuild, and cleanup ignores the supplied provider key. `providers/video/merge.py` separately merges same-candidate presence spans at 60 seconds; Explore additionally deduplicates starts in 2.5-second slots and merges within eight seconds. Policies are distributed and not recorded as one versioned run configuration.

`recognition/learn.py:owner_learn_from_review` persists an exemplar, turns face_scan on, scans current source synchronously, and enqueues other inventory sources. `queue.py`, `process.py`, `archive_pass.py`, `drain.py` handle claiming, retry, incremental/full sweeps, and a background thread. `allowlist.py` is a **Person** opt-out, not an approved video corpus. Status aggregates are available but not a full owner Jobs contract. Native sample errors can be returned alongside completion; validate success semantics before trusting displayed counts.

Correction paths: `process.py:owner_correct_appearance`, `owner_withdraw_appearance`; `observations.py:record_withdrawal`; `exemplars.py:withdraw_exemplar`. These provide owner authority/withdrawal primitives but do not implement the complete reasoned reversible retirement, dependency-staleness, or immutable supersession lifecycle.

## Speech, voice and retrieval

Migration 013 declares processing runs, timestamped transcript words, anonymous/assigned turns, spoken moments with original text and Qdrant point references, voice exemplars, withdrawals, and separate transcription/Person-learning queue indexes. Migration 018 concerns authored Story speech provenance; it does not implement I13 source-video transcript overlays.

`speech/media.py` resolves source paths; `embeddings.py` extracts temporary WAV spans via ffmpeg and embeds with ECAPA. `transcribe.py` uses faster-whisper word timestamps and optional pyannote, otherwise explicitly labels pause-gap grouping. `process.py` creates one spoken moment per turn. `store.py:replace_video_transcript` deletes/replaces words and turns; assignment updates turns/moments in place. `learn.py` teaches a span, assigns overlapping turns, recognizes the current source and queues other eligible sources. `process.py:recognize_person_on_video` ignores face overlap as identity proof, but needs the fake-only embedding hook for turn matching. The legacy `hvrt/hvrt/voice_learn.py` has a different real-audio recognition implementation; reuse requires explicit ownership/lineage decisions, not silently routing MB writes into SQLite.

`speech/index.py` indexes `memorybox_spoken_moments` in Qdrant. `speech/retrieve.py:search_spoken_moments` supports phrase ILIKE, Person filtering, and lexical/semantic subject retrieval, re-fetching SQL rows to exclude withdrawn moments. `ask`/planner/MBQL retrieval consumes speech and appearance evidence; `explore/find.py` turns hits into video cards with source/time fields. Phrase escaping/boundaries, cross-turn phrases, invalid intervals, stale vectors, and ranking require bounded proof. Face and voice data are separate; transparent combined-confidence policy is not implemented.

## Consumers, jobs and derivatives

| Consumer/store | Inventory and gaps |
|---|---|
| Explore Gallery / video detail | `explore/static/explore.js`: `openModal`, `closeModal`, `submitExploreLearn`, `bindSpeechTranscript`, `bindAppearanceView`, timeline handlers. Existing filters, scroll state, Prev/Next, tabs, source player, crop selection, voice selection, and transcript click seeking should be reused. |
| Review / Person | `review/static/review.html`, `person/static/person-explore.js`, `person/face_evidence.py`, appearance APIs. Identity controls exist, but combined per-video speech/appearance adjudication needs extension. |
| Shared navigation / administration | `shell/static/shell.js:FAMILY/SYSTEM`; `status/static/status.html`, `settings/static/settings.html`, accepted `historian_capture/static/historian_capture.html`. No I13 Admin top-nav, unified Jobs or Learned Evidence destination. Link existing Historian Capture without changing its accepted workflow. |
| Native processing | Recognition and speech queue/process/run records; `speech/now.py` and drains. No common persisted manifest scope, accepted release gate, safe pause/resume protocol, or complete owner-facing Jobs reconciliation. |
| Legacy SQLite | Checkpoint schema includes videos, people, scenes, transcripts, transcript_segments, transcript_words, face_appearances, analysis_passes, jobs, annotations, evidence_effective, actors, places, decision_model, learning_runs, learning_run_steps, voice_samples. Legacy runtime indexes/producer history are not established by native migration inventory. |
| Files | Source sample videos; full-source browser proxies; face crops/gallery images; voice WAV exemplars and JSON metadata; temporary speech WAVs; model caches; native `detections.json`; poster caches. No generated file is deletion-eligible merely because it is short or lies in a working directory. |

## Screen comparison and verification limits

The five approved PNGs show Learn with distinct face/voice confirmation and transcript rows; People with separate appearance/speech and unknown observations; an Admin landing; persisted Processing Jobs with scope/release lock; and Learned Evidence with provenance/correction/reasoned retirement. Existing code implements only parts of the first two inside the shared evidence modal. It lacks the three Admin screens as specified. The contact sheet was visually inspected; the running UI was not launched or rendered. Consequently visual fidelity, accessibility, natural playback and navigation end-to-end remain unverified. No placeholder markup or passing unit check is counted as screen acceptance.
