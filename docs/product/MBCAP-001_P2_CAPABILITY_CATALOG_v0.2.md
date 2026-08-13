<!-- Extract from docs/source/MBCAP-001_MemoryBox_Capability_Catalog_P2_v0.2.docx — DOCX is master -->

# MBCAP-001 — MemoryBox Capability Catalog (P2 Working Draft v0.2)

**Status:** Working Draft · ingested 2026-08-13 · **DOCX master** in `docs/source/`

**Purpose (extract):** Reusable MemoryBox capabilities that must not disappear between EVS → UX → Domain → Engineering Increment.

# MBCAP-001 — MemoryBox Capability Catalog

## P2 Working Draft v0.2

Status: Working Draft - updated through approved P2 UX exploration decisions
Purpose: Capture reusable MemoryBox capabilities, enabling functions, and previously identified backlog work that must be implemented across multiple Experience Validation Scenarios.

# 1. Purpose

The MemoryBox Experience Validation Scenario catalog defines what a user should ultimately be able to accomplish.

Some MemoryBox functionality, however, cannot be adequately represented by a single EVS. A user experience may require:

multiple steps;

several underlying services;

reusable capabilities shared by many EVSs;

background processing;

learning and correction;

persistent domain objects;

or product/UX infrastructure that supports many experiences.

MBCAP-001 exists to capture that layer.

Its purpose is to prevent important enabling functionality from disappearing between:

EVS → UX → Domain Model → Engineering Increment

The intended traceability is:

EVS → Experience Flow → Capability → Domain Objects / Services → Implementation Increment

A capability may support one EVS, many EVSs, or an entire class of MemoryBox experiences.

# 2. What Belongs in MBCAP

A capability belongs here when it is:

reusable across multiple EVSs;

inherently multi-step;

infrastructure needed to make EVSs usable at real-world scale;

learning, recognition, correction, or processing functionality;

background analysis that produces evidence used later;

or previously identified work that does not naturally belong to a single EVS.

MBCAP is not another EVS catalog.

# 3. P2 Capability Backlog

## CAP-P2-001 — UX Refinement & Product Maturation

Status: Identified — definition to be refined.

P2 requires refinement of the P1 product shell and interaction model so MemoryBox remains usable as archives, evidence sets, and result sets become substantially larger.

Previously identified areas include:

high-volume photo and video browsing;

timeline-first exploration;

adaptive timeline zoom;

clusters and timeline banding;

hover/preview behavior;

natural-language and structured filtering;

drill-down and return/navigation continuity;

progressive discovery;

Guided Exploration versus deeper Explorer-style interaction;

graceful continuation of prior exploration;

contextual capability discovery rather than requiring users to learn product commands;

dynamic and saved views;

summaries and representative highlights.

This capability will be refined separately before decomposition into implementation work.

Approved P2 UX patterns now include:

mixed-media result canvas rather than file-type silos;

two-row/high-density gallery with user-controlled card density;

unified Timeline/scrubber with banding, handles, adaptive precision and immediate gallery synchronization;

shared full evidence viewer for Photo/Video and extensible evidence types;

contextual People / Story / Artifact / Source / Learn states;

optional synchronized video transcript inside the same viewer shell;

quick rollover/focus preview derived from the full evidence viewer;

Location/Map exploration as a synchronized result lens;

saved Living Album definitions that preserve exploration intent/state.

## CAP-P2-002 — Archive Health, Dashboard & Guided Work Queues

MemoryBox should evolve the existing Status concept into an owner-facing Archive Health capability.

The system should identify useful work such as:

unidentified people;

missing or uncertain dates;

missing locations;

unlinked artifacts;

incomplete relationships;

evidence needing confirmation;

processing/provider problems;

other gaps MemoryBox can help the owner resolve.

MemoryBox should offer direct “work on this now” flows rather than merely reporting deficiencies.

This capability supports Review & Learn and ongoing archive improvement.

## CAP-P2-003 — Face Identity & Appearance Learning

MemoryBox should maintain its own reusable facial-identity evidence for canonical MB People.

Face evidence may originate from:

confirmed Immich people/assets;

manually identified faces in MemoryBox photos;

manually boxed faces in videos;

confirmed recognition results;

other future photo providers.

Immich identities remain provider identities mapped to canonical MemoryBox People.

MemoryBox should preserve provenance for each face example and use MB-owned recognition processing rather than making MemoryBox identity dependent upon Immich’s internal recognition model.

## CAP-P2-004 — Photo Face Identification & Face-Evidence Capture

While viewing a photograph in MemoryBox, an owner should be able to draw/select a bounding box around a face.

The owner may then:

identify a previously unknown person;

associate the face with an existing MB Person;

create a new MB Person when appropriate;

explicitly identify a particularly clear face as useful recognition evidence.

The resulting annotation must retain:

source asset;

bounding box;

identified Person;

who identified it;

date/time of identification;

provenance;

confirmation status.

This becomes reusable input into identity learning and recognition.

## CAP-P2-005 — Video Face Identification & Learning

Retain the previously established video face bounding-box capability.

While viewing a video frame, an owner can identify a face and associate that observation with a canonical MB Person.

A confirmed video face may become additional recognition evidence for that Person.

The feature must also function as a correction mechanism when automated recognition:

misses a person;

identifies the wrong person;

or lacks sufficient confidence.

## CAP-P2-006 — Video Person Recognition & Appearance Timeslotting

MemoryBox should run facial recognition over video using available confirmed face evidence.

The primary stored result should not merely be:

Person X occurs in Video Y.

MemoryBox should create an Appearance representing where that person appears within the video.

An Appearance should conceptually include:

Person;

source video;

start time;

end time;

representative frame or frames;

recognition confidence;

recognition method/source;

confirmation or correction status;

provenance.

This enables retrieval at the meaningful moment level rather than only at the source-file level.

Examples:

“Show me all videos with Peggy.”

“Show me Peggy in this video.”

“When does Dad appear?”

“Show me Peggy and Dad together.”

Results should open or play at the appropriate video timeslot.

## CAP-P2-007 — Searchable Video Moments

Expand video handling from source-level retrieval into searchable time-based moments.

MemoryBox should be able to associate portions of video with:

people;

speech;

transcript text;

events;

places;

objects/artifacts;

stories;

other evidence.

The distinction between a source video and a searchable moment within that video should be explicit.

This capability builds upon the proven HVRT time-slice approach.

## CAP-P2-008 — Speaker Identity & Voice Recognition

Extend existing diarization and speaker-recognition concepts into MemoryBox.

Capabilities should include:

speaker diarization;

owner identification of an unknown speaker;

known-speaker exemplars;

reuse of confirmed voice evidence;

correction of incorrect speaker identification;

association with canonical MB People.

A Person may therefore accumulate identity evidence from both:

face + voice

while MemoryBox preserves the provenance and confidence of each independently.

## CAP-P2-009 — Audio/Video Transcript & Spoken-Moment Retrieval

Audio and video should support:

speech-to-text;

searchable transcripts;

transcript time ranges;

speaker association;

jump-to-source-time behavior.

This should ultimately support experiences such as:

“Play Peggy talking about Alaska.”

“Find every recording where Dad talks about the war.”

“Let me hear Grandpa’s voice.”

The returned object should be the relevant moment or passage, not merely the containing media file.

## CAP-P2-010 — Cross-Modal Person Identity Learning

MemoryBox should progressively build knowledge about a Person across multiple forms of evidence.

Potential identity evidence includes:

faces;

voices;

owner confirmations;

relationships;

names in communications;

tagged photographs;

stories;

video appearances;

other confirmed assertions.

Human confirmation remains high-authority evidence but retains provenance and revision history.

Identity learning must never silently overwrite confirmed information.

## CAP-P2-011 — Relationship Graph & Derived Kinship Inference

MemoryBox should expand from storing direct family relationships into reasoning over the canonical Person relationship graph.

Examples:

Tom is sibling of Peggy.

Peggy is mother of Tim.

Tom is father of Dan.

MemoryBox may derive that Dan and Tim are cousins.

Derived relationships must:

remain distinguishable from directly asserted facts;

identify the relationship path used;

preserve provenance;

be explainable;

allow correction when source relationships are incorrect.

This enables experiences including:

“Who are my cousins?”

“Show me pictures of all my cousins.”

“How is Tim related to me?”

## CAP-P2-012 — Rich Cross-Source Correlation

MemoryBox should correlate People, Places, Events, Trips, Stories and evidence across multiple providers and evidence types.

Examples include combining:

photos;

videos;

email;

calendar;

stories;

journal;

documents;

audio;

communications;

artifacts.

This capability supports richer questions where no single source contains the answer.

## CAP-P2-013 — Evidence-Backed Narrative Generation

MemoryBox should be able to synthesize evidence from multiple sources into a coherent answer or narrative while preserving the evidence behind its conclusions.

Generated narrative should distinguish:

known facts;

recollections;

inferred relationships;

uncertain information;

missing evidence.

The narrative itself should not become authoritative evidence merely because AI generated it.

## CAP-P2-014 — Dynamic Views, Collections & Result Sets

MemoryBox should support reusable ways of grouping and revisiting evidence without forcing every useful grouping to become a fixed container of result IDs.

The preferred customer-facing model is a Living Album: save the exploration definition - the question and state - then rerun it against the current archive when reopened.

A Living Album definition may preserve:

original Ask / natural-language intent;

normalized People, Place, Event/Trip/theme and other context;

date/time band and Timeline state;

media/evidence modalities and filters;

sort and view preferences where meaningful;

Map/location state;

trust/evidence refinements and other normalized query constraints.

Living mode reruns the definition against the current archive. Newly imported evidence, newly contributed Stories, newly learned identities/Places and improved recognition may therefore change membership automatically.

Curated mode preserves owner selection/order while retaining the underlying saved intent. Newly matching items may be suggested without silently altering the curated presentation.

Snapshot/Frozen mode preserves the exact result set/version for reproducibility, presentation, sharing, printing or a deliberately fixed keepsake.

The difference between Living, Curated and Snapshot must remain explicit to the user.

Examples:

Peggy around Christmas at Mom’s House;

Alaska with Sue;

all video moments containing Dad;

Mom’s recipes;

unidentified people;

Christmas memories through the years.

## CAP-P2-015 — Summary & Highlight Generation

For large evidence sets, MemoryBox should identify representative items and create useful summaries without overwhelming the user.

Examples include:

trip highlights;

year summaries;

Person summaries;

representative photos;

significant timeline moments;

cross-source event summaries.

Highlights must remain traceable to their underlying evidence.

## CAP-P2-016 — Full Correction, Merge, Unlink & Withdrawal Lifecycle

MemoryBox needs consistent correction mechanisms across major domain objects.

These include:

People;

relationships;

Places;

Events;

Stories;

Journal entries;

Artifacts;

annotations;

identity assertions;

media associations.

Correction should generally preserve history and provenance rather than destructively replacing prior evidence.

Required patterns include:

merge;

split where needed;

correct;

unlink;

supersede;

withdraw;

restore/reconsider.

## CAP-P2-017 — Trust, Authority & Contributor Provenance

As MemoryBox accepts knowledge from more sources and people, it needs richer handling of:

who made an assertion;

who supplied evidence;

owner versus contributor authority;

confidence;

disagreements;

corrections;

revision history.

An author’s original Story or recollection should remain distinguishable from another person’s later assessment of its accuracy.

## CAP-P2-018 — SMS/Text Ingestion & Retrieval

SMS/text remains deferred from P1 and should become a supported evidence source in P2.

Text messages should participate in the same evidence architecture as email and other communications, supporting:

ingestion;

preservation of originals where available;

participant association;

date/time;

search;

Person correlation;

event/trip correlation;

narrative evidence.

## CAP-P2-019 — Richer Email Processing

Expand P1 email ingestion beyond basic evidence retrieval into richer extraction and correlation.

Potential functions include:

thread awareness;

participant identity;

attachments;

events;

places;

relationships;

important moments;

artifact/story connections;

cross-source correlation.

## CAP-P2-020 — Proactive Memory Capture

MemoryBox should periodically help owners preserve knowledge that does not yet exist in the archive.

Prompts may be generated from existing evidence, such as:

an important photograph;

an artifact;

an unexplained event;

an unidentified person;

an incomplete story;

a Personal Profile question.

Responses may arrive through supported low-friction channels and become provenance-preserved evidence.

## CAP-P2-021 — Family Contribution

MemoryBox should support controlled contribution of stories, identification, annotations, memories, and evidence from other family members.

Contribution must integrate with:

canonical People;

provenance;

correction;

trust;

ownership;

permissions.

This capability precedes or intersects with the fuller multi-user account architecture.

## CAP-P2-022 — Multi-User Identity, Role & Personal Context

Late P2/P2.5 should support multiple authorized users operating against one shared archive.

Each account maps to a canonical MB Person while retaining a separate archive-level role.

Examples:

Tom — Owner;

Sue — authorized User.

Roles govern authority and permissions; Person identity provides relational context.

The system must eventually support user-specific:

relationship context;

preferences;

journals/profiles;

permissions;

contribution history;

queries such as “Who are my cousins?”

while preserving one shared evidence and Person graph.

## CAP-P2-023 — Settings, Provider Health & Processing Controls

MemoryBox requires a mature Settings and system-management area covering items such as:

providers;

connections;

storage;

processing status;

recognition services;

confidence controls where appropriate;

system health;

archive configuration.

This capability should remain separate from the everyday family exploration UX.

## CAP-P2-024 — Place Anchors, Named Locations & Location Provenance

MemoryBox should treat Place as a first-class family anchor and allow evidence to be associated with a human-readable named location.

A user should be able to place/select a map pin for a photo, video moment, Artifact, Story-related evidence, event or other supported object and save a name such as “Dad’s House,” “Mom’s House,” or “Family Cabin.”

Coordinates remain implementation detail. The family-facing concept is the named Place.

Location evidence should preserve:

named Place;

coordinates / geographic area or radius;

source evidence/object;

location source: embedded GPS, imported metadata, owner assignment, event association, or AI inference;

who confirmed/assigned it and when;

confidence and provenance;

revision/correction history.

Future visual-setting recognition may infer that a photo/video setting resembles a known Place. Exact GPS, owner-confirmed Place and inferred visual setting must remain distinguishable.

## CAP-P2-025 — Map-Based Result Exploration

MemoryBox should provide Map as a secondary lens on the current result set, synchronized with Ask, filters, Gallery and Timeline.

Map is not a generic GIS application and not a top-level destination. It answers “where” for the current exploration.

Capabilities should include:

appropriate automatic map extent for the current results;

markers and clusters for matching evidence;

hover/focus quick preview;

zoom/drill into clusters;

select a marker/Place to add or refine a location filter;

return to the Gallery/Timeline with the new Place filter and all other context preserved;

natural-language / STT commands such as “only Alaska,” “show Dad’s house,” or “map these memories.”

## CAP-P2-026 — Shared Evidence Viewer & Contextual Evidence Actions

MemoryBox should use a shared evidence-viewer shell so inspection, context, teaching and return behavior remain consistent across evidence types.

Photo and Video are the baseline implementations. Video adds transport controls and an optional synchronized transcript without changing the overall viewer shell.

The contextual rail may expose People, Story, Artifact, Source and Learn on demand. Story/Artifact may open as lightweight overlays or deepen into their dedicated experiences.

The viewer must preserve:

current Ask/query and normalized context;

filters;

Timeline range and playhead;

Map/location state;

Gallery density and browsing position;

modal object position within the current result set.

Contextual Learn should allow confirmed face/voice evidence from photos, artifact images, Stories/linked evidence and paused video frames to become reusable recognition evidence with provenance.

# 4. Capability-to-EVS Relationship

Capabilities should not be duplicated for every EVS.

For example:

EVS: “Show me all videos with Peggy.”

May require:

CAP-P2-003 Face Identity & Appearance Learning

CAP-P2-006 Video Person Recognition & Appearance Timeslotting

CAP-P2-007 Searchable Video Moments

CAP-P2-010 Cross-Modal Person Identity Learning

CAP-P2-016 Correction Lifecycle

Another EVS may reuse most of the same capabilities.

This is the primary reason for maintaining MBCAP independently of the EVS catalog.

# 5. Open Work

The following areas need further decomposition before MBCAP-001 can be considered complete:

UX Refinement
The broad P2 UX backlog is identified but requires deliberate review and prioritization.

Experience Flows
Previously identified multi-step EVSs should be examined and mapped to capabilities rather than expanded into oversized EVS descriptions.

HVRT Capability Inventory
Existing HVRT functionality should be mapped explicitly:

HVRT capability → MBCAP capability → EVS → P2 implementation increment

This should identify what can be reused, adapted, or discarded.

Increment Planning
Capabilities should eventually be grouped into coherent P2 implementation increments. They should not automatically become one increment per capability.

v0.2 additions requiring downstream traceability:

map CAP-P2-024/025/026 and revised CAP-P2-014 to relevant EVSs and P2 increments;

add domain-model detail for Place, PlaceAssertion/LocationEvidence and SavedView/LivingAlbum definitions;

define live versus curated versus frozen versioning semantics;

define how inferred visual settings are linked to named Places without silently promoting inference to confirmed location.

# 6. Working Principle

EVSs validate that MemoryBox can deliver the experience.

MBCAP defines the reusable machinery MemoryBox must possess to deliver those experiences repeatedly, consistently, and at scale.
