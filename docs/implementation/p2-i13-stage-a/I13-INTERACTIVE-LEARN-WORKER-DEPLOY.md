# I13 consolidated deployment — Interactive Learn worker + Admin repair

**Status:** Ready for founder-authorized single deploy  
**Branch:** `codex/p2-i13-stage-a`  
**Do not deploy until Tom authorizes.**

---

## What this deploy fixes

| Area | Change |
|------|--------|
| Interactive Learn follow-on | Dedicated worker claims only `owner_learn` rows for the active bounded admission |
| Processing lane gap | Works while admission is **started** (proof) or **stopped + interactive_learn_enabled** (post-I13) |
| Bulk drains | `MEMORYBOX_RECOGNITION_DRAIN=0` and `MEMORYBOX_SPEECH_DRAIN=0` unchanged |
| Admin landing | Dark-theme cards; human-readable status (no raw JSON) |
| Processing Jobs | Truthful worker note; owner_learn queued/completed counts; status row colors |
| Learned Evidence | Safe empty API handling; exemplars filter `method=owner_learn`; highlight uses `is_owner_learn` |
| Review & Learn | Dark-theme clarification banner pointing to Explore Learn |

---

## FlightSim deploy (after Tom authorizes)

```powershell
cd C:\MemoryBox
git fetch origin codex/p2-i13-stage-a
git checkout origin/codex/p2-i13-stage-a -- `
  memorybox/processing/scope.py `
  memorybox/processing/interactive_drain.py `
  memorybox/recognition/queue.py `
  memorybox/recognition/process.py `
  memorybox/recognition/scan.py `
  memorybox/speech/queue.py `
  memorybox/speech/process.py `
  memorybox/admin/i13_admin.py `
  memorybox/admin/static/admin.html `
  memorybox/admin/static/jobs.html `
  memorybox/admin/static/learned_evidence.html `
  memorybox/review/static/review.html `
  memorybox/shell/static/shell.css `
  memorybox/app.py `
  docs/implementation/p2-i13-stage-a/INTERACTIVE-LEARN-OPERATING-STATE.md `
  docs/implementation/p2-i13-stage-a/inspect-interactive-learn-reconciliation.py

# Restart serve only (admission stays started; drains stay 0)
# Use your established serve restart procedure
```

**Preserve:** `MEMORYBOX_I13_ADMISSION_ID=9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a`, both bulk drains `0`, admission **started**.

---

## Automated proof sequence (engineering on FlightSim)

```powershell
cd C:\MemoryBox
$Python = 'C:\MemoryBox\.venv\Scripts\python.exe'
$env:MEMORYBOX_DATABASE_URL = 'postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox'
$env:MEMORYBOX_I13_ADMISSION_ID = '9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a'
$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'

# 1. Before restart — note queued owner_learn rows
docker exec memorybox-pg psql -U memorybox -d memorybox -c "
  SELECT 'face' AS lane, video_external_id, status, enqueue_reason
  FROM recognition_queue_items
  WHERE i13_admission_id = '9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a'::uuid
    AND enqueue_reason = 'owner_learn'
  UNION ALL
  SELECT 'voice', video_external_id, status, enqueue_reason
  FROM speech_queue_items
  WHERE i13_admission_id = '9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a'::uuid
    AND enqueue_reason = 'owner_learn';"

# 2. Restart serve (founder-authorized deploy step)

# 3. Status — interactive worker should be true
Invoke-RestMethod http://127.0.0.1:8790/admin/api/i13/status | ConvertTo-Json -Depth 4

# 4. Wait up to 2 minutes; refresh Jobs — owner_learn rows should move to completed
Invoke-RestMethod http://127.0.0.1:8790/admin/api/jobs | ConvertTo-Json -Depth 5

# 5. Reconciliation inspector
$ProofRoot = 'C:\MemoryBox\docs\test-output\i13-final'
New-Item -ItemType Directory -Force -Path $ProofRoot | Out-Null
$env:MEMORYBOX_I13_LEARN_RECON_OUTPUT = "$ProofRoot\learn-recon.json"
& $Python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py

# 6. Confirm no bulk drain activity — archive still locked
docker exec memorybox-pg psql -U memorybox -d memorybox -c "
  SELECT enqueue_reason, status, count(*)
  FROM recognition_queue_items
  WHERE i13_admission_id = '9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a'::uuid
  GROUP BY 1,2
  ORDER BY 1,2;"
```

**Pass criteria:** existing face + voice `owner_learn` jobs reach **`completed`** exactly once; `interactive_learn_worker_enabled: true`; bulk drains remain `0`; no new off-manifest queue rows.

---

## Founder visual checklist (after deploy + restart)

| # | Check | Pass |
|---|-------|------|
| 1 | `/admin/ui` — dark cards readable; status shows Interactive Learn / worker / archive locked in plain language | |
| 2 | `/admin/jobs/ui` — prior face + voice `owner_learn` rows show **completed** (not stuck queued) | |
| 3 | `/admin/learned-evidence/ui` — Eugene face + voice exemplars visible; no crash on load | |
| 4 | `/review/ui` — banner clarifies Learn is in Explore (readable on dark background) | |
| 5 | Bulk drains still `0` in status; no archive processing started | |

I13 remains **open** until this checklist passes and Phase 5 automation completes.

---

## Rollback (if deploy causes regression)

```powershell
cd C:\MemoryBox
# Record pre-deploy SHA first: git rev-parse HEAD

git fetch origin codex/p2-i13-stage-a
git checkout <PRE_DEPLOY_SHA> -- `
  memorybox/processing/scope.py `
  memorybox/processing/interactive_drain.py `
  memorybox/recognition/queue.py `
  memorybox/recognition/process.py `
  memorybox/recognition/scan.py `
  memorybox/speech/queue.py `
  memorybox/speech/process.py `
  memorybox/admin/i13_admin.py `
  memorybox/admin/static/admin.html `
  memorybox/admin/static/jobs.html `
  memorybox/admin/static/learned_evidence.html `
  memorybox/review/static/review.html `
  memorybox/shell/static/shell.css `
  memorybox/app.py `
  docs/implementation/p2-i13-stage-a/INTERACTIVE-LEARN-OPERATING-STATE.md `
  docs/implementation/p2-i13-stage-a/inspect-interactive-learn-reconciliation.py `
  docs/implementation/p2-i13-stage-a/I13-INTERACTIVE-LEARN-WORKER-DEPLOY.md `
  tests/test_i13_stage_a.py `
  tests/test_i13_interactive_learn_worker.py

# Restart serve. Admission stays started; drains stay 0.
# Queued owner_learn rows remain queued until a forward fix is redeployed.
```

Replace `<PRE_DEPLOY_SHA>` with the git SHA recorded immediately before deploy.
