# MBBS-P2 Increment 9 — Spoken Moments

**Document:** MBBS-P2 Increment 9 Definition  
**Version:** v1.0  
**Status:** APPROVED — Definition locked; NOT build-authorized  
**Roadmap placement:** Immediately after P2-I8B Person-Seeded Video Recognition & Learning.

## 1. Purpose

P2-I9 turns spoken content inside MemoryBox video into first-class, time-addressable, searchable evidence.

MemoryBox shall transcribe speech from configured video sources, align transcript text to source-video timestamps, separate speaker turns where possible, allow the owner to teach a canonical MemoryBox Person from a clean spoken passage, derive reusable MemoryBox-owned voice evidence, and retrieve exact authentic spoken passages by Person, phrase, or subject.

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

The original video/audio stream is immutable evidence.

Transcripts, diarization, speaker identity assignments, voice embeddings, and spoken moments are derived, rebuildable evidence with provenance.

A transcript must never replace the original voice. A retrieved spoken result must always be traceable back to the authentic recording.

### 4.2 Timestamped transcript, not a detached document

The I9 transcript is a synchronized representation of spoken content tied to source media time.

Every transcript unit used for retrieval must preserve source media ID, start/end offset, text, transcription provider/model/version, confidence where available, and processing provenance.

The transcript is experienced inside Video Detail through the **Text** pill and follows playback time.

### 4.3 Speaker diarization precedes Person identity

I9 shall distinguish:

1. **speech transcription** — what was spoken;
2. **speaker diarization** — which anonymous speaker turn produced the speech;
3. **speaker identification** — which canonical MemoryBox Person, if any, produced that turn.

A segment may therefore initially be:

> Speaker A — “We used to go there every Christmas.”

without MemoryBox yet claiming that Speaker A is Peggy.

Unknown and uncertain speaker identity must remain explicit until evidence supports assignment.

### 4.4 Voice learning uses source audio, not transcript words

The owner teaches a Person by selecting a clean spoken interval in the synchronized transcript.

That transcript selection resolves to source-media timestamps. MemoryBox then uses the corresponding original audio interval to create voice-recognition evidence.

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

## 5. In Scope

### 5.1 Initial transcription pass

I9 shall support a controlled initial/background pass over the configured acceptance video corpus and then over eligible configured video sources.

For each eligible video:

1. discover the source video;
2. obtain/extract the audio stream;
3. detect speech;
4. transcribe speech;
5. retain timestamp alignment;
6. diarize speaker turns where technically available;
7. persist transcript/speaker segments;
8. index transcript content for exact and semantic retrieval;
9. expose processing status/failure information.

### 5.2 Ongoing processing for newly added video

After the initial pass, newly discovered or changed eligible videos shall be processed by durable background work.

Operational behavior shall support initial backlog processing, incremental new-video processing, retry of failed work, no-op for unchanged completed media, and targeted reprocessing when needed.

The intended operating pattern is compatible with an overnight/background job for newly added video.

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

For a sufficiently clean selected spoken interval:

1. owner pauses the source video;
2. owner selects/refines the transcript interval;
3. owner assigns an existing canonical MemoryBox Person;
4. owner invokes **Learn**;
5. MemoryBox resolves the selection to original audio timestamps;
6. MemoryBox persists an owner-confirmed voice exemplar with provenance;
7. MemoryBox generates its own voice embedding/representation;
8. the exemplar becomes reusable for recognition;
9. MemoryBox launches targeted recognition work against eligible diarized speaker segments;
10. new Person-linked speaker observations/Spoken Moments become available for retrieval.

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

MemoryBox shall support semantic retrieval over transcript content, constrained by Person where requested.

Example:

> `Peggy talking about Christmas`

may match passages discussing Christmas-related ideas even when the exact word “Christmas” is absent.

### 5.12 Spoken Moment semantic concept

The exact schema is implementation-owned, but I9 requires a durable **Spoken Moment** concept with:

- source media ID;
- start/end offsets;
- transcript text or transcript-segment references;
- diarized speaker ID/cluster;
- canonical Person ID when known;
- speaker confidence/state;
- voice exemplar/model/version provenance;
- transcription/diarization provenance;
- correction/review state;
- playback/jump target.

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

I9 may reuse existing Archive Health/developer patterns.

## 6. Explicitly Out of Scope

I9 does **not** include:

- synthetic voice cloning;
- generating speech in the voice of a deceased or living family member;
- reconstructing words a Person did not actually say;
- narrative generation from transcripts;
- broad life-story summarization;
- I10 cross-modal event correlation;
- I11 evidence-backed family narrative generation;
- replacing original audio/video with transcript;
- a standalone transcription application;
- a full-feature transcript editor;
- general-purpose audio production/editing;
- mandatory identification from laughter alone;
- mandatory active-speaker/lip-sync inference;
- full voice-biometric research beyond usable family speaker recognition;
- processing the entire production archive as a prerequisite for acceptance.

## 7. Trust and Provenance Rules

1. Original recorded audio/video is the source of truth.
2. Transcript text is derived evidence and may contain errors.
3. Diarized speaker identity and canonical Person identity are separate concepts.
4. Unknown or uncertain speakers remain unknown/uncertain.
5. Owner-confirmed speaker identity outranks weaker system inference.
6. Corrections/negative evidence must be preserved and respected.
7. Every transcript segment preserves source timestamps and model provenance.
8. Every voice exemplar preserves source media/time and owner/system provenance.
9. Every recognized Person assignment preserves confidence/model provenance.
10. MemoryBox must never imply that a Person spoke words unless source passage and identity evidence support the claim.
11. MemoryBox shall not synthesize a Person’s voice as part of I9.
12. Search results must remain reachable back to authentic source evidence.

## 8. Required Data / Service Concepts

### 8.1 Transcript Segment

- source media ID;
- start/end offsets;
- transcript text;
- original transcript text if corrected;
- diarized speaker/cluster ID;
- transcription confidence where available;
- transcription model/provider/version;
- processing run/version;
- correction state/provenance.

### 8.2 Voice Exemplar

- canonical Person ID;
- source media ID;
- start/end offsets;
- audio excerpt/reference;
- owner/system source type;
- voice embedding/model/version;
- quality metadata as needed;
- active/withdrawn state;
- provenance.

### 8.3 Speaker Observation / Assignment

- source media ID;
- transcript/speaker segment ID;
- anonymous diarized speaker ID;
- candidate/assigned Person ID or null;
- confidence;
- supporting exemplar/model information;
- review/correction state;
- provenance.

### 8.4 Spoken Moment

- source media ID;
- start/end offsets;
- transcript segment references;
- Person ID where known;
- speaker state/confidence;
- searchable/indexed text;
- playback target;
- provenance.

### 8.5 Processing Run / Queue State

Must distinguish initial transcript pass, new-video processing, Learn-triggered recognition, correction-triggered reprocessing, model/version-triggered reprocessing, and retry after failure.

## 9. Operational Flow

### 9.1 Initial / incremental transcription

Eligible video  
→ extract audio  
→ speech detection  
→ timestamped transcription  
→ diarization  
→ persist transcript + anonymous speaker turns  
→ index exact text + semantic representation  
→ expose in synchronized Text view

### 9.2 Owner voice Learn

Video Detail  
→ Text  
→ pause video  
→ select/refine clean spoken passage  
→ assign canonical Person  
→ Learn  
→ resolve timestamps to original audio  
→ persist owner-confirmed voice exemplar  
→ generate MB voice embedding  
→ current-video recognition  
→ prioritized background recognition  
→ Person-linked speaker observations  
→ Spoken Moments

### 9.3 Retrieval

Ask / MBQL intent  
→ canonical Person resolution when requested  
→ phrase/semantic/person constraints  
→ retrieve matching Spoken Moments  
→ display evidence-backed results  
→ open exact source passage  
→ playback at relevant timestamp

## 10. Query / MBQL Behavior

I9 shall extend existing shared Ask/Explore state rather than create a new spoken-search application.

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

## 11. UX Requirements

1. Transcript lives in Video Detail, not a separate application.
2. **Text** is the primary transcript reveal control.
3. Transcript scroll/focus follows current playback timestamp.
4. User can pause and select a clean spoken passage.
5. Mouse selection plus keyboard/arrow refinement is the intended baseline.
6. Assign Person + Learn should be available without leaving video context.
7. Unknown speaker state must be understandable.
8. Corrections should feel like teaching MemoryBox, not database maintenance.
9. Opening a Spoken Moment jumps to authentic recording at the right time.
10. Returning from detail preserves prior Ask/Gallery/Timeline state.

## 12. Acceptance Gate

I9 is accepted only when demonstrated on real FlightSim data.

### A. Transcription

1. A controlled multi-video acceptance corpus is processed.
2. Speech is converted to timestamped transcript text.
3. Transcript segments remain traceable to source video/time.
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

### D. Owner Learn

1. Owner selects a clean spoken interval.
2. Owner assigns a canonical MemoryBox Person.
3. Learn persists a reusable owner-confirmed voice exemplar.
4. MemoryBox generates its own voice representation from source audio.
5. Current-video recognition runs first.
6. Additional eligible work is queued for prioritized background recognition.

### E. Voice recognition

1. Learned Person is correctly recognized in at least one additional valid spoken segment when suitable evidence exists.
2. At least one negative/control speaker remains unassigned or is not falsely assigned.
3. Confidence/unknown behavior is visible and trustworthy.
4. Recognition provenance/model version is preserved.

### F. Correction safety

1. A deliberately wrong speaker→Person assignment can be corrected/removed.
2. Reprocessing does not silently restore the rejected assignment from the same evidence.
3. Uncertain identity can remain unassigned.

### G. Retrieval

Demonstrate:

1. **Exact phrase:** query equivalent to `Peggy saying "I love you"` returns authentic matching passage when it exists.
2. **Person speaking:** query equivalent to `Peggy talking` returns Person-linked spoken passages.
3. **Semantic subject:** query equivalent to `Peggy talking about Christmas` retrieves relevant authentic passages based on transcript meaning.

Opening any result plays the correct source video at or near the relevant spoken timestamp.

### H. Non-verbal behavior

If laughter or another non-verbal vocal event is detected, MemoryBox may retain/retrieve it, but acceptance does not require identifying a Person solely from isolated non-speech sound.

### I. Scale proof

Acceptance shall use a **controlled subset**, not the complete video archive.

Recommended starting corpus:

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
3. **Transcript and voice identity are separate.**
4. **Diarization precedes identity.**
5. **Learn uses real audio.**
6. **Voice teaching is reusable.**
7. **Unknown stays unknown.**
8. **Corrections stick.**
9. **Search supports exact words and meaning.**
10. **Playback is immediate and authentic.**
11. **Incremental processing works.**
12. **I9 does not synthesize family voices.**
13. **I9 does not become I10/I11.**
14. **The UX remains MemoryBox.**

## 14. Implementation Planning Questions for Cursor

Before runtime implementation, Cursor shall inspect the current codebase and return a code-grounded implementation assessment covering:

1. existing video-detail player and Text/transcript hooks;
2. existing audio extraction/transcription code or experiments;
3. existing Whisper/local model infrastructure relevant to STT;
4. existing HVRT voice-learn/voice-print POC code and reuse potential;
5. existing job/queue infrastructure for initial/incremental transcription;
6. existing Qdrant/vector/search indexing for semantic transcript retrieval;
7. existing MBQL paths for Person + spoken phrase/subject queries;
8. data/schema changes for transcript segments, diarized speaker turns, voice exemplars, speaker assignments, and Spoken Moments;
9. recommended transcription and diarization engines based on the local stack;
10. voice-embedding/speaker-recognition approach and correction/negative-evidence design;
11. CPU/GPU/storage implications for the controlled corpus and later full archive;
12. acceptance corpus recommendation using actual FlightSim inventory.

Cursor shall identify genuine founder decisions separately from engineering choices it can make without reopening product scope.

## 15. Build Authorization Rule

This definition is **APPROVED and locked**, but runtime implementation is **not yet build-authorized**.

Runtime implementation, schema migration, or UX modification does not begin until:

1. this approved definition is committed to the repository as the authoritative I9 source;
2. Cursor verifies the exact committed path/version;
3. Cursor returns a code-grounded implementation assessment;
4. founder explicitly authorizes the I9 build.
