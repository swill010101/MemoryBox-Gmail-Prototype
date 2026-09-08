# Interactive Learn reconciliation vs accepted I13 PRD

**Date:** 2026-09-08  
**Inspector:** [inspect-interactive-learn-reconciliation.py](inspect-interactive-learn-reconciliation.py)  
**Operating state:** [INTERACTIVE-LEARN-OPERATING-STATE.md](INTERACTIVE-LEARN-OPERATING-STATE.md)  
**Read-only:** no Learn, drains, archive register/unlock/start

Voice-pilot annotations and bounded voice pilots **do not** satisfy interactive Learn acceptance. Learn is a separate owner-driven workflow in Explore (`/explore/ui` Learn tab) gated by a **bounded `acceptance_learning` admission** — **started** during proof, then **`enable-interactive-learn`** on the stopped admission with `MEMORYBOX_I13_ADMISSION_ID` kept in serve env.

---

## Six PRD checkpoints (FlightSim classification)

Run on FlightSim (deployment env + TitaNet venv):

```powershell
cd C:\MemoryBox
$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
```

| # | PRD checkpoint | Classification | Evidence |
|---|---|---|---|
| 1 | Face box → Person → Learn | **failed** | Explore Learn UI + `POST /recognition/learn` exist; **no started acceptance_learning face admission**; Gate 3 transcribe-only → Learn returns 403. Voice pilots ≠ this workflow. |
| 2 | Transcript selection → Person → voice Learn | **failed** | Transcript highlight + `POST /speech/learn` exist; **voice Learn locked** under current authorization. Annotations (`POST /annotations/transcript`) save owner truth **without** training. |
| 3 | Learned evidence in Admin → Learned Evidence | **failed** | **No** I13 Admin landing or Learned Evidence screen (`I13-FR-024/025`). Substitutes: People, `/review/ui` read-only pilot/corroboration — not PRD Admin destination. |
| 4 | Work in Admin → Jobs | **failed** | **No** I13 Processing Jobs page. `/status/ui` Archive Health has legacy incremental jobs only. |
| 5 | Learned evidence corrected or removed | **not tested** | APIs: `POST /recognition/appearances/correct`, `POST /speech/moments/correct`, `POST /annotations/transcript` withdraw. No unified Learned Evidence admin UI; no bounded live exercise recorded for I13 closeout. |
| 6 | Interactive Learn enabled while archive/drains locked | **failed** (Learn) / **passed** (locks) | Archive Outcomes C/D/E rejected — no unlocked archive admission; drains off. **Interactive Learn not enabled** — requires separate `acceptance_learning` register+start (not authorized). |

**Summary:** 4 failed, 1 not tested, 0 passed for interactive Learn PRD checkpoints. Archive/drain locks behave as required.

---

## Code surfaces (exist vs missing)

| Surface | Status | Path |
|---|---|---|
| Explore Learn tab (face + voice) | Implemented | `memorybox/explore/static/explore.js` — `submitExploreLearn` |
| Face Learn API | Implemented, gated | `POST /recognition/learn` — `recognition/learn.py` |
| Voice Learn API | Implemented, gated | `POST /speech/learn` — `speech/learn.py` |
| Scope middleware | Enforced | `memorybox/processing/http.py` |
| Admin landing | **Missing** | — |
| Admin Learned Evidence | **Missing** | — |
| Admin Jobs (I13) | **Missing** | — |

Automated scope tests (Learn denied without admission): `tests/test_i13_stage_a.py` — `test_native_denials_before_any_side_effect`.

---

## FR-005 playback (plain language)

| Topic | Detail |
|---|---|
| **Required PRD behavior** | Opening evidence from the Gallery seeks to the moment’s start on the **full source video** and playback **continues naturally** past the relevance interval — no forced stop at evidence end. |
| **Prior behavior (pre-I13 fix)** | The Gallery player paused at the relevance end (`bindAppearanceView` clamp), producing a “chopped” clip feel even though the file was full-length. Documented in [causal-analysis.md](../../assessments/p2-i13/causal-analysis.md). |
| **Current behavior (this branch)** | `bindAppearanceView` seeks to start only; comment: “relevance end is metadata, never a playback stop.” Unit test: `test_real_binder_seeks_and_never_clamps_or_restarts`. Offline Chromium synthetic proof: [browser-playback-proof.json](browser-playback-proof.json). |
| **User-visible consequence** | Owner should scrub past the highlighted moment without the player snapping back or stopping at interval end. |
| **FlightSim live status** | **Not tested** on family video in full Explore modal workflow. Synthetic offline proof only. |
| **Recommendation** | Treat FR-005 as **passed (bounded)** on code + offline proof, **not tested** on live FlightSim family media — **not** a sole blocker if founder accepts deferring full rendered Gallery regression. Optional: Tom spot-check one appearance on `/explore/ui` before sign-off. |

---

## Implication for I13 closeout

Bounded work **completed and evidenced:** Gate 3 transcription, voice pilots (Outcome W), corroboration, scope/archive locks.

Interactive Learn + three Admin screens remain **PRD requirements not met** on FlightSim under current authorization. Founder must choose: **defer/waive** interactive Learn + Admin UI for this closeout, **reject** closeout until implemented, or **authorize** a bounded `acceptance_learning` admission and live UI proof before sign-off.
