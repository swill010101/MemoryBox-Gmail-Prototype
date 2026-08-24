# MBAT-P2-I10A.2 — Speech input / shared narrative field

**Increment:** P2-I10A.2 · **LOCKED** · **BUILD AUTHORIZED** 2026-08-24  
**Prove (when built):** `python -m memorybox prove-i10a2` (**Recommendation** name)  
**Contracts:** [MBPRD-P2-I10A2_SPEECH_INPUT.md](MBPRD-P2-I10A2_SPEECH_INPUT.md) · [MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md](MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md)

I10A.1 chrome cases stay on `prove-person-i10a1`. Do not treat I9 `prove` as this increment.

---

## Original field ATs (kept)

| ID | Criterion |
|---|---|
| AT-01 | Story: speech → editable Story text; Story not saved until normal Save. |
| AT-02 | Journal: same shared behavior into Journal body. |
| AT-03 | Artifact description: speech inserts text; no extra Artifact or voice record for **convenience** description. |
| AT-04 | Starting speech does not delete existing text. |
| AT-05 | Convenience / typed path: insert at cursor. |
| AT-06 | After transcript, user can type, delete, correct, dictate again. |
| AT-07 | Speech activity does not implicit-Save. |
| AT-08 | Mic permission denied: typing works; text preserved. |
| AT-09 | STT unavailable: concise nontechnical message; typing continues. |
| AT-10 | One shared speech lifecycle, not per-screen copies. |
| AT-11 | No mic on names, dates, email, phone, Person pickers, titles (v1). |
| AT-12 | Convenience dictation does not create permanent audio evidence. |

---

## Founder additions

| ID | Criterion |
|---|---|
| A-01 | Shared narrative editor used by Story body, Journal body, Artifact description, Person notes. |
| A-02 | Story authored speech **preserves audio** on Save. |
| A-03 | Journal authored speech **preserves audio** on Save. |
| A-04 | Pause and Resume continue the **same** recording. |
| A-05 | Stop enters Review and does **not** save. |
| A-06 | User can play/review recorded audio before Save. |
| A-07 | User can edit transcript independently of audio. |
| A-08 | Final approved text is the searchable/displayed transcript. |
| A-09 | Hidden pre-edit STT text is **not** a permanent memory content version. |
| A-10 | Start Over discards the current unsaved take (with confirm when meaningful). |
| A-11 | Cancel before Save leaves no durable orphan recording. |
| A-12 | ~30s continuous silence while **actively recording** **pauses** capture and shows “Are you still there?” — not auto-stop, not a hours-long walk-away recording. Continue resumes; Stop ends the take. |
| A-13 | Intentional Pause does not trigger the silence prompt. |
| A-14 | Natural fillers/pauses remain in preserved audio (no aggressive cleanup). |
| A-15 | Person-note convenience dictation does **not** automatically create permanent audio. |
| A-16 | Artifact: authored-memory (Tell its story / Story) can preserve audio; simple description dictation may be transient. |
| A-17 | Journal private Record/Stop POC is **replaced** by the shared lifecycle, not duplicated. |
| A-18 | Editing an existing Story preserves existing authentic audio while allowing text edits. |
| A-19 | New spoken content on an existing Story follows Record → Review/Edit → Save; does not flatten old capture provenance. |
| A-20 | No microphone on short structured fields by default. |

---

## FlightSim (when authorized)

`python -m memorybox prove-i10a2 --flightsim` on P1. Exercise Story record → pause → resume → stop → review → save; Journal same; Person notes convenience (no orphan audio); Artifact description convenience; Tell its story opens Story authored-memory.
