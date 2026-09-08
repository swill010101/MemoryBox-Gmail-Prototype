# Consolidated I13 acceptance review

**Date:** 2026-09-08  
**Branch:** `codex/p2-i13-stage-a`  
**Prepared for:** Tom (founder acceptance)  
**I13 status:** **OPEN** — awaiting founder sign-off below

---

## Executive summary

P2-I13 bounded evidence work is complete for the **authorized** tracks: Gate 3 transcription, six stopped voice pilots (Outcome W), read-only face/voice corroboration (FlightSim verified), Gate 4 Outcome A defer + B plan preview, and archive Outcomes C/D/E rejected with locks held.

**I13 is not ready for silent closeout.** The accepted PRD also requires **interactive Learn** (Explore face/voice Learn) and **three Admin screens** (landing, Learned Evidence, Jobs). Those are **not** satisfied on FlightSim under current authorization. Voice-pilot annotations and bounded voice pilots **do not** prove interactive Learn.

See [INTERACTIVE-LEARN-RECONCILIATION.md](INTERACTIVE-LEARN-RECONCILIATION.md) and run:

```powershell
cd C:\MemoryBox
$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
```

---

## Completed bounded evidence (authorized)

| Track | Status | Evidence |
|---|---|---|
| Gate 3 transcribe (22 noops) | Complete | Admission `458d1a76…` — do not retry |
| Voice pilots (six current) | Complete | [I13-VOICE-PILOT-STATUS.md](I13-VOICE-PILOT-STATUS.md) |
| Voice matrix Outcome W | Waived | `Tom-waived-additional-voice-pilot-matrix-run-2026-09-08` |
| Face/voice corroboration | Complete (read-only) | FlightSim `ok: true`, 8 assignments — [FACE-VOICE-CORROBORATION-NOTE.md](FACE-VOICE-CORROBORATION-NOTE.md) |
| Gate 4 A defer + B preview | Complete | [GATE-4-DECISION-PRD.md](GATE-4-DECISION-PRD.md) |
| Archive C/D/E | Rejected | Register/unlock/start/drains remain disabled |

---

## Interactive Learn reconciliation (PRD — not voice pilots)

| # | Checkpoint | Class | Summary |
|---|---|---|---|
| 1 | Face box → Person → Learn | **failed** | UI + API exist; **Learn locked** — no started `acceptance_learning` face admission |
| 2 | Transcript → Person → voice Learn | **failed** | UI + API exist; voice Learn locked; annotations ≠ Learn |
| 3 | Admin → Learned Evidence | **failed** | Screen not implemented |
| 4 | Admin → Jobs | **failed** | I13 Jobs screen not implemented |
| 5 | Correct / remove learned evidence | **not tested** | Partial APIs; no unified admin UI; no bounded live proof |
| 6 | Learn enabled while archive/drains locked | **failed** / locks **passed** | Archive correctly locked; **interactive Learn not enabled** |

Full detail: [INTERACTIVE-LEARN-RECONCILIATION.md](INTERACTIVE-LEARN-RECONCILIATION.md).

---

## FR-005 playback (one of several open items — not the sole gate)

| | |
|---|---|
| **Required PRD behavior** | Gallery opens the **full source** at the evidence start; playback **continues past** the relevance interval without forced stop. |
| **Old behavior** | Player paused at relevance end — felt like a short clip ([causal-analysis.md](../../assessments/p2-i13/causal-analysis.md)). |
| **Current code (this branch)** | Seeks to start only; no end clamp (`explore.js` `bindAppearanceView`). Unit test + [browser-playback-proof.json](browser-playback-proof.json) (synthetic Chromium). |
| **User-visible effect** | Owner can watch through and past the moment without the player trapping them at interval end. |
| **FlightSim live** | **Not tested** on family video in full Explore workflow. |
| **Recommendation** | **Accept bounded** (code + offline proof) with optional Tom spot-check on `/explore/ui`, **or** defer full rendered regression — **not** a standalone reason to accept/reject entire I13 without addressing Learn + Admin gaps above. |

---

## Founder decisions already recorded

| Date | Decision | Reference |
|---|---|---|
| 2026-09-08 | Defer Gate 4 execution (Outcome A) | [GATE-4-DECISION-PRD.md](GATE-4-DECISION-PRD.md) |
| 2026-09-08 | Narrow waiver + plan preview (Outcome B) | `Tom-narrow-bounded-voice-acceptance-waiver-2026-09-08` |
| 2026-09-08 | Waive additional voice matrix pilot (W) | `Tom-waived-additional-voice-pilot-matrix-run-2026-09-08` |
| 2026-09-08 | Reject archive C/D/E; continue corroboration + matrix | [FOUNDER-AUTHORIZATION.md](FOUNDER-AUTHORIZATION.md) |

---

## Bounded voice evidence (do not retry)

| Admission | Role | Status |
|---|---|---|
| `1039c733…` | Original Eugene (T1) | **stale** |
| `9e0a2605…` | Tom off-camera O1 | **current** |
| `46cb1d21…` | N1 unknown | **current** |
| `f59050d5…` | Patio Eugene | **current** |
| `66fb93af…` | Lifecycle reprocessing | **current** |
| `339b3a14…` | Overlap/poor-audio | **current** |
| `458d1a76…` | Gate 3 transcribe | **stopped** |

---

## Full requirement matrix

[I13-ACCEPTANCE-MATRIX.md](I13-ACCEPTANCE-MATRIX.md) — all checklist items, FRs, gates.

---

## Combined founder decision request

Choose **one** primary path and note any waivers:

### A — Accept bounded I13 closeout (recommended only with explicit waivers)

Accept P2-I13 for **authorized bounded evidence** (Gate 3, voice pilots W, corroboration, locks) and **explicitly waive** for post-I13 or a follow-on increment:

- [ ] Interactive Learn checkpoints 1–2 (Explore face/voice Learn end-to-end)
- [ ] Admin screens 3–4 (Learned Evidence, Jobs)
- [ ] Checkpoint 5 live proof (correction/removal admin UX)
- [ ] FR-005 full FlightSim Explore render (optional if accepting code + synthetic proof)

**Reference:** `Tom-accept-bounded-i13-waive-interactive-learn-admin-YYYY-MM-DD`

### B — Reject closeout; implement before sign-off

Return work for: interactive Learn under bounded `acceptance_learning` admission + Admin screens (or PRD amendment).

**Reference:** `Tom-reject-i13-return-for: __________`

### C — Authorize bounded Learn proof first, then re-review

Do **not** accept I13 yet. Authorize a **separate** bounded `acceptance_learning` plan (face/voice lanes, explicit register+start, **not** archive C/D/E). After live Explore proof, re-run reconciliation inspector and return to this review.

**Reference:** `Tom-authorize-bounded-acceptance-learning-proof-YYYY-MM-DD`

### D — Other

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

**Signature / reference:** ___________________  
**Date:** ___________________

---

## Post-acceptance actions (only after signed path A with waivers)

1. Record accepted HEAD on `codex/p2-i13-stage-a`
2. Update handoff + roadmap — I13 **ACCEPTED** with waiver references
3. Unblock P2-I14 **planning** only
4. **Do not** run archive register/unlock/start or enable drains as part of closeout

---

## Locks that remain after any acceptance

- Archive Outcomes C/D/E
- Full 22-source archive processing
- P2-I14 execution without new increment PRD
