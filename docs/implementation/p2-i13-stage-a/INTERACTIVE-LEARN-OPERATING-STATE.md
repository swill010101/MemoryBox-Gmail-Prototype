# Interactive Learn — post-I13 operating state

**Status:** Required for I13 closeout (2026-09-08)  
**Migration:** `033_p2_i13_interactive_learn.sql`  
**Scope admission:** bounded `acceptance_learning` plan only

---

## Problem

The bounded proof runbook started an `acceptance_learning` admission, proved Explore Learn, then **stopped** the admission and **removed** `MEMORYBOX_I13_ADMISSION_ID`. That returned the product to the pre-I13 Learn-disabled condition. I13 must not close with Learn available only during a temporary proof window.

---

## Intended post-I13 behavior

| # | Requirement | Implementation |
|---|-------------|----------------|
| 1 | Learn controls stay visible and usable for owner-selected face and transcript evidence | Explore Learn UI unchanged; authorization uses `check_interactive_learn`, not `state == started` alone |
| 2 | Learn affects only selected evidence, Person, and source | `require_interactive_source` validates one manifest source + admitted Person; follow-on is inline scan/recognize on **that source only** |
| 3 | Interactive Learn cannot initiate an archive sweep | Bounded interactive Learn never calls `enqueue_full_eligible_archive` or multi-source `enqueue_videos`; archive pass remains a separate, locked entry point |
| 4 | Archive register / unlock / start and archive drains stay separately locked | Unchanged: `require_admission` + `state == started` for drains, archive-pass, queue reservation |
| 5 | Stopping bounded proof admission must not silently disable Learn | After proof: `stop` → `enable-interactive-learn` → **keep** `MEMORYBOX_I13_ADMISSION_ID` in serve env |

---

## Authorization model (two lanes)

**Processing lane** (`Admission.check`): requires `state == started`. Used for drains, queue reservation, archive pass, bulk enqueue.

**Interactive Learn lane** (`Admission.check_interactive_learn`): allowed when:

- `purpose == acceptance_learning`
- `scope_kind == bounded` (not archive)
- **either** proof window: `state == started` with `start_ref`
- **or** post-I13 steady state: `state == stopped` and `interactive_learn_enabled == true`

Routes using interactive lane:

- `POST /recognition/learn`
- `POST /speech/learn`
- `POST /speech/moments/correct`

All other `/recognition/*` and `/speech/*` mutations remain on the processing lane.

---

## Lifecycle after bounded proof

```powershell
# 1. Proof window (unchanged)
& $python -B -m memorybox.processing register ...
& $python -B -m memorybox.processing start --id $admission --reference <START_REF>
$env:MEMORYBOX_I13_ADMISSION_ID = $admission
# restart serve; run face/voice Learn + Admin proof

# 2. End bulk processing — drains stay 0
& $python -B -m memorybox.processing stop --id $admission --reference <STOP_REF>

# 3. Persist interactive Learn (NEW — do not skip)
& $python -B -m memorybox.processing enable-interactive-learn `
  --id $admission `
  --reference Tom-post-i13-interactive-learn-enabled-2026-09-08

# 4. KEEP admission in serve env (do NOT Remove-Item MEMORYBOX_I13_ADMISSION_ID)
# restart serve

# 5. Verify
& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
```

Admin `/admin/api/i13/status` reports `interactive_learn_enabled: true` when the flag is set on a stopped bounded admission.

---

## What remains locked after I13

- Archive Outcomes C / D / E
- `register` / `unlock` / `start` on archive scope
- `MEMORYBOX_RECOGNITION_DRAIN=1` or speech drain for archive-wide work
- Fan-out Learn enqueue across the 22-source manifest
- Retrying stopped voice pilots or Gate 3 admission

---

## Failure mode

If interactive Learn still returns `403 interactive_learn_locked` after the steps above, treat as **I13 architecture failure** — do not deploy or sign acceptance until the separation is corrected.
