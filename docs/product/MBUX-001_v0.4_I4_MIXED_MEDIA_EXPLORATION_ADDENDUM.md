# MBUX-001 — MemoryBox UX Foundation & Design Principles

## Version 0.4 — I4 Mixed-Media Exploration Addendum

**Status:** Approved UX direction for current P2 implementation.  
**Supplements:** MBUX-001 v0.3. Where this addendum is more specific about the Mixed-Media Find / Explore experience, **this addendum governs**.  
**Recorded in-repo:** 2026-08-13 (founder-provided text; formatting only).

---

### PURPOSE

This addendum defines the primary MemoryBox exploration pattern developed during P2 UX review.

MemoryBox should not present a Curator answer with a small evidence section beneath it.

The Curator explains the find.  
The Library/result canvas is where the user experiences and works with the find.

The governing interaction loop is:

**Ask → Refine → Browse → Inspect → Teach/Learn when useful → Close → Continue**

The user should remain in one coherent exploration context throughout this loop.

---

### 1. TOP-LEVEL EXPERIENCE

Primary top-level navigation should represent important family objects or meaningful things the user wants to do rather than every supporting application panel.

**Current working top-level navigation:**

- Ask  
- People  
- Stories  
- Journal  
- Artifacts  
- Family Night  
- Teach  

System Health, Status, provider controls, metadata panels, transcripts, Timeline controls, Library internals, and similar supporting functions are not primary top-level destinations.

System or archive-health issues should normally be surfaced contextually when user action is useful.

Stories remain a top-level destination for now, but Stories primarily provide meaning and context around People, Artifacts, external evidence, Events, Places, Moments, and related family context. A disconnected Story with no subject/context/provenance is not the intended MemoryBox model.

---

### 2. ASK IS BOTH QUESTION AND COMMAND

Ask accepts natural-language questions and commands.

Typing and STT must manipulate the same underlying state and command model.

Examples:

- “Tell me about Peggy around Christmas.”  
- “People.”  
- “Clear context and go to People.”  
- “Only show photos.”  
- “Add video.”  
- “Remove Peggy.”  
- “Show 1998 through 2005.”  
- “Reset filters.”  
- “Show everything again.”  

When speech or typed Ask changes filters, context, date range, navigation, or result state, the visible UI must immediately reflect MemoryBox’s interpretation.

Voice is not a separate application mode. It is another control path for the same MemoryBox experience.

---

### 3. ASK VISUAL TREATMENT

Ask remains highly visible and easy to invoke but should not consume excessive vertical space after a result exists.

Approved direction:

- MemoryBox logo and branding remain visible.  
- “Life doesn’t live in folders.” remains the brand tagline.  
- “What would you like to see?” and the Ask entry field should preferably share one horizontal row where available rather than being vertically stacked.  
- The Ask entry field remains generously sized and easy to target by mouse, touch, keyboard, or STT.  
- The current query remains visible unless intentionally cleared or replaced.  

---

### 4. CURATOR + LIBRARY RESULT MODEL

A Curator answer orients the user but does not replace exploration.

Example:

> “I found 23 memories of Peggy around Christmas, including 14 photos, two video moments, six emails, and a story Rick told.”

The Curator summary should remain concise by default.

The principal working surface beneath the Curator is a mixed-media Library/result canvas.

The evidence is not relegated to a small supporting-evidence region beneath a narrative.

The mixed-media result itself is the working experience.

---

### 5. MIXED-MEDIA GALLERY

The gallery displays relevant result objects together by default rather than splitting them into separate Photo, Video, Email, Artifact, or other application areas.

Potential cards include: Photos, Video moments, Audio moments, Email, SMS/Text, Calendar evidence, Recipes, Documents, Artifacts, Stories, Other supported evidence/context.

Cards should share a coherent visual grammar while retaining enough indication of media type to be understandable.

Default result ordering is newest to oldest unless user intent requires another order.

The gallery should support high information density without becoming visually chaotic.

**Target:** On a standard 13-inch laptop or iPad landscape-class display, the normal result surface should support approximately **12 or more** visible mixed-media objects when practical.

Use multiple gallery rows when available screen height supports them. **Two rows** is the approved current target. Larger displays may expose additional rows or objects.

The user controls gallery density independently from timeline range.

Gallery density control should allow:

- more objects / smaller cards, or  
- fewer objects / larger cards  

Changing density does not change query meaning, result membership, timeline selection, or filters.

---

### 6. QUICK PREVIEW

Cards may expose a lightweight hover/rollover preview for rapid scanning.

Quick preview may show: larger preview, date, people, media duration, sender/recipient, short excerpt, relevant context.

Quick preview must remain lightweight. Full inspection occurs in the evidence modal.

---

### 7. LIGHTWEIGHT FILTERS

The main exploration surface should expose only a small, understandable filter set.

Typical examples: All, Photos, Video, Audio, Email/Text, Artifacts, Stories, More.

Do not expose a large permanent advanced filter panel.

Current context/filter state should also be represented with quiet chips such as: Peggy, Christmas, 1998–2021.

Filters and context may be added, removed, reset, or changed by direct manipulation, typed Ask, or STT. All methods manipulate the same state.

---

### 8. UNIFIED TIMELINE / SCRUB CONTROL

The Timeline is both:

1. a graphical representation of where matching memories occur in time, and  
2. a direct navigation/scrub control for the gallery.  

Do not create redundant separate timeline and gallery-scrubber controls when one unified control can perform both roles.

The unified Timeline should:

- show the result’s temporal extent  
- show evidence density using dots/clusters  
- show the active visible/selected range  
- support a movable playhead/scrub interaction  
- support range banding  
- support left/right range handles  
- support Reset  

Moving/scrubbing the Timeline changes what portion of the current result the gallery is displaying.

Scrubbing should feel similar to media scrubbing:

- move slightly left/right = move through the gallery slowly  
- move farther left/right = move through the gallery more quickly  

The Timeline remains synchronized with the mixed-media gallery.

---

### 9. TIMELINE RANGE AND PRECISION

The initial Timeline range is derived from the matched result set.

Examples:

- Peggy around Christmas: earliest 1998, latest 2021 → initial range 1998–2021  
- “Life of Tom”: earliest matched 1955, latest matched/current 2026 → initial range 1955–2026  

The Timeline does not invent dates earlier or later than the relevant result merely because the term “life span” is used.

Use **“Reset”** rather than “Full Range.” Reset restores the Timeline to the complete temporal extent of the current result/query.

Banding a portion of the Timeline means: **Make this the period I am exploring.**

Example: drag across 2005–2011 → MemoryBox should narrow the active range, increase Timeline precision, and immediately reapply that range to the gallery.

As precision increases, Timeline labeling/granularity should adapt where appropriate: decades → years → months → days.

The user should be able to broaden the range again by dragging the left or right range handles outward.

Therefore:

- Band inward to explore more deeply.  
- Move handles outward to broaden.  
- Reset to restore the complete result range.  

---

### 10. TIMELINE AND GALLERY STATE ARE ONE EXPERIENCE

Every meaningful Timeline change must immediately reapply to the gallery.

Every date-range/filter change visible in the gallery should remain reflected in Timeline state.

Timeline is not a passive visualization. It is one of the main controls for the result set.

---

### 11. EVIDENCE DETAIL MODAL

Selecting a result object should not normally navigate to a completely new application screen.

Open the selected object in a large modal/detail workspace within the existing exploration context.

Desktop target: approximately **85–95%** of available working canvas where appropriate.

The underlying result context may remain dimly perceptible.

The modal should provide enough space for media plus relevant contextual information/actions without requiring the user to abandon the result set.

Closing the modal returns the user to exactly the prior exploration state:

- same query  
- same person/event/context  
- same filters  
- same Timeline range  
- same Timeline/playhead position  
- same gallery density  
- same gallery position  
- same reasonable scroll position  

The user should never have to reconstruct the search after inspecting an item.

---

### 12. EXTERNAL OBJECT DETAIL

The modal uses a common evidence-detail shell with media-specific behavior (photo, video moment, audio, email, SMS/Text, calendar, recipe, artifact, documents) as specified in the founder addendum source.

---

### 13. CONTEXTUAL TEACH / LEARN

Teaching should normally occur while the user is naturally inspecting evidence.

Photo face teaching, video face teaching (**paused/still frame only**), and video/audio voice teaching behave as specified in the founder addendum source.

Teaching interactions must preserve provenance and remain correctable.

---

### 14. LEARN IS CONTEXTUAL AND BACKGROUND-CAPABLE

Where confirmed evidence can improve future recognition, provide a contextual Learn action. Long-running learning/recognition work should continue in the background where practical and should not trap the user in an administrative process.

---

### 15. CONTEXT CONTINUITY

Governing exploration rule:

**Ask → Refine → Browse → Open Modal → Inspect/Teach → Close → Continue**

The user remains in the same mental place.

Do not reset the user to Home, People, the beginning of the query, or a generic Library screen after closing detail.

---

### 16. I4 IMPLEMENTATION PRINCIPLE

For the current P2 I4 Timeline work, functionality and UX must be implemented as one synchronized exploration model.

Timeline should not be completed as an isolated timeline page that will later need to be redesigned around mixed-media exploration.

I4 may implement underlying services and state independently, but the visible accepted UX must conform to this addendum.

---

**END ADDENDUM**
