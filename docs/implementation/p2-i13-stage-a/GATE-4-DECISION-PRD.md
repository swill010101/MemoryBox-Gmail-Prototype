# Gate 4 decision — archive acceptance, unlock, and start

**Status:** Outcome **A — Defer** signed 2026-09-08; narrow acceptance waiver + Outcome **B plan-only** authorized same day (Tom option 2). No register/unlock/start.
**Branch:** `codex/p2-i13-stage-a`  
**Predecessors:** Gate 3 complete (`458d1a76…`); overlap voice pilot complete (`339b3a14…`)

This document is a **decision PRD only**. It does not register an archive admission, unlock archive scope, start processing, enable drains, authorize Learn, or begin **P2-I14**.

---

## Naming clarification

| Term | Meaning |
|---|---|
| **Gate 4 (this document)** | I13 deployment gate: `scope_kind=archive` plan → founder **acceptance** → **unlock** → separate **start** ([DEPLOYMENT-PLAN.md](DEPLOYMENT-PLAN.md) steps 19–20) |
| **P2-I14 (product increment)** | Next roadmap increment after **full I13 acceptance**: Unified Person Evidence & Timeline ([MBRM-001C](../../product/MBRM-001C_P2_POST_I12_ROADMAP.md)) — **not authorized by Gate 4 planning** |

If the request was to begin **P2-I14** product work, stop here: I14 follows I13 acceptance, not Gate 4 alone.

---

## Problem and why it matters now

Gate 3 transcription evidence-generation and seven bounded voice pilots (including overlap/poor-audio) are complete. I13 admission machinery, fail-closed scope checks, and locked archive behavior are partially proven, but **archive release** — the path that allows admitted face/voice archive passes on an explicit reviewed inventory — has never been exercised on FlightSim.

Without an explicit Gate 4 decision, archive scope remains locked (`archive_locked` in `memorybox/processing/scope.py`), recognition/speech drains must stay off outside approved windows, and the acceptance checklist item for **locked archive behavior** stays open.

Tom asked to begin the next phase for Gate 4. That means **founder review of this PRD**, not automatic processing.

---

## Success criteria (how we know Gate 4 is resolved)

Gate 4 is **resolved** when Tom records one authorized outcome below and any chosen execution path is completed or formally waived:

| Outcome | Success looks like |
|---|---|
| **A — Defer** | Written decision to complete prerequisite acceptance work first (face/voice corroboration, acceptance_learning plan export, or explicit waiver scope); Gate 4 execution deferred with review reference |
| **B — Plan-only** | Reviewed `scope_kind=archive` plan JSON authored and preview-validated on FlightSim (`python -B -m memorybox.processing preview --plan …`); plan SHA recorded; **no** register/unlock/start |
| **C — Register only** | Fresh backup → `register` archive plan → record admission UUID and plan digest → **stop** before unlock (audit state only) |
| **D — Unlock only** | After separate **bounded acceptance** reference recorded → `unlock --acceptance-ref … --reference …` → admission state `unlocked`; **no** `start`, no drain, no enqueue |
| **E — Full archive start path** | Backup → register → unlock → separate `start` → explicit enqueue under admission → bounded drain window → `stop` → drains off, admission env unset |
| **F — Waive archive run** | Founder records that pre-I13 locked behavior and completed bounded pilots satisfy archive-release **intent** for I13 Stage A; no archive register/unlock/start; checklist updated with waiver reference |

Gate 4 resolution does **not** mean full I13 acceptance, P2-I14 authorization, Learn unlock, or generalized corpus processing.

---

## Scope

### In scope for this decision

- Whether Gate 4 should proceed now or defer until acceptance prerequisites are clearer.
- What **archive inventory** would be (explicit source list — same 22, subset, or other reviewed list; **no wildcards**).
- Which **lanes** (`face`, `voice`, `transcribe`) and **Person UUIDs** an archive plan would admit.
- Work limits: `max_work_items` (hard ceiling 10,000 in schema), `max_attempts_per_item` (1–3).
- Three-reference lifecycle: **acceptance-ref** (bounded acceptance complete) → **unlock-ref** → **start-ref** (separate founder strings).
- Operator backup, rollback, and “do not retry stopped admission” boundaries.

### Explicitly out of scope (not authorized by any Gate 4 outcome unless a future signed plan says otherwise)

- P2-I14 Unified Person Evidence & Timeline implementation
- Learn unlock or annotation→exemplar automation without a reviewed plan
- Provider-wide Immich seed/sync (`seed_immich` is denied by admission code)
- Legacy prove commands, bare `python`, or `startmb` shortcuts
- Wildcard or runtime-discovered archive inventory
- Widening an existing admission in place (requires new plan + new review)
- Re-running completed admissions: Gate 3 `458d1a76…`, overlap pilot `339b3a14…`, or any stopped voice pilot

---

## Prerequisites (current state)

| Prerequisite | Status |
|---|---|
| Gate 3 evidence-generation | **Complete** — [gate-3-evidence-generation-report.json](gate-3-evidence-generation-report.json) |
| Bounded voice pilots (7 admissions) | **Complete** — [I13-VOICE-PILOT-STATUS.md](I13-VOICE-PILOT-STATUS.md) |
| Overlap / poor-audio pilot | **Complete** — [overlap-poor-audio-voice-pilot-report.json](overlap-poor-audio-voice-pilot-report.json) |
| 22-source membership | Confirmed 2026-09-05 — [bounded-manifest-proposal.json](bounded-manifest-proposal.json) |
| Owner annotations in MB | Voice track substantial; face/voice **corroboration** matrix not complete |
| `acceptance_learning` plan with full coverage tags on 22 sources | **Not authored** — scope preview requires all eight coverage tags for bounded acceptance_learning |
| Archive plan JSON (`scope_kind=archive`) | **Not authored** |
| Bounded acceptance reference for `unlock --acceptance-ref` | **Not recorded** |

**Deployment-plan requirement (step 19):** archive planning assumes owner annotations are captured and **bounded acceptance is separately completed**. Voice pilots satisfy **narrow voice evidence**, not the full corpus `acceptance_learning` contract. Gate 4 unlock therefore needs either:

1. A completed **acceptance_learning** bounded plan (22 sources, owner truth, coverage tags, Person targets), **or**
2. An explicit founder **acceptance waiver** stating which checklist gaps remain open and what the acceptance-ref string means for archive unlock.

---

## What archive admission would do (code truth)

From [scope-plan-schema.md](scope-plan-schema.md) and `memorybox/processing/control.py`:

1. **`register --plan … --review-ref …`** — creates admission in state `registered`; no workers, no enqueue.
2. **`unlock --id … --acceptance-ref … --reference …`** — only for `scope_kind=archive`; requires prior bounded acceptance reference; state → `unlocked`; still no enqueue.
3. **`start --id … --reference …`** — archive requires prior unlock; state → `started`; still **zero** automatic enqueue until operator enables drains and enqueues admitted work.

Face archive pass (`memorybox/recognition/archive_pass.py`) calls `require_admission("face", archive=full)` and enqueues only **admitted** People × admitted sources — no discovery sweep.

**Implication:** Outcome E is high-impact. Even a small archive plan can create large queue cardinality (`sources × people × lanes`). Preview and hard limits must be reviewed before any start.

---

## Decision options

### Outcome A — Defer Gate 4 (recommended default)

**What happens:** Finish or waive acceptance prerequisites first — export owner truth from FlightSim (`inventory-transcript-coverage.py`, `/annotations/transcript/coverage`), decide face/voice corroboration scope, optionally author `acceptance_learning` bounded plan, **then** return to archive plan design.

**Pros:** Matches deployment-plan sequencing; avoids unlock without a clear acceptance-ref meaning.

**Cons:** Gate 4 checklist item stays open longer.

---

### Outcome B — Plan-only (recommended if proceeding now without runtime writes)

**What happens:** Agent drafts archive plan JSON + readiness doc; Tom runs preview on FlightSim; record plan SHA; no DB admission transitions.

**Pros:** Surfaces workload cardinality and schema validation with zero processing risk.

**Cons:** Does not prove unlock/start machinery.

---

### Outcome C / D / E — Progressive admission transitions

Escalating operator paths. Each step requires fresh backup before writes. **Do not skip unlock before start** on archive plans.

**Outcome E risks:** Recognition queue growth, long runtime, legacy NULL-stamped rows must remain ineligible unless explicitly stamped under the new admission.

---

### Outcome F — Waive archive execution for Stage A

**What happens:** Record that I13 Stage A’s archive-lock proof is satisfied by offline tests + locked runtime + bounded pilots without a corpus archive pass. Update checklist with waiver reference.

**Pros:** Avoids high-cardinality archive work if not needed for I13 closeout.

**Cons:** FlightSim archive unlock/start path remains unproven at runtime.

---

## Recommended sequencing

1. **Sign this PRD** with an outcome (A–F).
2. If not **F**: run read-only export on FlightSim to inform archive inventory and Person list — do not commit private exports to Git.
3. If **B+**: author `archive-manifest-proposal.json` (or subset plan) with explicit sources, truth refs, lanes, limits; preview before register.
4. Only after **acceptance-ref** meaning is clear: prepare `DEPLOYMENT-READINESS-GATE-4-ARCHIVE.md` + guarded deploy helper (same pattern as Gate 3 / overlap pilot).
5. **P2-I14** planning begins only after Tom declares I13 acceptance or explicitly splits I14 prep from I13 closeout.

---

## Constraints and dependencies

- FlightSim operator: Tom only.
- Tooling: TitaNet release `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5` for voice-related helpers; processing CLI via FlightSim checkout.
- Drains: `MEMORYBOX_RECOGNITION_DRAIN=0`, `MEMORYBOX_SPEECH_DRAIN=0` except during an explicitly approved bounded execute window.
- After any run: admission **stopped**, `MEMORYBOX_I13_ADMISSION_ID` unset in service env.
- Stopped admissions are immutable — new work needs a new plan and admission.

---

## Edge cases

| Case | Handling |
|---|---|
| Preview rejects plan (coverage incomplete) | Expected for full 22-source acceptance_learning; narrow archive inventory or defer |
| Work items exceed `max_work_items` | Reduce sources, People, or lanes; never raise ceiling without founder review |
| Acceptance-ref without written bounded acceptance | Stop — unlock denied by design |
| Tom wants face archive on all Immich videos | Off-manifest — requires explicit per-video archive inventory, not `--full` discovery |
| Overlap with voice pilot spans | Archive plan must not silently reuse pilot spans as owner truth without review refs |

---

## Open questions for Tom (answer before sign-off)

1. **Which outcome?** A (defer), B (plan-only), C, D, E, or F (waive)?
2. **Archive inventory scope:** Same 22 manifest sources, strict subset, or a different explicit list?
3. **Lanes and People:** Face only, voice only, both, transcribe? Which canonical Person UUIDs?
4. **Bounded acceptance:** Will you complete a full `acceptance_learning` plan first, or issue a **narrow waiver** referencing completed voice pilots + annotations (exact reference string)?
5. **Relationship to P2-I14:** Confirm Gate 4 is I13 archive closeout, not authorization to start I14 product build.
6. **If B–E:** Review reference string for `register --review-ref`?

---

## Sign-off

| Field | Value |
|---|---|
| Outcome (A / B / C / D / E / F) | **A — Defer** |
| Acceptance / waiver reference | _n/a — defer; no unlock_ |
| Unlock reference (D/E only) | _n/a_ |
| Start reference (E only) | _n/a_ |
| Signed | Tom (chat 2026-09-08) |
| Date | 2026-09-08 |
| Admission UUID | _none — Gate 4 not registered_ |

**Deferred until:** face/voice corroboration scope decided, or full corpus acceptance path chosen.

**2026-09-08 update:** Tom authorized [NARROW-ACCEPTANCE-WAIVER.md](NARROW-ACCEPTANCE-WAIVER.md) and Gate 4 Outcome **B** plan-only preview — see [archive-manifest-proposal.json](archive-manifest-proposal.json) and [DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md](DEPLOYMENT-READINESS-GATE-4-ARCHIVE-PLAN-PREVIEW.md). Register/unlock/start still require fresh sign-off.

---

## Execution package (only after sign-off)

| Outcome | Next artifact |
|---|---|
| A | Update [FOUNDER-AUTHORIZATION.md](FOUNDER-AUTHORIZATION.md); list deferred prerequisites |
| B | `archive-manifest-proposal.json` + preview transcript |
| C–E | `DEPLOYMENT-READINESS-GATE-4-ARCHIVE.md` + guarded deploy helper (to be authored after sign-off) |
| F | Waiver entry in `FOUNDER-AUTHORIZATION.md` + checklist update only |
