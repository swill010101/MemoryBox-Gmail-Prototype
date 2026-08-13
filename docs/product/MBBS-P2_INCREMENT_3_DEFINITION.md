# MBBS-P2 Increment 3 — Archive Health & Provider Honesty

**Status:** **ACCEPTED** (2026-08-13: FlightSim `prove-p2-i3 --flightsim` → `ok: true` · founder approval) · Definition **LOCKED**  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority:** Locked MBPS-002 · Locked MBEVS-001 v1.0 · MBRM-001A sequencing · **P2-I1 ACCEPTED** · **P2-I2 ACCEPTED**  
**Depends on:** P2-I1 ACCEPTED · P2-I2 ACCEPTED (Archive Health entry already exists under I2 shell)  
**Absorbs:** **TASK-P1P2-004** Immich Photos inventory  
**CLI prove:** `python -m memorybox prove-p2-i3` · `prove-p2-i3 --flightsim`  
**Gate:** **PASSED** — FlightSim prove + founder acceptance (2026-08-13).

---

## 0. Product intent

I1 proved Person-in-Media. I2 made MemoryBox feel like one product with a distinct **Archive Health** entry (owner/system destination).

I3 makes that entry **honest and actionable**:

> **The owner can see what the archive really has, whether sources and processing are healthy, what MemoryBox still does not know, and a few high-leverage things to work on next — without turning MemoryBox into an admin cleanup product or implying false completeness.**

End-to-end outcomes:

1. Existing **Status** is **evolved** into owner-facing **Archive Health** language/layout (not a parallel admin product).  
2. Remains a **secondary owner/system destination** under the I2 shell.  
3. Provider counts are **honest**: real / partial (labeled) / unavailable — **never** a false zero.  
4. Every Archive Health number has an **explicit meaning** (no ambiguous “Videos: 428”).  
5. Three concepts stay distinct: **source/provider health**, **processing state**, **archive knowledge gaps**.  
6. Thin I1-proven sync/recognition/processing signals are visible enough to operate — without redesigning recognition.  
7. “Work on these now” stays **small** (~5, hard ceiling ~7), high-leverage first, and is an **end-to-end action** (gap → correct → return → update).  
8. Ask/Home polish and mature Settings are **out**.  
9. I1 + I2 regression proves remain green.

I3 is **ops / honesty / guided correction maturation**, not the I4 timeline engine and not Ask gallery polish.

---

## 1. Locked founder decisions (2026-08-13)

### 1.A Evolve Status — do not fork (Q1)

- Archive Health **evolves the existing Status surface**.  
- **Do not** create a separate parallel admin product.  
- Recast Status into owner-facing Archive Health language and layout.  
- Keep Archive Health as a **secondary owner/system destination** under the I2 shell (not family primary nav).

### 1.B Honest provider counts (Q2)

For Immich and other providers:

| State | Presentation |
|-------|----------------|
| Known | **Real count** |
| Partially known | **Partial count**, clearly labeled as partial |
| Not determinable | **Unavailable / unknown** (with reason when useful) |

**Never** show `0` as a substitute for unavailable, unauthorized, unsupported, or unreachable.  
**Do not** imply completeness when coverage is unknown.

### 1.C Small “Work on these now” (Q3)

- Target **~5** visible recommendations.  
- Hard ceiling **~7**.  
- Prioritize **high-leverage** corrections whose value propagates broadly.  
- When an item is resolved, another may enter the visible set.  
- **Do not** create a giant defect/error backlog in the normal UI.

### 1.D Thin I1-proven operational state (Q4)

Archive Health must let the owner understand basic operational state such as:

- last Immich sync  
- whether recognition work is queued / running / completed / failed / deferred  
- stale or failed processing  
- provider healthy / degraded / unavailable  

**Do not** redesign the recognition system in I3.

### 1.E Ask/Home polish out (Q5)

- **Do not** reopen Home, Ask, gallery, or broader UX refinement in I3.  
- Separate MemoryBox UX-principles work governs later UX refinement.

### 1.F Settings maturity out (Q6)

- Archive Health may provide a **clear route** to the relevant Settings / provider area.  
- **Do not** build the mature Settings experience here (**I14**).

---

## 2. Locked product rules (A–D)

### 2.A Explicit metric meanings

Every Archive Health number must have an **explicit meaning**. Avoid ambiguous labels such as “Videos: 428”.

Prefer clear distinctions such as:

- Photos available  
- Source videos  
- Searchable video moments  
- Known People  
- Unidentified face candidates  
- Stories  
- Journal entries  
- Communications  

Where useful, drill-down should identify **where the metric came from** or **how it was determined**.

### 2.B Three distinct concepts

Archive Health must separate:

1. **Source / provider health** — Can MemoryBox currently reach and use the source?  
2. **Processing state** — queued / running / completed / failed / stale / deferred  
3. **Archive knowledge gaps** — What MemoryBox still does not know or understand  

**Do not** treat provider health as equivalent to archive completeness.

### 2.C “Work on this now” is end-to-end

A recommendation is not enough. At least one real acceptance case must prove:

1. Archive Health identifies a gap  
2. Owner selects **Work on this now**  
3. MemoryBox opens the appropriate **existing** correction/review surface **in context**  
4. Owner completes the correction  
5. Owner returns to Archive Health  
6. The relevant health item / count / status **updates appropriately**

Use existing correction surfaces where they already exist. **Do not** invent a new cleanup engine solely for I3.

### 2.D High-leverage prioritization

Favor recommendations whose value propagates. Example: an **undated source video** whose date would position many derived video moments ranks above a low-impact isolated cleanup item when both are available.

---

## 3. IN scope

### 3.1 Archive Health surface (P2-AH-01)

| Area | I3 expectation |
|------|----------------|
| Evolve Status | Recast existing Status → Archive Health language/layout |
| Explicit metrics | Labeled counts per §2.A; provenance/how-determined where useful |
| Three-way split | Provider health · processing state · knowledge gaps (§2.B) |
| Shell | I2 system destination only |

### 3.2 TASK-004 — Immich Photos inventory

- Real **Photos available** (or equivalent explicit label) when Immich is healthy and authorized.  
- Partial / unavailable / degraded labeled honestly (§1.B).  
- Restoring provider access must allow health state to **recover correctly**.

### 3.3 Small actionable queues (P2-AH-02)

~5 visible items (ceiling ~7), e.g.:

- Unidentified / unreviewed face or people candidates  
- Missing or uncertain dates (esp. high-leverage source video)  
- Missing locations when evidence supports  
- Unlinked artifacts / incomplete relationships (thin)  
- Stale sync / failed processing (as actionable when an existing path exists)

Each visible item must support the **Work on this now** loop (§2.C) via an existing surface when one exists.

### 3.4 High-leverage cleanup (P2-AH-03)

Rank by propagation value (§2.D). No IQ/blur engines; no invented Immich metrics.

### 3.5 Thin operational observability (from I1)

Last Immich sync; recognition queue/process summary; stale/failed; provider health — subordinate to coverage/gaps, not a dominant ops console redesign.

### 3.6 Settings route only

Link/route to existing Settings or provider configuration entry points. No mature Settings rebuild.

---

## 4. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Timeline-first high-volume explore / graphical band | **P2-I4** |
| Ask/Home / gallery / journey / broader UX polish | Out of I3 (UX-principles later) |
| Mature Settings area | **P2-I14** |
| Recognition system redesign | Not I3 |
| New cleanup / defect engine | Forbidden |
| Continuous Immich Person sync redesign | Later ID increments |
| Multi-user / owner vs interactive user roles | Late |
| Cast / Home Assistant | Deferred |
| Confidence- or provider-structure-first family UX | Forbidden as default |
| Giant deficiency backlog in normal UI | Forbidden |
| Implying completeness because providers are healthy | Forbidden |

---

## 5. MBPS / EVS / task traceability

| Source | I3 role |
|--------|---------|
| **P2-AH-01** Archive Health | Primary IN |
| **P2-AH-02** Small actionable queues | Primary IN |
| **P2-AH-03** High-leverage cleanup | Primary IN |
| **P2-SET-02** Provider health | Thin signals + route to Settings → full Settings **I14** |
| **TASK-P1P2-004** Immich Photos inventory | Absorbed |
| **EVS-216** What archive information / how much missing | Primary |
| **EVS-214** What should I work on next | Primary (small queues + E2E action) |
| **EVS-203** Help add dates to undated media | Supporting (high-leverage Work on this now path) |
| **P2-UX-02/03** Timeline explore | **OUT → I4** |
| Ask/Home polish | **OUT** |

---

## 6. Prerequisites

- P1 baseline on FlightSim.  
- **P2-I1 ACCEPTED**.  
- **P2-I2 ACCEPTED**.  
- Immich reachable on FlightSim for honesty + recovery gate (and a controlled unavailable case for false-zero proof).

---

## 7. Acceptance corpus (minimum)

| Case | Requirement |
|------|-------------|
| Evolved Status | Archive Health is clearly the evolved Status surface; owner/system destination |
| Photos honest (healthy) | Immich healthy + authorized → real Photos total with explicit meaning |
| Photos honest (down) | Unavailable / unauthorized / unsupported → unavailable/degraded/partial — never false zero |
| Recovery | Restoring provider access → health recovers correctly |
| Metric clarity | Source videos ≠ searchable video moments; other metrics explicitly labeled |
| Three concepts | Provider health, processing state, knowledge gaps visually/conceptually distinct |
| Thin ops | I1 sync/queue state visible enough to operate; does not dominate |
| Small queues | ~5 recommendations; never a large deficiency dump (ceiling ~7) |
| High-leverage | At least one recommendation demonstrates prioritization when such a gap exists |
| E2E Work on this now | Gap → open existing surface in context → correct → return → Archive Health updates |
| No false completeness | Healthy providers ≠ archive complete |
| Scope lock | No I4 timeline; no Ask polish; no mature Settings |
| Regression | `prove-p2-i1 --flightsim` and `prove-p2-i2 --flightsim` still pass |
| Prove | Dedicated `prove-p2-i3` / `--flightsim` passes |

---

## 8. Exact acceptance gate (owner ACCEPTED)

Pass **all** on FlightSim before marking I3 **ACCEPTED**:

1. Archive Health is clearly the evolved Status surface and remains an owner/system destination.  
2. With Immich healthy and authorized, a real Photos total is shown.  
3. When Immich is unavailable, unauthorized, or cannot expose a metric, the UI shows unavailable / degraded / partial as appropriate — **never** a false zero.  
4. Restoring provider access causes health state to recover correctly.  
5. Source video counts and searchable video-moment counts are clearly distinguished.  
6. Provider health, processing state, and archive knowledge gaps are visually/conceptually distinct.  
7. I1 recognition/sync queue state is visible enough to operate, but does not dominate the screen.  
8. “Work on these now” normally shows about **5** recommendations and never becomes a large deficiency dump.  
9. At least one recommendation demonstrates **high-leverage prioritization** when such a gap exists.  
10. At least one “Work on this now” action completes the full **gap → correction → return → Archive Health update** loop.  
11. Archive Health never claims or implies archive completeness merely because providers are healthy.  
12. No I4 timeline engine is pulled into I3.  
13. No Ask/Home polish is pulled into I3.  
14. No mature Settings rebuild is pulled into I3.  
15. P2-I1 and P2-I2 regression proves remain green.  
16. A dedicated P2-I3 proof/harness and FlightSim owner gate pass (`prove-p2-i3` / `prove-p2-i3 --flightsim`).

Implement prove only after build authorization.

---

## 9. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Status becomes dashboard dump | ~5 / ceiling 7; progressive disclosure; thin ops |
| Fake zeros | §1.B + gate items 2–3; prove asserts unavailable ≠ 0 |
| Provider healthy = “complete” | §2.B + gate item 11 |
| Work on this now is display-only | §2.C + gate item 10 |
| Low-impact spam in queue | §2.D + gate item 9 |
| I4 timeline via “coverage by time” | Hard OUT |
| Ask polish / Settings rebuild | Hard OUT (§1.E–F) |
| Recognition redesign | Thin I1 signals only (§1.D) |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A sequencing (I2→I3 Archive Health) | Approved |
| P2-I1 | **ACCEPTED** |
| P2-I2 | **ACCEPTED** (2026-08-13) |
| Founder I3 decisions (§1 Q1–Q6 + rules A–D) | **LOCKED** (2026-08-13) |
| **This I3 definition** | **LOCKED** |
| Build authorization | **AUTHORIZED** (2026-08-13 — Tom: “build it”) |
| Implementation | **COMPLETE** on `cursor/p2-iteration-roadmap-3061` |
| FlightSim owner gate (`prove-p2-i3 --flightsim`) | **PASSED** (2026-08-13 · `ok: true`) |
| Founder acceptance | **ACCEPTED** (2026-08-13 — Tom: “i3 approved”) |

P2-I3 is **ACCEPTED**. Next: [MBBS-P2_INCREMENT_4_DEFINITION.md](MBBS-P2_INCREMENT_4_DEFINITION.md) (draft; no build until Q1–Q8 locked + authorized).
