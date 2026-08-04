# MBKM-001 — Memory Box Knowledge Model

| Field | Value |
|-------|--------|
| **Doc ID** | MBKM-001 |
| **Title** | Memory Box Knowledge Model |
| **Version** | 0.1 |
| **Status** | Governing — conceptual vocabulary |
| **Authority** | Subordinate to [MB-FB-001](MB-FB-001%20Memory%20Box%20Founders%20Book.md) and [MBPS-001](MBPS-001%20Memory%20Box%20Product%20Specification.md). Glossary-of-record for knowledge concepts. |
| **Source** | `MBKM-001_a618.docx` |
| **Consistency** | Terminology and conflict resolutions: [MB-RECONCILE-001](MB-RECONCILE-001%20Core%20Terminology%20and%20Principles.md). |

## Consistency callout

- **Story** (human/curated) is distinct from **Narrative** (AI assembly from evidence) — see MB-RECONCILE-001.
- **Relationship** in this draft primarily means Person–Person ties; typed links among other concepts are **KnowledgeLinks** (reconcile naming). Full split lands in MBKM 0.2.
- **Artifact / Evidence / Media** are roles an item may wear, not three duplicate objects.

Purpose

MemoryBox does not organize files.

It understands lives.

This document defines the conceptual model through which MemoryBox understands people, relationships, stories, places, moments, artifacts, and the evidence that connects them.

This is not a database schema.

It is not an implementation guide.

It is the conceptual language of MemoryBox.

Every future database, API, AI model, prompt, graph, and user interface should derive from this model.

## Chapter 1 — A Human Life Is Not a Folder

Traditional software organizes information into files and folders.

MemoryBox organizes understanding.

People do not remember life through directory structures.

They remember through relationships.

A face reminds them of a vacation.

A recipe reminds them of a grandmother.

A song reminds them of high school.

A photograph reminds them of a conversation.

Everything is connected.

MemoryBox exists to preserve those connections.

### Design Principle

MemoryBox models relationships before storage.

Storage serves understanding.

Never the reverse.

### What We Decided

MemoryBox models human memory rather than computer storage.

### Why

People think in relationships.

Not folders.

### Open Questions

Can every meaningful memory eventually be represented through relationships?

## Chapter 2 — The Building Blocks

MemoryBox understands life through a relatively small number of core concepts.

Everything else emerges from the relationships between them.

These concepts become the vocabulary of MemoryBox.

### Person

A human being.

Living or deceased.

Known or initially unknown.

A Person is never merely a face.

A Person accumulates stories, relationships, places, moments, artifacts, conversations, values, achievements, and memories throughout life.

### Relationship

How two or more people are connected.

### Examples

Father

Mother

Friend

Neighbor

Teacher

Co-worker

Mentor

Spouse

Sibling

Relationships explain stories.

### Story

The primary container of meaning.

Stories connect everything else.

People.

Places.

Moments.

Artifacts.

Evidence.

Narrative.

Stories are first-class concepts.

### Moment

A meaningful period of time.

A birthday.

A vacation.

A military deployment.

A wedding.

A fishing trip.

A conversation.

Moments often contain many pieces of evidence.

### Place

A location that carries meaning.

Not simply coordinates.

Home.

Grandma's kitchen.

The lake.

Forest Park.

The family farm.

Meaning defines the place.

### Artifact

Something intentionally preserved.

Photographs.

Recipes.

Pocket watches.

Letters.

Videos.

Recordings.

Newspaper clippings.

Military medals.

Objects become meaningful through stories.

### Evidence

Anything supporting understanding.

Photographs.

Videos.

Audio.

Documents.

Emails.

Calendar entries.

Receipts.

OCR.

Speech transcripts.

Evidence supports stories.

It never replaces them.

### Conversation

A human interaction.

Written.

Spoken.

Recorded.

Conversations frequently become stories.

### Collection

A meaningful grouping.

Not a folder.

Collections emerge naturally from life.

### Tradition

A recurring family experience.

Christmas.

Sunday dinner.

The annual fishing trip.

Traditions connect generations.

### Season

Not simply weather.

Life seasons.

Christmas.

School year.

Harvest.

Summer vacation.

Retirement.

Season provides context.

### Timeline

A perspective on time.

Every Person.

Every Story.

Every Place.

Every Relationship.

Every Collection.

Can have its own timeline.

### Narrator

The individual telling the story.

Perspective matters.

Rick's story about Peggy.

Tom's story about Peggy.

Sue's story about Peggy.

MemoryBox preserves all three.

### Media

The physical or digital representation of evidence.

Images.

Video.

Audio.

Documents.

Media is evidence.

Not understanding.

### Memory

The human interpretation of events.

Sometimes supported by evidence.

Sometimes standing alone.

Memory should always preserve uncertainty when appropriate.

### Design Rule

Core concepts should remain remarkably stable over decades.

Technology changes.

The understanding of a human life should not.

### What We Decided

MemoryBox understands a relatively small vocabulary of concepts connected through rich relationships.

### Why

Simplicity in concepts enables complexity in understanding.

### Open Questions

Should Favorites, Values, Beliefs, Organizations, Pets, and Life Chapters be first-class concepts or specializations of Stories and Relationships?

## Chapter 3 — Relationships Are Everything

Traditional databases emphasize records.

MemoryBox emphasizes relationships.

Everything meaningful is connected.

A photograph...

contains People.

Occurred at a Place.

During a Moment.

Supports a Story.

May contain Artifacts.

Has Evidence.

May introduce new Relationships.

The value comes from the connections.

Not the file.

### Examples

A Recipe


↓

Grandma


↓

Thanksgiving


↓

Family Tradition


↓

Kitchen


↓

Voice Recording


↓

### Story

A Pocket Watch


↓

Dad


↓

Military Service


↓

His Father


↓

Photograph


↓

Recorded Story


↓

### Artifact

A Baseball Photograph


↓

Tom


↓

Brother


↓

Little League


↓

Coach


↓

Neighborhood


↓

### Story

Everything connects.

### Design Rule

Relationships are first-class knowledge.

They are not metadata.

### What We Decided

MemoryBox models lives as connected networks of understanding.

### Why

Human memory naturally works through association.

### Open Questions

Should every relationship carry confidence, provenance, and history?
