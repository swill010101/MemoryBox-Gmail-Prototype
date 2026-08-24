# P2-I10A.2 — Reusable Speech Input for Text Entry

**Status:** PRD **DRAFT** 2026-08-24 · owner text below · Cursor assessment complete · **not locked** · **not build-authorized**  
**Increment:** P2-I10A.2  
**Assessment:** [MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md)  
**Definition:** [MBBS-P2_INCREMENT_10A2_DEFINITION.md](MBBS-P2_INCREMENT_10A2_DEFINITION.md)  
**Surface map:** [MBAS-P2-I10A2_SURFACE_MAP.md](MBAS-P2-I10A2_SURFACE_MAP.md)  
**Depends:** I10A · I10A.1 · I10B (accepted). Existing Story, Journal 5A, Artifact, Person Edit text entry.  
**Does not start:** I10C · I11 · I9 · Immich · voice-as-evidence

**Repository fact (assessment):** Story, Journal, and Artifact **do not** already share a multiline editor. I10A.2 **must** consolidate that control first, then add speech once.

---

# Owner PRD

**Primary objective:** Allow users to speak naturally wherever MemoryBox expects substantial written narrative or notes.

## 1. Problem

MemoryBox currently requires typing for substantial authored text such as:

* Stories
* Journal entries
* Artifact descriptions and stories
* Person notes
* Other substantial free-text narrative fields

Typing is appropriate for editing, but it should not be the only practical method of capture.

MemoryBox is intended to make capture easier than organization. A user should be able to speak a memory, explanation, description, or note directly into the same place where it could be typed.

The implementation should not create separate speech workflows for Story, Journal, Artifact, or future text-entry surfaces.

## 2. Product Decision

Add reusable **speech-to-text input** to substantial free-text entry fields.

Speech and typing operate on the **same text value**.

The microphone is an input method, not a separate content type, editor, or workflow.

Initial required surfaces:

* Story create/edit
* Journal create/edit
* Artifact create/edit
* Person substantial notes fields where applicable

The same capability should automatically be available to future MemoryBox surfaces that use the approved reusable multiline/narrative text-entry component.

## 3. Scope Boundary

### In scope

Substantial free-text fields such as:

* Story narrative
* Journal body
* Artifact description/story
* Person notes
* Long-form comments or explanations
* Future narrative/memory capture fields

### Not automatically in scope

Do not add microphone controls to every text box.

Exclude ordinary structured or short-entry fields such as:

* Person name
* Nickname
* Email address
* Phone number
* Dates
* Search/typeahead Person pickers
* Place selectors
* Relationship selectors
* Titles unless later UX review establishes a useful reason

The design principle is:

**Speech belongs where the user is composing thoughts, memories, explanations, or narrative — not beside every field that technically accepts characters.**

## 4. User Experience

A supported text-entry area displays a quiet microphone action associated with the field.

### Start

User selects the microphone.

MemoryBox begins listening.

The UI must clearly indicate that recording/transcription is active.

### While speaking

Recognized speech appears in or is staged for the same text field.

The user can see what MemoryBox understood.

The user may stop speaking without leaving the editor.

### Stop

User stops speech input explicitly or through the approved end-of-input behavior.

The resulting transcript becomes editable text in the existing field.

### Continue

The user may:

* type corrections;
* continue typing;
* reposition the cursor;
* speak additional text;
* remove dictated text;
* resume dictation.

Speech must not create a second parallel copy of the field.

## 5. Insert Behavior

Speech should respect the current editing position.

Default behavior:

* Empty field → insert from beginning.
* Cursor at end → append.
* Cursor within existing text → insert at cursor.
* Selected text → do **not** silently overwrite unless replacement behavior is explicitly implemented and obvious.

Do not replace existing authored content merely because the microphone was activated.

## 6. Transcript Review

Speech recognition is not authoritative.

The transcript must remain ordinary editable text before the containing object is saved.

The user can correct transcription errors using normal editing.

Do not require a separate transcript-management screen for routine text dictation.

## 7. Save Semantics

Speech input does **not** change the save model of the containing surface.

Examples:

### Story

Dictated Story text remains unsaved until the normal Story Save action.

### Journal

Dictated Journal text follows the existing Journal save behavior.

### Artifact

Dictated Artifact description/story follows the existing Artifact save behavior.

Starting or stopping speech must never implicitly save the object.

## 8. Cancel Semantics

Canceling the containing editor behaves exactly as it does for typed content.

Dictated but unsaved text is treated as unsaved editor content.

Speech input must not create hidden durable records merely because transcription occurred.

## 9. Reusable Component Requirement

Do not implement:

* Story microphone logic
* Journal microphone logic
* Artifact microphone logic

as three independent features.

Implement speech capability through the approved shared multiline/narrative text-entry component or equivalent reusable abstraction.

A supported field should be able to declare conceptually:

`speech input allowed`

without implementing its own speech lifecycle.

This is a product-wide capability.

## 10. Visual Behavior

The microphone control should be:

* recognizable;
* available without dominating the editor;
* visually consistent wherever used;
* associated clearly with the text field it affects.

While active, show unmistakable listening state.

Possible states:

* Idle
* Listening
* Processing/transcribing
* Error/unavailable

Do not expose model/provider terminology during ordinary use.

## 11. Speech Availability / Failure

If speech recognition is unavailable:

* typed entry must continue working normally;
* existing field content must remain untouched;
* the user receives a concise human-readable explanation;
* the editor must not become blocked.

Example:

`Speech input isn't available right now. You can keep typing.`

Do not present raw provider, HTTP, model, microphone-device, or stack errors in the family-facing interface.

## 12. Permission Handling

If microphone permission is required, request it only when the user first attempts speech input or through an appropriate previously approved permission flow.

If permission is denied:

* explain briefly that microphone access is needed for speech input;
* preserve normal typed entry;
* allow the user to retry after permissions change.

## 13. Voice Is Input, Not Evidence by Default

I10A.2 provides **dictation into authored text**.

It does not automatically mean the microphone recording becomes preserved audio evidence.

For example:

Speaking an Artifact description:

> “Dad carried this pocket watch during the war.”

may produce editable text in the description field.

It does not automatically create a Voice Memory or audio Artifact.

Preserving authentic recorded voice as evidence is a separate capture behavior and must remain governed by its appropriate capability/increment.

## 14. Relationship to Spoken-Moment Capabilities

Do not confuse I10A.2 with:

* speech recognition inside historical videos;
* diarization;
* speaker identification;
* searchable spoken moments;
* voice enrollment;
* playback of authentic voice evidence.

Those are archive-analysis capabilities.

I10A.2 is **live owner speech used as text input**.

## 15. Future Compatibility

The implementation must remain compatible with future:

* STT provider changes;
* local speech models;
* cloud speech services where allowed;
* voice commands;
* mobile/tablet use;
* accessibility improvements.

The UI must not depend on one provider's internal terminology or payload shape.

## 16. Acceptance Tests

### AT-01 — Story dictation

Given a Story editor,

when the user starts speech input and speaks,

the recognized words appear as editable Story text.

The Story is not saved until normal Story Save.

### AT-02 — Journal dictation

Given a Journal editor,

speech input inserts editable text into the Journal body using the same reusable behavior as Story.

### AT-03 — Artifact dictation

Given an Artifact narrative/description field,

speech input inserts editable text without creating a separate Artifact or voice record.

### AT-04 — Existing text preserved

Given existing text in a supported field,

starting speech input does not delete or replace that text.

### AT-05 — Insert at cursor

Given the cursor positioned within existing narrative text,

new dictated text is inserted at the appropriate editing position.

### AT-06 — Editing after transcription

After speech is converted to text,

the user can freely type, delete, correct, and continue dictating.

### AT-07 — Save unchanged

Speech activity does not create an implicit Save.

The containing screen retains its existing Save/Cancel contract.

### AT-08 — Permission denied

If microphone permission is denied,

typed entry remains fully operational and existing text is preserved.

### AT-09 — STT unavailable

If speech recognition fails or is unavailable,

the user receives a concise nontechnical message and may continue typing.

### AT-10 — Shared behavior

Story, Journal, Artifact, and other approved narrative fields use one shared speech-input behavior rather than screen-specific implementations.

### AT-11 — No microphone clutter

Ordinary structured fields such as names, dates, email addresses, phone numbers, and Person pickers do not acquire microphone controls simply because they accept text.

### AT-12 — No unintended audio evidence

Routine dictation does not create or preserve a separate audio evidence object unless the user entered an explicitly approved voice-recording workflow.

## 17. Out of Scope

I10A.2 does not implement:

* general voice navigation;
* spoken Ask;
* TTS responses;
* speaker recognition;
* diarization;
* historical media transcription;
* searchable spoken moments;
* voice enrollment;
* automatic audio-memory preservation;
* AI rewriting or summarizing dictated text;
* microphone controls on every input field.

## 18. Cursor Implementation Direction

Before coding:

1. Identify all existing multiline/substantial text-entry components.
2. Identify Story, Journal, Artifact, and Person-note fields using them.
3. Determine whether they currently share one component or require consolidation.
4. Propose the smallest reusable speech-input abstraction.
5. Preserve existing editor Save/Cancel behavior.
6. Do not introduce screen-specific microphone implementations.
7. Do not expose speech-provider implementation details in normal UX.
8. Add the acceptance cases above.
9. Log capabilities outside this boundary rather than expanding I10A.2.

**Assessment of step 3:** they do **not** share one component. Consolidation is Required (see assessment).

## 19. Locked Intent (when Tom accepts)

**MemoryBox users may speak wherever they would naturally compose a substantial block of text.**

Speech and typing edit the same content.

The feature is reusable across MemoryBox.

The microphone does not belong beside every short field.

Dictation does not implicitly save the object or create permanent audio evidence.

Capture should feel easier, while the existing Story, Journal, Artifact, and Person editing models remain intact.

---

**Not locked. Planning only. Do not implement until Tom accepts this PRD and authorizes build.**
