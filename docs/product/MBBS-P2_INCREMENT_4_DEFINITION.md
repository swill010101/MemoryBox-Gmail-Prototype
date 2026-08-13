# MBBS-P2 Increment 4 — Timeline-first High-Volume Explore

**Status:** **DRAFT for founder review / approval** · **No build** until this definition is approved  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority:** Locked MBPS-002 · Locked MBEVS-001 v1.0 · MBRM-001A sequencing · **P2-I1..I3 ACCEPTED**  
**Depends on:** **P2-I1 ACCEPTED** (moments) · **P2-I2 ACCEPTED** (shell + context return) · **P2-I3 ACCEPTED** (honest coverage; undated gaps)  
**UX canvas dependency:** Final I4 **UX acceptance is held** until the new **mixed-media curator / Library / timeline canvas** is incorporated (see §1)  
**CLI prove (proposed):** `python -m memorybox prove-p2-i4` (functionality) · later UX gate after canvas incorporation  
**Gate:** Definition approval → build authorization → functionality prove → **UX ACCEPTED only after canvas incorporation + founder UX pass**

---

## 0. Product intent

I1 made people searchable in photos and video moments. I2 made MemoryBox one product. I3 made archive coverage honest.

I4 makes **large mixed-media exploration practical**:

> **The owner can move through a large photo/video archive as a living timeline gallery — zoom and band by time, see where known media sit, open items without losing context — without confidence scores or provider folders becoming the primary interface.**

I4 has **two tracks** that must not be conflated:

| Track | Purpose | When “done enough” |
|-------|---------|---------------------|
| **A — Functionality** | Timeline/query/filter/open/return behaviors at Immich scale | Functionality prove / FlightSim capability gate |
| **B — Final UX** | Curator-feel mixed-media canvas (Library + timeline as one composition) | **Held** until new canvas is incorporated + founder UX acceptance |

**Do not mark I4 ACCEPTED on functionality alone.** Final acceptance requires Track B.

---

## 1. Locked directional decision (founder 2026-08-13)

> Continue I4 **functionality**; **hold final UX acceptance** until the new **mixed-media curator / Library / timeline canvas** is incorporated.

Implications:

1. I4 may implement and prove **explore capabilities** (time index, band/zoom semantics, undated grouping, mixed result stream, open-at-moment, context return, scale) against current Library/shell as a **capability substrate**.  
2. **Final UX ACCEPTED** waits for incorporation of the new canvas — the curator-facing composition that unifies Library + timeline + mixed-media gallery (MBUX quiet-curator; mockups/experience boards as feeling reference, not pixel-match).  
3. Shipping a thin “admin timeline scrubber” on old Library chrome may satisfy **Track A** temporarily; it **cannot** alone satisfy **Track B / ACCEPTED**.  
4. Canvas work may arrive from parallel UX / mockup / PRD streams; I4 definition treats **incorporation** as a hard acceptance prerequisite, not optional polish.

---

## 2. End-to-end outcomes

### 2.A Functionality outcomes (Track A)

1. **Timeline-first** navigation for large result sets (P2-UX-02).  
2. **Adaptive zoom / clustering / banding** — year → month → day → dense bands as needed.  
3. Time model: known dates on a spine; **unknown dates grouped** (never fake-dated, never silently dropped).  
4. **Click + band-select** (and accessible alternate) change the active period; the result set follows.  
5. **Mixed stream**: photos + searchable video moments (source video files secondary / drill-through).  
6. Open photo → detail/preview; open video moment → Review/jump `t=` (I1).  
7. **Return** restores period / band / filters / scroll (I2).  
8. Structured filters + Ask handoff/refine (P2-UX-03 slice) without replacing timeline.  
9. Windowed/virtualized loading at Immich scale (tens of thousands).  
10. No confidence-first or provider-folder-first default.

### 2.B Final UX outcomes (Track B — held for canvas)

1. Explore reads as one **curator canvas**: Library + timeline + gallery as one composition (not a bolted scrubber on admin Library).  
2. Gallery-first; evidence codes / provider internals progressive-disclosure only.  
3. MBUX quiet-curator language; mockups / experience boards validate *feel*, not pixel slavery.  
4. Living-room / shared viewing posture remains viable (no cast required).  
5. Founder UX pass after canvas incorporation.

---

## 3. Clarifications still to approve (founder)

| # | Question | Proposed default |
|---|----------|------------------|
| Q1 | Where does the canvas land? | **Library becomes the canvas host**; Ask deep-links “Open in Library / Timeline.” No third parallel explore app. |
| Q2 | Mixed media in one stream? | **Yes** — photos + searchable video moments. |
| Q3 | Undated media? | Explicit **Undated** group on/ beside the timeline spine. |
| Q4 | Band / zoom? | Graphical axis: click focus + drag band; keyboard/accessible alternate required. |
| Q5 | Scale for functionality prove? | FlightSim Immich corpus (**tens of thousands**) navigable (windowed). |
| Q6 | Filters in I4? | Person, modality, dated/undated, place when known + Ask refine. Visual-attribute search thin/best-effort. |
| Q7 | Ask rewrite? | **Out** except deep-link / handoff into canvas. Ask polish = separate UX-principles work. |
| Q8 | Saved views? | **Out** → **I13** (unless founder later pulls thin save). |
| Q9 | Canvas source of truth? | Incorporate the **new mixed-media curator/Library/timeline canvas** (from UX/mockup stream) before Track B / ACCEPTED. Exact artifact path/PR locked at incorporation time. |
| Q10 | May Track A ship behind a flag before canvas? | **Yes for internal FlightSim prove**; **no ACCEPTED** and no claim of final explore UX until Track B. |

---

## 4. IN scope

### 4.1 Track A — Functionality

| Capability | Expectation |
|------------|-------------|
| Time index | Query/filter media by dated period + undated group |
| Zoom levels | ≥2 coarse↔fine levels |
| Band select | Range → result set updates |
| Mixed stream API/UI substrate | Photos + moments with stable ids and open targets |
| Open moment | Jump `t=` preserved |
| Context return | Period/band/filters/scroll restore |
| Scale | Windowed fetch; no full-corpus thumb dump |
| Filters | Person / modality / dated|undated (+ place when known) |
| Ask handoff | Apply filters / open canvas with context |

### 4.2 Track B — Canvas incorporation (required for ACCEPTED)

| Capability | Expectation |
|------------|-------------|
| Curator canvas | Unified Library + timeline + mixed gallery composition |
| Gallery-first | No admin evidence-primary layout |
| MBUX feel | Quiet-curator; mockups as validation reference |
| Shell fit | Remains I2 family exploration surface |
| Founder UX pass | Explicit acceptance after incorporation |

### 4.3 Preserve prior increments

I1 moments · I2 shell/context · I3 honesty (undated ≠ fake; unavailable ≠ 0 elsewhere).

---

## 5. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Final UX ACCEPTED without canvas | **Forbidden** (§1) |
| Ask/Home invitation polish, journeys, viewer identity | UX-principles follow-on |
| Archive Health changes | **I3** (done) |
| Mature Settings | **I14** |
| Kinship | **I6** |
| SMS / richer email | **I7–I8** |
| Spoken STT moments | **I9** |
| Full Dynamic Views | **I13** |
| Confidence- / provider-folder-first UX | Forbidden as default |
| Cast / HA / multi-user | Deferred / late |

---

## 6. MBPS / EVS traceability

| Source | I4 role |
|--------|---------|
| **P2-UX-02** Timeline-first high-volume explore | Primary (A+B) |
| **P2-UX-03** Natural + structured refinement | Track A slice |
| **P2-UX-04** Progressive disclosure | Required (esp. Track B) |
| **P2-VID-03** Searchable moments | Open-at-moment |
| **EVS-002** Mixed-media timeline explore | Primary |
| **EVS-081..229** (photo/place/time set per MBRM-001A) | Supporting |
| **EVS-249** Save query | Out → I13 (Q8) |
| **EVS-237** Funniest video | Out of I4 gate |

---

## 7. Prerequisites

- P1 FlightSim baseline.  
- **P2-I1..I3 ACCEPTED**.  
- Immich-scale photos + HVRT moments for mixed stream.  
- I2 context return on Library ↔ Review ↔ Ask.  
- **For ACCEPTED:** new mixed-media curator/Library/timeline **canvas incorporated**.

---

## 8. Acceptance — split gates

### 8.A Functionality gate (Track A — not ACCEPTED)

Pass on FlightSim when authorized:

1. Time-bounded query + undated group work.  
2. ≥2 zoom levels; band-select changes result set.  
3. Mixed stream includes photos + video moments.  
4. Moment open uses jump `t=`.  
5. Return restores explore state.  
6. Immich-scale navigation remains usable (windowed).  
7. Person (or equivalent) filter + Ask handoff work.  
8. I1–I3 proves still green.  
9. `prove-p2-i4` functionality suite passes.

**Label:** Functionality **PROVED** / ready for canvas — **not** product ACCEPTED.

### 8.B Final UX / ACCEPTED gate (Track B — held)

Only after canvas incorporation:

1. Explore is the **curator canvas** (Library + timeline + gallery one composition).  
2. Gallery-first; no admin evidence-primary UI.  
3. Graphical timeline with dated density + undated group is first-class in the canvas.  
4. Click/band (and accessible alternate) feel native to the canvas.  
5. MBUX quiet-curator feel validated (mockups/boards as reference).  
6. Open → return still coherent inside canvas.  
7. No Ask rewrite / Settings / kinship / STT scope leak.  
8. Founder explicit UX acceptance.  
9. Full `prove-p2-i4 --flightsim` (incl. UX markers) green.  

**Only then:** mark I4 **ACCEPTED**.

---

## 9. Risks & watch items

| Risk | Mitigation |
|------|------------|
| ACCEPTED claimed on Track A alone | §1 + split gates; stop-line forbids it |
| Canvas never arrives / slips | Hold ACCEPTED; functionality may stay PROVED only |
| Thin scrubber on old Library becomes “good enough” | Track B explicitly requires curator canvas |
| Load-all thumbs | Windowed fetch; scale case in 8.A |
| Fake dates | Undated group only |
| Ask rewrite sneaks in | Q7 OUT |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A sequencing (I3→I4 Timeline) | Approved direction |
| P2-I1..I3 | **ACCEPTED** |
| Direction: functionality continue; UX ACCEPTED hold for canvas | **STATED** (2026-08-13) |
| Founder approval of **this reworked definition** (incl. Q1–Q10) | **AWAITING** |
| **This I4 definition** | **DRAFT — review; wait for approval** |
| Build / code | **NOT AUTHORIZED** until definition approved + “Build P2-I4” |
| Track A functionality prove | After build auth |
| Track B / product **ACCEPTED** | **HELD** until canvas incorporated + founder UX pass |

**No I4 code until this definition is approved and build is explicitly authorized.**  
**No I4 ACCEPTED until the mixed-media curator/Library/timeline canvas is incorporated.**
