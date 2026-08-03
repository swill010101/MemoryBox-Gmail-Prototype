# MBPS-001 — Memory Box Product Specification

| Field | Value |
|-------|--------|
| **Doc ID** | MBPS-001 |
| **Title** | Memory Box Product Specification |
| **Version** | 0.1 (Conceptual Draft) |
| **Status** | Governing — product definition |
| **Authority** | Defines WHAT Memory Box is. Subordinate to [MB-FB-001 Founder's Book](MB-FB-001%20Memory%20Box%20Founders%20Book.md). Guides engineering, UX, architecture, and future business decisions. Functional Architecture (MBX-A-*) is subordinate to this specification. |
| **Source** | `MBPS-001_Memory_Box_Product_Specification_v0.1.docx` |

This document defines WHAT Memory Box is. It intentionally avoids implementation details. It is the product definition that guides engineering, UX, architecture and future business decisions.

---

## 1. Product Definition

Memory Box is a trusted personal knowledge system that helps people preserve, rediscover, and continue telling the stories of a life by connecting people, stories, places, moments, artifacts, and evidence into one conversational experience.

---

## 2. Product Goals

- Help people rediscover their lives rather than organize files.
- Make conversation the primary interface.
- Keep AI invisible; make trust visible.
- Allow the system to grow with a family over decades.
- Capture meaning, not just media.
- Allow a family to begin with only artifacts and through discovery, teaching, and learning build a memory system.

---

## 3. Product Design Goals

- Warm
- Calm
- Curious
- Trustworthy
- Evidence-first
- Simple before powerful
- Progressive disclosure of advanced capabilities
- Feel like a family historian—not enterprise software.

---

## 4. Primary Concepts

| Concept | Definition |
|---------|------------|
| **Person** | The anchor for relationships and memories. |
| **Story** | A narrative connecting many people, places, moments and artifacts. |
| **Moment** | A point or period in time. |
| **Place** | A meaningful location. |
| **Artifact** | Anything meaningful: photo, video, recipe, text, email, calendar, keepsake, playlist, medal, journal, voice memo, scanned object, etc. |
| **Evidence** | Information supporting a narrative. |
| **Relationship** | Connections between entities. |
| **Contributor** | A person who adds memories or stories. |
| **Narrative** | The AI-generated explanation assembled from evidence. |
| **User** | The current user of the system; all relationships and memory systems are oriented to that user. |

---

## 5. Product Capabilities

### Capture

- Voice memos
- Email ingestion
- Text messages
- Photo annotation
- Document scanning
- Import existing repositories, recipes, photos, voice, text, email, social media posts — anything important to the user
- Physical artifact cataloging

### Discover

- Conversational questions
- People exploration
- Stories
- Places
- Timeline
- Collections

### Teach

- By inputting new information, voice, stories, journals and more the system considers this information as very important and high confidence
- Identify faces
- Identify speech
- Identify relationships
- Identify places

### Learn

- Face confirmation
- Speaker confirmation
- Place labeling
- Relationship confirmation
- Story enrichment
- Confidence improvement

### Remember

- Life interview questions
- AI-generated prompts
- Weekly memory capture
- Voice storytelling

### Share

- Family sharing
- Read-only experiences
- Memory care
- Funeral presentations
- Export stories

---

## 6. Product Principles

- People are the anchors.
- Stories are first-class objects.
- Artifacts gain value from meaning.
- Never fabricate memories.
- Always preserve provenance.
- Capture must always be easier than organization.
- Memory Box asks thoughtful questions when appropriate.
- Users remain in control of privacy and conversation depth.

---

## 7. Core User Flows

1. Ask → Narrative → Evidence → Feedback → Learning
2. Capture → Transcribe → Understand → Link → Save
3. Review → Confirm → Improve → Rediscover
4. Story → Share → Preserve

---

## 8. Out of Scope for Version 1

- Digital human avatars
- Autonomous reasoning without user approval
- Social networking
- Social media
- Advertising
- Fully automated life reconstruction

---

## 9. Open Product Questions

- Conversation depth/privacy model
- Family permissions
- Story ownership and collaborative editing
- Artifact taxonomy
- Prompt cadence
- Long-term archival strategy

---

## 10. Next Specifications

| Doc ID | Title | Status |
|--------|--------|--------|
| MBUX-001 | User Experience Specification | Planned |
| MBKM-001 | Knowledge Model | Planned |
| MBDM-001 | Conceptual Data Model | Planned |
| MBTS-001 | Technical Specification | Planned |

Functional Architecture series ([MBX-A-*](../architecture/README.md)) elaborates HOW these product requirements are realized in layers, query model, data model, learning, and UX — and remains subordinate to this specification and the Founder's Book.
