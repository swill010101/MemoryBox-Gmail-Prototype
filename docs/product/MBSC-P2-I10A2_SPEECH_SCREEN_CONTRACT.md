# MBSC-P2-I10A.2 — Shared narrative field and speech

**Status:** Contract **LOCKED** 2026-08-24 · **BUILD AUTHORIZED**  
**PRD:** [MBPRD-P2-I10A2_SPEECH_INPUT.md](MBPRD-P2-I10A2_SPEECH_INPUT.md)

One component. Two speech semantics. Containing Save/Cancel unchanged.

---

## S.1 Shared narrative field (Frozen)

Replace Story `#ed-body`, Journal `#body` / `#editBody`, Artifact `#ed-desc`, Person `#mb-edit-notes` with **one** reusable control (same interaction, same speech hook). Pages keep their own Save/Cancel.

Capability: `speech input allowed`. Semantics attribute: `authored-memory` | `convenience` | off.

No mic on short structured fields (PRD §3).

## S.2 Convenience speech (Frozen)

Quiet mic on the field. Listening / processing / error. Insert at cursor. Audio **transient** after successful transcription unless the field is authored-memory. Never Save. Never create a Voice Memory from Person notes or simple Artifact description.

## S.3 Authored-memory speech (Frozen)

Used on Story body and Journal body (including Tell its story → Story).

| State | Family-facing | Must |
|---|---|---|
| Ready | Mic / start telling | Not recording |
| Record | Pause · Stop | Capture running; ~30s silence → **pause** + modal “Are you still there?” (Continue recording resumes / Stop). No auto-stop/discard. Walk-away must not keep recording. |
| Pause | Resume · Stop | Same take frozen; silence timer off. Silence modal uses this state. |
| Processing | (wait) | After Stop: pulsing “Turning speech into words…”; upload % when known |
| Review | Play / pause / scrub · edit text · Start Over · (then Save on the page) | Stop already happened; object **not** saved |
| Saved | Normal Story/Journal saved chrome | Audio + approved text + provenance committed |

**Start Over** (Review or unsaved take): confirm if meaningful audio exists; discard take; Ready.

Cancel/back without Save: no durable orphan audio.

## S.4 Persist on Save only (authored-memory) (Frozen)

Package: original audio · final approved text · speaker/author · capture time · speech-derived metadata · existing object links. No hidden raw STT memory version. Do not rewrite older version audio when the user later edits text or adds a new take on a new save.

## S.5 Wording (Frozen)

No provider, pipeline, or model terms in ordinary UI.
