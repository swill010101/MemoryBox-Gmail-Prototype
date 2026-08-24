# P2-I10A.2 — Reusable Speech Input (shared narrative editor)

**Status:** PRD **LOCKED** 2026-08-24 · **BUILD AUTHORIZED** (Tom: “Lock it, approved.... authorized to build”)  
**Increment:** P2-I10A.2  
**Do not reopen:** I10A.1  
**Assessment:** [MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md)  
**Definition:** [MBBS-P2_INCREMENT_10A2_DEFINITION.md](MBBS-P2_INCREMENT_10A2_DEFINITION.md)  
**Surface map:** [MBAS-P2-I10A2_SURFACE_MAP.md](MBAS-P2-I10A2_SURFACE_MAP.md)  
**Screen contract:** [MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md](MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md)  
**Acceptance:** [MBAT-P2-I10A2_ACCEPTANCE.md](MBAT-P2-I10A2_ACCEPTANCE.md)  
**Depends:** I10A Stories **ACCEPTED** · I10A.1 **ACCEPTED** · I10B Artifacts **ACCEPTED** (one I10B row superseded below; do not reopen I10B for polish)  
**Does not start:** I10C Journal product chrome · I11 · I9 archive STT · spoken Ask · TTS · three screen-specific mics

**Legend:** **Frozen** · **Existing** · **Required** · **Recommendation** · **Open**

---

## Change control (Frozen)

These founder decisions **supersede** earlier I10A.2 planning (2026-08-24 first draft) and one I10B row:

1. **Superseded:** “All routine dictation audio is discarded after STT.”  
   **Replacement:** Audio retention follows **semantic intent**. Authored spoken memory is preserved. Convenience dictation may be transient.

2. **Superseded:** I10B “Dictating Artifact description | Forbidden.”  
   **Replacement:** Substantial free-text fields may support speech through the **shared** I10A.2 component. Artifact **object description** is convenience dictation (audio may be transient). **Narrated Artifact story/memory** is authored memory (audio preserved) and uses the Story editor via Tell its story — not a second Artifact `MediaRecorder`.

Do not resurrect the older rules in later planning.

---

## 1. Problem

Typing is the only practical capture path for substantial authored text (Stories, Journal, Artifact description, Person notes). Capture should be easier than organization. Speech must not become four separate products.

## 2. Product decision (Frozen)

1. **Required first:** one reusable **narrative text-entry** component for substantial free-text. Story, Journal, Artifact, and Person notes **do not** share one today.
2. Speech is a capability on that component: `speech input allowed`, with **field-level semantics** (`authored-memory` | `convenience`).
3. I10A.2 ships the shared field **and** speech across all four current surfaces. No later screen-specific forks.
4. Short structured fields do **not** get a microphone.

## 3. Initial surfaces (Frozen)

| Surface | Field | Speech semantics |
|---|---|---|
| Story create/edit | Story body | **Authored-memory** |
| Journal create/edit | Journal body | **Authored-memory** |
| Artifact Tell its story | Story body (existing navigation) | **Authored-memory** (Story) |
| Artifact editor | Object description | **Convenience** |
| Person Edit | Notes | **Convenience** (default) |

Story title, Story one-line description `<input>`, Artifact name, dates, emails, phones, pickers: **no mic**.

## 4. Two semantic uses (Frozen)

### Authored-memory speech

Story, Journal, and narrated Artifact story/memory (via Story). Spoken audio **is** authentic authored memory.

On containing **Save**, persist:

- original authentic audio (unaltered by later text edits);
- user’s **final approved text** (canonical readable/searchable);
- author/person provenance, capture timestamp, links already on the object;
- metadata that text originated through speech and, if true, that the user edited it.

Do **not** persist a hidden pre-edit STT blob as a family-memory version. Diagnostics belong in AI trace, not the memory record.

### Convenience dictation

Person notes (default) and simple Artifact description. Faster typing. Final **text** is durable. Audio **need not** be preserved. Do not silently create Voice Memories.

The shared editor chooses semantics from the **field**, not a global “always discard” or “always keep” rule.

## 5. Shared component (Frozen)

Do not implement Story-mic, Journal-mic, Artifact-mic separately.

The Journal 5A `MediaRecorder → POST /capture/transcribe` whole-body replace **is not** the target. Reuse preserve/STT **capability** where it fits authored-memory; replace the private interaction.

Conceptual API: narrative field + `speech input allowed` + `speech-semantics="authored-memory|convenience"`.

## 6. Authored-memory workflow (Frozen)

**Ready → Record → Pause/Resume → Stop → Review/Edit → Save** (Save is the **containing** Story/Journal/Artifact-linked Story save).

While recording: **Pause** and **Stop**. Pause does not end the take; **Resume** continues it; silence timer **off** while paused.

**Stop** enters Review. Does **not** Save.

Review: play, pause playback, scrub as practical, read/edit transcript, type more, keep the take, or **Start Over**. UX: natural speech, not a performance.

**Start Over:** discard unsaved take + its transcript + review edits; return to Ready. Confirm if a meaningful recording exists. Do not keep abandoned takes as evidence.

Starting, pausing, stopping, reviewing, or Start Over **never** implicitly Saves. Cancel/exit before Save leaves **no durable orphan audio**.

## 7. Silence (Frozen)

Natural pauses, fillers, repeats, slang stay in the **audio**. Do not aggressively auto-stop or “clean” the recording.

If **actively recording** (not paused) and ~**30 seconds continuous silence**: non-destructive **Are you still there?** with **Continue Recording** and **Stop**. **No auto-stop.** Pause: timer does not apply.

## 8. Transcript vs audio (Frozen)

Audio and approved text **may differ**. Example: spoken “sixty-seven — no, sixty-eight” edited to “1968”. Do not regenerate audio to match text.

## 9. Existing Story / Journal (Frozen)

Same editor. User may type, dictate additional speech (new take → Review → Save), edit text without touching existing preserved audio. Original audio stays authentic. If later takes exist, **do not flatten provenance** (prior version’s audio vs new capture).

Do not force a separate “voice editing” app.

## 10. Insert behavior (convenience and typed editing) (Frozen)

Convenience dictation inserts at cursor; empty field starts at beginning; do not wipe the field because the mic started; do not silently overwrite a selection in v1.

Authored-memory review edits the transcript in the same narrative field. Whole-body replace from the Journal POC is **forbidden**.

## 11. Failure and permission (Frozen)

Typing always works. Concise family-facing errors only (no provider/HTTP/model/stack). Mic permission on first speech attempt. Denied: explain, keep typing, allow retry.

Family UX wording: **Tell the story → review it → fix the words if needed → listen back if desired → save when ready.** No STT/MediaRecorder/model jargon.

## 12. Out of scope (Frozen)

Spoken Ask · TTS · I9 historical media STT · diarization · speaker id · voice enrollment · AI rewrite of dictation · mic on every input · finishing I10C family Journal chrome · Artifact-private recorder · reopening I10A.1.

## 13. Acceptance

See [MBAT-P2-I10A2_ACCEPTANCE.md](MBAT-P2-I10A2_ACCEPTANCE.md) (AT-01–AT-12 plus founder additions A-01–A-20).

---

**LOCKED and BUILD AUTHORIZED 2026-08-24.**
