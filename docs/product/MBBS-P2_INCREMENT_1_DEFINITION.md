# MBBS-P2 Increment 1 — Show me Peggy (Person-in-Media Vertical)

**Status:** **ACCEPTED** (FlightSim owner gate 2026-08-13: `prove-p2-i1 --flightsim` → `ok: true` · Peggy George · real Immich + HVRT) · Definition **LOCKED**  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)  
**Authority:** Locked MBPS-002 · MBEVS-001 v1.0 · founder I1 clarifications below  
**CLI prove:** `python -m memorybox prove-p2-i1` (harness / fake corpus) · `prove-p2-i1 --flightsim` on P1 runtime with **real Immich + real HVRT** (fakes/degraded fail)  
**FlightSim env (ACCEPTED):** `MEMORYBOX_P1_RUNTIME_HOST=1` · Immich via `MEMORYBOX_PHOTO_PROVIDER=immich` · HVRT via `MEMORYBOX_VIDEO_PROVIDER=hvrt` + `MEMORYBOX_VIDEO_WORKER_URL` · corpus ids `MEMORYBOX_P2_I1_POSITIVE_VIDEO_ID` / `MEMORYBOX_P2_I1_NEGATIVE_VIDEO_ID` · optional `MEMORYBOX_P2_I1_PERSON_NAME` (default Peggy) / `MEMORYBOX_P2_I1_PERSON_ID` / `MEMORYBOX_P2_I1_HVRT_FACE_ID`  
**APIs:** `POST /people/sync/immich` · `GET /recognition/queue` · `POST /recognition/queue/process` · `POST /recognition/appearances/correct`  
**Gate:** **PASSED** — full eligible-archive queue (515), Immich face evidence, real HVRT timeslots + jump `t=`, Ask photos+moments, owner correct→reuse, negative video no false hit.
## 0. Product intent

Deliver the first meaningful P2 proof:

> **Show me Peggy.**

End-to-end:

1. Peggy is a canonical MB Person because she is **named in Immich** — no redundant MB enrollment.  
2. Results include **relevant photos** and **exact video face-appearance moments** (not only source video files).  
3. Opening a video result **jumps to** Peggy’s appearance timeslot.  
4. Owner can **correct** a missed or incorrect face/person association.  
5. The correction becomes **reusable identity evidence** at owner-confirmed authority.  
6. Subsequent retrieval reflects the correction where appropriate.  
7. **Provenance** and **system-managed confidence/uncertainty** remain preserved (method, confidence, exemplars, confirmation state).  
8. Open / detail / correct / return preserves the original result context.  
9. A newly known Person triggers **full eligible-archive** evaluation via a **durable recognition queue** with **owner-observable** processing state (not a flag-only bit).

**Moment = face-appearance timeslot only** (speech/STT passages are P2-I9).

---

## 1. Locked clarifications (2026-08-12)

### 1.A Eligible video

**Eligible video** means every source video that is:

- accessible to MemoryBox through a **configured and healthy** video source, and  
- **technically processable** by the supported recognition pipeline.

Videos excluded because of corruption, unsupported codec, permissions, unavailable source, or other processing failure **must remain visible as excluded/failed with reason** — not silently omitted from the queue/work set.

### 1.B Recognition authority

- Automated face recognition may associate an appearance with a Person at **system confidence**.  
- **Owner-confirmed / corrected** identity remains **higher-authority** evidence than automated association.  
- Recognition results preserve **method**, **confidence**, **source exemplars**, and **confirmation state**.

### 1.C Reprocessing scope

- Material identity-evidence changes cause the recognition system to determine the appropriate reprocessing scope.  
- A **newly known Person** requires **full eligible-archive evaluation** (every eligible video enters the durable queue).  
- Later exemplar additions/corrections may use **targeted or incremental** reprocessing **where the system can prove equivalent coverage**.  
- “Eligible for reprocessing” **≠** setting a flag alone — work items must exist in a durable queue with observable state.

### 1.D Acceptance corpus (minimum)

The acceptance test must include at least:

| Case | Requirement |
|------|-------------|
| Positive | One source video where **Peggy clearly appears** |
| Negative | One video where **Peggy does not appear** |
| Ambiguous | Ideally one **difficult/ambiguous** appearance |
| Correction | A **correction** case (miss or wrong association → owner correct → reuse) |
| Queue scale | **Enough source videos** to demonstrate the persistent **full-library** queue (not a one-video toy path) |

---

## 2. IN scope

### 2.1 Provider identity sync (MBPS P2-ID-01..03)

- Canonical MB Person remains MB-owned; Immich People are mapped provider identities with provenance.  
- **Nightly** Immich→MB Person synchronization by default.  
- Owner **Sync / Poll now** for immediate provider refresh.  
- Newly named/changed Immich Person **automatically creates or maps** to canonical MB Person when unambiguous.  
- Ambiguous conflicts → Review (no silent destructive merge/split).  
- Immich UUID never becomes `people.id`.

### 2.2 Face evidence (MBPS P2-ID-04) — required in I1

- Confirmed **Immich face assets** are usable as **provenance-preserved** recognition evidence (source, bounding region as available, provider ids, confidence, confirmation, timestamps).  
- Owner confirmations/corrections in photo or video frames become reusable face evidence with provenance and **higher authority** than automated associations.  
- Automated associations remain labeled with method/confidence/confirmation state.

### 2.3 Video face-appearance timeslots (MBPS P2-VID-01..04)

- Source video remains immutable evidence.  
- Derived appearance observations are rebuildable layers.  
- Recognition identifies **where** a person appears (start/end, representative frame, confidence, method, correction/confirmation state, provenance, source exemplars).  
- Searchable **face-appearance moments** for Ask (and thin related surfaces as needed for the proof).  
- Opening a video result **seeks to** the relevant timeslot.  
- Owner can identify/correct a face in a video frame and associate to canonical MB Person.  
- Reuse proven HVRT timeslice/face concepts where suitable (**VID-05 earn-in**).  
- **Real timeslot recognition is required for acceptance.** Degraded-provider UX alone does **not** pass.

### 2.4 Durable recognition work queue

On **newly known Person** (map/create from Immich or equivalent first-known event):

- Enqueue **full eligible-archive evaluation** — every eligible source video gets durable work (or an explicit excluded/failed-with-reason record).  
- Prioritization and background scheduling are allowed.  
- Owner can observe processing state (queued / running / completed / failed / excluded-with-reason; aggregate progress OK if per-video detail is available on demand).

On **later material exemplar additions/corrections**:

- System chooses full vs targeted/incremental reprocess **only if equivalent coverage can be proven**; otherwise fall back to full eligible-archive evaluation.

### 2.5 Ask retrieval & thin context UX

- Person ask (“Show me Peggy” / equivalent) returns **photos + face-appearance moments**.  
- Negative videos (no appearance) must not be fabricated as hits; system confidence disclosed where associations are automated.  
- Progressive disclosure of uncertainty (system-managed thresholds — not owner dials).  
- Formalize thin Experience Flows only for:  
  - Ask → results → open moment → correct → return  
  - Recognize → Confirm/Correct → Reuse evidence  

### 2.6 Minimal status (only if technically necessary)

- Thin owner-visible sync/queue status may appear on People or a minimal status strip.  
- **Do not** pull full TASK-004 Immich Photos inventory into I1 unless required to expose sync/reprocessing status. Default: **TASK-004 stays P2-I3**.

---

## 3. OUT of scope / deferred

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
| Silently dropping unprocessable videos from the work set | Forbidden |

---

## 4. EVS coverage

### 4.1 Primary canonical EVSs (I1 homes)

EVS-009, EVS-011, EVS-024, EVS-029, EVS-030, EVS-037, EVS-040, EVS-042, EVS-043, EVS-055, EVS-058, EVS-100, EVS-103, EVS-228, EVS-246, EVS-250.

Aliases (e.g. EVS-191≡009) are **not** separate acceptance.

### 4.2 P1 regression earn-ins

- EVS-014 — teach face in video → same person in Ask (timeslot-capable).  
- EVS-028 / 032-class — video results prefer moments over file-only when timeslots exist.  
- Laughing/person video regression paths jump to appearance when indexed.

### 4.3 Composite founder proof

“Show me Peggy” + §1.D corpus + §6 gate are authoritative for I1 acceptance.

---

## 5. Capabilities & services affected

| Area | I1 expectation |
|------|----------------|
| Person & Identity | Sync, map/create, conflict review |
| Provider Immich adapter | People list/changes; **face assets** for evidence |
| Face evidence store | Provenance-preserved exemplars; confirmation authority |
| Recognition work queue | Durable jobs for all eligible videos; excluded/failed-with-reason visible |
| Video intelligence / HVRT | Real face-appearance timeslots |
| Ask / Query Planner | Person → photos + moments |
| Review / correct UX | Frame associate/correct; return to context |
| Thin status | Sync + queue observability |

No schema/patch prescriptions until **Build P2-I1**.

---

## 6. Dependencies & environments

| Dependency | Requirement |
|------------|-------------|
| P1 baseline | Ask, People, Immich provider config, evidence model |
| HVRT / timeslot path | **Must work for acceptance** |
| Immich | Named people + face assets readable with configured credentials |
| Video sources | Configured/healthy; enough videos for full-library queue demo + §1.D corpus |

If HVRT cannot produce real timeslots, **I1 fails**.

---

## 7. Acceptance gate

Pass **all** of the following on FlightSim / designated runtime with real-family material where practical:

1. **No redundant enrollment:** Immich-named Peggy (or designated person) becomes canonical MB Person after nightly sync or Sync now without prior MB-only create.  
2. **Sync controls:** Nightly sync configured; **Sync / Poll now** refreshes provider people.  
3. **Face evidence:** Immich face assets usable as provenance-preserved exemplars.  
4. **Authority:** Automated associations show system confidence/method; owner confirmation/correction outranks them and is stored with confirmation state.  
5. **Eligible definition honored:** Queue covers all eligible videos; unprocessable videos appear as **excluded/failed with reason** (not silent omit).  
6. **Full-archive enqueue on newly known Person:** Durable queue work (or explicit exclusion records) spans the eligible archive — not a flag-only path. Owner can observe state.  
7. **Corpus:** Includes clear appearance video, non-appearance video, ideally ambiguous appearance, a correction case, and enough videos to demonstrate persistent full-library queue behavior.  
8. **Ask results:** “Show me Peggy” returns photos + face-appearance moments when evidence exists; does not invent hits on the negative video.  
9. **Jump-to-moment:** Opening a positive video moment seeks to the appearance timeslot.  
10. **Correct → reuse:** Owner correction updates reusable evidence; subsequent Ask reflects it where appropriate.  
11. **Confidence:** System-managed; no owner threshold dial; no false certainty.  
12. **Context return:** Open/detail/correct → return restores prior result context.  
13. **HVRT real:** Real timeslot recognition output; degraded-only UX fails.

Known residuals (e.g. queue still draining) must be explicit and must not hide missing timeslot capability.

---

## 8. Explicit non-goals for implementers

- Do not implement speech moments “while we’re here.”  
- Do not redesign full shell, Archive Health, or Settings.  
- Do not treat aliases EVS-183..202 as extra tests.  
- Do not ship owner confidence sliders.  
- Do not silently omit failed/unprocessable videos from the work set.  
- Do not treat “eligible” as a boolean without durable queue items / exclusion records.  
- Do not accept I1 without real timeslot recognition.

---

## 9. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Large archive queue time | Prioritization + observable progress; acceptance proves full enqueue + §1.D corpus |
| Immich face API/key limits | Pre-build validation; flag blockers early |
| HVRT env gaps | Block acceptance |
| Incremental reprocess bugs | Only allow when equivalent coverage is provable; else full eligible-archive |
| Context-return scope creep | Keep thin; full shell is I2 |

---

## 10. Authorization stop-line (final planning baseline)

| Step | Status |
|------|--------|
| MBRM-001A planning direction | Approved |
| Founder I1 clarifications (§1) | Locked into this definition |
| **This I1 definition** | **LOCKED — final planning baseline** |
| Build / code / migrations / FlightSim implement | **AUTHORIZED** (founder “approved to build” 2026-08-12) |
| FlightSim owner gate (`prove-p2-i1 --flightsim`) | **ACCEPTED** (2026-08-13) |

P2-I1 is **ACCEPTED**. **P2-I2 Product Shell** is **ACCEPTED** (2026-08-13) — [MBBS-P2_INCREMENT_2_DEFINITION.md](MBBS-P2_INCREMENT_2_DEFINITION.md). **P2-I3 Archive Health** is **ACCEPTED** (2026-08-13) — [MBBS-P2_INCREMENT_3_DEFINITION.md](MBBS-P2_INCREMENT_3_DEFINITION.md). Next: [MBBS-P2_INCREMENT_4_DEFINITION.md](MBBS-P2_INCREMENT_4_DEFINITION.md) (draft).
