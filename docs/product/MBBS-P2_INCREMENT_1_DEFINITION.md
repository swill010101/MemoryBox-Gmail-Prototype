# MBBS-P2 Increment 1 — Show me Peggy (Person-in-Media Vertical)

**Status:** Draft for founder review · **Date:** 2026-08-12  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (planning direction approved)  
**Authority:** Locked MBPS-002 · MBEVS-001 v1.0  
**Gate:** **No build / no code** until this definition is founder-approved and build is explicitly authorized.

## 0. Product intent

Deliver the first meaningful P2 proof:

> **Show me Peggy.**

End-to-end, where dependencies permit:

1. Peggy is a canonical MB Person because she is **named in Immich** — no redundant MB enrollment.  
2. Results include **relevant photos** and **exact video face-appearance moments** (not only source video files).  
3. Opening a video result **jumps to** Peggy’s appearance timeslot.  
4. Owner can **correct** a missed or incorrect face/person association.  
5. The correction becomes **reusable identity evidence**.  
6. Subsequent retrieval reflects the correction where appropriate.  
7. **Provenance** and **system-managed confidence/uncertainty** remain preserved.  
8. Open / detail / correct / return preserves the original result context.  
9. Newly known Persons are **enqueued** for face recognition across the **entire eligible existing video archive**, with **owner-observable** processing state (not a flag-only “eligible” bit).

**Moment = face-appearance timeslot only** (speech/STT passages are P2-I9).

---

## 1. IN scope

### 1.1 Provider identity sync (MBPS P2-ID-01..03)

- Canonical MB Person remains MB-owned; Immich People are mapped provider identities with provenance.  
- **Nightly** Immich→MB Person synchronization by default.  
- Owner **Sync / Poll now** action for immediate provider refresh.  
- Newly named/changed Immich Person **automatically creates or maps** to canonical MB Person when unambiguous.  
- Ambiguous conflicts → Review (no silent destructive merge/split).  
- Immich UUID never becomes `people.id`.

### 1.2 Face evidence (MBPS P2-ID-04) — required in I1

- Confirmed **Immich face assets** are usable as **provenance-preserved** recognition evidence (source, bounding region as available, provider ids, confidence, confirmation, timestamps).  
- Owner confirmations/corrections in photo or video frames also become reusable face evidence with provenance.  
- No flattening of provider vs owner-confirmed authority.

### 1.3 Video face-appearance timeslots (MBPS P2-VID-01..04)

- Source video remains immutable evidence.  
- Derived appearance observations are rebuildable layers.  
- Recognition identifies **where** a person appears (start/end, representative frame, confidence, method, correction state, provenance).  
- Searchable **face-appearance moments** for Ask/Library-thin results.  
- Opening a video result **seeks to** the relevant timeslot.  
- Owner can identify/correct a face in a video frame and associate to canonical MB Person.  
- Reuse proven HVRT timeslice/face concepts where suitable (**VID-05 earn-in**).  
- **Real timeslot recognition is required for acceptance.** Degraded-provider UX alone does **not** pass.

### 1.4 Durable recognition work queue (founder decision #4)

When a Person becomes newly known/mapped (or face evidence materially changes):

- Place work covering **all applicable existing source videos** into a **durable, persistent** recognition queue.  
- Prioritization and background scheduling are allowed.  
- “Eligible for reprocessing” **must not** mean merely setting a flag.  
- Owner can observe processing state (at least: queued / running / completed / failed / deferred-with-reason; aggregate progress acceptable if per-video detail is available on demand).

### 1.5 Ask retrieval & thin context UX

- Person ask (“Show me Peggy” / equivalent) returns **photos + face-appearance moments**.  
- Progressive disclosure of uncertainty (system-managed thresholds — not owner dials).  
- Formalize thin Experience Flows only for:  
  - Ask → results → open moment → correct → return  
  - Recognize → Confirm/Correct → Reuse evidence  

### 1.6 Minimal status (only if technically necessary)

- Thin owner-visible sync/queue status may appear on People or a minimal status strip.  
- **Do not** pull full TASK-004 Immich Photos inventory into I1 unless required to expose sync/reprocessing status. Default: **TASK-004 stays P2-I3**.

---

## 2. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Speech/STT spoken moments | P2-I9 |
| Full product shell / IA redesign | P2-I2 |
| Archive Health redesign + TASK-004 inventory | P2-I3 |
| Timeline-first high-volume chrome | P2-I4 |
| Universal Person pickers on all surfaces | P2-I5 (Ask path in I1 only) |
| Kinship inference | P2-I6 |
| SMS / richer email | P2-I7 / I8 |
| Cross-source narrative / external history | P2-I11 / I12 |
| Dynamic views, Settings maturity, campaigns, trust-private formalization, import-back | I13–I17 |
| Multi-user / tone dial | Late |
| Synthetic media | P3 |
| Owner-adjustable confidence threshold dials | Out for P2 unless decision reopened |
| Inventing Immich library totals as zeros | Forbidden |

---

## 3. EVS coverage

### 3.1 Primary canonical EVSs (acceptance homes on I1)

From MBRM-001A Appendix A.1 (I1 primary):

EVS-009, EVS-011, EVS-024, EVS-029, EVS-030, EVS-037, EVS-040, EVS-042, EVS-043, EVS-055, EVS-058, EVS-100, EVS-103, EVS-228, EVS-246, EVS-250.

Aliases (e.g. EVS-191≡009, EVS-193≡011) are **not** separate acceptance.

### 3.2 P1 regression earn-ins (must become moment-complete under I1)

Without re-phasing:

- EVS-014 / alias 196 — teach face in video → same person in Ask (must land on timeslot-capable retrieval).  
- EVS-028 / 032-class person photo/video retrieval — video results must prefer moments over file-only when timeslots exist.  
- EVS-001/007-class smiling/laughing person retrieval remains regression; laughing **video** paths should jump to appearance when indexed.

### 3.3 Composite founder proof (not a numbered EVS)

“Show me Peggy” composite acceptance in §6 is authoritative for I1 gate even when split across multiple EVSs.

---

## 4. Capabilities & services affected

| Area | I1 expectation |
|------|----------------|
| Person & Identity | Sync, map/create, conflict review |
| Provider Immich adapter | People list/changes; **face assets** for evidence |
| Face evidence store | Provenance-preserved exemplars |
| Recognition work queue | Durable jobs for all eligible source videos; observable state |
| Video intelligence / HVRT | Real face-appearance timeslots |
| Ask / Query Planner | Person → photos + moments |
| Review / correct UX | Frame associate/correct; return to context |
| Thin status | Sync + queue observability |

No schema/patch prescriptions in this definition — those come only after build authorization.

---

## 5. Dependencies & environments

| Dependency | Requirement |
|------------|-------------|
| P1 baseline | Ask, People, Immich provider config, evidence model |
| HVRT / timeslot path | **Must work for acceptance** on FlightSim (or designated P1 runtime) |
| Immich | Named people + face assets readable with configured credentials |
| Media-server / libraries | Existing videos reachable for enqueue/process |

If HVRT cannot produce real timeslots, **I1 fails** — do not accept degraded-only UX.

---

## 6. Acceptance gate (FlightSim / real-family where practical)

Pass **all** of the following:

1. **No redundant enrollment:** A person named only in Immich (e.g. Peggy) exists as canonical MB Person after nightly sync or Sync now, without prior `/people` manual create.  
2. **Sync controls:** Nightly sync is configured/documented; **Sync / Poll now** refreshes provider people.  
3. **Face evidence:** Immich face assets for that Person are stored/usable as provenance-preserved face evidence.  
4. **Queue is real:** After the Person is known, **all eligible existing source videos** are represented in a **durable recognition queue** (not a boolean flag). Owner can observe processing state.  
5. **Ask results:** “Show me Peggy” (or equivalent) returns **photos** and **face-appearance video moments** when such evidence exists.  
6. **Jump-to-moment:** Opening a video moment seeks to the appearance timeslot (start appropriately).  
7. **Correct → reuse:** Owner corrects a miss/wrong association; evidence is retained with provenance; a subsequent Ask reflects the correction where appropriate.  
8. **Confidence:** Uncertainty/confidence behavior is system-managed; no owner threshold dial; no false certainty.  
9. **Context return:** After open/detail/correct, owner returns to the prior result context.  
10. **HVRT real:** Acceptance uses real timeslot recognition output — degraded-provider messaging alone is insufficient.

Known residuals must be explicit (e.g. queue still draining) and must not hide missing timeslot capability.

---

## 7. Explicit non-goals for implementers

- Do not implement speech moments “while we’re here.”  
- Do not redesign full shell, Archive Health, or Settings.  
- Do not treat aliases EVS-183..202 as extra tests.  
- Do not ship owner confidence sliders.  
- Do not mark reprocess “done” without durable queue work items for eligible videos.  
- Do not accept I1 on FlightSim without real timeslot recognition.

---

## 8. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Large video archive → long queue | Prioritization + observable progress; acceptance may use a representative corpus **plus** proof that full-archive enqueue occurred |
| Immich face asset API/key limits | Pre-build validation against FlightSim Immich; flag blockers early |
| HVRT env gaps | Block acceptance; do not redefine pass criteria |
| Context-return UX scope creep | Keep thin; full shell is I2 |
| Catalog duplicates confusing QA | Use canonical lower EVS ids only |

---

## 9. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A planning direction | Approved (with founder decisions) |
| This I1 definition | **Awaiting founder approval** |
| Build / code / migrations / FlightSim implement | **Blocked** until explicit “Build P2-I1” authorization |

After approval: implementers receive a separate build authorization. Until then — **planning docs only**.
