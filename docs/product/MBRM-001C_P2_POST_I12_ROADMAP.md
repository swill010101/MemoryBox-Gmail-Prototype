# MBRM-001C — MemoryBox P2 Roadmap After Historian Capture

**Status:** Founder direction locked · implementation definitions to follow  
**Date:** 2026-09-03  
**Owner:** Tom  
**Supersedes sequencing after P2-I12 in:** `MBRM-001B_P2_HISTORIAN_COLLECTION_AND_CAMPAIGNS.md`  
**Does not reopen:** accepted P2 increments, I11A strategic hold, or I12 planning/build decisions

---

## 1. Purpose

This roadmap records the founder-approved direction for MemoryBox immediately after **P2-I12 — Historian Collection & Campaigns V1**.

The next priority is **not External Historical Context**. Before MemoryBox adds outside historical information, it should finish proving that it can correctly understand, index, retrieve, and present the family's own authentic video, face, speech, voice, Story, Artifact, communication, and timeline evidence.

The guiding principle is:

> **Before MemoryBox learns more about the outside world, finish teaching it how to understand and present the family's own evidence.**

---

## 2. New post-I12 execution sequence

```text
P2-I12 — Historian Collection & Campaigns V1
  ↓
P2-I13 — Video, Face, STT & Voice Pipeline Revalidation
  ↓
P2-I14 — Unified Person Evidence & Timeline
  ↓
P2-I15 — External Historical Context
  ↓
P2-I16 — Dynamic / Saved Views
  ↓
P2-I17 — Settings & Processing Controls
  ↓
P2-I18 — Trust Consistency & Private Owner Trust
  ↓
P2-I19 — Portability & Import-back
```

### Deferred narrative work

- **P2-I11A** remains on strategic hold. It may later reopen through the recorded direct-narrative / narrative-from-chunk gate.
- **P2-I11B** remains deferred. Reassess its placement after I13–I15, when MemoryBox has stronger underlying evidence and retrieval behavior.
- The exact post-I15 timing of I11A/I11B should be reassessed from the working product rather than assumed now.

---

## 3. P2-I13 — Video, Face, STT & Voice Pipeline Revalidation

### One-line outcome

MemoryBox should rebuild confidence in the complete video-understanding pipeline before processing the full video archive.

### Why I13 is next

The current HVRT/video system has proven important concepts, but it also leaves derived artifacts that should be reviewed before scale-up:

- 1–2 second video fragments derived from larger source videos;
- playback behavior tied too tightly to exact derived span end times;
- STT output that needs clearer start/end semantics and better playback behavior;
- voice/speaker recognition that needs the same full-pipeline review as face recognition;
- a held-out set of videos intentionally not yet processed while the smaller corpus was used for proof.

These are not source-evidence problems. They are **derived/rebuildable processing problems**.

### Core architectural lock

**Source videos remain immutable evidence. Derived observations, moments, recognition spans, transcripts, speaker assignments, and search units are rebuildable.**

Do not delete or rewrite source video.

Do not discard confirmed human teaching or other authoritative identity evidence merely because derived output is rebuilt.

### I13 starts with assessment, not code changes

Before any wipe/rebuild or algorithm change, document the full current pipeline:

```text
SOURCE VIDEO
  → frame / face detection
  → face observations
  → face recognition
  → appearance grouping
  → appearance start/end times
  → searchable video moment representation
  → Gallery / Ask result
  → source-video playback behavior
```

and separately:

```text
SOURCE AUDIO / VIDEO AUDIO
  → audio extraction
  → speech regions
  → STT
  → transcript time spans
  → diarization
  → speaker teaching / identity
  → reusable voice exemplars
  → speaker recognition
  → spoken moments
  → Ask / transcript retrieval
  → source playback behavior
```

For every stage, identify:
- authoritative input;
- generated/derived output;
- current persistence location;
- provenance;
- rebuildability;
- correction path;
- current known defects;
- expected acceptance proof.

### Fragment problem — design direction to test

Do **not** assume that every short face-recognition appearance should become a separately playable 1–2 second video clip.

Separate:

**Recognition evidence**
- Person X observed from `start_time` to `end_time`.

from:

**Playback experience**
- Open the immutable source video at the relevant start point and allow natural continued playback.

The derived appearance can remain precise without forcing the user to experience a chopped fragment.

### STT playback direction to test

Retain exact transcript boundaries:
- `start_time`
- `end_time`

for indexing, evidence, transcript highlighting, and search.

Default playback should likely:
1. open the original source video at the relevant start time;
2. highlight the matched transcript/span;
3. continue playback naturally beyond the span end.

Stopping automatically at `end_time` should be treated as an optional exact-passage behavior, not necessarily the default user experience.

### Voice recognition direction

Review speaker/voice recognition as a complete teaching and retrieval loop:

```text
speech span
  → diarization
  → owner identifies speaker
  → confirmed voice exemplar
  → recognition across other audio/video
  → candidate speaker moments
  → owner correction
  → reusable improved evidence
```

A meaningful acceptance scenario is:

> Teach MemoryBox Peggy's voice once, then find Peggy speaking elsewhere and open the original recording/video at the correct place.

### Rebuild sequence

Do not wipe derived data until the assessment and replacement design are approved.

When approved:
1. inventory current source and derived data;
2. preserve authoritative human-confirmed evidence;
3. identify exactly which derived tables/files/indexes are rebuildable;
4. snapshot/record current state for comparison;
5. remove only the obsolete/rebuildable derived outputs;
6. rebuild the existing smaller proof corpus;
7. prove face, STT, voice, search, timeline, and playback behavior;
8. inspect failures;
9. only after acceptance, add and process the held-out videos;
10. then process the full intended video collection.

### I13 UX scope

I13 is primarily **backend, evidence-model, processing, and proof work**.

Reuse existing MemoryBox screens wherever practical:
- Gallery / Explore
- Person
- video viewer
- transcript view
- Review & Learn / Teach
- existing Ask behavior

Do not invent a new admin-style UX unless a diagnostic surface is truly required.

---

## 4. P2-I14 — Unified Person Evidence & Timeline

### One-line outcome

A Person query and Person surface should represent **everything MemoryBox knows about that person**, not only photos/video or one provider's evidence.

### Headline acceptance ask

> **Show me Peggy George.**

MemoryBox should coordinate all applicable evidence across:
- photos;
- source video and recognized appearances;
- spoken moments / voice;
- Stories;
- Artifacts;
- Journal where applicable;
- email;
- SMS/text;
- calendar;
- other linked evidence.

The system should preserve evidence type, provenance, trust, and source boundaries while presenting one coherent Person experience.

### Unified Gallery / retrieval direction

- Person retrieval should search across all supported content.
- Communications should use prepared/optimized representations rather than expensive raw cleanup at Ask time.
- Evidence should arrive as one coordinated result rather than photos/video first and communications much later.
- Gallery visibility remains a presentation decision; hidden communications may still participate in reasoning/narrative.
- Existing MemoryBox visual patterns remain the default UX.

### Timeline direction

Stories, Artifacts, communications, calendar, video moments, spoken moments, and other evidence should participate in the timeline when they have meaningful temporal placement.

Do not blindly place objects according to whichever timestamp is easiest.

#### Story dates

Potential dates include:
- date/range of the remembered event;
- recollection/recording date;
- Story creation/save date.

The **event/memory date** should normally drive timeline placement. Recording/save date remains provenance.

#### Artifact dates

Potential dates include:
- creation/manufacture;
- acquisition;
- ownership/use period;
- event association;
- photograph/scan date.

Timeline placement should reflect the meaningful historical context when known. A recent scan date must not silently imply the Artifact belongs historically to that date.

### Optimized communications

The 2026-09-03 communications decision remains active:
- immutable original email/SMS remains preserved;
- ingestion maintains a separate optimized/threaded representation;
- Ask/Gallery consumes the optimized form;
- evidence IDs and provenance link back to originals.

I14 is the natural product-integration point for proving that prepared communications participate correctly in Person retrieval and timeline behavior.

---

## 5. P2-I15 — External Historical Context

### One-line outcome

After MemoryBox can reliably present family evidence, add factual external historical context without confusing outside history with family evidence.

### Primary EVS direction

- What events in the U.S. were happening around the time of this photo/video?
- What events in the world were happening then?
- Create a family-year narrative and include selected major U.S. events.

### Trust boundary

External historical information is **context**, not family evidence.

MemoryBox must:
- cite external sources;
- distinguish outside historical facts from family evidence;
- match historical context to the precision of the family date;
- never imply an outside event affected the family unless family evidence supports that relationship.

---

## 6. Renumbered downstream increments

This roadmap changes the post-I12 numbering recorded in MBRM-001B.

| Previous MBRM-001B ID | Previous name | New ID |
|---|---|---|
| P2-I13 | Dynamic Views | **P2-I16** |
| P2-I14 | Settings & Processing Controls | **P2-I17** |
| P2-I15 | Trust Consistency & Private Owner Trust | **P2-I18** |
| P2-I16 | Portability & Import-back | **P2-I19** |
| Deferred backlog | External Historical Context | **P2-I15** |

New increments inserted before them:

| New ID | Name |
|---|---|
| **P2-I13** | Video, Face, STT & Voice Pipeline Revalidation |
| **P2-I14** | Unified Person Evidence & Timeline |

---

## 7. Backlog items explicitly carried forward

The following remain active unless separately closed:

### Video / identity
- face recognition across video;
- appearance start/end times;
- useful searchable moments;
- owner correction and reusable face evidence;
- removal/rebuild of bad derived fragments where appropriate;
- process held-out videos after pipeline proof.

### Speech / voice
- STT with precise transcript time spans;
- source-video/audio jump-to-time;
- natural continued playback;
- diarization;
- speaker teaching;
- voice exemplars;
- cross-video/audio speaker recognition;
- correction loop.

### Cross-source retrieval
- Person Ask across all applicable evidence;
- Stories/Artifacts included in Person experience;
- communications/calendar integration;
- unified timeline behavior;
- context continuity.

### Communications performance
- ingest-time optimized communications representation;
- safe thread normalization/deduplication;
- evidence/provenance preservation;
- coordinated Person Gallery results without long delayed insertion.

### Dynamic views
- live/saved intent-based result sets;
- curated mode;
- frozen/snapshot mode.

### Settings / processing
- provider/source health;
- processing controls;
- storage;
- model/service status;
- archive configuration;
- visibility into full-archive processing when I13 scales beyond the proof corpus.

### Trust / correction
- merge;
- split;
- unlink;
- supersede;
- withdraw;
- conflict handling;
- contributor provenance;
- owner authority and private assessment.

### Later contribution
- Historian Capture V2;
- native iOS/Android contribution;
- voice-first contributor workflow;
- richer adaptive questioning;
- multi-user family identity/permissions.

---

## 8. Planning discipline for I13

I13 should be developed in a dedicated **MB P2-I13** planning chat.

The expected workflow is:
1. Tom brings forward the current full video/face/STT/voice workflow.
2. Review current behavior stage by stage.
3. Identify what is authoritative vs derived.
4. Identify defects and hidden assumptions.
5. Agree on desired recognition, moment, transcript, speaker, and playback semantics.
6. Define what may safely be wiped/rebuilt.
7. Define proof corpus and acceptance cases.
8. Define how/when held-out videos enter the pipeline.
9. Reuse existing MemoryBox screens wherever possible.
10. Only after founder agreement, create the I13 PRD/domain/acceptance/implementation packet for Cursor.
11. No destructive reset or broad rebuild before that packet is accepted.

---

## 9. Founder decision summary

Locked 2026-09-03:

- Complete I12 Historian Capture first.
- Make **I13 Video, Face, STT & Voice Pipeline Revalidation** the next major increment.
- Review the entire pipeline before attempting fixes.
- Treat short fragments, STT playback, and voice recognition as parts of one broader video/audio evidence problem.
- Preserve source videos and authoritative human teaching.
- Rebuild only derived/rebuildable outputs after the replacement workflow is agreed.
- Prove the existing smaller video corpus before adding the held-out videos.
- Then process the remaining/full video set.
- Follow with **I14 Unified Person Evidence & Timeline**.
- Person Ask must ultimately search all supported evidence, including Stories and Artifacts.
- Stories and Artifacts should participate meaningfully in the timeline.
- External Historical Context moves to **I15**.
- Dynamic Views, Settings, Trust, and Portability shift to I16–I19.
- I13 should primarily reuse existing MemoryBox screens; expected work is backend/process/proof heavy.
- I11A remains on hold and I11B deferred pending reassessment after stronger evidence pipelines exist.

---

## 10. Next move

Finish P2-I12.

In parallel, use the dedicated **MB P2-I13** planning conversation to document and challenge the full current video/face/STT/voice workflow.

When I12 is nearing completion, point Cursor to this roadmap as the authoritative post-I12 sequencing decision.

Do **not** begin destructive I13 cleanup or implementation solely from this roadmap. I13 requires its own reviewed planning packet and explicit build authorization.
