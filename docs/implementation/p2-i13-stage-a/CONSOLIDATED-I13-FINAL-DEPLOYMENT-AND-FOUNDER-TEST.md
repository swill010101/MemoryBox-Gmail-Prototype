# P2-I13 — consolidated final deployment and founder test

**Status:** Deployment package prepared — **do not deploy until founder authorizes Phases 1–6 in one session**  
**Branch:** `codex/p2-i13-stage-a`  
**Final release SHA:** see [I13-FINAL-RELEASE.json](I13-FINAL-RELEASE.json) (`release_sha`)  
**Runbook authority:** single founder authorization covers Phases 1–6 without routine pauses  

**Governing scope:** Interactive Learn + Admin (A), persistent interactive Learn (B), legacy HVRT fragment reconciliation on the **22-video manifest only** (C). **Deferred to I18:** Scan for New Assets, archive intake, job-progress expansion, scheduled/nightly scanning. **Not authorized:** archive Outcomes C/D/E.

---

## Baseline reconciliation (completed on desktop)

| Check | Result |
|-------|--------|
| `306c079272f4561b83412576d77e6a44c7cf2fa9` Learn/Admin baseline | Present on branch |
| `bd76228a76d5b4b029814a77e82d6c64eafcd7a0` interactive Learn lifecycle | Present on branch |
| `8beb1a09f0dc5d44d3a936a6ce040d210b337e7b` fragment reconciliation gate | Present on branch (prior to this runbook commit) |
| Working tree | Clean before runbook commit |
| Migration `033_p2_i13_interactive_learn.sql` | Exactly **one** file; no duplicate 033 |
| Pending I13 migrations on FlightSim (expected) | 030, 031, 032 already applied or pending; **033 only** new for this release |
| Learn HTTP | Saves exemplar promptly; follow-on via `enqueue_interactive_owner_learn` (not sync scan/recognize) |
| Automated suite | `python -m unittest discover -s tests -p "test_i13*.py"` → **184 OK** (24 skipped) |

**Do not deploy the branch tip.** Deploy the pinned `release_sha` from `I13-FINAL-RELEASE.json` only.

---

## Expected disk usage (before authorization)

| Item | Location | Estimate |
|------|----------|----------|
| One PostgreSQL backup | `E:\MemoryBox-backups\i13-final-<timestamp>\` | ~200–800 MB (similar to prior Gate 3 backups) |
| Proof JSON (inventory, preview, inspectors) | `E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\` | < 50 MB |
| **Not created** | worktree, repo copy, release checkout, venv, media derivatives, C: backup | 0 |

---

## Constants (copy into FlightSim session)

```powershell
$ReleaseSha   = '<from I13-FINAL-RELEASE.json>'
$RepoRoot     = 'C:\MemoryBox'
$ProofRoot    = 'E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output'
$BackupRoot   = 'E:\MemoryBox-backups'
$Python       = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
$Plan         = 'docs\implementation\p2-i13-stage-a\acceptance-learning-bounded-plan.json'
$PlanDigest   = 'edd2ddc39e960992f2479d92578d8b9a870fbdc566386ce52df908495b291ca4'
$FounderRef   = 'Tom-i13-final-founder-session-2026-09-09'
$InteractiveRef = 'Tom-post-i13-interactive-learn-enabled-2026-09-09'
```

**Designated Tom test sources (22-video manifest):**

| Use | File | `video_external_id` |
|-----|------|---------------------|
| Face Learn (item 2) | `20111105_1532.MP4` | `vid-c57dbd21f993f6d1` |
| Voice Learn (item 3) | `20111105_1530.MP4` | `vid-da41273dbd9ac4bb` (transcript ~37–42 s or owner-chosen bounded span) |
| FR-005 (item 7) | Same face source or Explore appearance from item 2 | — |
| Fragment check (item 8) | `20111105_1532.MP4` + `20111105_1530.MP4` | pilot: 9 fragment presentations → 2 source cards |

---

## Phase 1 — Safe preflight

| Cursor / operator automation | Tom's manual observations |
|------------------------------|---------------------------|
| `cd C:\MemoryBox`; `git status`; preserve untracked local files; **do not** create worktree | — |
| `git fetch origin`; `git checkout $ReleaseSha` (detached HEAD at pin, or branch reset to pin) | — |
| Verify `git rev-parse HEAD` equals `$ReleaseSha` | — |
| Load deployment env (`MEMORYBOX_DATABASE_URL`, media paths); `$env:MEMORYBOX_RECOGNITION_DRAIN='0'`; `$env:MEMORYBOX_SPEECH_DRAIN='0'`; no stray `MEMORYBOX_I13_ADMISSION_ID` | — |
| `& $Python -B -m memorybox migrate --check` or query `schema_migrations`; confirm **only 033** pending after 030–032 | — |
| `& $Python -c "import psycopg; ..."` smoke test DB | — |
| Confirm `:8790` / `:8791` paths unchanged; note current serve mechanism | — |
| `Get-PSDrive C,E \| Select Name,Free` — report free GB on C: and E: | — |
| Create `$ProofRoot` if missing | — |
| Run read-only fragment inventory → `$ProofRoot\legacy-hvrt-fragment-inventory.json` | — |
| Run read-only fragment preview → `$ProofRoot\legacy-hvrt-fragment-preview.json` | Skim preview: before/after card counts and preserved gaps look reasonable |
| **Stop if:** SHA mismatch, dirty tree unsafe, 033 not sole pending migration, DB unreachable, E: low space | — |

```powershell
New-Item -ItemType Directory -Force -Path $ProofRoot | Out-Null
$env:MEMORYBOX_I13_FRAGMENT_INVENTORY_OUTPUT = "$ProofRoot\legacy-hvrt-fragment-inventory.json"
& $Python -B docs\implementation\p2-i13-stage-a\inventory-legacy-hvrt-fragments.py
$env:MEMORYBOX_I13_FRAGMENT_INVENTORY_JSON = "$ProofRoot\legacy-hvrt-fragment-inventory.json"
$env:MEMORYBOX_I13_FRAGMENT_PREVIEW_OUTPUT = "$ProofRoot\legacy-hvrt-fragment-preview.json"
& $Python -B docs\implementation\p2-i13-stage-a\preview-fragment-reconciliation.py
```

---

## Phase 2 — Backup and deployment

| Cursor / operator automation | Tom's manual observations |
|------------------------------|---------------------------|
| `$stamp = Get-Date -Format yyyyMMdd-HHmmss`; `$bak = "$BackupRoot\i13-final-$stamp"`; `pg_dump` to `$bak\memorybox.dump`; verify file size > 0 | — |
| Publish manifest fragment allowlist (no DB writes): `publish-fragment-allowlist.py --inventory ... --reference $FounderRef` then redeploy same SHA if allowlist file changed in repo **or** allowlist already in release | — |
| Stop MemoryBox serve + worker cleanly | — |
| Already at `$ReleaseSha`; `& $Python -B -m memorybox migrate` (applies **033 only** if 030–032 done) | — |
| Restart MemoryBox monolith + video worker from **this** checkout | — |
| Smoke: `GET /`, `/historian-capture/ui`, `/explore/ui`, `/people/ui`, `/admin/ui` return 200 | Open Gallery, People, Historian Capture, one existing video — all still load |
| `$env:MEMORYBOX_RECOGNITION_DRAIN='0'`; `$env:MEMORYBOX_SPEECH_DRAIN='0'` | Confirm playback on a **pre-existing** appearance still works |

**Stop if:** backup fails verification, migration error, or baseline routes broken.

---

## Phase 3 — Register one bounded acceptance admission

| Cursor / operator automation | Tom's manual observations |
|------------------------------|---------------------------|
| `& $Python -B -m memorybox.processing preview --plan $Plan` — confirm `source_count=22`, `work_items≤88`, **`enqueued` not auto-created** | — |
| Confirm preview output `max_work_items=88` is a **ceiling**, not 88 jobs spawned | — |
| `register --plan $Plan --review-ref $FounderRef` → **record `$admission` UUID** | — |
| Verify returned `plan_sha256` equals `$PlanDigest` | — |
| `start --id $admission --reference $FounderRef` | — |
| Set `$env:MEMORYBOX_I13_ADMISSION_ID = $admission`; persist in serve config; restart serve | — |
| **Drains remain 0.** Queue rows appear in Admin → Jobs when Tom Learns; optional: enable **one** drain (`MEMORYBOX_RECOGNITION_DRAIN=1` **or** `MEMORYBOX_SPEECH_DRAIN=1`) only if completed job outcomes required — return to 0 before Phase 6 | — |

```powershell
$preview = & $Python -B -m memorybox.processing preview --plan $Plan | ConvertFrom-Json
$preview.source_count  # expect 22
$preview.work_items     # expect <= 88
$reg = & $Python -B -m memorybox.processing register --plan $Plan --review-ref $FounderRef | ConvertFrom-Json
$admission = $reg.id
$reg.preview.enqueued   # expect 0
$reg.plan_sha256        # must equal $PlanDigest
& $Python -B -m memorybox.processing start --id $admission --reference $FounderRef
$env:MEMORYBOX_I13_ADMISSION_ID = $admission
# restart serve; record $admission and digest in $ProofRoot\admission-record.json
```

**Stop if:** plan ≠ 22 sources, digest mismatch, archive scope detected, or bulk enqueue > 0 without Learn action.

---

## Phase 4 — Tom's guided live test

Tom performs **only** these eight checks. Operator stays available; no DB prompts for Tom.

| # | Tom action | Expected visible result |
|---|------------|-------------------------|
| **1** | Open **Admin** from MemoryBox shell (`/admin/ui`) | **Jobs** and **Learned Evidence** destinations visible |
| **2** | Explore → **`20111105_1532.MP4`** → Learn tab → box one face → choose Person → **Learn** | Person selection succeeds; **one** scoped job in Admin → Jobs (`owner_learn`, same source); **no** 22-video or archive fan-out |
| **3** | Same or **`20111105_1530.MP4`** → highlight one transcript span → Person → **Learn** | Response returns promptly; exemplar saved; **one** scoped background job on **that source only** |
| **4** | **Admin → Jobs** (`/admin/jobs/ui`) | Each job shows type/lane, Person, source, status; View opens Explore on source |
| **5** | **Admin → Learned Evidence** | New face + voice exemplars with source, time, Person, modality, status |
| **6** | Withdraw **one** designated test exemplar (face or voice) with reason | Item shows withdrawn/retired; original video + annotations still intact |
| **7** | **FR-005:** open appearance from item 2; play past relevance end | Seeks to evidence start; **continues** past relevance end without stopping |
| **8** | Gallery: search representative HVRT results for **`20111105_1532.MP4`** and **`20111105_1530.MP4`** | Pilot: **not** nine separate half-second cards — **two** source cards with moment lists; meaningful gap (e.g. 40.5–60.5 s on 1532) still separate moments inside card |

Operator records Tom's pass/fail notes in `$ProofRoot\tom-observations.md` (short bullets).

---

## Phase 5 — Automated post-proof verification

| Cursor / operator automation | Tom's manual observations |
|------------------------------|---------------------------|
| Save `$env:MEMORYBOX_I13_ADMISSION_ID` in inspector env | — |
| `inspect-interactive-learn-reconciliation.py` → `$ProofRoot\learn-recon.json` | — |
| `inspect-face-voice-corroboration.py` → `$ProofRoot\corroboration.json` | — |
| `fr005-explore-playback-spotcheck.py` → `$ProofRoot\fr005-proof.json` | — |
| `verify-fragment-reconciliation.py` with inventory JSON | — |
| Query Admin APIs / DB read-only: Learn queue rows scoped to `$admission`; no off-manifest source changes; no archive admission unlocked | — |
| Confirm `register/unlock/start` archive and drains still locked | — |
| Write `$ProofRoot\phase5-summary.json` with before/after fragment counts from preview | — |

```powershell
$env:MEMORYBOX_I13_LEARN_RECON_OUTPUT = "$ProofRoot\learn-recon.json"
& $Python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
& $Python -B docs\implementation\p2-i13-stage-a\inspect-face-voice-corroboration.py
& $Python -B docs\implementation\p2-i13-stage-a\fr005-explore-playback-spotcheck.py
$env:MEMORYBOX_I13_FRAGMENT_INVENTORY_JSON = "$ProofRoot\legacy-hvrt-fragment-inventory.json"
& $Python -B docs\implementation\p2-i13-stage-a\verify-fragment-reconciliation.py
```

**Stop if:** unexplained material inspector failure, off-manifest mutation, or archive gate open.

---

## Phase 6 — Permanent bounded Learn operating state

| Cursor / operator automation | Tom's manual observations |
|------------------------------|---------------------------|
| `stop --id $admission --reference $FounderRef-proof-complete` | — |
| `enable-interactive-learn --id $admission --reference $InteractiveRef` | — |
| **Keep** `MEMORYBOX_I13_ADMISSION_ID=$admission` in serve config | — |
| `$env:MEMORYBOX_RECOGNITION_DRAIN='0'`; `$env:MEMORYBOX_SPEECH_DRAIN='0'`; restart serve | — |
| Re-run `inspect-interactive-learn-reconciliation.py` — Learn enabled while archive locked | Optional: one more face or voice Learn on manifest source — still works |
| Confirm processing drains and archive actions remain locked | — |

**Do not** `Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID`.

---

## Phase 7 — Final acceptance

| Cursor / operator automation | Tom's manual observations |
|------------------------------|---------------------------|
| Update [I13-ACCEPTANCE-MATRIX.md](I13-ACCEPTANCE-MATRIX.md) — classify every row | — |
| Complete [CONSOLIDATED-FINAL-I13-ACCEPTANCE-REVIEW.md](CONSOLIDATED-FINAL-I13-ACCEPTANCE-REVIEW.md) with SHA, backup path, UUID, digest, automated JSON, Tom notes, lock state | **Sign** accept or reject |
| **Do not** close I13 or start I14 until signed | — |

---

## Interruption rule (Phases 1–6)

Stop immediately if:

- deployed SHA ≠ `$ReleaseSha`
- worktree dirty and cannot preserve safely
- migration **033** is not the only expected pending migration
- backup fails verification
- plan exceeds 22 videos or 88-item ceiling without explicit Learn
- any archive register/unlock/start or archive drain would occur
- evidence or source integrity threatened
- automated test produces unexplained **material** failure

---

## Related documents

| Topic | Document |
|-------|----------|
| Interactive Learn steady state | [INTERACTIVE-LEARN-OPERATING-STATE.md](INTERACTIVE-LEARN-OPERATING-STATE.md) |
| Fragment gate | [LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md](LEGACY-HVRT-FRAGMENT-RECONCILIATION-GATE.md) |
| Acceptance matrix | [I13-ACCEPTANCE-MATRIX.md](I13-ACCEPTANCE-MATRIX.md) |
| Release pin | [I13-FINAL-RELEASE.json](I13-FINAL-RELEASE.json) |
| I18 deferral | Scan for New Assets, archive intake, job-progress UI, nightly scan — **out of I13 scope** |

---

## Founder authorization block (sign before Phase 1)

```
I authorize one continuous FlightSim session executing Phases 1–6 of
CONSOLIDATED-I13-FINAL-DEPLOYMENT-AND-FOUNDER-TEST.md at release SHA __________.

Reference: Tom-i13-final-founder-session-2026-09-09
Date: __________
```
