# I13 Learn navigation reconciliation

**Date:** 2026-09-09  
**Status:** Founder acceptance finding — documents intended routes; no removal of legacy surfaces  
**Authority:** [CONSOLIDATED-I13-FINAL-DEPLOYMENT-AND-FOUNDER-TEST.md](CONSOLIDATED-I13-FINAL-DEPLOYMENT-AND-FOUNDER-TEST.md), MBUX-001 v0.4 family nav

---

## Three distinct experiences

| # | Surface | URL | Role | I13 owner workflow? |
|---|---------|-----|------|---------------------|
| **1** | **Explore → video → Learn tab** | `/explore/ui` (modal Learn rail) | Box a face and/or select transcript span → choose Person → **Learn**. Saves exemplar promptly; follow-on work is **queued** (not sync full-video scan). | **Yes — primary I13 Learn** |
| **2** | **Admin → Learned Evidence** | `/admin/learned-evidence/ui` | Review face/voice exemplars, appearances, spoken moments; **withdraw** test exemplars. Does not create new Learn actions. | **Yes — I13 evidence management** |
| **3** | **Global Review & Learn** | `/review/ui` | **Legacy Increment 7** thin review: scrub video, face candidate, box, Teach via I6; plus read-only **voice-pilot results** and **face/voice corroboration** panels added during I13 pilots. | **No — not the I13 Learn screen** |

Additional I13 admin (not Learn creation):

| Surface | URL | Role |
|---------|-----|------|
| Admin landing | `/admin/ui` | Hub linking Jobs, Learned Evidence, Explore Learn |
| Admin → Jobs | `/admin/jobs/ui` | Scoped queue items for active `MEMORYBOX_I13_ADMISSION_ID`; status **queued** until a drain runs |

---

## Why Review & Learn still appears in top nav

MBUX-001 v0.4 locks the family label **“Review & Learn”** → `/review/ui`. That predates I13 interactive Learn. The legacy page remains required for:

- I7 face-candidate → box → Teach path (still used by some deep links and Library/People “Open Review”)
- Read-only **bounded voice-pilot results** (operator/founder evidence review)
- Read-only **face/voice corroboration** reports

These are **not** substitutes for Explore Learn or Admin Learned Evidence.

---

## Smallest correction (recommended, no removal)

1. **Review page banner** (`review.html`): State explicitly “Legacy I7 Review — not I13 Explore Learn” and link to **Explore Learn** (`/explore/ui`) and **Admin → Learned Evidence** (`/admin/learned-evidence/ui`).
2. **Admin landing** (`admin.html`): Already points owners to Explore for Learn; keep as the I13 entry hub.
3. **Top nav label**: **Do not rename** in this increment (MBUX lock). Optional follow-up: “Review (legacy)” sublabel in page chrome only, not family nav, after UX sign-off.
4. **Do not** remove voice-pilot or corroboration panels from Review until pilots are archived under a separate decision.

---

## Owner route card (copy for runbook / founder session)

```
Create learned evidence  →  Explore → open video → Learn tab → box face / select words → Person → Learn
Review / withdraw evidence  →  Admin → Learned Evidence
Track scoped jobs  →  Admin → Jobs  (status stays "queued" until recognition/speech drain enabled)
Legacy review / pilot readouts  →  Review & Learn (top nav)  — not I13 Learn
```

---

## Jobs vs “running”

With `MEMORYBOX_RECOGNITION_DRAIN=0` and `MEMORYBOX_SPEECH_DRAIN=0` (founder session default):

- Learn **saves the exemplar immediately** (Admin → Learned Evidence should list it).
- Follow-on queue rows appear in Admin → Jobs with status **`queued`**, not **`running`**, until the operator enables the matching drain on the **worker** process.
- Enabling a drain processes **one scoped job at a time** — not archive-wide intake.

---

## Phase 4 mapping (founder checklist)

| Runbook item | Correct surface |
|--------------|-----------------|
| Face Learn on 1532 | Explore → Learn |
| Voice Learn on 1530 | Explore → Learn |
| Admin Jobs | `/admin/jobs/ui` |
| Admin Learned Evidence | `/admin/learned-evidence/ui` |
| Withdraw exemplar | Admin → Learned Evidence |
| FR-005 playback | Explore appearance |
| Gallery fragments | Explore Gallery |

**Not** in Phase 4: top-nav Review & Learn voice-pilot panels (legacy read-only).
