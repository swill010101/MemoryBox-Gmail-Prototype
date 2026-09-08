# Gate 3 decision — bounded evidence-generation authorization

**Status:** Outcome A completed on FlightSim 2026-09-08 — see [gate-3-evidence-generation-report.json](gate-3-evidence-generation-report.json).
**Branch:** `codex/p2-i13-stage-a`  
**Plan:** [bounded-manifest-proposal.json](bounded-manifest-proposal.json) (`purpose: evidence_generation`, transcribe lane only)

This document is a **decision PRD only**. It does not register an admission, start processing, enable drains, or authorize Learn, face/voice matching, or Gate 4 archive work.

---

## Problem and why it matters now

Gate 2 locked deployment, annotation workflow, and six bounded voice pilots are complete. The original Stage A sequence placed **Gate 3** next: founder approval to register the membership-confirmed 22-source plan and, in a **separate** decision, start a bounded **transcription-only** evidence run under I13 admission controls.

Without an explicit Gate 3 decision, processing remains fail-closed: no admitted corpus transcription, no acceptance/learning plan, and no path to Gate 4. Tom asked to make this decision now rather than continue only on overlap/poor-audio voice gaps (which are a separate track).

---

## Success criteria (how we know Gate 3 is resolved)

Gate 3 is **resolved** when Tom records one of the authorized outcomes below and the chosen path is executed or formally waived:

| Outcome | Success looks like |
|---|---|
| **A — Full bounded run** | Admission registered and started; 22 transcription units enqueued under that admission; drain enabled only for the run; all items complete (expected mostly `noop`); admission stopped; legacy NULL-stamped rows unchanged; drains returned to `0`; no Learn or recognition work |
| **B — Waive transcription run** | Founder records that existing stored words on all 22 manifest sources satisfy the evidence-generation intent; no transcription enqueue; Gate 3 transcription **run** explicitly skipped with review reference |
| **C — Register/start only** | Admission registered and started for audit/provenance; **no** drain enablement and **no** enqueue; admission stopped after recording state |

Gate 3 resolution does **not** mean full I13 acceptance, voice matrix completion, or Gate 4 unlock.

---

## Scope

### In scope for this decision

- Whether to authorize Gate 3 for the **existing** `bounded-manifest-proposal.json` (22 sources, transcribe lane only, `max_work_items: 1000`, `max_attempts_per_item: 2`).
- Work limits: preview confirms **22 work items**, **44 max attempts**, plan SHA `330c2f90fa0de3b319097d17f31ca5dfabe6bd57b469a1a033a79e3851259b35`.
- Operator procedure, backup gate, and rollback boundaries if Outcome A or C is chosen.

### Explicitly out of scope (not authorized by any Gate 3 outcome)

- Learn unlock or exemplar creation from annotations
- Face or voice recognition drains on the 22-source corpus
- Gate 4 archive register/unlock/start
- Overlap/poor-audio voice pilot (requires new owner annotations first)
- Face/voice corroboration acceptance matrix
- Re-transcription to replace existing words (immutable transcript policy; existing engine skips sources that already have words)
- Generalized accuracy claims or full I13 sign-off

---

## Gate 2 evidence summary (prerequisites met)

| Area | Status |
|---|---|
| Migration 030/031/032 on FlightSim | Applied |
| Locked app + annotation workflow | Owner accepted |
| 22-source membership | Confirmed 2026-09-05 |
| Bounded voice pilots (6 admissions) | Stopped; see [I13-VOICE-PILOT-STATUS.md](I13-VOICE-PILOT-STATUS.md) |
| Owner annotations | Ten reviewed voice assignments; annotation UI in production use |
| Drains / admission env | Must remain off except during an explicitly approved bounded run |

Remaining voice gaps (overlap/poor-audio, face/voice corroboration) are **documented** and **do not block** a Gate 3 transcription decision—they block full I13 voice acceptance, not admission registration.

---

## Critical fact: transcripts already exist on all 22 sources

Tom’s 2026-09-06 coverage checkpoint reports **zero** manifest sources without stored transcript words (**35,861 words** total on the 22-source manifest). The annotation workflow depends on those words.

Runtime behavior under admitted transcription (`memorybox/speech/process.py`): if a source already has a transcript and the enqueue reason is `transcribe`, the item completes as **`noop`** — no new words, no replacement.

**Implication:** Outcome A is primarily an **I13 admission and audit-trail exercise**, not a corpus re-transcription. It proves register → start → enqueue → bounded drain → stop on the canonical plan. It does not fix missing speech or advance voice matching.

Re-run preflight on FlightSim before any Outcome A execution:

```powershell
python -B docs/implementation/p2-i13-stage-a/inventory-transcript-coverage.py
```

Expect 22/22 `transcript_available: true` unless media or DB state changed since the checkpoint.

---

## Decision options

### Outcome A — Authorize full bounded transcription run (recommended if you want machinery proof)

**What happens:** Fresh backup → `register` → `start` → enqueue 22 transcribe units stamped with admission ID → enable **speech drain only** → process until complete → `stop` → disable drain → unset admission env.

**Pros:** Exercises the designed Gate 3 path end-to-end; immutable admission audit; confirms fail-closed stamping on queue rows; low media risk (expected all noops).

**Cons:** Operator time (~45–60 min with backup); ceremonial if all noops; does not advance voice acceptance.

**Does not authorize:** Recognition drain, Learn, face/voice lanes, or Gate 4.

---

### Outcome B — Waive transcription run; declare evidence-generation satisfied

**What happens:** Record a founder decision that pre-I13 stored transcripts on the confirmed 22-source manifest satisfy the **intent** of the evidence-generation phase. Skip register/start/enqueue for transcription. Proceed to **separate** planning for acceptance/learning or Gate 4—neither is automatic.

**Pros:** Avoids redundant no-op queue work; matches current reality (words exist; Tom is annotating).

**Cons:** I13 transcription admission path not proven at corpus scale (voice pilots used separate `voice_pilot` purpose, not this plan).

**Requires:** Explicit review reference and written waiver in `FOUNDER-AUTHORIZATION.md` after sign-off.

---

### Outcome C — Register and start only (audit state, no enqueue)

**What happens:** Backup → `register` → `start` → record admission UUID and plan digest → `stop` without enabling drain or enqueue.

**Pros:** Minimal processing footprint; admission machinery proven without queue/drain activity.

**Cons:** Stops short of step 17 enqueue authorization; partial relative to DEPLOYMENT-PLAN Gate 3 steps 16–18.

---

## Recommendation

**If the goal is to close Gate 3 as originally designed:** choose **Outcome A**. The run is low risk given existing transcripts, and it produces the audit record the deployment plan expects before any acceptance/learning plan.

**If the goal is to avoid ceremonial queue work:** choose **Outcome B**, provided you accept that corpus-scale I13 transcription admission remains unproven until a later need arises.

**Outcome C** is a compromise if you want an admission UUID on record without touching drains.

**Do not** treat Gate 3 as a substitute for overlap/poor-audio voice work or Gate 4 archive authorization.

---

## Execution package (only after sign-off)

If Outcome **A** or **C** is approved, follow [DEPLOYMENT-READINESS-GATE-3-EVIDENCE-GENERATION.md](DEPLOYMENT-READINESS-GATE-3-EVIDENCE-GENERATION.md).

If Outcome **B** is approved, no FlightSim processing run; update `FOUNDER-AUTHORIZATION.md` with the waiver reference only.

---

## Constraints and dependencies

- FlightSim operator: Tom only.
- Use established backup procedures before any Outcome A/C write path.
- Plan file must match preview SHA; any source hash/duration change requires a **new** plan and new review.
- `MEMORYBOX_RECOGNITION_DRAIN` must stay `0` for all Gate 3 outcomes.
- After any run, admission must be **stopped** and `MEMORYBOX_I13_ADMISSION_ID` unset in service env.
- Do not use `startmb.ps1` as a shortcut; do not enable legacy prove commands.

---

## Edge cases

| Case | Handling |
|---|---|
| Preflight shows fewer than 22 sources with words | Stop; reconcile manifest vs DB before Outcome A |
| Source hash mismatch vs plan | Stop; new plan version required |
| Item fails (not noop) | Stop admission; preserve backup; no automatic retry |
| Speech drain left enabled after run | Rollback procedure: stop admission, set drain `0`, unset admission ID |
| Tom wants face/voice on 22 sources | **Not Gate 3** — requires new `acceptance_learning` plan with owner truth and coverage |

---

## Open questions for Tom (answer before sign-off)

1. **Which outcome?** A (full run), B (waive run), or C (register/start only)?
2. **If A:** Approve plan limits as previewed (`22` items, `44` max attempts, ceiling `1000`) without change?
3. **If A or C:** Supply review reference string for `register --review-ref` (e.g. `Tom-approved-gate-3-evidence-generation-2026-09-08`)?
4. **If A:** Separate start reference for `start --reference` (e.g. `Tom-approved-gate-3-bounded-start-2026-09-08`)?
5. **If B:** Waiver reference text to record in `FOUNDER-AUTHORIZATION.md`?

---

## Sign-off

| Field | Value |
|---|---|
| Decision (A / B / C) | **A** — full bounded run |
| Review / waiver reference | `Tom-approved-gate-3-evidence-generation-outcome-a-2026-09-08` |
| Start reference (A/C only) | `Tom-approved-gate-3-bounded-start-2026-09-08` |
| Signed | Tom (chat 2026-09-08; executed same day) |
| Date | 2026-09-08 |
| Admission | `458d1a76-4ecb-4722-bd76-20125b14c1d3` (stopped) |

**Parallel note (not Gate 3):** Tom reported Eugene Will evidence and an off-camera Tom Will reference saved in MB for the overlap/poor-audio voice track. Next voice pilot planning starts with Eugene Will after Gate 3 executes.
