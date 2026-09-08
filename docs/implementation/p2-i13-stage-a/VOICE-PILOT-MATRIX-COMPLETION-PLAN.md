# Voice pilot matrix — completion plan (smallest bounded plan)

**Status:** Matrix **complete** — **no additional voice pilot run** is the smallest correct plan  
**Authority:** [VOICE-ASSIGNMENT-COVERAGE.md](VOICE-ASSIGNMENT-COVERAGE.md), [inspect-voice-assignment-coverage.py](inspect-voice-assignment-coverage.py)

---

## Checkpoint reality vs historical Gate 2→3 prompt

The locked deployment and annotation workflow are accepted. All 22 manifest sources have transcripts. The **canonical eight** owner voice assignments fill the five required categories. **Six stopped current voice pilots** (plus one stale original Eugene pilot) already executed the smallest useful bounded plans.

Gate 3 transcription evidence-generation and Gate 4 Outcome B archive preview are also complete. **Learn and drains remain locked.**

---

## Smallest exact bounded voice-pilot plan

**Recommendation: do not register or execute another voice pilot** for the five-category matrix.

| Field | Value |
|---|---|
| Additional spans | **0** |
| Additional admissions | **0** |
| Workload ceiling | n/a — no run |
| Expected outcome | Preserve current stopped admissions and results |
| Rollback | n/a — no runtime writes |
| Stop behavior | n/a |
| Evidence preservation | Do not retry admissions listed in [I13-VOICE-PILOT-STATUS.md](I13-VOICE-PILOT-STATUS.md); legacy queue/transcript counts unchanged |

### Historical smallest executable shape (already completed)

The first bounded plan remains [bounded-voice-pilot-proposal.json](bounded-voice-pilot-proposal.json) — four spans, 41.46 s, one Eugene training + three held-outs. It was executed on admission `1039c733…` (now **stale** after T1 retirement). Subsequent pilots supersede it with current evidence:

| Pilot | Plan file | Admission | Role |
|---|---|---|---|
| Eugene (original) | `bounded-voice-pilot-proposal.json` | `1039c733…` **stale** | First matrix proof |
| Tom off-camera | `tom-bounded-voice-pilot-proposal.json` | `9e0a2605…` **current** | Tom train + O1 match |
| N1 Unknown | (N1 readiness package) | `46cb1d21…` **current** | no-match |
| Eugene Patio | `eugene-patio-bounded-voice-pilot-proposal.json` | `f59050d5…` **current** | extra Eugene held-out |
| Reprocessing lifecycle | reprocessing package | `66fb93af…` **current** | fresh Eugene ref |
| Overlap / poor-audio | `overlap-poor-audio-voice-pilot-proposal.json` | `339b3a14…` **current** | overlap + controls |

Re-running any of these would violate evidence-preservation rules and add no missing category.

---

## Evidence-preservation rules (locks)

- Stopped admissions are immutable; new work needs a **new** reviewed plan.
- Retired training (`T1`) stale-cascaded prior Eugene admission; do not revive.
- Prior Tom, N1, Patio, and reprocessing results must stay **current** (verified on overlap pilot).
- No automatic retry; one attempt per span per admission.
- Immutable machine transcripts; owner overlays additive only.
- Drains off and `MEMORYBOX_I13_ADMISSION_ID` unset outside an approved execute window.
- Tooling: `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe` — never bare `python` on FlightSim.

---

## If a category were absent (not the case today)

The smallest new plan would be a **single-span** `voice_pilot` admission: one training **or** one held-out on an unused annotation, parent 22-source hashes pinned, budget of one extraction / one embedding / zero or one comparison, 120 s per-step timeout, 20 min overall, no automatic retry. That path is **not opened** because all categories are satisfied.

---

## Consolidated stop-before-run

See [CONSOLIDATED-VOICE-PILOT-PRODUCTION-REQUEST.md](CONSOLIDATED-VOICE-PILOT-PRODUCTION-REQUEST.md) for the single founder decision point immediately before any future real bounded voice run.
