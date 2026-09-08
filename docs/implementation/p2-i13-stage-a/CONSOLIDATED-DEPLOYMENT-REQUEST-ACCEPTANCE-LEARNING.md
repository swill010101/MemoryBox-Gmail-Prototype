# Consolidated deployment request — bounded acceptance_learning + I13 Admin

**Date:** 2026-09-08  
**Branch:** `codex/p2-i13-stage-a`  
**Founder decision:** **B — Reject bounded closeout; complete accepted I13 scope**  
**Reference:** `Tom-reject-bounded-closeout-complete-i13-scope-2026-09-08`

---

## What shipped in this commit (desktop → origin)

| Deliverable | Location |
|---|---|
| Admin landing | `/admin/ui` |
| Admin → Jobs | `/admin/jobs/ui` + `GET /admin/api/jobs` |
| Admin → Learned Evidence | `/admin/learned-evidence/ui` + withdraw APIs |
| I13 admission status | `GET /admin/api/i13/status` |
| Shell nav | Admin in SYSTEM menu |
| Bounded acceptance_learning plan | [acceptance-learning-bounded-plan.json](acceptance-learning-bounded-plan.json) SHA `edd2ddc39…` |
| Plan builder | [build-bounded-acceptance-learning-plan.py](build-bounded-acceptance-learning-plan.py) |
| FR-005 offline spot-check | [fr005-explore-playback-spotcheck.py](fr005-explore-playback-spotcheck.py) |
| Readiness | [DEPLOYMENT-READINESS-ACCEPTANCE-LEARNING.md](DEPLOYMENT-READINESS-ACCEPTANCE-LEARNING.md) |
| Tests | `tests/test_i13_admin.py` |

Explore Learn activates under a **bounded `acceptance_learning` admission on the accepted 22-video manifest only** — not archive-wide Learn. During proof the admission is **started**; after proof, run **`enable-interactive-learn`**, keep `MEMORYBOX_I13_ADMISSION_ID` in serve env. Learn follow-on is **queued** (Admin → Jobs), not synchronous full-video recognition. See [INTERACTIVE-LEARN-OPERATING-STATE.md](INTERACTIVE-LEARN-OPERATING-STATE.md).

---

## FlightSim deploy (copy-paste)

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i13-stage-a
git pull origin codex/p2-i13-stage-a

# Load deployment env; keep drains off
$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'

$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
$plan = 'docs\implementation\p2-i13-stage-a\acceptance-learning-bounded-plan.json'

# Operator: fresh backup here (required before register/start)

& $python -B -m memorybox.processing preview --plan $plan

& $python -B -m memorybox.processing register --plan $plan --review-ref Tom-reject-bounded-closeout-complete-i13-scope-2026-09-08
# Save admission UUID from output:
# $admission = '<uuid>'

& $python -B -m memorybox.processing start --id $admission --reference Tom-bounded-acceptance-learning-proof-2026-09-08

$env:MEMORYBOX_I13_ADMISSION_ID = $admission
# Restart: python -m memorybox serve
```

---

## Live proof sequence (after serve restart)

1. **Face Learn:** `/explore/ui` → bounded source → Learn → box face → Person → Learn  
2. **Voice Learn:** same modal → highlight transcript span → Person → Learn  
3. **Admin Jobs:** `/admin/jobs/ui` — scoped rows; View opens Explore source  
4. **Learned Evidence:** `/admin/learned-evidence/ui` — exemplars listed; test withdraw with reason  
5. **FR-005:** open appearance in Explore; play **past** relevance end (manual)  
6. **Offline FR-005 binder:**  
   `& $python -B docs\implementation\p2-i13-stage-a\fr005-explore-playback-spotcheck.py`  
7. **Reconciliation inspector:**  
   `& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py`

---

## Post-proof steady state (required — do not remove admission env)

```powershell
& $python -B -m memorybox.processing stop --id $admission --reference Tom-bounded-acceptance-learning-proof-complete-2026-09-08

& $python -B -m memorybox.processing enable-interactive-learn `
  --id $admission `
  --reference Tom-post-i13-interactive-learn-enabled-2026-09-08

# KEEP $env:MEMORYBOX_I13_ADMISSION_ID = $admission in serve config
# Restart serve; re-run inspect-interactive-learn-reconciliation.py — check 6 must pass
```

**Do not** `Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID` after I13 acceptance. That re-disables interactive Learn.

---

## Explicitly not authorized in this deployment

- Archive Outcomes **C / D / E**
- `MEMORYBOX_RECOGNITION_DRAIN=1` or speech drain on archive-wide work
- Retrying Gate 3 or stopped voice pilots

---

## After live proof succeeds

Agent will publish **one consolidated final I13 acceptance review** for founder signature. I13 remains **OPEN** until that review is signed.
