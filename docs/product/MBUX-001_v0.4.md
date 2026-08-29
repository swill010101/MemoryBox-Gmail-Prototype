<!-- Extract from docs/source/MBUX-001_MemoryBox_UX_Foundation_and_Design_Principles_v0.4.docx — DOCX is master -->

# MBUX-001 — MemoryBox UX Foundation & Design Principles (v0.4)

**Status:** Working Baseline · approved interaction patterns through P2 I4 screen review · ingested 2026-08-13

**DOCX master:** `docs/source/MBUX-001_MemoryBox_UX_Foundation_and_Design_Principles_v0.4.docx`

**Supersedes for UX detail:** the standalone I4 Mixed-Media Exploration Addendum (kept historical below).

MEMORYBOX

MBUX-001

MemoryBox UX Foundation & Design Principles

Version 0.4 - Approved P2 Exploration Baseline

Status: Working Baseline - approved interaction patterns through P2 I4 screen review

The experience follows the memory, not the file type.

Design for a capable person who uses technology - not a person who understands software.

Prepared August 2026

# 1. Purpose and Status

MBUX-001 defines the user-experience foundation for MemoryBox. It is the governing reference for how MemoryBox should feel, present information, organize controls, accept input, move between contexts, expose evidence, and remain understandable to a non-technical user.

This document is intentionally not a screen-by-screen specification and not a catalog of every component. It defines reusable principles and rules that allow many screens to feel like one product.

Cursor should not independently invent the interaction model or visual language when MBUX-001 already establishes the rule.

Version note: v0.4 incorporates the approved P2 screen-review decisions through August 13, 2026, including the mixed-media exploration canvas, unified timeline/scrubber, shared evidence viewer, quick preview, location/map exploration, named Places, and Living Albums. Earlier architectural principles remain in force unless this version is more specific.

## 1.1 What MBUX-001 governs

Usability and simplicity

Navigation and context continuity

Panel, form, field and action design

Save, cancel, undo and correction behavior

Keyboard focus and input flow

Global Ask and conversational interaction

Voice/STT/TTS interaction principles

Evidence, uncertainty and trust presentation

Visual hierarchy and aesthetic direction

Reusable UX patterns and implementation consistency

UX acceptance criteria for Cursor-generated work

## 1.2 What MBUX-001 does not replace

MBEVS - what users must ultimately be able to accomplish

MBEF - reusable multi-step experience flows

MBCAP - reusable product capabilities

MBDM / knowledge model - domain objects and relationships

Application/technical architecture - how the product is built

Detailed implementation specifications where engineering detail is required

# 2. The User We Are Designing For

MemoryBox is built first for the Family Historian: the person who has taken responsibility for preserving family meaning. The user may be technically comfortable, but MemoryBox must not require technical knowledge.

Design for a capable person who uses technology - not a person who understands software.

A successful user may comfortably use a smartphone, email, Google Photos, a television, a browser, or common office applications. That does not mean the user should need to understand providers, indexing, databases, confidence models, embeddings, processing jobs, entity graphs, storage architecture, or software terminology.

Technical complexity belongs underneath the experience. When technical detail is necessary for an owner or advanced user, reveal it progressively and place it where it supports a decision rather than where it creates clutter.

# 3. The MemoryBox Experience Promise

People are the reason. MemoryBox is the curator, not the exhibit.

MemoryBox should help the user reconnect with people, stories, places, moments and meaningful things. The product succeeds when technology fades into the background and the family experiences authentic memories and understanding.

The intended first emotional response is curiosity and wonder, not admiration of the software. A strong interaction should naturally create the thought: "Wait - I can ask that?"

## 3.1 Experience character

# 4. Governing UX Principles

## 4.1 Human meaning before system structure

Organize and label the interface according to how a person thinks about the task, not how the database or service stores it. People, stories, places, moments and meaningful things outrank files, providers and internal entities.

## 4.2 Conversation is a primary interface

Natural language should remain available throughout MemoryBox. Typing and speaking are two inputs to the same underlying experience, not separate products.

## 4.3 People are anchors, not containers

People are powerful entry points, but evidence can connect many people, places, events, stories and artifacts. Do not force the interface into a single-person folder model.

## 4.4 The experience follows the memory, not the file type

Photos, video, audio, email, text, calendar, documents and scans are evidence types. They should support the memory, story, person or event rather than dictate the navigation architecture.

## 4.5 Same user action, same interaction pattern

A familiar action should work the same way wherever practical. A gallery is a gallery. Open/detail/return, identify, correct, link, save and inspect-evidence patterns should not be reinvented screen by screen.

## 4.6 One obvious next action

At any moment, the primary action should be visually and conceptually obvious. Secondary possibilities should remain available without competing with it.

## 4.7 Progressive disclosure beats visible complexity

Show what is useful now. Reveal advanced controls when the user asks, when context makes them useful, or in an explicitly advanced area.

## 4.8 Evidence is reachable, not dominant

The normal experience should remain human and uncluttered, while supporting evidence, provenance, uncertainty and conflicts are always accessible.

## 4.9 The family teaches; MemoryBox remembers

Corrections, identifications, relationships, dates and stories should feel like useful teaching, not administrative data cleanup.

## 4.10 Preserve emotional moments

Do not interrupt meaningful viewing, listening or reading simply because another capability exists. Sometimes the correct UX is silence.

## 4.11 Capture should be easier than organization

Voice, typing, drag/drop, email and guided capture should reduce work. Automatic processing should occur underneath where safe.

## 4.12 Trust before convenience

Never hide uncertainty, silently invent facts, overwrite original evidence, or use smooth UX to obscure an important trust decision.

## 4.13 Context follows the user

Current person, place, event, story, artifact, result set and conversational context should survive reasonable drill-down and follow-up actions.

## 4.14 Design for correction

The user must be able to recover from mistakes. Prefer clear correction, undo, merge, unlink, supersede or withdraw patterns over irreversible destructive behavior.

## 4.15 Beautiful is functional

Aesthetics are not decoration in MemoryBox. Visual calm, quality and coherence communicate trust, reduce cognitive load and make emotionally important material feel respected.

# 5. Panel and Form Design Standards

This section is deliberately prescriptive. AI-generated application panels tend to expose implementation structure, multiply actions, and group fields according to code rather than human meaning. MemoryBox should resist those defaults.

## 5.1 One panel, one understandable purpose

A panel should have a clear reason to exist that can be stated in ordinary language. If a panel is trying to edit identity, relationships, provider state, recognition thresholds and notes at the same time, it probably contains several different tasks.

## 5.2 Group fields by human meaning

Fields are grouped according to the user's mental model, not the underlying data model.

Related information should be visually grouped, ordered and labeled together. For a Person, for example, Identity, Life, Family/Relationships and Notes are more understandable groupings than a sequence based on database columns or API payload order.

Use section headings only when they clarify meaningful groups.

Keep the most common and important fields first.

Place rarely used or technical fields behind progressive disclosure.

Do not repeat the same field or concept in multiple sections unless there is a clear user reason.

Avoid long uninterrupted forms when a few meaningful groups will scan better.

## 5.3 Minimize controls

If one control can perform the task clearly, do not create several controls for the same intent.

Avoid duplicate buttons with slightly different wording.

Do not expose actions simply because the backend exposes separate endpoints.

Prefer one primary action plus clearly subordinate secondary actions.

Use menus for infrequent secondary actions when that reduces clutter without hiding important capability.

Do not create a button when selecting, typing, dragging, speaking, or direct manipulation is already the natural action.

## 5.4 Primary and secondary action hierarchy

Each editing or decision surface should normally have one visually dominant action. Secondary actions should be quieter. Destructive actions should be separated from the primary completion path.

Examples: Save Story is primary; Cancel is secondary; Delete/Withdraw belongs away from Save. Confirm Person is primary; Not this person and Defer are available but should not compete visually unless the task specifically requires comparison.

# 6. Save, Commit, Cancel and Undo

MemoryBox should not require the user to understand its persistence model. The save model should reflect the significance and reversibility of the action.

## 6.1 One logical editing task normally has one completion action

Do not scatter multiple Save buttons across one logical panel.

If a panel represents one coherent edit, the user should normally complete that edit once. Separate Save Person, Save Relationships, Save Notes and Apply Changes buttons on the same logical surface create ambiguity about what is saved and what remains unsaved.

## 6.2 Lightweight corrections may commit immediately

Simple teaching actions such as confirming a face, correcting a label, or accepting a suggested link may commit immediately when the result is visible, low-risk and reversible. Provide Undo and preserve history/provenance.

## 6.3 Significant authored content requires explicit completion

Stories, Journal entries, substantial Artifact creation, AI-composed narratives and other meaningful authored content should use explicit review/save/confirmation rather than silent commitment.

## 6.4 Avoid mixed save models inside one surface

Do not make some fields auto-save, some require Save, and some require a separate Apply button unless the distinction is unmistakable and necessary. Mixed persistence models create uncertainty and distrust.

# 7. Focus, Keyboard and Interaction Flow

The interface should be ready for the user before the user has to prepare the interface.

## 7.1 Initial focus

When a panel opens for data entry, focus should normally move to the field most likely to be used first.

Do not force an extra click before typing when the user clearly opened a surface to type.

Do not steal focus while the user is reading, listening, watching, or entering information.

For Ask, place the text caret in the Ask field when the user invokes Ask by keyboard or explicitly opens it for entry.

## 7.2 Tab and reading order

Tab order follows visual and conceptual order.

Do not jump unpredictably between distant sections.

Primary action should appear after the information it completes.

Keyboard operation should not reveal a different or inferior information architecture than mouse/touch operation.

## 7.3 Enter, Escape, Back and Return

Enter should perform the expected primary action only when accidental submission is unlikely.

Escape should dismiss transient surfaces without destroying meaningful work.

Back should return the user to the prior meaningful context, not an arbitrary default page.

Returning from an object should preserve the result set, filter state, timeline position and reasonable scroll context.

# 8. Navigation and Context Continuity

MemoryBox should feel like exploration of one connected archive, not movement between separate applications.

## 8.1 Approved architectural baseline

Person, Place, Event and Artifact use a shared Context Explorer concept with specialized components as needed.

Photos and Videos are evidence/media types rather than automatic top-level navigation categories.

Timeline is a synchronized navigation/view mechanism used within relevant experiences rather than merely a chronological report.

Review & Learn is both contextual and available as a dedicated destination.

Global Ask is available throughout major MemoryBox experiences and inherits current context unless the user changes it.

## 8.2 Drill-down and return

Open -> inspect -> act -> return should be reliable across MemoryBox. If the user opens Peggy from an Alaska result set, explores a video moment, makes a correction and returns, MemoryBox should preserve enough context that the user can continue the Alaska exploration rather than starting over.

## 8.3 Do not make navigation the experience

Navigation exists to support curiosity. Home and major exploration surfaces should not become dense menus or dashboards whose primary purpose is moving between product areas.

# 9. Home and Ask

Home is an invitation, not a dashboard.

The first purpose of Home is to make exploration feel possible. It should answer: Do I have something worth exploring? Can I simply ask? Can MemoryBox really help me?

The Ask interaction is central because it represents possibility, not because MemoryBox is merely a chatbot.

## 9.1 Home priorities

Invite a natural question.

Show enough authentic family material to establish emotional relevance.

Offer a small number of useful or curious starting points.

Allow easy continuation of recent meaningful exploration.

Keep archive administration and system health subordinate unless the user intentionally seeks them.

## 9.2 Suggested journeys

Suggestions should sound like curiosity: Tell me about Grandpa. Show Christmas through the years. What recipes did Mom leave behind? They should not read like software commands or feature advertising.

# 10. Voice, STT and TTS

Voice is another doorway into MemoryBox, not another MemoryBox.

## 10.1 One underlying action model

Speaking, typing, mouse and touch should operate the same domain objects and experience flows. "Add Sue as Peggy's sister" should invoke the same relationship action as a visual edit, with the same authority, provenance, correction and confirmation rules.

## 10.2 STT

Show transcription when review matters, but do not force transcript management for every spoken action.

Preserve original audio where the voice itself is evidence or authored memory.

Make correction of recognition/transcription errors easy and local.

Do not expose speech-processing terminology unless diagnostically necessary.

## 10.3 TTS

TTS should support hands-free and living-room experience without forcing voice output.

Spoken responses should be concise enough to follow naturally; deeper evidence can remain visual or available on request.

Do not speak over video, authentic voice or emotionally important audio. Authentic family audio has priority.

# 11. Evidence, Trust and Uncertainty

Every MemoryBox answer conceptually has two layers: the Experience Layer and the Evidence Layer. The Experience Layer is the simple human answer. The Evidence Layer explains why MemoryBox believes the answer and remains available when needed.

## 11.1 Present confidence in human language

Avoid making raw percentages the main user experience. When uncertainty matters, use understandable language and allow the user to inspect supporting evidence. Technical confidence values may remain available in advanced trust views when useful.

## 11.2 Do not turn trust into clutter

Evidence controls should not compete with the photograph, story, video, person or narrative. Trust is created by easy access to evidence and honest uncertainty, not by covering every screen in badges and confidence labels.

## 11.3 Corrections should strengthen trust

When MemoryBox is wrong, correction should be straightforward and respectful. The system should not defend its answer or make the user navigate a technical exception flow.

# 12. Visual Design Language - Working Direction

The exact visual system will evolve through screen review. This section establishes direction rather than final pixel values. A later v0.9/v1.0 may add canonical reference screens and design tokens after the product demonstrates which patterns recur.

## 12.1 Overall aesthetic

Modern, warm, calm, premium consumer software - never enterprise administration.

Light, spacious composition with strong hierarchy.

Soft neutral surfaces and restrained accent color; current concept direction favors subtle blues rather than loud multi-color UI.

Rounded geometry used consistently, not decoratively.

Family photographs and authentic media should provide much of the visual richness.

Generous whitespace where it helps comprehension and emotional material breathe.

Typography should be highly readable, contemporary and quiet.

Depth, shadows and borders should be subtle and purposeful.

Animations/transitions should reinforce continuity and orientation, not spectacle.

## 12.2 Visual hierarchy

At a glance the user should be able to tell what this screen is about, what is primary, and what to do next. Primary memory content outranks metadata. Primary action outranks secondary action. Section groups outrank individual field labels. Supporting evidence and system status recede until needed.

## 12.3 Avoid the generic AI-admin look

Do not fill screens with equal-weight cards simply because cards are easy to generate.

Do not use dense grids of small controls as the default solution.

Do not create a left/right/top toolbar for every available function.

Do not expose raw identifiers, provider names, internal statuses or developer terminology in normal family experiences.

Do not use excessive badges, pills and colored status indicators when plain language and hierarchy are clearer.

## 12.4 Authentic media has the right of way

Photos, video, voice, handwritten material and other authentic evidence are often emotionally significant. Controls should support that material rather than visually compete with it. A video of a family member speaking should feel like the center of the experience, not one widget in a management panel.

# 13. Reusable Experience Patterns - Carried Forward

The earlier approved UX architecture identified reusable patterns that remain valid. MBUX-001 keeps these as architecture anchors while this version adds practical usability and aesthetic rules.

# 14. Shared Components and Design-System Direction

MemoryBox should increasingly implement common UX behavior through shared components and design tokens so product-wide refinement can be applied consistently instead of repairing every screen independently.

## 14.1 Shared behavior first

Buttons and action hierarchy

Form fields and labels

Section/panel containers

Object cards and result galleries

Person/place/event/artifact chips or references

Evidence/provenance disclosure

Modal/drawer behavior

Save/Cancel/Undo patterns

Navigation, back and breadcrumbs

Ask and voice controls

Empty/loading/error states

## 14.2 Design tokens later, but prepare now

Exact spacing, type scale, radius, color and elevation tokens need not be frozen in this early working version. Cursor should nevertheless avoid hard-coding arbitrary one-off visual values throughout the application. Repeated visual values should be centralized so the later MBUX v1 alignment increment can update the product coherently.

# 15. Cursor Implementation Directives

Functional correctness remains the priority during P2, but known UX mistakes should not be multiplied.

Preserve accepted product behavior while applying these UX rules.

Before creating a new panel, identify its single primary purpose and primary user action.

Use existing shared components and patterns where they satisfy the task; do not create a new pattern solely because a new screen is being built.

Group controls by human meaning, not backend service or database ownership.

Prefer one primary action and one logical completion model.

Keep technical/system controls out of everyday family exploration unless explicitly requested.

Preserve current context across reasonable drill-down and return flows.

Use natural, family-centered language instead of implementation terminology.

Keep authentic memory content visually dominant over controls and metadata.

When MBUX and an existing ad-hoc panel conflict, MBUX governs unless a later explicit product decision overrides it.

# 16. P2 Integration and UX Alignment Strategy

P2 continues on two parallel paths.

## 16.1 P2 capability build

Continue building the core capabilities and evidence flows. Working capability outranks cosmetic perfection during active capability development.

## 16.2 MBUX evolution

Review real Cursor screens, existing MemoryBox screens and canonical mockups; convert observations into reusable UX rules and reference patterns.

## 16.3 Convergence

Toward the end of P2, stabilize MBUX-001 v1.0 and run a deliberate UX Alignment increment across the visible application while preserving accepted functionality.

The alignment increment should normalize navigation, panels, field grouping, controls, focus, save behavior, terminology, shared components, spacing, typography, color and hierarchy. Human review and final tuning will still be required.

# 17. UX Acceptance Checklist

A Cursor-generated or revised MemoryBox screen should be challenged with these questions before it is considered UX-aligned:

☐ Can a capable non-technical user tell what this screen is for within a few seconds?

☐ Is the primary action obvious?

☐ Could two or more visible actions be collapsed into one?

☐ Is there more than one Save/Apply behavior for one logical task?

☐ Are related fields grouped together in human terms?

☐ Does initial keyboard focus land where the user is likely to begin?

☐ Does tab/reading order make sense?

☐ Can the user back out or undo without losing unrelated work?

☐ Will returning from a detail view preserve exploration context?

☐ Is any technical language exposed that the user does not need?

☐ Are advanced options shown before they are useful?

☐ Is authentic memory content visually more important than controls?

☐ Is evidence reachable without dominating the experience?

☐ Does the screen look and behave like the rest of MemoryBox?

☐ Does the screen feel contemporary, calm, warm and intentionally designed?

☐ Would this screen still make sense when entered by voice or followed by a spoken response?

☐ Does it respect the truth, provenance and correction principles of MemoryBox?

# 18. Working Visual References and Canonical Screens

The current mockup and trailer work establishes a useful visual direction: warm modern minimalism, soft neutral surfaces, restrained blue accents, rounded forms, uncluttered composition, authentic family imagery, and a central natural-language invitation. These references are directional, not pixel-perfect requirements.

As MBUX evolves toward v0.9, select a small number of canonical MemoryBox screens - likely Home/Ask, Person, Story/Answer, Media/Object Viewer, and Review & Learn - as visual exemplars. Cursor should use them to infer the common product feel without copying every layout literally.

Canonical screens illustrate the design language. MBUX principles govern when a particular screenshot and the reusable rule conflict.

# 19. Known Open Work for v0.5-v0.9

Review the existing Cursor-generated panels and convert recurring problems into explicit rules.

Review the original concept/mockup screens for visual patterns worth preserving.

Choose canonical screen references.

Refine action hierarchy and panel layout rules using real product examples.

Define consistent modal vs drawer vs full-page behavior.

Define empty/loading/error states in MemoryBox language.

Refine high-volume photo/video browsing and timeline interaction.

Refine Review & Learn queue density and progressive disclosure.

Define accessibility targets, minimum text/control sizes and contrast requirements.

Define responsive behavior for desktop, tablet and living-room/TV experiences where needed.

Introduce design tokens only after repeated patterns are clear enough to justify freezing them.

# 20. Source Basis

This working baseline is derived from existing MemoryBox project sources and prior design work, including:

Memory Box Founder's Book - product philosophy, people/stories, simplicity, trust and evidence.

MBPS-001 Memory Box Product Specification - product goals, design goals, principles and core flows.

Existing MBUX-001 UX Architecture v0.1/v0.2 - reusable experience patterns and approved founder UX decisions.

Earlier expansive MemoryBox User Experience concept draft - curator, wonder, invitation, silence, Home and progressive discovery.

MBEF-001 Experience Flow Catalog - save behavior, undo/history, context continuity and completion principles.

MBRM-001 Roadmap & P2 Backlog - P2 UX foundation, navigation shell, high-volume exploration and alignment direction.

MBCAP-001 Capability Catalog - CAP-P2-001 UX Refinement & Product Maturation and supporting P2 UX needs.

MemoryBox Business Case - Family Historian, value proposition, trust principles and UX failure as a critical product risk.

Experience Storyboards / concept work - curator behavior, narrative/evidence layering, authentic media priority and emotional pacing.

Original mockup and trailer direction - warm modern minimal visual language centered on family content and natural questions.

# 21. Working Decision Summary

MBUX-001 is the governing UX foundation, not a screen catalog.

P2 capability development continues in parallel; do not stop core progress for cosmetic rework.

New work should stop repeating known usability defects even before full product normalization.

A late-P2 UX Alignment increment will normalize the visible application to MBUX-001 v1.0.

Shared components and centralized visual values are required to make that later alignment efficient.

The target user is capable but non-technical.

MemoryBox should look contemporary and premium while remaining warm, calm and family-centered.

One obvious action, coherent field grouping, sensible focus, consistent navigation and a clear save model are foundation requirements, not polish.

Voice, typing, mouse and touch share one underlying interaction model.

Authentic family content and stories have visual and emotional priority over software controls.

# 22. Approved P2 Exploration Patterns - v0.4

This section records interaction patterns approved during P2 screen review. These are governing UX patterns for implementation, not illustrative suggestions. Cursor should preserve the interaction model and may vary implementation detail only where it does not change the approved user behavior.

## 22.1 Ask and Curator

Ask is both a natural-question surface and a command surface. Typed input and STT operate on the same underlying context, filter, navigation and action state.

On result screens, Ask remains prominent but compact. Where width permits, the prompt “What would you like to see?” and the Ask entry field share one horizontal row. The Curator gives a concise orientation to the result; the mixed-media result canvas is the working experience.

Commands may navigate, add/remove filters, clear context, change modalities, change date/place scope, reset state, or open a saved Living Album.

The visible UI must reflect MemoryBox’s interpreted command state so the user can see what changed.

## 22.2 Mixed-Media Gallery as the Working Canvas

The principal result surface is a mixed-media gallery rather than separate file-type applications. Photos, video moments, audio moments, email/text, Stories, Artifacts, calendar evidence, documents, recipes and other supported evidence may appear together when relevant.

On a standard 13-inch laptop or iPad landscape-class screen, the normal target is approximately 12 or more visible result objects when practical. Two gallery rows are the approved baseline when available height permits; larger screens expose more objects or rows.

Gallery density is directly adjustable: more/smaller objects or fewer/larger objects.

Changing density changes presentation only, not result membership, query, filters or timeline state.

Lightweight modality filters remain available without a permanent advanced-filter sidebar.

## 22.3 Unified Timeline / Scrubber

Timeline and gallery are synchronized views of one result state. The timeline is not a passive chart and should not be duplicated by a separate gallery scrubber when one direct-control surface can do both jobs.

The timeline shows temporal extent, density/clusters, an active range, a playhead/scrub position and range handles. Banding a period makes that period the active exploration range and increases temporal precision. Handles broaden or narrow the range. Reset restores the full temporal extent of the current result.

Scrub slightly left/right to move slowly through the gallery; move farther to move faster.

Precision may adapt from years to months to days as the user narrows the range.

Every timeline change immediately reapplies to the gallery.

## 22.4 Shared Evidence Viewer

Photo and Video use the same full evidence-viewer shell and proportions. The evidence occupies the main area; a compact contextual rail provides access to People, Story, Artifact, Source and Learn. The viewer should feel like one product regardless of evidence type.

People already identified by visible face boxes should not be redundantly repeated as a large persistent panel. Selecting People may reveal additional identity/relationship context when requested.

Story and Artifact context may open as a lightweight overlay on top of the evidence viewer, with an option to enter the fuller Story or Artifact experience. If no Story or Artifact exists, the contextual state may offer to add or link one.

Photo is the base viewer experience.

Video adds playback transport, scrub/playhead, audio/mute and related media controls without changing the overall viewer size.

Video transcript is optional and off by default. When enabled, the media viewport shrinks within the same viewer and a synchronized transcript follows playback.

Closing the viewer restores the exact prior Ask, filters, timeline range/playhead, gallery density and browsing position.

## 22.5 Contextual Teach / Learn

Any suitable evidence moment may become a Teach/Learn opportunity. A photo, an artifact image, a Story-linked image, or any paused video frame can contain identity evidence worth confirming or correcting.

Confirmed/learned face or voice evidence remains provenance-preserved and can improve future recognition. Learned moments themselves remain discoverable evidence and may participate in the same gallery and timeline clusters as other matching results.

Known face boxes may be shown when useful; normal viewing should remain uncluttered.

A paused video frame may support identify, assign, reassign, unassign, adjust box, remove and Learn actions. Continuous face-box tracking during playback is not required.

With transcript enabled, a user may select a speech span, identify the speaker and use the confirmed audio span as reusable voice evidence.

## 22.6 Quick Rollover / Focus Preview

The quick preview is derived from the full evidence viewer and exists only to help the user decide whether to open an item. It should be fast, quiet and consistent across evidence types.

Mouse hover and keyboard focus trigger equivalent preview behavior. Touch opens/selects the full viewer rather than depending on hover.

Show only useful at-a-glance information when available: thumbnail/still, type, date, place, people, short title, brief description/excerpt, source and duration.

Do not turn the preview into a miniature detail screen.

## 22.7 Location and Map as First-Class Exploration

Location is a first-class exploration dimension alongside People, Time, media type and Event/Trip. It belongs in the result experience, not in software Settings.

Map is a secondary lens on the current result set: Gallery answers what, Timeline answers when, and Map answers where. Map is not a separate top-level destination.

Map markers/clusters show only the current result context.

Hover/focus may show the same lightweight quick preview used by the gallery.

Selecting a marker/place can refine the current result with a location filter and return to the synchronized gallery/timeline state.

The map should choose an appropriate geographic extent based on the result (local, regional, national or world).

## 22.8 Named Places and Saved Map Pins

The user may save a human-readable Place for evidence by placing/selecting a map pin and naming it, for example “Dad’s House,” “Mom’s House,” or “Family Cabin.” Latitude/longitude remain implementation detail; the family-facing object is the named Place.

A named Place is a durable family anchor that can connect photos, video moments, Artifacts, Stories, events and other evidence. Future AI visual-setting recognition may infer that an image/video setting resembles a known Place, but inferred setting must remain distinguishable from exact GPS or owner-confirmed location.

Preserve location provenance: exact embedded GPS, owner-saved Place, imported place metadata, or AI-inferred setting.

Do not silently collapse exact, approximate and inferred location into the same confidence state.

## 22.9 Living Albums - Saved Intent, Not Frozen Results

A user may save the current exploration definition so it can be reproduced later. The saved object stores the Ask/intent and normalized state - not merely today’s matching result IDs.

The customer-facing working name is Living Album. Reopening a Living Album reruns its definition against the current archive, so newly imported evidence, newly contributed Stories, newly learned People/Places and improved recognition can appear automatically.

A Living Album may preserve: original Ask, normalized People, Place, Event/Trip/theme, date band, modalities, filters, sort, gallery density/view mode, map state, trust/evidence refinements and other meaningful exploration state.

Living is the default dynamic mode.

Curated mode preserves intentional owner selection/order while retaining the underlying saved intent and may suggest new matches.

Snapshot/Frozen mode preserves an exact result set/version for sharing, presentation, print or reproducibility.

The UI must clearly distinguish a live/recomputed view from a curated or frozen collection.

## 22.10 Design Consequence

The result canvas, Timeline, Map, shared evidence viewer, contextual Learn and Living Albums are not separate mini-applications. They are interoperable views/actions over one continuous exploration state. The user should be able to move among them without reconstructing the question or losing context.

## v0.4 revision summary

Locked mixed-media two-row high-density exploration canvas and gallery density control.

Unified timeline and scrub behavior into one synchronized temporal control.

Locked shared Photo/Video evidence viewer, optional synchronized transcript and contextual People/Story/Artifact/Source/Learn rail.

Locked quick rollover/focus preview derived from the full evidence viewer.

Added Location as a first-class result filter and Map as the “where” lens on current results.

Added owner-saved named Places/map pins with provenance and future inferred-setting linkage.

Added Living Album: saved exploration intent/state that recomputes against the current archive, plus Curated and Snapshot modes.

### Table 1

| MemoryBox should feel | MemoryBox should not feel |
| --- | --- |
| Warm, calm, modern, personal | Enterprise, administrative, technical |
| Inviting and curious | Instruction-heavy or demanding |
| Confident but humble | Authoritative when evidence is uncertain |
| Premium and visually considered | Generic, dated, template-driven |
| Simple before powerful | Feature-dense by default |
| Evidence-backed | AI-magical or unexplained |
| Consistent | Like separate tools stitched together |

### Table 2

| Pattern | Purpose |
| --- | --- |
| Ask / Search | Express an information need naturally. |
| Browse / Explore | Explore without needing a precise question. |
| View Result Set | Review, filter and open one or more matching objects. |
| View Object | Experience one item plus its relevant context. |
| Play / Experience Media | View or hear authentic media with minimal interference. |
| Filter / Refine | Narrow the current context without starting over. |
| Associate / Link | Connect people, stories, places, events, artifacts and evidence. |
| Teach / Correct | Improve MemoryBox through human clarification. |
| Import / Capture | Bring new evidence or memory into the archive. |
| Inspect Evidence | Understand why MemoryBox believes something. |
| Tell / Edit Story | Create durable human-authored narrative. |
| Compose / Synthesize | Create a proposed evidence-backed AI narrative for review. |
| Review / Confirm / Save | Control what becomes durable knowledge. |
