# FlightSim readiness: bounded acceptance_learning proof

**Branch:** `codex/p2-i13-stage-a` at or after implementation commit  
**Founder reference:** `Tom-reject-bounded-closeout-complete-i13-scope-2026-09-08`  
**Plan:** [acceptance-learning-bounded-plan.json](acceptance-learning-bounded-plan.json)  
**Plan SHA-256:** `edd2ddc39e960992f2479d92578d8b9a870fbdc566386ce52df908495b291ca4`

## Scope

| In | Out |
|---|---|
| Interactive Explore Learn (face + voice) | Archive Outcomes C/D/E |
| Admin landing, Jobs, Learned Evidence | Archive drains / `--full` archive pass |
| Bounded `acceptance_learning` register + start | Gate 3 re-run |
| FR-005 Explore spot-check (manual + offline binder) | New voice pilots |

## Preconditions

1. Deployment env loaded (`MEMORYBOX_DATABASE_URL`, media paths).
2. `$env:MEMORYBOX_RECOGNITION_DRAIN = '0'` and `$env:MEMORYBOX_SPEECH_DRAIN = '0'`.
3. TitaNet venv Python: `C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe`
4. Fresh backup before register/start (operator procedure under `C:\MemoryBox-backups\`).

## Deploy steps (Tom on FlightSim)

```powershell
cd C:\MemoryBox
git fetch origin
git checkout codex/p2-i13-stage-a
git pull origin codex/p2-i13-stage-a

$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
$plan = 'docs\implementation\p2-i13-stage-a\acceptance-learning-bounded-plan.json'

# 1) Preview (read-only)
& $python -B -m memorybox.processing preview --plan $plan

# 2) Register + start (after backup)
& $python -B -m memorybox.processing register --plan $plan --review-ref Tom-reject-bounded-closeout-complete-i13-scope-2026-09-08
# record returned admission UUID
& $python -B -m memorybox.processing start --id <ADMISSION_UUID> --reference Tom-bounded-acceptance-learning-proof-2026-09-08

# 3) Configure serve env and restart
$env:MEMORYBOX_I13_ADMISSION_ID = '<ADMISSION_UUID>'
# restart python -m memorybox serve
```

## Live proof checklist

| # | Action | Pass criterion |
|---|---|---|
| 1 | `/explore/ui` → video → Learn tab → box face → Person → Learn | `POST /recognition/learn` succeeds; row in Admin → Learned Evidence |
| 2 | `/explore/ui` → highlight transcript words → Person → Learn | `POST /speech/learn` succeeds; voice exemplar visible in Admin |
| 3 | `/admin/ui` → Jobs | Scoped queue rows visible; archive lock shows locked |
| 4 | `/admin/learned-evidence/ui` | Face/voice exemplars listed; withdraw test on disposable row |
| 5 | FR-005 | `/explore/ui` appearance: play continues past relevance end (manual) |
| 6 | Offline binder | `& $python -B docs\implementation\p2-i13-stage-a\fr005-explore-playback-spotcheck.py` → `"passed": true` |

## After proof

```powershell
& $python -B -m memorybox.processing stop --id <ADMISSION_UUID> --reference Tom-bounded-acceptance-learning-proof-complete-2026-09-08
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
# restart serve
```

Record proof JSON on E: (optional):

```powershell
$env:MEMORYBOX_I13_LEARN_RECON_OUTPUT = 'E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\acceptance-learning-proof.json'
& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
```

## Locks preserved

- Do **not** run archive register/unlock/start.
- Do **not** enable recognition/speech drains unless separately authorized for queue drain proof.
- Do **not** retry stopped voice pilots or Gate 3 admission.
