# MBBS-P2 Increment 9 — Spoken Moments

**Document:** MBBS-P2 Increment 9 Definition  
**Version:** v1.1  
**Status:** **ACCEPTED** 2026-08-20 (Tom: “i9 is accepted”) — founder locks ingested 2026-08-19; runtime authorized 2026-08-20  
**Lineage:** Product body from `docs/source/MBBS-P2_INCREMENT_9_DEFINITION_v1.0_APPROVED.md` at `bfbba2fd9d71a36b452fae378e3d612d7a871bbb` (`cursor/marvin-capture-v01-3344`). This v1.1 records founder locks that close §14 of v1.0.  
**Roadmap placement:** After **P2-I8A** (ACCEPTED 2026-08-19) and **P2-I8B** Person-Seeded Video Recognition & Learning. **I9 runtime authorized 2026-08-20 and ACCEPTED 2026-08-20.** Next definition is **P2-I10**. I8.5 Face-SoT stays later.

## Founder locks (2026-08-19)

These are product locks. Tom authorized I9 **runtime** 2026-08-20.

1. **I8B coexistence.** I9 does not reopen I8B. Face ranges are optional context only. I8B founder ACCEPTED remains a separate owner gate.
2. **Local diarization.** Diarization must be local and must preserve anonymous/unknown speakers. Cursor may choose WhisperX/pyannote or an equivalent local engine based on repo/host compatibility and quality. Do **not** weaken required behavior merely to avoid an additional model dependency.
3. **Video speech only.** Standalone audio-only sources are **OUT** of I9 (cassettes, voice memos, capture-journal STT). Do not expand unless explicitly authorized later.
4. **Learn UX.** Owner Learn shall reuse existing MemoryBox **Choose a person… + Learn** applied to a selected transcript span. Do not create a separate speaker-management product.
5. **Semantic retrieval is evidence-first.** Transcript embeddings/Qdrant plus MBQL Person/intent constraints. Residual chat/model reasoning may assist query interpretation but shall **not** replace retrieval against authentic transcript evidence.
6. **Three distinct concepts** (where supported): **word-level timing**, **diarized speaker turns**, and **Spoken Moments / result spans**.
7. **Acceptance corpus.** Reuse a controlled subset of known I8B videos where practical. Face evidence remains **optional supporting context only** (never automatic proof that an anonymous speaker is that Person).

**P2-I8A** Unified Communications is already **ACCEPTED**. That does not authorize I9 build.

---

## 1. Purpose

P2-I9 turns spoken content inside MemoryBox **video** into first-class, time-addressable, searchable evidence.

MemoryBox shall transcribe speech from configured **video** sources, align transcript text to source-video timestamps, separate speaker turns where possible, allow the owner to teach a canonical MemoryBox Person from a clean spoken passage, derive reusable MemoryBox-owned voice evidence, and retrieve exact authentic spoken passages by Person, phrase, or subject.

I9 is not a transcription application and is not a narrative-generation increment. Its product outcome is that a family member can find and hear the actual moment when a real Person said something.

## 2. Product Outcome

After I9, MemoryBox can answer questions such as:

- **Peggy saying “I love you.”**
- **Show me Peggy talking.**
- **Peggy talking about Christmas.**
- **My dad saying “shit.”**
- **Find where Peggy talks about her mother.**

A successful result is not merely a video file. It is a specific authentic spoken passage with:

- source video;
- start/end time;
- synchronized transcript;
- speaker identity when known with sufficient confidence;
- provenance/confidence;
- direct playback beginning at or near the relevant spoken moment.

## 3. Why I9 Exists Now

I8B operationalizes Person recognition and time-bounded appearance evidence in video. I9 adds the spoken-content layer.

Before I9, MemoryBox may know that a Person appears in a video and may be able to jump to an appearance range. It does not yet operationally know:

- what was said;
- exactly when it was said;
- which anonymous speaker turn corresponds to which canonical Person;
- how to teach a Person’s voice from a real video passage;
- how to reuse that voice evidence across other video;
- how to retrieve authentic passages by phrase or semantic subject.

I9 supplies that capability without pulling forward I10 cross-modal correlation or I11 evidence-backed narrative generation.

## 4. Governing Architecture

### 4.1 Original media remains the source of truth

The original video stream (including its audio) is immutable evidence.

Transcripts, diarization, speaker identity assignments, voice embeddings, and spoken moments are derived, rebuildable evidence with provenance.

A transcript must never replace the original voice. A retrieved spoken result must always be traceable back to the authentic recording.

### 4.2 Timestamped transcript, not a detached document

The I9 transcript is a synchronized representation of spoken content tied to source media time.

Every transcript unit used for retrieval must preserve source media ID, start/end offset, text, transcription provider/model/version, confidence where available, and processing provenance.

The transcript is experienced inside Video Detail through the **Text** pill (or the existing equivalent control) and follows playback time.

### 4.3 Three layers: words, turns, moments

Where supported, I9 shall preserve three distinct concepts:

1. **Word-level timing** — what was spoken, aligned to source time (transcription).
2. **Diarized speaker turns** — which **anonymous** speaker produced a stretch of speech (Speaker A / B / unknown). Diarization precedes Person identity.
3. **Spoken Moments / result spans** — the retrievable passage shown in Ask/Explore (may group or clip turns; always plays authentic source at `t=`).

A turn may therefore initially be:

> Speaker A — “We used to go there every Christmas.”

without MemoryBox claiming that Speaker A is Peggy.

Unknown and uncertain speaker identity must remain explicit until evidence supports assignment.

### 4.4 Voice learning uses source audio, not transcript words

The owner teaches a Person by selecting a clean spoken interval in the synchronized transcript, using existing **Choose a person… + Learn** (not a new speaker product).

That transcript selection resolves to source-media timestamps. MemoryBox then uses the corresponding original **video audio** interval to create voice-recognition evidence.

Flow:

> selected transcript span → timestamp range → source audio interval → owner assigns canonical Person → Learn → MemoryBox voice exemplar/embedding → targeted speaker recognition

Text itself is never treated as a voiceprint.

### 4.5 MemoryBox owns voice evidence

Voice exemplars, embeddings, speaker observations, Person assignments, corrections, and Spoken Moments produced by I9 are MemoryBox-owned derived evidence.

They must preserve model/version and owner/system provenance.

### 4.6 Visual Person evidence is optional supporting evidence only

I9 may use I8B appearance ranges and other available contextual evidence to assist speaker review or confidence.

A speaker may be identified, taught, and recognized from audio even when that Person is **not visible in the frame**. For example, if Dad is on camera speaking with Peggy off camera, Peggy’s transcribed spoken passage may still be selected, assigned to Peggy, and used as an owner-confirmed voice-learning exemplar.

The mere presence of Peggy’s face in the same video/time range does **not** automatically prove that an anonymous speaker is Peggy, and the absence of Peggy’s face does **not** prevent voice identification.

Active-speaker/lip-sync analysis is not required for I9 acceptance.

### 4.7 Local speech stack

Transcription and diarization run **locally**. Cloud STT is not the I9 product path.

Diarization must preserve anonymous/unknown speakers. Engine choice (WhisperX, pyannote, or equivalent local stack) is an engineering decision **provided** quality and anonymous-speaker behavior are not weakened to avoid a model dependency.

### 4.8 Semantic retrieval is evidence-first

Ask/MBQL may use residual model fill only to interpret intent (same MBQL/I7A contract as other asks).

Retrieval of “talking about Christmas” (and similar) shall hit **authentic transcript evidence**: indexed transcript text and **transcript embeddings in Qdrant** (derived), constrained by canonical Person when requested. Residual chat shall not invent or rank passages that are not grounded in stored transcript evidence.

## 5. In Scope

### 5.1 Initial transcription pass

I9 shall support a controlled initial/background pass over the configured acceptance video corpus and then over eligible configured **video** sources.

For each eligible video:

1. discover the source video;
2. obtain/extract the audio stream from that video;
3. detect speech;
4. transcribe speech with timestamp alignment (word-level where the engine supports it);
5. diarize speaker turns locally, keeping unknown/anonymous IDs;
6. persist transcript units, turns, and processing provenance;
7. index transcript content for exact and semantic retrieval;
8. expose processing status/failure information.

### 5.2 Ongoing processing for newly added video

After the initial pass, newly discovered or changed eligible **videos** shall be processed by durable background work.

Operational behavior shall support initial backlog processing, incremental new-video processing, retry of failed work, no-op for unchanged completed media, and targeted reprocessing when needed.

The intended operating pattern is compatible with an overnight/background job for newly added video. Queue identity is **per video** for transcription (not people × every file). Learn-triggered work is **that Person’s** eligible speaker turns/videos, current video first.

### 5.3 Synchronized Text view in Video Detail

Video Detail shall expose a **Text** pill or equivalent existing MemoryBox detail control.

When selected:

- timestamped transcript text is displayed with the video;
- transcript position follows the current video timestamp;
- current spoken passage remains visible as playback advances;
- clicking/selecting transcript text may seek the video to that time;
- pausing stabilizes the transcript for review/teaching;
- context-return behavior follows existing MBUX rules.

I9 shall not create a separate transcription application.

### 5.4 Transcript interval selection

While paused, the owner shall be able to select a spoken passage using mouse selection and keyboard refinement sufficient to establish a clean start/end interval.

The interaction must make it practical to isolate one speaker’s voice and avoid contaminating a training sample with overlapping speakers.

Mouse selection plus arrow-key boundary refinement is the intended baseline.

### 5.5 Owner Learn — voice

Reuse existing MemoryBox **Choose a person… + Learn**. No separate speaker-management product.

For a sufficiently clean selected spoken interval:

1. owner pauses the source video;
2. owner selects/refines the transcript interval;
3. owner assigns an existing canonical MemoryBox Person (empty dropdown until chosen);
4. owner invokes **Learn**;
5. MemoryBox resolves the selection to original video-audio timestamps;
6. MemoryBox persists an owner-confirmed voice exemplar with provenance;
7. MemoryBox generates its own voice embedding/representation from that audio;
8. the exemplar becomes reusable for recognition;
9. MemoryBox runs recognition on the **current video** first;
10. MemoryBox enqueues other eligible speaker segments/videos for **that Person** by priority;
11. new Person-linked speaker observations/Spoken Moments become available for retrieval.

### 5.6 Speaker recognition

I9 shall compare diarized speaker segments against known MemoryBox voice exemplars.

Recognition shall support at least:

- confirmed Person;
- sufficiently high-confidence system-recognized Person;
- uncertain/review state;
- unknown speaker.

The system must not force a Person when signal is weak, ambiguous, overlapping, or inconsistent.

### 5.7 Targeted recognition after Learn

A Learn action must not require a blocking full-library rescan.

Default behavior:

1. process the current video first for immediate feedback;
2. enqueue other eligible speaker segments/videos for that Person by priority;
3. allow broader background recognition asynchronously.

### 5.8 Corrections and negative evidence

I9 must support enough correction behavior to make voice identity safe:

- incorrect speaker→Person assignment can be corrected or removed;
- rejected identity evidence is retained as correction/negative evidence;
- later automated processing must not silently recreate a rejected assignment from the same evidence;
- owner-confirmed identity outranks weaker inference;
- uncertain segments may remain unassigned;
- targeted reprocessing can update affected assignments/Spoken Moments.

### 5.9 Exact phrase retrieval

MemoryBox shall support spoken passage retrieval constrained by canonical Person and exact or near-exact transcript content.

Examples:

- `Peggy saying "I love you"`
- `My dad saying "shit"`

A successful result returns the specific spoken passage(s), not merely the containing file.

### 5.10 Person-speaking retrieval

MemoryBox shall support:

- `Peggy talking`
- `Show me everything Peggy says`

Results shall return Person-linked spoken passages or appropriately grouped Spoken Moments.

### 5.11 Semantic subject retrieval

MemoryBox shall support semantic retrieval over **stored transcript evidence**, constrained by Person where requested.

Example:

> `Peggy talking about Christmas`

may match passages discussing Christmas-related ideas even when the exact word “Christmas” is absent, **only if** those passages exist in the transcript index/embeddings.

MBQL/residual interpretation may help compile the ask. It must not substitute generated paraphrase for missing evidence.

### 5.12 Spoken Moment semantic concept

The exact schema is implementation-owned, but I9 requires a durable **Spoken Moment** concept with:

- source media ID (video);
- start/end offsets;
- transcript segment and/or word-range references;
- diarized speaker ID/cluster (anonymous until identified);
- canonical Person ID when known;
- speaker confidence/state;
- voice exemplar/model/version provenance;
- transcription/diarization provenance;
- correction/review state;
- playback/jump target.

Spoken Moments are the **result span**, distinct from word tokens and from raw diarized turns.

### 5.13 Lightweight transcript correction

I9 should support lightweight correction of obvious transcript errors where practical.

Corrections preserve original machine transcript, corrected text, who/what corrected it, timestamp alignment, and provenance.

I9 does not require a full transcript editor.

### 5.14 Non-verbal vocal events

I9 may retain non-verbal vocal events such as laughter, crying, or singing where the selected transcription/diarization stack reliably emits them.

Queries such as `Peggy laughing` may be supported when sufficient speaker/context evidence exists.

Identifying a Person solely from an isolated laugh/cry/non-speech vocalization is **not** an I9 acceptance requirement.

### 5.15 Processing visibility

The owner/developer path shall expose enough status to determine video transcription state, diarization state, voice-learning/recognition state, pending/running/completed/failed work, failure reason, useful counts, and run kind.

I9 may reuse existing Archive Health/developer patterns. Transcription queue must not cartesian-expand people × every video.

## 6. Explicitly Out of Scope

I9 does **not** include:

- standalone audio-only ingest (cassettes, voice memos, capture-journal STT as Spoken Moments);
- synthetic voice cloning;
- generating speech in the voice of a deceased or living family member;
- reconstructing words a Person did not actually say;
- narrative generation from transcripts;
- broad life-story summarization;
- I10 cross-modal event correlation;
- I11 evidence-backed family narrative generation;
- replacing original audio/video with transcript;
- a standalone transcription application;
- a separate speaker-management / voice-gallery product;
- a full-feature transcript editor;
- general-purpose audio production/editing;
- mandatory identification from laughter alone;
- mandatory active-speaker/lip-sync inference;
- full voice-biometric research beyond usable family speaker recognition;
- processing the entire production archive as a prerequisite for acceptance;
- music listening-history / playlist EVS (EVS-064, EVS-123, EVS-243) unless later authorized.

## 7. Trust and Provenance Rules

1. Original recorded video (with its audio) is the source of truth.
2. Transcript text is derived evidence and may contain errors.
3. Word timing, diarized speaker identity, and canonical Person identity are separate concepts.
4. Unknown or uncertain speakers remain unknown/uncertain.
5. Owner-confirmed speaker identity outranks weaker system inference.
6. Corrections/negative evidence must be preserved and respected.
7. Every transcript segment preserves source timestamps and model provenance.
8. Every voice exemplar preserves source media/time and owner/system provenance.
9. Every recognized Person assignment preserves confidence/model provenance.
10. MemoryBox must never imply that a Person spoke words unless source passage and identity evidence support the claim.
11. MemoryBox shall not synthesize a Person’s voice as part of I9.
12. Search results must remain reachable back to authentic source evidence.
13. Face appearance in the same timeslot is optional context, not identity proof.
14. Semantic Ask results must cite stored transcript evidence.

## 8. Required Data / Service Concepts

### 8.1 Word / transcript timing unit

Where the engine supports it: source video ID, word or token text, start/end offsets, transcription model/version, confidence.

### 8.2 Diarized speaker turn

Anonymous speaker/cluster ID, source video ID, start/end, linked transcript units, diarization model/version. Person ID is null until assignment.

### 8.3 Transcript segment (retrieval/display grain)

May alias or group words/turns for the Text view. Preserves original vs corrected text, provenance, correction state.

### 8.4 Voice exemplar

Canonical Person ID; source video ID; start/end; audio excerpt/reference; owner/system source type; voice embedding/model/version; quality metadata; active/withdrawn; provenance.

### 8.5 Speaker observation / assignment

Source video ID; turn and/or segment ID; anonymous diarized speaker ID; candidate/assigned Person ID or null; confidence; supporting exemplar/model; review/correction state; provenance.

### 8.6 Spoken Moment

Result span: source video ID; start/end; transcript references; Person ID when known; speaker state/confidence; searchable/indexed text; playback target; provenance.

### 8.7 Processing run / queue state

Must distinguish initial transcript pass, new-video processing, Learn-triggered recognition, correction-triggered reprocessing, model/version-triggered reprocessing, and retry after failure. Unchanged completed videos are no-ops.

## 9. Operational Flow

### 9.1 Initial / incremental transcription

Eligible **video**  
→ extract audio from that video  
→ speech detection  
→ timestamped transcription (word-level where supported)  
→ local diarization (anonymous turns)  
→ persist words / turns / segments  
→ index exact text + transcript embeddings  
→ expose in synchronized Text view

### 9.2 Owner voice Learn

Video Detail  
→ Text  
→ pause video  
→ select/refine clean spoken passage  
→ **Choose a person… + Learn** (existing interaction)  
→ resolve timestamps to original video audio  
→ persist owner-confirmed voice exemplar  
→ generate MB voice embedding  
→ current-video recognition  
→ prioritized background recognition for that Person  
→ Person-linked speaker observations  
→ Spoken Moments

### 9.3 Retrieval

Ask / `compile_ask`  
→ canonical Person resolution when requested  
→ phrase / talking / semantic-subject constraints  
→ retrieve matching Spoken Moments from transcript evidence (SQL + Qdrant embeddings)  
→ display evidence-backed results  
→ open exact source passage  
→ playback at relevant timestamp

## 10. Query / MBQL Behavior

I9 shall extend existing shared Ask/Explore state rather than create a new spoken-search application. Later STT still calls `compile_ask`.

Required intent families include:

### Exact phrase
- `Peggy saying "I love you"`
- `Dad saying "shit"`

### Person speaking
- `Peggy talking`
- `Show me Dad talking`

### Semantic subject
- `Peggy talking about Christmas`
- `Dad talking about the war`

Where intent is to hear the passage, result actions use existing PLAY/open-at-time behavior.

Person ambiguity uses existing canonical Person lock/clarify rules. MemoryBox must not substring-union unrelated People.

Residual model fill may interpret the ask. Retrieval remains evidence-first against transcripts.

## 11. UX Requirements

1. Transcript lives in Video Detail, not a separate application.
2. **Text** is the primary transcript reveal control.
3. Transcript scroll/focus follows current playback timestamp.
4. User can pause and select a clean spoken passage.
5. Mouse selection plus keyboard/arrow refinement is the intended baseline.
6. **Choose a person… + Learn** is available on that span without leaving video context and without a new speaker product.
7. Unknown speaker state must be understandable.
8. Corrections should feel like teaching MemoryBox, not database maintenance.
9. Opening a Spoken Moment jumps to authentic recording at the right time.
10. Returning from detail preserves prior Ask/Gallery/Timeline state.

## 12. Acceptance Gate

I9 is accepted only when demonstrated on real FlightSim **video** data, **after I8B is founder ACCEPTED** and I9 build has been explicitly authorized.

### A. Transcription

1. A controlled multi-video acceptance corpus is processed.
2. Speech is converted to timestamped transcript text (word-level where supported).
3. Transcript units remain traceable to source video/time.
4. Newly added eligible video can be processed incrementally without retranscribing unchanged video.
5. Failed transcription work is visible and retryable.

### B. Synchronized Text experience

1. Video Detail exposes Text.
2. Transcript follows playback time.
3. User can click/select transcript and navigate to corresponding video time.
4. Paused selection can be refined sufficiently for clean voice teaching.

### C. Diarization

1. Multi-speaker video produces distinct anonymous speaker turns where supported.
2. Unknown speakers remain anonymous before identity teaching.
3. Diarization errors do not force false Person identity.
4. Diarization is local.

### D. Owner Learn

1. Owner selects a clean spoken interval.
2. Owner assigns a canonical MemoryBox Person via existing Choose Person + Learn.
3. Learn persists a reusable owner-confirmed voice exemplar from **source audio**.
4. MemoryBox generates its own voice representation.
5. Current-video recognition runs first.
6. Additional eligible work is queued for that Person only (prioritized background).

### E. Voice recognition

1. Learned Person is correctly recognized in at least one additional valid spoken segment when suitable evidence exists.
2. At least one negative/control speaker remains unassigned or is not falsely assigned.
3. Confidence/unknown behavior is visible and trustworthy.
4. Recognition provenance/model version is preserved.
5. Overlapping I8B face ranges are not treated as automatic speaker proof.

### F. Correction safety

1. A deliberately wrong speaker→Person assignment can be corrected/removed.
2. Reprocessing does not silently restore the rejected assignment from the same evidence.
3. Uncertain identity can remain unassigned.

### G. Retrieval

Demonstrate:

1. **Exact phrase:** query equivalent to `Peggy saying "I love you"` returns authentic matching passage when it exists.
2. **Person speaking:** query equivalent to `Peggy talking` returns Person-linked spoken passages.
3. **Semantic subject:** query equivalent to `Peggy talking about Christmas` retrieves relevant authentic passages from **transcript embeddings/index**, not from ungrounded chat.

Opening any result plays the correct source video at or near the relevant spoken timestamp.

### H. Non-verbal behavior

If laughter or another non-verbal vocal event is detected, MemoryBox may retain/retrieve it, but acceptance does not require identifying a Person solely from isolated non-speech sound.

### I. Scale proof

Acceptance shall use a **controlled subset**, not the complete video archive.

Reuse a controlled subset of **known I8B videos** where practical (Peggy George plus one additional Person, negative/control, multi-speaker if available), plus:

- approximately **5–8 videos**;
- approximately **30–90 minutes total runtime**;
- preferably individual files under approximately **20 minutes**;
- more than one known speaker;
- at least one negative/control segment/video;
- at least one multi-speaker example;
- at least one clean owner-Learn passage;
- at least one additional occurrence suitable for recognition;
- enough recording-quality variation to expose obvious weaknesses.

Full-archive transcription/voice-recognition rollout occurs only after I9 acceptance and operational confidence.

## 13. Critical Success Factors

1. **The result is a passage, not merely a file.**
2. **Timestamp alignment is trustworthy.**
3. **Words, turns, and Spoken Moments stay distinct.**
4. **Diarization precedes identity; unknown stays unknown.**
5. **Learn uses real video audio and existing Choose Person + Learn.**
6. **Voice teaching is reusable.**
7. **Corrections stick.**
8. **Search is evidence-first (exact words and meaning from transcripts).**
9. **Playback is immediate and authentic.**
10. **Incremental per-video processing works (no people×archive cartesian).**
11. **I9 does not synthesize family voices.**
12. **I9 does not become I10/I11 or a transcription app.**
13. **I9 does not ingest standalone audio.**
14. **The UX remains MemoryBox.**

## 14. Implementation planning (closed)

v1.0 §14 founder questions are **closed** by the locks at the top of this document. Remaining work is engineering after **this definition is approved**, **I8B is ACCEPTED**, and **Tom explicitly authorizes the I9 build**.

Code-grounded assessment (2026-08-19, I8B tree): Explore Transcript control is a placeholder; capture `faster_whisper` is not Spoken Moments; HVRT `voice_learn.py` (ffmpeg + ECAPA) is the POC to promote into Postgres; I8B `recognition_queue` is the durable-job pattern but must **not** be reused as people×every-video; Qdrant today indexes communications Evidence — I9 adds derived transcript embeddings; MBQL `compile_ask` must gain saying/talking/about intents.

## 15. Hold / build authorization

v1.1 locks stand. **I9 build authorized** 2026-08-20 (Tom). Runtime may proceed on a dedicated I9 branch. Do not cartesian people × videos. Do not ingest cassettes/memos. **ACR-P2-001-A** continue-on-tape is not I9.
