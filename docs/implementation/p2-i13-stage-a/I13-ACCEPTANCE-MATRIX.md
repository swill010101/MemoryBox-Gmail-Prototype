# I13 acceptance matrix

**Date:** 2026-09-08  
**Branch:** `codex/p2-i13-stage-a`  
**Status:** Pending founder acceptance — see [CONSOLIDATED-I13-ACCEPTANCE-REVIEW.md](CONSOLIDATED-I13-ACCEPTANCE-REVIEW.md). Open items include **interactive Learn + Admin screens** and **FR-005 live render** — not FR-005 alone.

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
| I13-FR-005 | Playback seek/continue | **passed (bounded code)** / **not tested (live)** | `bindAppearanceView` seeks only; unit test + [browser-playback-proof.json](browser-playback-proof.json); full FlightSim Explore render not recorded |
| I13-FR-006 | Navigation state preservation | **deferred** | Explore modal exists; full rendered proof deferred |
| I13-FR-007 | Transcript follow/scroll | **deferred** | Partial highlight; follow deferred |
| I13-FR-008 | Transcript seek | **deferred** | Click seek exists; full keyboard proof deferred |
| I13-FR-009 | Voice sample confirmation lifecycle | **failed (interactive Learn)** | Bounded voice **pilots** passed; Explore voice Learn locked without acceptance_learning admission |
| I13-FR-010 | Face sample confirmation | **failed (interactive Learn)** | Explore face Learn UI exists; gated — not live-proven on FlightSim |
| I13-FR-011 | Combined Learn adjudication | **deferred** | Independent APIs; partial-failure UX deferred |
| I13-FR-012 | Background work + manifest gate | **passed (bounded)** | I13 admission machinery + Gate 3 + voice pilots under scope locks |
| I13-FR-013 | Review with per-modality provenance | **passed (bounded)** | Review UI voice pilots + corroboration; full unified adjudication deferred |
| I13-FR-014 | Immutable correction supersession | **partial → deferred** | Annotations support withdraw/revision; full cross-store supersession deferred |
| I13-FR-015 | Retirement lifecycle | **passed (bounded)** | T1 retirement + stale cascade + `66fb93af…` reprocessing pilot |
| I13-FR-016 | Owner Jobs page | **deferred** | Queues exist; UI deferred |
| I13-FR-017 | Release lock before archive | **passed (policy)** | Intentionally disabled; founder rejected archive C/D/E |
| I13-FR-018 | Timeline precision | **deferred** | Explore timeline exists; regression deferred |
| I13-FR-019 | Retrieval on owner truth | **deferred** | Search paths exist; four-mode acceptance deferred |
| I13-FR-020 | Legacy moment presentation | **pending** | [LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md](LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md); two-source pilot ≠ gate complete; live Gallery proof required |
| I13-FR-021 | Fragment inventory | **pending** | [inventory-legacy-hvrt-fragments.py](inventory-legacy-hvrt-fragments.py) — manifest-scoped; run on FlightSim before acceptance |
| I13-FR-022 | Fragment migration | **deferred** | Not authorized |
| I13-FR-023 | Derivative deletion | **deferred** | Not authorized |
| I13-FR-024 | Admin shell | **failed** | No I13 Admin top-nav destination |
| I13-FR-025 | Admin destinations | **failed** | Learned Evidence + Jobs screens missing; partial substitutes only |
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

## Legacy HVRT fragment reconciliation gate

**Authority:** [LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md](LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md)  
**Corpus:** accepted **22-video manifest only** — not archive-wide

| # | Checkpoint | Class | Evidence |
|---|---|---|---|
| F1 | Inventory 0.5–2 s HVRT observations + lineage | **pending** | `inventory-legacy-hvrt-fragments.py` output on FlightSim |
| F2 | Read-only preview (grouping, before/after, suppressed dupes) | **pending** | `preview-fragment-reconciliation.py` after inventory |
| F3 | Apply grouping across manifest population (post-review) | **pending** | `publish-fragment-allowlist.py` + deploy; two-source pilot ≠ complete |
| F4 | Source videos / observations / provenance preserved | **passed (design)** | Presentation-only; no DB migration |
| F5 | Duplicate presentations removed; evidence not deleted | **passed (pilot)** | Two-source FlightSim owner report; full manifest pending |
| F6 | Separate appearances / timing gaps preserved | **passed (pilot)** | 40.5–60.5 s gap tests + owner 1532 pilot |
| F7 | Pipeline cannot recreate half-second fragment cards | **passed (code)** | `test_i13_fragment_correction.py` + `test_i13_fragment_reconciliation_gate.py` |
| F8 | Post-correction counts + live Gallery/retrieval proof | **pending** | `verify-fragment-reconciliation.py` + owner FlightSim notes |

**Do not close I13** on FR-005 playback or the one-video/two-source pilot alone.

---

## Interactive Learn reconciliation (PRD — not voice pilots)

Inspector: [inspect-interactive-learn-reconciliation.py](inspect-interactive-learn-reconciliation.py) — [INTERACTIVE-LEARN-RECONCILIATION.md](INTERACTIVE-LEARN-RECONCILIATION.md)

| # | Checkpoint | Class | Evidence |
|---|---|---|---|
| L1 | Face box → Person → Learn | **failed** | Explore + API; Learn locked — no started acceptance_learning face admission |
| L2 | Transcript → Person → voice Learn | **failed** | Annotations ≠ Learn; voice Learn locked |
| L3 | Admin → Learned Evidence | **failed** | Screen not implemented |
| L4 | Admin → Jobs | **failed** | I13 Jobs screen not implemented |
| L5 | Correct / remove learned evidence | **not tested** | Partial APIs; no admin UI; no live proof |
| L6 | Learn on while archive/drains locked | **failed** (Learn) / locks **passed** | Archive C/D/E rejected; Learn not enabled |

---

## Acceptance gates (PRD §8)

| Gate | Class | Evidence |
|---|---|---|
| Integrity | **passed (bounded)** | Admission digests; pilot immutability; legacy counts unchanged |
| Playback | **passed (bounded code)** / **not tested (live)** | Code fix + synthetic browser proof; FlightSim family-video Explore not recorded |
| Transcript | **passed (bounded)** | Annotations + effective words/moments |
| Face | **deferred** | Archive face lane rejected; face moments exist for corroboration read path |
| Voice | **passed (bounded)** | Six current stopped pilots; matrix waiver W |
| Corroboration | **passed (bounded)** | Read-only report + API + tests |
| Retrieval | **deferred** | — |
| Legacy fragment reconciliation | **pending** | Gate F1–F3, F8 open — see fragment reconciliation section |
| Jobs | **failed** | No I13 Admin Jobs UI |
| Regression | **deferred** | Automated tests pass; rendered workflow deferred |
| Safety | **passed (policy)** | Archive/register/unlock/start disabled |
| Proof | **passed (bounded)** | Gate 3 + voice pilots + corroboration + this matrix |

---

## Summary counts

| Class | Count (checklist + gates + key FR) |
|---|---|
| **passed** | Voice pilots, Gate 3, corroboration, retirement lifecycle, safety locks, FR-005 code fix |
| **waived** | Additional voice matrix pilot (W) |
| **deferred** | Archive C/D/E execution, retrieval, polish |
| **pending** | Legacy HVRT fragment reconciliation (full manifest), interactive Learn steady state, Admin live proof |
| **failed** | Interactive Learn 1–4, Learn enablement (L6), Admin screens |
| **not tested** | Learn correction/removal live (L5), FR-005 FlightSim Explore render |

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
cd C:\MemoryBox
# deployment env loaded (MEMORYBOX_DATABASE_URL)
$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
& $python -B docs\implementation\p2-i13-stage-a\inspect-face-voice-corroboration.py
& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
```
