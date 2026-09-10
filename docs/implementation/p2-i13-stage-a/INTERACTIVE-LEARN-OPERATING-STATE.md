# Interactive Learn — post-I13 operating state

**Status:** Required for I13 closeout (2026-09-08)  
**Migration:** `033_p2_i13_interactive_learn.sql`  
**Admission:** bounded `acceptance_learning` on the **accepted 22-video manifest** only

---

## Corpus boundary (not archive-wide Learn)

Persistent interactive Learn authorizes owner-selected face and voice Learn **only** for:

- **People** listed in the bounded plan `person_ids`, and  
- **Sources** listed in the plan manifest (the founder-reviewed **22-video** corpus).

It is **not** archive-wide Learn. Sources outside that manifest remain locked until a **separately deferred** archive decision (Outcomes C/D/E) is approved. I13 does not implement or authorize that expansion.

---

## Problem

The bounded proof runbook started an `acceptance_learning` admission, proved Explore Learn, then **stopped** the admission and **removed** `MEMORYBOX_I13_ADMISSION_ID`. That returned the product to the pre-I13 Learn-disabled condition. I13 must not close with Learn available only during a temporary proof window.

---

## Intended post-I13 behavior

| # | Requirement | Implementation |
|---|-------------|----------------|
| 1 | Learn controls stay visible and usable for owner-selected face and transcript evidence **within the 22-video manifest** | Explore Learn UI unchanged; authorization uses `check_interactive_learn` on bounded `acceptance_learning` |
| 2 | Learn affects only selected evidence, Person, and source | `require_interactive_source` validates one manifest source + admitted Person |
| 3 | Interactive Learn cannot initiate an archive sweep | No multi-source enqueue; no `enqueue_full_eligible_archive` from Learn |
| 4 | Archive register / unlock / start and archive drains stay separately locked | Unchanged processing lane (`state == started`) |
| 5 | Stopping bounded proof admission must not silently disable Learn | After proof: `stop` → `enable-interactive-learn` → **keep** `MEMORYBOX_I13_ADMISSION_ID` |

---

## Learn HTTP action vs follow-on work

The Learn request must return promptly after saving the owner-selected evidence. It must **not** run long recognition work synchronously in the HTTP handler.

| Step | When | Visible in Admin → Jobs |
|------|------|---------------------------|
| Save face/voice exemplar (+ span turn assignment for voice) | **Synchronous** in `POST /recognition/learn` or `POST /speech/learn` | Learned Evidence (exemplar row) |
| Rescan / recognize on **that source only** | **Asynchronous** — `owner_learn` queue row on current video | Jobs (`enqueue_reason=owner_learn`, same admission) |

Implementation: `enqueue_interactive_owner_learn` + `reserve_interactive_queue_item` (interactive lane). Follow-on is processed by the **dedicated Interactive Learn worker** (`memorybox/processing/interactive_drain.py`), which starts automatically when interactive Learn is authorized. It claims **only** `enqueue_reason=owner_learn` rows for the active admission. **`MEMORYBOX_RECOGNITION_DRAIN` and `MEMORYBOX_SPEECH_DRAIN` remain `0`.** Set `MEMORYBOX_INTERACTIVE_LEARN_WORKER=0` only to disable the dedicated worker during diagnosis.

This is **not** “inline” synchronous recognition — follow-on is **queued**, strictly scoped to the selected source.

---

## Authorization model (two lanes)

**Processing lane** (`Admission.check`): requires `state == started`. Used for drains, bulk queue claim, archive pass, archive enqueue.

**Interactive Learn lane** (`Admission.check_interactive_learn` + `reserve_interactive_queue_item`): allowed when:

- `purpose == acceptance_learning`
- `scope_kind == bounded` (the 22-video manifest — **not** archive)
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
# 1. Proof window
& $python -B -m memorybox.processing register ...
& $python -B -m memorybox.processing start --id $admission --reference <START_REF>
$env:MEMORYBOX_I13_ADMISSION_ID = $admission
# restart serve; run face/voice Learn + Admin proof

# 2. End bulk processing — drains stay 0
& $python -B -m memorybox.processing stop --id $admission --reference <STOP_REF>

# 3. Persist interactive Learn (required)
& $python -B -m memorybox.processing enable-interactive-learn `
  --id $admission `
  --reference Tom-post-i13-interactive-learn-enabled-2026-09-08

# 4. KEEP admission in serve env (do NOT Remove-Item MEMORYBOX_I13_ADMISSION_ID)
# restart serve

# 5. Verify
& $python -B docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py
```

Admin `/admin/api/i13/status` reports `interactive_learn_enabled: true` when the flag is set on the stopped bounded admission.

---

## Future archive admission (documented only — not authorized now)

When a founder later approves archive Outcomes C/D/E and registers a **separate** `scope_kind=archive` admission:

| Topic | Behavior |
|-------|----------|
| Bounded interactive Learn | **Unchanged** while `interactive_learn_enabled` remains on the stopped bounded admission and `MEMORYBOX_I13_ADMISSION_ID` still points to it. Learn stays limited to the **22-video manifest**. |
| Archive processing | Requires its **own** admission UUID, explicit unlock + start, and processing lane. Not enabled by I13 closeout. |
| Expansion beyond 22 videos | Requires archive decision + new reviewed plan. Interactive Learn on the bounded admission does **not** silently extend to new sources. |
| Superseding bounded Learn | A future operator decision may stop the bounded admission, register a new plan, and re-run `enable-interactive-learn` on a wider corpus — that is a **new reviewed admission**, not automatic. |
| Concurrent admissions | Serve env holds one `MEMORYBOX_I13_ADMISSION_ID`; archive work uses a different admission when authorized. |

I13 implementation does **not** add archive register/unlock/start, archive drains, or corpus expansion.

---

## What remains locked after I13

- Archive Outcomes C / D / E
- Learn on sources **outside** the 22-video manifest
- `register` / `unlock` / `start` on archive scope
- `MEMORYBOX_RECOGNITION_DRAIN=1` or speech drain for archive-wide work (unless separately authorized for bounded queue drain proof)
- Fan-out Learn enqueue across other manifest sources
- Retrying stopped voice pilots or Gate 3 admission

---

## Failure mode

If interactive Learn returns `403 interactive_learn_locked` after the lifecycle above, or Learn HTTP handlers perform synchronous full-video scan/recognize, treat as **I13 architecture failure** — do not deploy or sign acceptance until corrected.
