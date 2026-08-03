# MBX-A-001 — Functional Architecture Part 1

| Field | Value |
|-------|--------|
| **Doc ID** | MBX-A-001 |
| **Title** | Functional Architecture — Part 1: Foundational Principles & Query Model |
| **Status** | Governing — Part 1 of 6 (functional / engineering) |
| **Authority** | Functional Architecture. **Subordinate to** [MB-FB-001 Founder's Book](../product/MB-FB-001%20Memory%20Box%20Founders%20Book.md) and [MBPS-001 Product Specification](../product/MBPS-001%20Memory%20Box%20Product%20Specification.md). Governs requirements elaboration, architecture, database design, prompt engineering, APIs, UI, and evaluation **within** that product hierarchy. No implementation shall knowingly violate this document or the higher product documents. |
| **Series** | See [README.md](README.md) in this folder for Parts 2–6 (planned). |

---

# Memory Box Functional Architecture

## Part 1 — Foundational Principles & Query Model

### 1. Purpose

Memory Box exists to help people rediscover, reconstruct, understand, and preserve the story of their lives through evidence contained within their personal digital artifacts.

Unlike traditional search engines that locate files, Memory Box reconstructs memories by correlating evidence from multiple sources while remaining transparent about certainty, assumptions, and missing information.

Memory Box is not intended to replace human memory.

Its purpose is to augment it.

### 2. Core Philosophy

Memory Box answers questions by reconstructing evidence from personal memories.

It does not invent answers. It reconstructs what the evidence supports.

Every answer represents the system's best reconstruction of events using available evidence while remaining honest about uncertainty.

The user should never wonder:

"Did the AI make that up?"

### 3. Foundational Principles

#### MB-P-001 — Evidence First

Every factual statement shall be supported by one or more pieces of evidence.

Evidence may include:

- Email
- Calendar
- Text Messages
- Photographs
- Videos
- Documents
- Owner-entered information

#### MB-P-002 — Preserve Original Evidence

Original source material shall never be modified.

All processing occurs from working copies.

Every derived artifact shall maintain provenance back to its original source.

#### MB-P-003 — Never Create False Memories

Memory Box shall never invent facts.

If sufficient evidence does not exist, the system shall explicitly state that the evidence is incomplete.

#### MB-P-004 — Suggestions Are Not Knowledge

When ambiguity exists, Memory Box may suggest likely interpretations.

Suggestions shall never become knowledge without owner confirmation.

Example:

> I believe "your sister" refers to Peggy George.
>
> Is that correct?

#### MB-P-005 — Owner Confirmation Is Highest Authority

Owner-confirmed knowledge supersedes:

- AI inference
- Pattern recognition
- Frequency analysis
- Metadata inference
- External knowledge

#### MB-P-006 — Confidence Shall Be Explained

Confidence is not merely a percentage.

Confidence shall explain why the system believes a conclusion.

Example:

> High confidence.
>
> Supported by:
>
> - 18 emails
> - 3 calendar events
> - No conflicting evidence

#### MB-P-007 — Missing Evidence Is Valuable

Missing evidence shall be reported.

Example:

> No surviving emails exist between June and September.
>
> Calendar information is unavailable.
>
> Referenced attachment could not be found.

#### MB-P-008 — Separate Facts From Interpretation

Every answer shall distinguish between four categories. These labels are canonical for prompts, APIs, UI, evaluation, and storage. Do not use Assumption or Hypothesis as product labels.

##### Facts

Supported directly by evidence.

Example:

> Peggy sent you an email on December 20, 2014 confirming travel plans. [[email:…]]

##### Observations

Patterns visible in evidence. An observation summarizes what the evidence shows across multiple items; it does not claim why.

Example:

> You exchanged significantly more emails with Peggy between 2012 and 2015.

##### Inferences

Reasonable conclusions. Supported by evidence but not proven. Must remain labeled as inferences until owner confirmation elevates them (see MB-P-004, MB-P-005).

Example:

> It appears the family decided to postpone Christmas because of weather.

##### Unknowns

Things the system cannot determine from available evidence.

Example:

> I found references to "the lake house," but I cannot determine which property this refers to.

#### MB-P-009 — Local First

Personal memories remain under owner control.

All primary processing should occur locally whenever practical.

#### MB-P-010 — Human Memory Is Contextual

Files do not create memories.

Context creates memories.

Memory Box therefore reconstructs context rather than merely retrieving files.

### 4. Functional Model

Memory Box is composed of four major functional systems.

#### Evidence Layer

Responsible for preserving and retrieving evidence.

Examples:

- Email
- Calendar
- Photos
- Videos
- Documents
- Text Messages

#### Personal Context Layer

Responsible for understanding the owner's world.

Examples:

- People
- Relationships
- Places
- Events
- Aliases
- Holidays
- Traditions
- Homes
- Pets
- Family terminology
- Personal timelines

This layer represents learned knowledge rather than retrieved evidence.

#### Reconstruction Layer

Responsible for answering questions.

Functions include:

- Planning
- Retrieval
- Correlation
- Timeline reconstruction
- Confidence evaluation
- Story reconstruction
- Narrative generation

#### Learning Layer

Responsible for improving future answers.

Learns through:

- Owner confirmation
- Corrections
- Metadata additions
- Relationship mapping
- Scene identification
- Place identification
- Identity resolution

### 5. Structured Query Model

Memory Box interprets requests using structured dimensions rather than keyword searches.

Every query is decomposed into a common grammar.

#### Action

Show · Tell · Find · Compare · Summarize · Reconstruct · Discover · Explain

#### Media

Email · Text Messages · Calendar · Photos · Videos · Documents · All

#### Person

Individual · Relationship · Group · Unknown

#### Place

Named place · Relative place · Room · Home · City · Country · Unknown

#### Event

Birthday · Christmas · Vacation · Wedding · Retirement · Funeral · Project · Medical event · Custom event

#### Activity

Cooking · Baseball · Woodworking · Piano · Gardening · Travel · Conversation · Celebration

#### Time

Exact date · Date range · Holiday · Season · Personal era · Relative period

#### Output

Story · Timeline · Gallery · Video · Comparison · Summary · Evidence · Interactive exploration

#### Conversation Scope

Direct communication · Shared thread · Complete thread · All related evidence

### 6. Personal Context Model

Memory Box maintains a separate knowledge model describing the owner's world.

This model is built over time through owner confirmation.

It includes:

- People
- Relationships
- Aliases
- Homes
- Rooms
- Traditions
- Pets
- Organizations
- Projects
- Frequently visited locations
- Important life events
- Recurring holidays
- Recurring activities
- Owner terminology

### 7. Knowledge Acquisition

Memory Box shall not silently learn personal facts.

When ambiguity exists the system asks.

Example:

> "I believe Peggy George is your sister.
>
> Is that correct?"

After confirmation:

| Field | Value |
|-------|--------|
| Relationship | Owner → Sister → Peggy George |
| Source | Owner confirmed |
| Confidence | Certain |

### 8. Temporal Understanding

Memory Box understands several forms of time.

- Exact dates
- Calculated dates
- Recurring holidays
- Holiday seasons
- Personal eras
- Life periods

Examples:

- "When we lived on Oak Street"
- "During retirement"
- "When Dan played baseball"
- "Christmas season"
- "Easter season"

These become reusable temporal concepts.

### 9. Evidence Views

Every evidence source may expose multiple views.

#### Email

- Original message
- Authored text
- Conversation thread
- Participant view

#### Photos

- Original image
- Recognized people
- Objects
- Owner metadata

#### Video

- Original media
- Scenes
- Recognized people
- Activities
- Speech transcript
- Owner annotations

#### (Implied for other media)

Text messages, calendar, and documents likewise expose original plus derived views while preserving originals.

This separation improves retrieval accuracy while preserving evidence.

### 10. Learning Hierarchy

Knowledge confidence follows this order.

1. Owner confirmed
2. Owner corrected AI suggestion
3. Repeated owner acceptance
4. High-confidence AI suggestion
5. AI inference
6. Unknown

### 11. Success Criteria

Memory Box succeeds when it enables users to ask questions naturally while remaining confident that:

- Every fact is traceable.
- Every uncertainty is disclosed.
- Every assumption is identified.
- Every learned relationship is owner controlled.
- No false memories are created.

### 12. What Memory Box Is

Memory Box is:

**A Memory Reconstruction Engine.**

Not a search engine.

Not a chatbot.

Not a photo organizer.

Not a document management system.

Those systems retrieve artifacts.

Memory Box reconstructs lives.

### 13. Conceptual Model Direction

The product is driven by a **personal knowledge graph**: a graph of a person's life in which evidence, people, places, events, relationships, and time are interconnected.

A relational database may still store and serve data. Storage technology is an implementation concern.

The **conceptual model** that drives requirements, reconstruction planning, Personal Context, Learning, and evaluation is the life graph — not a collection of independent tables or file indexes.

Part 3 (Canonical Data Model) shall define this graph formally. Until then, no design shall treat relational tables as the product’s primary mental model.

---

## Companion documents (planned)

| Part | Working title | Status |
|------|----------------|--------|
| Part 1 | Foundational Principles & Query Model | **This document** |
| Part 2 | Functional Components & Layer Responsibilities | Planned |
| Part 3 | Canonical Data Model — personal knowledge graph (evidence, people, places, events, relationships, time); relational storage allowed | Planned |
| Part 4 | Query Planning & Reconstruction Pipeline | Planned |
| Part 5 | Learning Architecture | Planned |
| Part 6 | User Experience | Planned |

After Parts 1–6 are complete, an implementation roadmap will identify the smallest coherent vertical slices that satisfy the Functional Architecture.
