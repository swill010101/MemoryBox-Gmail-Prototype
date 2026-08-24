# P2-I10A.2 — Assessment reconciliation

**Status:** Planning only **2026-08-24** · not build-authorized · does not implement code  
**Owner draft PRD:** Reusable Speech Input for Text Entry (this increment)  
**Draft PRD file:** [MBPRD-P2-I10A2_SPEECH_INPUT.md](MBPRD-P2-I10A2_SPEECH_INPUT.md)  
**Surface map:** [MBAS-P2-I10A2_SURFACE_MAP.md](MBAS-P2-I10A2_SURFACE_MAP.md)  
**Definition:** [MBBS-P2_INCREMENT_10A2_DEFINITION.md](MBBS-P2_INCREMENT_10A2_DEFINITION.md)  
**Base:** `cursor/p2-i10a1-person-build-49da` (I10A.1 **ACCEPTED** 2026-08-24)

Screenshot intent is not proof of a shared editor. This document traces the **current repository**.

---

## Architectural finding (owner question)

**Story, Journal, and Artifact do not share a multiline editor component.**

They are three independently authored pages, each with its own `<textarea>`, styles, and save wiring. There is no shared web component, no shared JS module, and no shared CSS class that means “narrative field.”

| Surface | File | Narrative control | Shared with others? |
|---|---|---|---|
| **Story** create/edit | `memorybox/story/static/story.html` | `#ed-body` `<textarea>` (paragraphs via blank lines; `# ` headings). Title `#ed-title` and description `#ed-desc` are **single-line `<input>`**. | No |
| **Artifact** create/edit | `memorybox/artifact/static/artifact.html` | `#ed-desc` `<textarea>` (object description). Name `#ed-label` is an `<input>`. Recollections are supposed to be Stories, not this box. | No |
| **Journal** 5A POC | `memorybox/journal/static/journal.html` | `#body` and `#editBody` `<textarea>`. Own Record/Stop/`MediaRecorder`/`POST /capture/transcribe`. Light theme, not I10A/I10B chrome. | No |
| **Person** notes | `memorybox/person/static/person-edit.html` | `#mb-edit-notes` `<textarea>` → `person_facts` `fact_kind=note`. | No |

**Recommendation (Required for I10A.2):** before attaching a microphone to any screen, extract one reusable **narrative text-entry** control (textarea + field-associated chrome, including a future mic slot). Adopt it on Story body first, then Artifact description, Person notes, and Journal body. Do **not** copy-paste mic logic into `story.html`, `artifact.html`, `journal.html`, and `person-edit.html`.

That consolidation is the increment’s first slice, not a later cleanup.

---

## What already exists (speech)

| Capability | Where | Relation to this PRD |
|---|---|---|
| Preserve audio + Whisper STT | `POST /capture/transcribe` · `memorybox/providers/capture/` | Journal POC and I10B’s **old** I10A.2 sketch. **Preserves audio on disk.** Conflicts with this PRD §13 / AT-12 unless dictation uses a **text-only** path. |
| Journal Record/Stop | `journal.html` inline JS | Replaces `#body` with `draft.text` (does **not** insert at cursor). Exposes duration/rms and audio id. Not family chrome. |
| Archive video STT | I9 `speech_queue` · Explore “Transcribe this video” | **Out.** Historical media, not live owner dictation. |
| Browser `SpeechRecognition` | **Not used** in MemoryBox static UI | Optional later provider; UI must not depend on it. |
| Story `story_versions.audio_uri` | Schema exists; I10A editor does not write it | Old I10A.2 sketch wanted capture audio on the working version. This PRD says dictation is **not** evidence by default. |

I10A Stories **froze** “do not expose dictation.” I10A.2 may add dictation **inside** the Story editor without reopening I10A.

I10B **Tell its story** is **not** Artifact-description dictation. Artifact UI already navigates to `/story/ui?new=1&artifact={id}&capture=1`. **Story ignores `capture=1` today** (opens the typed editor only). I10B also Frozen **“Dictating Artifact description | Forbidden.”** This owner PRD’s AT-03 (mic on Artifact `#ed-desc`) **reverses that lock** unless Tom explicitly supersedes I10B for object-description dictation only (testimony still on Stories).

Both Story body and (if allowed) Artifact description can use the **same** narrative control; they remain different objects.

---

## Conflict with the previous I10A.2 name

Roadmap text still says **“Unified Voice Capture & Transcription”** and I10B lists preserve-audio, play original, `audio_uri`, narrator confirm, queued transcribe jobs.

This owner PRD is **live dictation into the same text value**, not a voice-memory recorder.

**Recommendation:** keep increment id **P2-I10A.2**. Rename the product title to **Reusable Speech Input for Text Entry**. Park **preserve authentic voice as evidence** as a later capability (not I10A.2, not I9). I10B Tell its story still consumes **Story-editor dictation**, not a second Artifact `MediaRecorder`.

---

## Insert / save vs today’s Journal POC

Journal STT does `document.getElementById("body").value = draft.text` — whole-field replace. That fails AT-04 / AT-05 if reused.

Save: Story Save memory / Save draft, Artifact Save, Person Save, Journal Save Journal are all **separate**. Speech must not call them. The shared control only mutates the textarea value.

Cancel: each screen already discards unsaved editor state. Dictation must not write `MEMORYBOX_CAPTURE_DIR` (or must treat those files as ephemeral scratch and delete them) if AT-12 is Frozen.

---

## In vs out (repository)

**In (narrative `<textarea>` after shared control):**

- Story `#ed-body`
- Artifact `#ed-desc`
- Person `#mb-edit-notes`
- Journal `#body` / `#editBody` (replace 5A recorder with the shared control; do not finish I10C)

**Out (do not add a mic):**

- Story title, Story description `<input>`, dates, place, people pickers, visibility
- Artifact name, kind, date, place, people, representation caption (short; later UX if needed)
- Person display name, nickname, other name, email, phone, dates
- Explore Ask box, search, Person picker typeahead
- Guided Capture question lists / transcript admin
- I9 video transcribe

**Do not start:** spoken Ask, TTS, I9, voice enrollment, I10C Journal product, I11, Artifact private recorder, three screen-specific mics.

---

## Proposed build sequence (when authorized — not now)

1. Shared narrative field (DOM + CSS + tiny JS: get/set value, cursor, selection). Prove it is the only `#ed-body` / `#ed-desc` / notes / journal body control.
2. Shared speech-input module bound **only** to that field (`speech input allowed`). Idle / listening / processing / error. Insert at cursor. Never Save.
3. Story editor first (reopen dictation here).
4. Artifact description, Person notes, Journal body (retire inline `MediaRecorder` on `/journal/ui` without claiming I10C done).
5. Acceptance AT-01–AT-12 as `prove-speech-input` (name **Open**).

---

## Open questions for Tom

1. **Audio files:** Discard after STT (this PRD), or keep preserve-then-transcribe from I10B/Journal? **Recommendation:** dictation = ephemeral; do not create Voice Memory / `audio_uri` on Save.
2. **STT engine:** Reuse Whisper via a **non-preserving** or scratch transcribe, vs browser speech, vs both? UI must stay provider-silent.
3. **Stories first vs all surfaces in one increment:** PRD lists Story, Journal, Artifact, Person as initial required. **Recommendation:** one increment, but **gate** on shared control + Story; remaining surfaces same increment, not three later forks.
7. **Artifact description mic vs I10B:** I10B forbade dictating Artifact description. This PRD wants it. Keep I10B (description typed only; mic only via Tell its story → Story body) or supersede for object-description dictation?
5. **Selected text:** Frozen “do not silently overwrite” — insert after selection, or obvious Replace? **Recommendation:** insert at cursor; do not replace selection in v1.
6. **I10C:** Journal family chrome remains I10C. I10A.2 only puts the shared field on the existing 5A shell (or wait for I10C to consume the control). **Recommendation:** wire Journal `#body` now so the POC mic does not remain a second implementation.

---

## Cursor implementation direction (locked for planning)

Do not bolt a microphone onto three screens. Consolidate the narrative field first. Then one speech lifecycle. Then attach `speech input allowed` to Story, Journal, Artifact, and Person notes.

**Not locked. Not build-authorized.**
