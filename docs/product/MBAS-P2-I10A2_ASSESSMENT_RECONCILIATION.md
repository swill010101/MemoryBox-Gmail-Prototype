# P2-I10A.2 — Assessment reconciliation (amended)

**Status:** Increment **ACCEPTED** 2026-08-24 (Tom: “i10A.2 is accepted”) · planning **LOCKED**  
**PRD:** [MBPRD-P2-I10A2_SPEECH_INPUT.md](MBPRD-P2-I10A2_SPEECH_INPUT.md)  
**Contract:** [MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md](MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md)  
**Acceptance:** [MBAT-P2-I10A2_ACCEPTANCE.md](MBAT-P2-I10A2_ACCEPTANCE.md)  
**Surface map:** [MBAS-P2-I10A2_SURFACE_MAP.md](MBAS-P2-I10A2_SURFACE_MAP.md)  
**Base:** `cursor/p2-i10a1-person-build-49da` (I10A.1 **ACCEPTED** — do not reopen)

---

## Architectural finding (unchanged)

**Story, Journal, Artifact, and Person notes do not share a multiline editor.** Four `<textarea>`s, four pages. I10A.2 **must** consolidate first. Do not bolt four mics onto the current markup.

| Surface | File | Today |
|---|---|---|
| Story | `story/static/story.html` | `#ed-body` |
| Artifact | `artifact/static/artifact.html` | `#ed-desc`; Tell its story → `?capture=1` (**ignored** by Story) |
| Journal | `journal/static/journal.html` | `#body` / `#editBody` + private Record/Stop → `/capture/transcribe` (whole-body replace) |
| Person | `person/static/person-edit.html` | `#mb-edit-notes` |

I9 archive STT and browser `SpeechRecognition` are **not** this increment’s UI. `POST /capture/transcribe` **preserves audio** today — correct for **authored-memory** Save; wrong as a blanket for Person notes / Artifact description; wrong as Journal’s whole-field replace UX.

---

## Founder decisions that close prior Open items

| Was Open | Now Frozen |
|---|---|
| Discard all dictation audio vs keep | **Semantics:** authored-memory keep on Save; convenience transient |
| I10B forbid Artifact description dictation | **Superseded.** Description = convenience speech |
| Stories first vs all four surfaces | **All four in I10A.2**, after shared component |
| Journal POC | **Not the target.** Shared lifecycle replaces it; audio-keep for Journal was directionally right |
| Person notes | Shared field; **convenience** default |

---

## Proposed shared-editor abstraction (Recommendation)

One client module, e.g. `memorybox/shell/static/mb-narrative-field.js` (+ CSS), wrapping a textarea:

- `MBNarrativeField.mount(el, { speech: "off" \| "convenience" \| "authored-memory" })`
- Same get/set text, cursor, selection
- Convenience: quiet mic, insert at cursor, discard audio after STT success
- Authored-memory: Ready → Record (Pause/Stop) → Pause (Resume) → Stop → Review (play/scrub/edit/Start Over) → page Save commits package

STT: reuse `CaptureSttProvider` / `/capture/transcribe` **or** a successor that can (a) preserve for authored-memory Save and (b) scratch/delete for convenience and for Cancel/Start Over. Family UI never names the provider.

Schema: `story_versions.audio_uri` exists but editor does not write it. Journal already has `audio_uri` on save. I10A.2 must persist authored-memory audio **on containing Save** and support **more than one vintage** of audio across revisions without mutating prior versions. Exact table vs single column is implementation at build; provenance must not flatten.

---

## Remaining contradictions (after amendment)

| Topic | Status |
|---|---|
| I10B “Dictating Artifact description \| Forbidden” | **Resolved** — I10A.2 supersedes; I10B not reopened for polish (footnote on that row) |
| I10B §E “Unified Voice” must-deliver (pause, review, preserve, shared UI, no Artifact MediaRecorder) | **Aligned** with authored-memory Story path. Queued job states / max duration remain **implementation** at build, not a product fork |
| I10B “Tell its story creates a Story not Artifact description” | **Aligned** — authored-memory stays on Story; Artifact `#ed-desc` is convenience only |
| Journal POC Record/Stop | **Must be replaced** in I10A.2 (A-17). Not I10C |
| Roadmap name “Unified Voice Capture & Transcription” | **Rename** to this PRD title; keep id I10A.2 |
| I10A “no dictation” | **Unchanged for I10A**; I10A.2 adds it inside Story editor |
| I10A.1 Person notes | **Not reopened**; I10A.2 only adds shared field + convenience speech |
| Single `audio_uri` vs multiple takes | **Recommendation:** one committed take per saved version; later revision may add a new clip; do not rewrite old version audio. Not founder-blocking |

No **material product contradiction** remains that blocks founder lock.

---

## Unresolved (not founder-blocking)

1. **STT engine choice** (local Whisper vs HTTP vs later browser): UI-silent; reuse existing capture provider unless it cannot delete scratch audio.
2. **Prove command name:** `prove-i10a2` **Recommendation**.
3. **Max duration / file size / async job vs sync transcribe:** I10B left Open; pick at build without changing this PRD’s Save/Review contract.
4. **Story `#ed-desc` one-line input:** stays without mic unless a later UX review.

---

## Proposed build sequence (when authorized)

1. Shared narrative field on all four surfaces (typed only still works).
2. Convenience speech (Person notes, Artifact description).
3. Authored-memory lifecycle on Story (honor `capture=1`).
4. Same lifecycle on Journal; delete private mic JS.
5. `prove-i10a2` ATs + A-01–A-20.

**Ready for founder lock. Not build-authorized.**
