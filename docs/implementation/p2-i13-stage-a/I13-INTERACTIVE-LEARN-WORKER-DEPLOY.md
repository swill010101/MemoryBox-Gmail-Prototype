# I13 consolidated deployment — Interactive Learn worker + Admin repair

**Status:** Engineering checkpoint complete — **not deploy-authorized until Tom approves**  
**Branch:** `codex/p2-i13-stage-a`  
**Approved commit:** `93f5105776fd5cabacb536f3935585b969ee5c5d`  
**Parent commit:** `c6aedcdb2f03a0d0ec76ced134301b8df0112cef` (19-file implementation)  
**Implementation parent:** `c21ff43166ea7a3ebdb6c6d1ef9964f24bbef176`

Do **not** deploy, restart FlightSim serve, stop admission, enable bulk drains, or start Phase 6 without explicit founder authorization.

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

## Desktop engineering proof (already complete)

| Check | Result |
|-------|--------|
| Approved commit | `93f5105776fd5cabacb536f3935585b969ee5c5d` |
| Parent | `c6aedcdb2f03a0d0ec76ced134301b8df0112cef` |
| Implementation parent | `c21ff43166ea7a3ebdb6c6d1ef9964f24bbef176` |
| Remote branch | `origin/codex/p2-i13-stage-a` → `93f5105776fd5cabacb536f3935585b969ee5c5d` |
| Tests | **Ran 200 tests** — OK (failures=0, errors=0, skipped=24) |
| Tracked worktree | Clean (only unrelated untracked docs under `docs/`) |

**Test nature:** All 200 tests are **synthetic/unit/offline doubles** — no production DB, no FlightSim runtime, no model weights. The 24 skips are **explicit PostgreSQL integration tests** gated by `I13_SYNTHETIC_PG_TEST=1` (disposable cluster at `127.0.0.1:55439`). They do **not** block deployment when the corresponding behavior is covered by the FlightSim proof below.

### Skipped PostgreSQL tests (24 reported; 19 unique)

| File | Class | Count | Gate |
|------|-------|------:|------|
| `tests/test_i13_annotations.py` | `Database` | 12 | `I13_SYNTHETIC_PG_TEST=1` — transcript annotation persistence |
| `tests/test_i13_voice_pilot.py` | `Database` | 5 | `I13_SYNTHETIC_PG_TEST=1` — voice pilot store/run lifecycle |
| `tests/test_i13_pg16_rehearsal.py` | `SQLTests` | 2 | `I13_SYNTHETIC_PG_TEST=1` — migration 032 rehearsal |

Note: unittest discovery loads `test_i13_voice_pilot.Database` twice (via `test_i13_pg16_rehearsal` import), so the runner reports **24** skips while **19** unique test methods are gated.

**FlightSim proof covers instead:** live `owner_learn` queue drain, admin status/jobs APIs, reconciliation inspector check 7, and bounded-admission queue scoping on production PostgreSQL.

---

## FlightSim deploy runbook (founder-authorized only)

Deploy the **exact reviewed commit** — not a path cherry-pick.

### Constants

```powershell
$ApprovedSha = '93f5105776fd5cabacb536f3935585b969ee5c5d'
$Branch      = 'codex/p2-i13-stage-a'
```

### Step 0 — Record baseline and verify clean tree

```powershell
cd C:\MemoryBox

$PreDeploySha = git rev-parse HEAD
Write-Host "PRE_DEPLOY_SHA=$PreDeploySha"

$Dirty = git status --porcelain | Where-Object { $_ -match '^[ MADRCU]' }
if ($Dirty) {
    Write-Error "STOP: tracked FlightSim changes exist before deploy. Resolve or stash tracked files first."
    exit 1
}
```

**Stop immediately** if any tracked modifications exist. Untracked runtime data (`.env`, databases, logs, media caches) is preserved and not touched by this procedure.

### Step 1 — Fetch approved commit

```powershell
git fetch origin $Branch
git cat-file -t $ApprovedSha   # must print: commit
git merge-base --is-ancestor $PreDeploySha $ApprovedSha; if ($LASTEXITCODE -ne 0) { Write-Warning "Approved commit is not a descendant of PRE_DEPLOY_SHA; review history before proceeding." }
```

### Step 2 — Deploy exact SHA (choose one)

**Option A — fast-forward tracking branch (preferred when FlightSim tracks `$Branch`):**

```powershell
git checkout $Branch
git merge --ff-only $ApprovedSha
```

**Option B — detached HEAD at exact SHA (when FlightSim must not move a branch tip):**

```powershell
git checkout --detach $ApprovedSha
```

### Step 3 — Verify FlightSim HEAD

```powershell
$Head = git rev-parse HEAD
if ($Head -ne $ApprovedSha) {
    Write-Error "STOP: HEAD=$Head does not equal approved SHA $ApprovedSha"
    exit 1
}
Write-Host "FlightSim HEAD verified: $Head"
```

### Step 4 — Restart serve only

Use the established FlightSim serve restart procedure. **Do not** stop admission, change drain flags, or start Phase 6.

**Preserve environment:**

- `MEMORYBOX_I13_ADMISSION_ID=9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a`
- `MEMORYBOX_RECOGNITION_DRAIN=0`
- `MEMORYBOX_SPEECH_DRAIN=0`
- Admission state: **started**

---

## FlightSim proof sequence (after restart)

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
Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/i13/status' | ConvertTo-Json -Depth 4

# 4. Wait up to 2 minutes; refresh Jobs — owner_learn rows should move to completed
Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/jobs' | ConvertTo-Json -Depth 5

# 5. Reconciliation inspector (must fail while stranded; pass only after completion)
$ProofRoot = 'C:\MemoryBox\docs\test-output\i13-final'
New-Item -ItemType Directory -Force -Path $ProofRoot | Out-Null
$env:MEMORYBOX_I13_LEARN_RECON_OUTPUT = "$ProofRoot\learn-recon.json"
& $Python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
if ($LASTEXITCODE -ne 0) { Write-Error "Inspector gate failed"; exit 1 }

# 6. Confirm no bulk drain activity — archive still locked
docker exec memorybox-pg psql -U memorybox -d memorybox -c "
  SELECT enqueue_reason, status, count(*)
  FROM recognition_queue_items
  WHERE i13_admission_id = '9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a'::uuid
  GROUP BY 1,2
  ORDER BY 1,2;"
```

**Pass criteria:** existing face + voice `owner_learn` jobs reach **`completed`** exactly once; `interactive_learn_worker_enabled: true`; bulk drains remain `0`; inspector check 7 passes; no new off-manifest queue rows.

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

## Rollback runbook (restore complete PRE_DEPLOY_SHA)

Rollback restores **the entire tree** at `$PreDeploySha`, including removal of files that did not exist at baseline (e.g. `memorybox/processing/interactive_drain.py`, `tests/test_i13_interactive_learn_worker.py`). Do **not** use a path-list checkout — that leaves new files behind.

```powershell
cd C:\MemoryBox

# Use the PRE_DEPLOY_SHA recorded in Step 0 before deploy
$PreDeploySha = '<PRE_DEPLOY_SHA>'

$Dirty = git status --porcelain | Where-Object { $_ -match '^[ MADRCU]' }
if ($Dirty) {
    Write-Warning "Tracked changes present before rollback; proceeding with hard reset."
}

git reset --hard $PreDeploySha

$Head = git rev-parse HEAD
if ($Head -ne $PreDeploySha) {
    Write-Error "STOP: rollback HEAD=$Head does not equal PRE_DEPLOY_SHA=$PreDeploySha"
    exit 1
}
Write-Host "Rollback verified: HEAD=$Head"

# Restart serve. Admission stays started; drains stay 0.
# Queued owner_learn rows remain queued until a forward fix is redeployed.
```

**Preserves:** untracked runtime data and environment files (`.env`, local DB volumes, logs) — `git reset --hard` does not delete untracked files. Review `git status` after rollback; do not run `git clean -fd` unless Tom explicitly authorizes removing specific untracked artifacts.

---

## Files in approved commit (19)

1. `memorybox/processing/interactive_drain.py` *(new)*
2. `memorybox/processing/scope.py`
3. `memorybox/recognition/queue.py`
4. `memorybox/recognition/process.py`
5. `memorybox/recognition/scan.py`
6. `memorybox/speech/queue.py`
7. `memorybox/speech/process.py`
8. `memorybox/admin/i13_admin.py`
9. `memorybox/admin/static/admin.html`
10. `memorybox/admin/static/jobs.html`
11. `memorybox/admin/static/learned_evidence.html`
12. `memorybox/review/static/review.html`
13. `memorybox/shell/static/shell.css`
14. `memorybox/app.py`
15. `tests/test_i13_stage_a.py`
16. `tests/test_i13_interactive_learn_worker.py` *(new)*
17. `docs/implementation/p2-i13-stage-a/INTERACTIVE-LEARN-OPERATING-STATE.md`
18. `docs/implementation/p2-i13-stage-a/inspect-interactive-learn-reconciliation.py`
19. `docs/implementation/p2-i13-stage-a/I13-INTERACTIVE-LEARN-WORKER-DEPLOY.md`
