# Deployment readiness — Gate 3 evidence-generation (transcription only)

**Status:** Tom authorized Outcome A on 2026-09-08. Execution package ready; FlightSim run pending.

If Outcome **A** is approved, follow this document and [deploy-gate-3-evidence-generation.ps1](deploy-gate-3-evidence-generation.ps1).

---

## Approved artifacts (fixed unless founder re-reviews)

| Item | Value |
|---|---|
| Plan file | `docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json` |
| Purpose | `evidence_generation` |
| Lanes | `transcribe` only |
| Sources | 22 (manifest `p2-i13-flightsim-22` v0.2-membership-confirmed) |
| Work items | 22 |
| Max attempts | 44 (2 per item) |
| Plan SHA-256 | `330c2f90fa0de3b319097d17f31ca5dfabe6bd57b469a1a033a79e3851259b35` |

Preview (dev or FlightSim):

```powershell
python -B -m memorybox.processing preview --plan docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json
```

---

## Expected runtime behavior

All 22 manifest sources already have stored transcript words (2026-09-06 checkpoint). Admitted transcription for sources with existing words completes as **`noop`** — no word replacement, no new immutable version unless the engine path differs (not expected).

Legacy speech queue rows with `i13_admission_id IS NULL` must **not** be claimed by this admission.

---

## Preconditions (stop if any fail)

1. Migrations 030–032 applied; no pending I13 migrations.
2. `MEMORYBOX_RECOGNITION_DRAIN=0` and `MEMORYBOX_SPEECH_DRAIN=0`; no stray `MEMORYBOX_I13_ADMISSION_ID`.
3. No other I13 admission in `started` state for this purpose.
4. Transcript coverage preflight: 22/22 sources with words (or founder explicitly accepts gaps).

```powershell
$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue

cd C:\MemoryBox
git pull --ff-only origin codex/p2-i13-stage-a

python -B docs/implementation/p2-i13-stage-a/inventory-transcript-coverage.py
python -B docs/implementation/p2-i13-stage-a/inventory-runtime.py
```

5. Fresh verified PostgreSQL backup on FlightSim `C:` before register (same standard as voice pilots).

---

## FlightSim execution (Outcome A)

Use a detached release checkout on `C:\MemoryBox` at the pushed commit. Check-only first:

```powershell
cd C:\MemoryBox
git fetch origin codex/p2-i13-stage-a
git pull --ff-only origin codex/p2-i13-stage-a
$sha = (git rev-parse HEAD).Trim()

powershell -NoProfile -ExecutionPolicy Bypass -File docs\implementation\p2-i13-stage-a\deploy-gate-3-evidence-generation.ps1 `
  -ExpectedReleaseSha $sha `
  -ReviewReference 'Tom-approved-gate-3-evidence-generation-outcome-a-2026-09-08' `
  -StartReference 'Tom-approved-gate-3-bounded-start-2026-09-08' `
  -ExpectedPlanSha '330c2f90fa0de3b319097d17f31ca5dfabe6bd57b469a1a033a79e3851259b35'
```

If check-only passes, rerun with `-Execute`. Paste the final JSON for recording.

---

## Outcome A — full bounded run (manual reference)

Replace `<REVIEW_REF>` and `<START_REF>` with Tom’s signed strings from the PRD.

### 1. Register (no workers, no enqueue)

```powershell
python -B -m memorybox.processing register `
  --plan docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json `
  --review-ref "<REVIEW_REF>"
```

Record returned `id` (admission UUID) and confirm `state: registered`.

### 2. Start (enables future admitted calls; still enqueues zero by itself)

```powershell
python -B -m memorybox.processing start `
  --id <ADMISSION_UUID> `
  --reference "<START_REF>"
```

### 3. Configure admission for enqueue/drain window only

In the **same** operator session used for enqueue and drain (and in worker env if drain runs in a separate process):

```powershell
$env:MEMORYBOX_I13_ADMISSION_ID = '<ADMISSION_UUID>'
```

Do **not** set recognition drain to `1`.

### 4. Enqueue 22 transcribe units (explicit operator action)

Use the established speech enqueue path that stamps `i13_admission_id` — one transcribe item per manifest source, no Person targets. If no consolidated helper exists in-repo yet, enqueue via the admitted API/CLI path documented for I13 scope (same pattern as voice pilot guards: manifest-only sources, reason `transcribe`).

**Stop** if enqueue would touch off-manifest sources or sets recognition items.

### 5. Enable speech drain only; process bounded batch

```powershell
$env:MEMORYBOX_SPEECH_DRAIN = '1'
# Run speech worker / drain until 22 admitted items complete or attempt cap hit — established FlightSim procedure
```

Monitor: expect `completed` + `noop: true` for sources with existing transcripts.

### 6. Stop admission and return to locked posture

```powershell
$env:MEMORYBOX_SPEECH_DRAIN = '0'

python -B -m memorybox.processing stop `
  --id <ADMISSION_UUID> `
  --reference "Tom-stopped-gate-3-evidence-generation-<date>"

Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
```

### 7. Post-run verification (read-only)

```powershell
python -B docs/implementation/p2-i13-stage-a/inventory-runtime.py
python -B docs/implementation/p2-i13-stage-a/inventory-transcript-coverage.py
```

Confirm: admission `stopped`; legacy NULL-stamped row counts unchanged vs pre-run snapshot; no new voice exemplars; annotation/transcript word totals stable (noop expectation).

Paste JSON outputs for agent recording.

---

## Outcome C — register/start/stop only

Execute steps 1–2 and 6 from Outcome A. **Skip** steps 3–5 (no admission env in workers, no enqueue, no drain).

---

## Rollback

| Failure | Action |
|---|---|
| Register/start fails | No drain; unset admission env; no retry without new review |
| Mid-run failure | `stop` admission; drain `0`; unset env; restore from backup only if data corruption (unexpected for noop path) |
| Wrong admission ID in env | Stop workers; unset env; verify no partial stamped work off-plan |

---

## Production writes (Outcome A)

- One `i13_processing_admissions` row + register/start/stop events
- Up to 22 admitted speech queue items stamped with admission ID
- Queue item status transitions (expected noop completions)
- No intentional transcript word changes if all noops

---

## Time and downtime

- Reserve **45–60 minutes** including backup (Outcome A).
- Outcome C: **~15 minutes** with backup.
- App/worker restart only if required to pick up admission env for drain window; prefer established locked launcher, not bare `startmb`.

---

## After Gate 3 (not automatic)

- **Gate 4** archive unlock/start remains a separate founder decision.
- **Acceptance/learning** requires a new plan with owner truth, coverage tags, and Person targets — not this evidence-generation plan.
- **Overlap/poor-audio voice pilot** remains blocked until Tom saves new annotations.
