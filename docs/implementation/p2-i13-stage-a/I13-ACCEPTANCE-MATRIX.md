# I13 acceptance matrix

**Date:** 2026-09-08  
**Branch:** `codex/p2-i13-stage-a`  
**Status:** Pending founder acceptance — I13 is **not closed** until Tom signs [CONSOLIDATED-I13-ACCEPTANCE-REVIEW.md](CONSOLIDATED-I13-ACCEPTANCE-REVIEW.md).

Classifications: **passed** | **waived** | **deferred** | **failed**

Authority: `MBPRD-P2-I13_Video_Face_Speech_Voice_Learning_v0.2.docx`, `MBBS-P2_INCREMENT_13_DEFINITION_DRAFT_v0.2.docx`, [FOUNDER-AUTHORIZATION.md](FOUNDER-AUTHORIZATION.md).

---

## Voice acceptance checklist (definition §8 / PRD §8)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| V1 | Select timestamp-backed speech, assign Person, confirm sample quality without presenting assignment as proven recognition | **deferred** | Annotation UI accepted (`7bc47b5`); full Learn/quality-confirmation lifecycle not implemented |
| V2 | Confirmed source-audio samples produce reviewable voice suggestions in bounded recognition | **passed** | Six stopped current voice pilots; `/review/voice-pilot-results`; [I13-VOICE-PILOT-STATUS.md](I13-VOICE-PILOT-STATUS.md) |
| V3 | Off-camera speaker suggestions without requiring visible face | **passed** | Tom pilot O1 match `0.487` — admission `9e0a2605…`; overlap O2 no_match `0.093` |
| V4 | Preserve independent face/voice evidence; transparent corroboration when both exist | **passed** | [FACE-VOICE-CORROBORATION-NOTE.md](FACE-VOICE-CORROBORATION-NOTE.md); `GET /review/face-voice-corroboration`; unit tests |
| V5 | Poor-audio, multi-person, no-match cases; uncertain output must not masquerade as confirmed | **passed** | Overlap pilot `339b3a14…` E2 match `0.584`, O2/N1 no_match; N1 pilot `46cb1d21…` |
| V6 | Record source/interval, model, thresholds, measured results and errors | **passed** | Pilot payloads in `i13_voice_pilot_results`; per-admission reports in `docs/implementation/p2-i13-stage-a/*-report.json` |
| V7 | Immutable machine transcripts + additive audited owner overlays | **passed** | Migrations 031; annotation tests; T1 retirement stale cascade |
| V8 | Scope/cardinality limits, queue/retry/worker gates, locked archive behavior | **partial → passed (bounded)** | Gate 3 `458d1a76…` 22 transcribe noops; scope.py fail-closed; archive register/unlock/start **disabled by founder decision** |

---

## Gate 4 / archive (founder decisions)

| Outcome | Class | Evidence |
|---|---|---|
| A — Defer archive execution | **passed** | [GATE-4-DECISION-PRD.md](GATE-4-DECISION-PRD.md); signed 2026-09-08 |
| B — Plan-only preview | **passed** | FlightSim preview 5 sources / 10 face units; [DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md](DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md) |
| C — Register admission | **deferred** | Founder rejected 2026-09-08 — do not proceed |
| D — Unlock archive | **deferred** | Founder rejected 2026-09-08 |
| E — Start archive drain | **deferred** | Founder rejected 2026-09-08 |

---

## Voice pilot matrix

| Requirement | Class | Evidence |
|---|---|---|
| Five-category matrix coverage | **waived** | Outcome W: `Tom-waived-additional-voice-pilot-matrix-run-2026-09-08`; [VOICE-ASSIGNMENT-COVERAGE.md](VOICE-ASSIGNMENT-COVERAGE.md) |
| Additional matrix pilot run | **waived** | Same reference; smallest plan = none required |

---

## PRD functional requirements (I13-FR-001 … I13-FR-026)

| FR | Summary | Class | Evidence / note |
|---|---|---|---|
| I13-FR-001 | Inventory / schema | **deferred** | Migrations 030–032; deployed schema reconciliation deferred post-I13 |
| I13-FR-002 | Archive fan-out root cause | **deferred** | Documented; archive execution rejected |
| I13-FR-003 | Invalid-set remediation | **deferred** | No remediation authorized |
| I13-FR-004 | Idempotency | **deferred** | Static risks documented in completeness matrix |
| I13-FR-005 | Playback seek/clamp | **failed** | Historical binder clamp reproduced in assessment; fix tracked post-closeout unless Tom waives |
| I13-FR-006 | Navigation state preservation | **deferred** | Explore modal exists; full rendered proof deferred |
| I13-FR-007 | Transcript follow/scroll | **deferred** | Partial highlight; follow deferred |
| I13-FR-008 | Transcript seek | **deferred** | Click seek exists; full keyboard proof deferred |
| I13-FR-009 | Voice sample confirmation lifecycle | **deferred** | Bounded pilots prove recognition path; UI lifecycle deferred |
| I13-FR-010 | Face sample confirmation | **deferred** | Explore flow exists; bounded face archive rejected |
| I13-FR-011 | Combined Learn adjudication | **deferred** | Independent APIs; partial-failure UX deferred |
| I13-FR-012 | Background work + manifest gate | **passed (bounded)** | I13 admission machinery + Gate 3 + voice pilots under scope locks |
| I13-FR-013 | Review with per-modality provenance | **passed (bounded)** | Review UI voice pilots + corroboration; full unified adjudication deferred |
| I13-FR-014 | Immutable correction supersession | **partial → deferred** | Annotations support withdraw/revision; full cross-store supersession deferred |
| I13-FR-015 | Retirement lifecycle | **passed (bounded)** | T1 retirement + stale cascade + `66fb93af…` reprocessing pilot |
| I13-FR-016 | Owner Jobs page | **deferred** | Queues exist; UI deferred |
| I13-FR-017 | Release lock before archive | **passed (policy)** | Intentionally disabled; founder rejected archive C/D/E |
| I13-FR-018 | Timeline precision | **deferred** | Explore timeline exists; regression deferred |
| I13-FR-019 | Retrieval on owner truth | **deferred** | Search paths exist; four-mode acceptance deferred |
| I13-FR-020 | Legacy moment presentation | **deferred** | Clamp defect related to FR-005 |
| I13-FR-021 | Fragment inventory | **deferred** | Checkpoint aggregates only |
| I13-FR-022 | Fragment migration | **deferred** | Not authorized |
| I13-FR-023 | Derivative deletion | **deferred** | Not authorized |
| I13-FR-024 | Admin shell | **deferred** | Not in I13 bounded closeout |
| I13-FR-025 | Admin destinations | **deferred** | I12 HC preserved; I13 admin pages deferred |
| I13-FR-026 | Unlock separation | **passed (policy)** | No unlock/start authorized; gates enforced in code |

---

## Architectural / non-functional requirements

| Requirement | Class | Evidence |
|---|---|---|
| One immutable source, derived moments | **partial → deferred** | Provider IDs + overlays; full referential proof deferred |
| No Immich writeback | **passed** | Inspected paths; no I13 writeback |
| Original media + machine transcript preserved | **passed (bounded)** | Gate 3 noops; annotation overlay model |
| Learned evidence provenance fields | **passed (bounded)** | Voice pilot payloads; face appearance fields |
| Face/voice independent; off-camera; corroboration transparent | **passed (bounded)** | Voice pilots + [FACE-VOICE-CORROBORATION-NOTE.md](FACE-VOICE-CORROBORATION-NOTE.md) |
| Versioned thresholds / resource limits | **passed (bounded)** | Pilot thresholds in plans; scope limits in `scope.py` |
| Before-confirmation “Assigned for learning” copy | **deferred** | Not implemented |
| Reasoned retirement + preservation copy | **passed (bounded)** | T1 retirement workflow |
| Auditability / recoverability | **passed (bounded)** | Gate 3 + pilot backups documented in handoff |
| Performance / async observability | **deferred** | Not measured for closeout |
| Owner privacy / access control | **deferred** | Single-owner convention; I13 admin policy deferred |
| Accessibility | **deferred** | Not in bounded closeout |
| Five approved screens | **deferred** | Partial; Admin/Jobs/Learned Evidence deferred |
| Explicit 22-source corpus | **passed** | [bounded-manifest-proposal.json](bounded-manifest-proposal.json) SHA pinned |
| I12 boundary preserved | **passed** | No I12 behavior change in I13 line |

---

## Acceptance gates (PRD §8)

| Gate | Class | Evidence |
|---|---|---|
| Integrity | **passed (bounded)** | Admission digests; pilot immutability; legacy counts unchanged |
| Playback | **failed** | FR-005 defect; separate waiver possible at founder review |
| Transcript | **passed (bounded)** | Annotations + effective words/moments |
| Face | **deferred** | Archive face lane rejected; face moments exist for corroboration read path |
| Voice | **passed (bounded)** | Six current stopped pilots; matrix waiver W |
| Corroboration | **passed (bounded)** | Read-only report + API + tests |
| Retrieval | **deferred** | — |
| Legacy fragment reconciliation | **deferred** | — |
| Jobs | **deferred** | — |
| Regression | **deferred** | Automated tests pass; rendered workflow deferred |
| Safety | **passed (policy)** | Archive/register/unlock/start disabled |
| Proof | **passed (bounded)** | Gate 3 + voice pilots + corroboration + this matrix |

---

## Summary counts

| Class | Count (checklist + gates + key FR) |
|---|---|
| **passed** | Voice core, Gate 3, corroboration, retirement lifecycle, safety locks |
| **waived** | Additional voice matrix pilot (W) |
| **deferred** | Archive C/D/E, admin UI, fragments, retrieval, most FR polish |
| **failed** | Playback clamp (FR-005) — **open for founder waiver or post-I13 fix** |

---

## Automated test evidence (dev machine)

Run before founder sign-off:

```powershell
Set-Location E:\MemoryBox-dev\p2-i13-stage-a
python -m unittest discover -s tests -p "test_i13*.py" -v
```

Corroboration-specific: `tests/test_i13_face_voice_corroboration.py` (7 tests).

FlightSim read-only corroboration (when DB available):

```powershell
python docs/implementation/p2-i13-stage-a/inspect-face-voice-corroboration.py
```
