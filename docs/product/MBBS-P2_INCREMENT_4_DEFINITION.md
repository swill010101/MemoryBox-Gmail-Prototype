# MBBS-P2 Increment 4 — Timeline-first High-Volume Explore

**Status:** **DRAFT for founder review** · **No build** until clarifications locked and explicit “Build P2-I4” authorization  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority:** Locked MBPS-002 · Locked MBEVS-001 v1.0 · MBRM-001A sequencing · **P2-I1..I3 ACCEPTED**  
**Depends on:** **P2-I1 ACCEPTED** (moments) · **P2-I2 ACCEPTED** (shell + context return) · **P2-I3 ACCEPTED** (honest coverage; undated gaps visible)  
**CLI prove (proposed):** `python -m memorybox prove-p2-i4` · `prove-p2-i4 --flightsim`  
**Gate:** Build only after founder lock + authorization. Mark **ACCEPTED** only after FlightSim owner gate.

---

## 0. Product intent

I1 made people searchable in photos and video moments. I2 made MemoryBox one product. I3 made archive coverage honest.

I4 makes **large mixed-media exploration practical**:

> **The owner can move through a large photo/video archive as a living timeline gallery — zoom and band by time, see where known media sit, open items without losing context — without confidence scores or provider folders becoming the primary interface.**

End-to-end outcomes:

1. **Timeline-first** navigation for large result sets (P2-UX-02).  
2. **Adaptive zoom / clustering / banding** — year → month → day → dense bands as needed.  
3. **Graphical timeline** (not a text date list): known dates indicated; **unknown dates grouped** together.  
4. **Mouse click and band-select** to raise precision; the gallery adjusts to that period.  
5. **Gallery-first** presentation of mixed media (photos + searchable video moments); admin codes / evidence dumps stay progressive-disclosure only.  
6. **Preview**, filters, drill-down, and **return** preserve exploration context (I2 stack).  
7. Natural-language / Ask refinement works **alongside** structured filters (P2-UX-03) without replacing the timeline.  
8. Does **not** force provider structure or confidence-first UX.  
9. I1 moments open at the right time; I3 honesty about undated gaps informs unknown-date grouping.  
10. Ask/Home may deep-link into this explore surface later — **Ask polish is not the I4 rewrite** (separate UX-principles work may refine Ask after).

I4 is the **high-volume explore engine**, not Archive Health, not Settings, not kinship, not speech moments.

---

## 1. Clarifications to lock (founder)

Confirm or adjust before build authorization:

| # | Question | Proposed default |
|---|----------|------------------|
| Q1 | Primary surface for the timeline engine? | **Evolve Library** into timeline-first explore; Ask can deep-link results into it. Do not invent a third parallel explore app. |
| Q2 | Mixed media in one gallery? | **Yes** — photos + searchable video moments in one timeline stream (source videos as files stay secondary / drill-through). |
| Q3 | Unknown / undated media? | **Grouped bucket** (e.g. “Undated”) accessible from the timeline; never silently dropped; never fake-dated. |
| Q4 | Band / zoom interaction? | Graphical timeline: click focus + drag band to set range; gallery follows. Keyboard/accessible alternate required. |
| Q5 | Scale target for ACCEPTED? | FlightSim real Immich photo corpus (**tens of thousands**) must remain navigable (not “load all thumbs”). |
| Q6 | Filters in I4? | Person, place (when known), modality (photo / video moment), dated vs undated — structured filters + Ask refinement. Heavy visual-attribute search may be thin/best-effort. |
| Q7 | Ask rewrite? | **Out of I4** except deep-link / “Open in Timeline” from Ask results. Broader Ask polish stays UX-principles follow-on. |
| Q8 | Saved views / “save this query”? | **Thin optional** if cheap (EVS-249); full Dynamic Views = **I13**. Default: OUT unless founder pulls thin save in. |

---

## 2. IN scope

### 2.1 Timeline-first explore (P2-UX-02)

| Capability | I4 expectation |
|------------|----------------|
| Timeline chrome | Dominant graphical time axis for the current result set / library scope |
| Adaptive zoom | Coarse → fine (e.g. years → months → days / dense bands) |
| Clustering / banding | Dense periods compress; sparse periods expand |
| Gallery | Large-set mixed-media thumbs; select → preview / open |
| Unknown dates | Explicit undated group; not mixed falsely into dated spine |
| Performance | Virtualized / windowed loading — no full-corpus dump |

### 2.2 Interaction

- Click timeline to focus a period.  
- Band-select (drag) to set a range; gallery filters to that range.  
- Open photo → Library/detail or lightbox; open video moment → Review/jump `t=` (I1).  
- Return restores timeline position / band / filters / scroll (I2 context).

### 2.3 Refinement (P2-UX-03) — I4 slice

- Structured filters: Person, modality, dated/undated, place when available.  
- Ask / natural language may refine or hand off into the timeline with filters applied.  
- Progressive disclosure for provider/confidence (P2-UX-04).

### 2.4 Absorb founder Ask explore notes (parked → I4)

From post-I2 flow review (held until after I3):

- Results feel like a **gallery**, not administrative evidence lists.  
- Timeline across the bottom (or equivalent dominant axis) with known dates marked.  
- Unknown dates grouped.  
- Click/band for higher precision.  
- Evidence area / photo codes not primary UI.

### 2.5 Preserve prior increments

- I1 jump-to-moment and face evidence remain coherent inside timeline open.  
- I2 shell + context return.  
- I3 honesty: undated / unavailable never look like zero coverage elsewhere.

---

## 3. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Archive Health redesign | **I3** (done) |
| Ask/Home invitation polish, journey chips, viewer identity UX | UX-principles / Ask follow-on — not I4 body |
| Mature Settings | **I14** |
| Kinship inference | **I6** |
| SMS / richer email | **I7–I8** |
| Spoken-moment STT engine | **I9** |
| Full Dynamic Views product | **I13** (thin save optional only if Q8 pulls in) |
| Confidence- or provider-folder-first UX | Forbidden as default |
| IQ / blur engines | Out |
| Cast / Home Assistant | Deferred |
| Multi-user | Late |

---

## 4. MBPS / EVS / task traceability

| Source | I4 role |
|--------|---------|
| **P2-UX-02** Timeline-first high-volume explore | Primary IN |
| **P2-UX-03** Natural + structured refinement | Primary IN (slice) |
| **P2-UX-04** Progressive disclosure | Required |
| **P2-VID-03** Searchable moments in results | Open-at-moment from gallery |
| **EVS-002** Christmas / mixed-media timeline explore | Primary |
| **EVS-081, 082, 095, 229** Photo find / attribute | Supporting (Person + time + gallery; attributes thin) |
| **EVS-085, 086, 110, 111** Temporal / dated explore | Supporting |
| **EVS-090, 105, 116, 119, 126, 128** Place-oriented explore | Supporting when place known |
| **EVS-227, 249** Discovery / save query | 249 thin optional (Q8) |
| **EVS-237** “Funniest video” | Out / later semantic ranking — not I4 gate |
| **P2-AH-*** | Out (I3) |

---

## 5. Prerequisites

- FlightSim P1 baseline.  
- **P2-I1..I3 ACCEPTED**.  
- Real Immich photo scale + HVRT moments available for mixed gallery.  
- I2 shell context return working on Library ↔ Review ↔ Ask.

---

## 6. Acceptance corpus (minimum)

| Case | Requirement |
|------|-------------|
| Timeline-first | Large set navigated by graphical timeline, not folder/provider tree |
| Zoom / band | At least two zoom levels + band-select changes gallery period |
| Undated | Unknown dates grouped; not fake-dated; reachable |
| Mixed media | Photos and video moments appear in one explore stream |
| Open moment | Video moment opens with jump `t=` |
| Context return | Open → return restores timeline/band/filter/scroll meaningfully |
| Scale | Tens of thousands of Immich photos remain usable (windowed) |
| Progressive disclosure | No confidence-first or evidence-code primary UI |
| Refinement | Person (or equivalent) filter + Ask handoff/refine demonstrated |
| Regression | `prove-p2-i1`, `prove-p2-i2`, `prove-p2-i3` `--flightsim` still green |
| Scope | No Ask rewrite; no Settings; no I6 kinship; no I9 STT |

---

## 7. Exact acceptance gate (proposed)

Pass **all** on FlightSim before **ACCEPTED**:

1. Library (or chosen primary surface) is timeline-first for high-volume media.  
2. Graphical timeline shows dated density; undated group exists.  
3. Click focus works; band-select narrows gallery to that range.  
4. Adaptive zoom demonstrated (coarse ↔ finer).  
5. Mixed gallery includes photos + searchable video moments.  
6. Opening a moment jumps to timeslot (`t=`).  
7. Open → return restores explore context (I2).  
8. Real Immich-scale corpus remains navigable (no full dump).  
9. Structured Person (or equivalent) filter works with timeline.  
10. Ask can hand off or refine into timeline without orphaning context.  
11. Primary UI is gallery/timeline — not admin evidence codes.  
12. No confidence-first / provider-folder-first default.  
13. No Ask/Home full polish rewrite; no Settings rebuild; no kinship/STT engines.  
14. I1–I3 FlightSim proves remain green.  
15. Dedicated `prove-p2-i4` / `--flightsim` passes.

---

## 8. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Load-all Immich thumbs | Windowed/virtualized fetch; prove scale case |
| Fake dates for undated | Explicit undated bucket (Q3) |
| Ask rewrite sneaks in | Q7 OUT; deep-link only |
| Timeline becomes admin scrubber | Gallery-first; progressive disclosure |
| Video file vs moment confusion | Moments in stream; source file secondary |
| Scope creep to I13 saved views | Q8 default OUT |

---

## 9. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A sequencing (I3→I4 Timeline) | Approved direction |
| P2-I1..I3 | **ACCEPTED** |
| Founder I4 clarifications (§1 Q1–Q8) | **AWAITING** Tom lock |
| **This I4 definition** | **DRAFT — review only** |
| Build / code / FlightSim implement | **NOT AUTHORIZED** until Tom locks Q1–Q8 and says **Build P2-I4** |

**No code for I4 until explicit build approval.**
