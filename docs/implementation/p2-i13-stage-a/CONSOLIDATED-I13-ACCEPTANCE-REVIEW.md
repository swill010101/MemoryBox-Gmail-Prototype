# Consolidated I13 acceptance review

**Date:** 2026-09-08  
**Branch:** `codex/p2-i13-stage-a`  
**Prepared for:** Tom (founder acceptance)  
**I13 status:** **OPEN** — awaiting founder sign-off below

---

## Executive summary

P2-I13 bounded acceptance work on the 22-source corpus is ready for founder review. This increment **does not** authorize archive processing (Outcomes C/D/E rejected), Learn unlock, or recognition drains.

**Completed in this track:**

1. Gate 3 evidence-generation (22 transcribe noops, legacy unchanged)
2. Six stopped **current** bounded voice pilots covering Eugene, Tom off-camera, N1 unknown, patio, lifecycle reprocessing, and overlap/poor-audio
3. Voice matrix Outcome **W** (no additional pilot required)
4. Gate 4 Outcome **A** (defer) + **B** (plan-only preview)
5. Read-only **face/voice corroboration** on canonical eight assignments (independent evidence, transparent overlap report)
6. Complete acceptance matrix with evidence links

**Known open item for founder decision:** playback relevance clamp (**I13-FR-005 / Playback gate = failed** in assessment). All other deferred items are explicitly post-I13 or rejected archive scope.

---

## Founder decisions already recorded

| Date | Decision | Reference |
|---|---|---|
| 2026-09-08 | Defer Gate 4 execution (Outcome A) | [GATE-4-DECISION-PRD.md](GATE-4-DECISION-PRD.md) |
| 2026-09-08 | Narrow acceptance waiver + plan preview (Outcome B) | `Tom-narrow-bounded-voice-acceptance-waiver-2026-09-08` |
| 2026-09-08 | Waive additional voice matrix pilot (Outcome W) | `Tom-waived-additional-voice-pilot-matrix-run-2026-09-08` |
| 2026-09-08 | **Reject** archive Outcomes C/D/E; continue corroboration + acceptance matrix | [FOUNDER-AUTHORIZATION.md](FOUNDER-AUTHORIZATION.md) |

---

## Bounded voice evidence (do not retry)

| Admission | Role | Status |
|---|---|---|
| `1039c733-2149-40b2-b027-97058e032af3` | Original Eugene (T1) | **stale** |
| `9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea` | Tom off-camera O1 | **current** |
| `46cb1d21-b464-4bc4-bf7c-7d0de0202ca6` | N1 unknown | **current** |
| `f59050d5-cb4b-4ff7-beee-609b28f7af61` | Patio Eugene | **current** |
| `66fb93af-92a9-4ef1-b3e6-c0f700e89276` | Lifecycle reprocessing | **current** |
| `339b3a14-5069-4554-846f-dc84d6745c00` | Overlap/poor-audio | **current** |
| `458d1a76-4ecb-4722-bd76-20125b14c1d3` | Gate 3 transcribe | **stopped** — do not retry |

---

## Corroboration (new)

Policy: face and voice remain **independent**; corroboration only reports same-source interval overlap and voice-pilot outcomes.

| Surface | Location |
|---|---|
| Implementation note | [FACE-VOICE-CORROBORATION-NOTE.md](FACE-VOICE-CORROBORATION-NOTE.md) |
| API | `GET /review/face-voice-corroboration` |
| Review UI | `/review/ui` → Face/voice corroboration |
| CLI | `inspect-face-voice-corroboration.py` |
| Tests | `tests/test_i13_face_voice_corroboration.py` |

---

## Full requirement matrix

See [I13-ACCEPTANCE-MATRIX.md](I13-ACCEPTANCE-MATRIX.md) for every checklist item, FR, architectural requirement, and gate with **passed / waived / deferred / failed** classification and evidence links.

---

## Locks that remain in force after acceptance

Even if I13 is accepted, these require **separate** founder authorization:

- Archive register / unlock / start (Outcomes C/D/E)
- `MEMORYBOX_RECOGNITION_DRAIN=1` or speech drain on 22-source learning
- Any new voice pilot or Gate 3 re-run
- P2-I14 work (blocked until I13 closeout)

---

## Founder acceptance (sign here)

**I13 bounded acceptance decision:**

- [ ] **Accept** P2-I13 as closed on the bounded evidence above (including corroboration read path and voice matrix waiver W), with deferred items documented for post-I13 increments
- [ ] **Accept with waiver** — specify playback (FR-005) waiver: ___________________
- [ ] **Reject** — return for: ___________________

**Signature / reference:** ___________________  
**Date:** ___________________

---

## Post-acceptance actions (agent / FlightSim — only after founder sign above)

1. Tag or document accepted HEAD on `codex/p2-i13-stage-a`
2. Update handoff + roadmap to mark I13 **ACCEPTED**
3. Unblock P2-I14 planning (not execution without new increment PRD)
4. Deploy corroboration endpoint to FlightSim if not already at HEAD:

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i13-stage-a
git pull origin codex/p2-i13-stage-a
# restart serve/ask as usual
python docs/implementation/p2-i13-stage-a/inspect-face-voice-corroboration.py
```

**Do not** run archive register/unlock/start or enable drains as part of I13 closeout.
