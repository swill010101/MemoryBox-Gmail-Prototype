# MBBS-P2 Increment 3 — Archive Health & Provider Honesty

**Status:** **DRAFT for founder review** · **No build** until explicit “Build P2-I3” authorization  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority:** Locked MBPS-002 · MBEVS-001 v1.0 · prior I1 + I2 ACCEPTED baselines  
**Depends on:** **P2-I1 ACCEPTED** · **P2-I2 ACCEPTED** (shell entry to Archive Health already exists)  
**Absorbs:** **TASK-P1P2-004** Immich Photos inventory  
**CLI prove (proposed):** `python -m memorybox prove-p2-i3` · `prove-p2-i3 --flightsim`  
**Gate:** Build only after explicit authorization. Mark **ACCEPTED** only after FlightSim owner gate.

---

## 0. Product intent

I1 proved Person-in-Media. I2 made MemoryBox feel like one product with a distinct **Archive Health** entry.

I3 makes that entry **honest and useful**:

> **The owner can see what the archive really has, what is missing or unhealthy, and a few high-leverage things to work on next — without turning MemoryBox into an admin cleanup product.**

End-to-end outcomes:

1. P1 `/status` evolves into owner-facing **Archive Health** under the I2 shell (system destination).  
2. **Real Immich Photos totals** when the provider is healthy and endpoints allow (**TASK-004**).  
3. **Unavailable ≠ 0** — missing keys, down providers, or unsupported metrics never look like an empty archive.  
4. Source counts vs searchable moments vs People / Stories / Artifacts / Journal / communications are distinguishable.  
5. A **small** “Work on these now” set (not thousands of deficiencies).  
6. Prefer **high-leverage** gaps (e.g. undated source video that would position many moments).  
7. Provider/processing health is visible enough to operate P2 (thin toward P2-SET-02; mature Settings stays **I14**).  
8. I1 sync/queue observability and I2 shell chrome remain coherent; no family-nav pollution.

I3 is **ops / honesty maturation**, not the I4 timeline explore engine and not Ask gallery polish.

---

## 1. Clarifications to lock (founder)

Confirm or adjust before build authorization:

| # | Question | Proposed default |
|---|----------|------------------|
| Q1 | How deep is Archive Health UI rewrite vs evolving current Status? | **Evolve** Status into Archive Health language/layout; do not rebuild as a separate product |
| Q2 | Immich Photos inventory when API/key limited? | Show **honest unavailable** + partial counts; never invent totals |
| Q3 | “Work on these now” queue size? | **≤ ~5–7** items; prioritize high-leverage (dates, identity, coverage) |
| Q4 | Recognition queue / Immich sync status? | **Include** thin I1-proven signals (queue summary, last sync); do not redesign recognition |
| Q5 | Family-facing Ask/Home? | **Out of I3** — Archive Health stays owner/system; Ask polish is separate follow-on |
| Q6 | Settings / provider connection UI? | **Entry + health signals only**; mature Settings = **I14** |

---

## 2. IN scope

### 2.1 Archive Health surface (P2-AH-01)

| Area | I3 expectation |
|------|----------------|
| Coverage | What is present: photos, videos, searchable moments, People, Stories, Artifacts, Journal, communications (as available) |
| Gaps | Meaningful missing/uncertain people, dates, places, links — summarized, not dumped |
| Provider health | Immich / HVRT (and other configured providers): healthy, degraded, unavailable |
| Processing | Thin recognition/sync/queue observability already proven in I1 |
| Shell | Remains I2 system destination (not family primary nav) |

### 2.2 TASK-004 — Immich Photos inventory

- Real photo **totals** when Immich is configured and reachable.  
- Distinguish library/source inventory from derived/searchable subsets where relevant.  
- If Immich key/endpoint cannot support a metric: **unavailable with reason**, not `0`.

### 2.3 Small actionable queues (P2-AH-02)

Surface a few high-value actions, e.g.:

- Unknown / unreviewed people candidates  
- Missing or uncertain dates (esp. source video)  
- Missing locations (when data exists to support)  
- Unlinked artifacts / incomplete relationships (thin)  
- Provider unhealthy / sync stale

Each item should deep-link into an existing correction surface when one exists (Review, People, etc.) — **Gap → Work on this now → Resolve** without inventing new engines.

### 2.4 High-leverage cleanup (P2-AH-03)

Prioritize corrections whose value propagates (e.g. dating a source video so derived moments land on the timeline). Do not build IQ/blur engines or invent unsupported Immich metrics.

### 2.5 Honesty rules

- Unavailable ≠ empty.  
- Degraded ≠ healthy with zeros.  
- Do not imply completeness when coverage is unknown.

---

## 3. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Timeline-first high-volume explore / graphical band | **P2-I4** |
| Ask/Home gallery polish, journey chips, viewer UX rework | Post-I2 follow-on (parked); not I3 |
| Mature Settings area | **P2-I14** |
| Continuous Immich Person sync redesign | Later ID increments (foundation already in I1) |
| Multi-user / owner vs interactive user roles | Late |
| Cast / Home Assistant | Deferred |
| Confidence-score-first or provider-structure-first family UX | Forbidden as default |
| Thousands of deficiency rows / admin cleanup product | Forbidden |

---

## 4. MBPS / EVS / task traceability

| Source | I3 role |
|--------|---------|
| **P2-AH-01** Archive Health | Primary IN |
| **P2-AH-02** Small actionable queues | Primary IN |
| **P2-AH-03** High-leverage cleanup | Primary IN |
| **P2-SET-02** Provider health | Thin signals only → full Settings **I14** |
| **TASK-P1P2-004** Immich Photos inventory | Absorbed |
| **EVS-216** What archive information do I have / how much missing? | Primary acceptance |
| **EVS-214** What should I work on next? | Primary acceptance (small queues) |
| **EVS-203** Help add dates to undated photos/videos | Supporting (queue → correction path) |
| **P2-UX-02/03** Timeline explore | **OUT → I4** |

---

## 5. Prerequisites

- P1 baseline on FlightSim.  
- **P2-I1 ACCEPTED** (sync/queue/moments).  
- **P2-I2 ACCEPTED** (shell + Archive Health entry).  
- Immich reachable on FlightSim for TASK-004 honesty gate.

---

## 6. Acceptance corpus (minimum)

| Case | Requirement |
|------|-------------|
| Honest Photos inventory | When Immich healthy: real total visible; when not: unavailable ≠ 0 |
| Coverage summary | Owner can see present vs meaningful gaps without false completeness |
| Work on these now | Small actionable set; no thousands of rows |
| High-leverage bias | At least one queue item prefers propagating corrections (e.g. undated video) when such gaps exist |
| Provider health | Immich/HVRT (as configured) report healthy / degraded / unavailable distinctly |
| Shell coherence | Archive Health remains system destination under I2 chrome |
| Regression | `prove-p2-i1 --flightsim` and `prove-p2-i2 --flightsim` still pass |

---

## 7. Acceptance gate

Pass **all** on FlightSim with real Immich (and HVRT where relevant):

1. Archive Health is the evolved Status surface — owner-facing, not family-nav.  
2. TASK-004: real Immich Photos total when healthy; honest unavailable otherwise.  
3. Unavailable never presented as zero coverage.  
4. Small “Work on these now” queues are present and actionable.  
5. Provider/processing health is readable.  
6. No I4 timeline engine; no Ask polish scope leak; no mature Settings rebuild.  
7. I1 + I2 proves remain green.

Proposed prove: `python -m memorybox prove-p2-i3` / `--flightsim` (implement only after build authorization).

---

## 8. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Status becomes a dashboard dump | AH-02 size cap; progressive disclosure |
| Fake Immich zeros | Honesty rules; prove asserts unavailable ≠ 0 |
| I4 timeline sneaks in via “coverage by time” | Hard OUT; dates queue links to existing correction only |
| Ask polish conflated with I3 | Parked Ask follow-on; Q5 default out |
| Settings rewrite | Thin health only; I14 owns Settings |

---

## 9. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A sequencing (I2→I3 Archive Health) | Approved direction |
| P2-I1 | **ACCEPTED** |
| P2-I2 | **ACCEPTED** (2026-08-13) |
| Founder I3 clarifications (§1 Q1–Q6) | **AWAITING** Tom lock |
| **This I3 definition** | **DRAFT — review only** |
| Build / code / FlightSim implement | **NOT AUTHORIZED** until Tom says **Build P2-I3** |

**No code for I3 until explicit build approval.**
