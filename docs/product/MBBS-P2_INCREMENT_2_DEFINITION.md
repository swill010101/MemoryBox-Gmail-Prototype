# MBBS-P2 Increment 2 — Product Shell & Context Maturation

**Status:** **DRAFT FOR FOUNDER REVIEW** · No build until explicitly approved  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority:** Locked MBPS-002 · MBEVS-001 v1.0 · prior I1 ACCEPTED baseline  
**Depends on:** **P2-I1 ACCEPTED** (Show me Peggy / Person-in-Media)  
**CLI prove (proposed):** `python -m memorybox prove-p2-i2` · `prove-p2-i2 --flightsim`  
**Gate:** Definition must be LOCKED + build authorized before implementation. Mark **ACCEPTED** only after FlightSim owner gate.

---

## 0. Product intent

I1 proved the first meaningful P2 vertical:

> **Show me Peggy** — photos + face-appearance moments, jump-to-timeslot, correct→reuse, durable full-archive queue.

I2 wraps that proof (and the existing P1 surfaces) into **one coherent MemoryBox product**:

> **MemoryBox feels like one product, not a set of disconnected tools.**

End-to-end owner outcomes:

1. Owner can move among **Ask, Library/Timeline, People, Stories, Journal, Artifacts, Review & Learn**, plus **entries** to Settings and Archive Health, without losing the sense of a single product.  
2. **Open → inspect → act → return** preserves meaningful context (results, selection, person, moment, prior ask).  
3. Family-facing exploration stays simple (**progressive disclosure**); provider/processing/confidence detail appears only when useful for an owner decision.  
4. The I1 Peggy path remains reachable and coherent inside the shell (Ask → results → open moment → correct → return).  
5. Shared / living-room style exploration is supported as a **first-class product posture** (not solo-admin chrome) — see §1 open questions on EVS-242 depth.

I2 is **product maturation (UX/shell)**, not a new provider capability wave.

---

## 1. Open questions for Tom (sign-off blockers)

Answer these before LOCKED:

| # | Question | Options / notes |
|---|----------|-----------------|
| Q1 | **Shell chrome depth** | (A) Light shared chrome + nav over existing P1 HTML surfaces, or (B) stronger IA redesign that still keeps P1 pages as destinations? |
| Q2 | **Primary home** | Is **Ask** the default front door (aligned with experience mockups), or a hub/home that links into Ask? |
| Q3 | **EVS-242 (Family Room TV)** | (A) Full cast/display to authorized TV / Home Assistant in I2, (B) shell supports shared-screen / living-room viewing posture but defers device cast to later, or (C) out of I2 entirely? |
| Q4 | **Settings / Archive Health entries** | Confirm I2 only needs **reachable entry points** (stub/thin), with full Archive Health + TASK-004 in **I3** and Settings maturity later (**I14** per 001A). |
| Q5 | **Context stack scope** | Minimum for ACCEPTED: Ask result → open photo/moment/person → return restores prior Ask results. Should Library/People/Review get the same depth in I2, or Ask-path only? |
| Q6 | **Visual language** | Preserve current thin functional shells, or bring forward validated mockup language (quiet curator / experience gallery) as the I2 shell look? |

Until Q1–Q6 are answered, treat §2 IN as the planning baseline and §8 acceptance as provisional.

---

## 2. IN scope

### 2.1 Coherent product shell (MBPS P2-UX-01)

Surfaces must feel like parts of **one product**:

| Surface | I2 expectation |
|---------|----------------|
| Ask | First-class; I1 Peggy path remains primary proof inside shell |
| Library / Timeline | Reachable; **not** the I4 high-volume timeline engine |
| People | Reachable; I1 sync/status affordances remain available |
| Stories | Reachable |
| Journal | Reachable |
| Artifacts | Reachable |
| Review & Learn | Reachable; I1 teach/correct remains coherent when entered from Ask |
| Settings | **Entry** only (thin/stub OK) |
| Archive Health / Status | **Entry** only (thin/stub OK); full honesty = I3 |

Shared chrome (exact form per Q1): product identity, primary nav, and a consistent way back to Ask / prior context.

### 2.2 Context maturation (open → inspect → act → return)

- Opening a result (photo, video moment, person, story, etc.) must not orphan the owner.  
- Return restores **meaningful prior context** (at minimum the Ask session/results that led here — Q5).  
- Correction / teach actions from I1 remain available without breaking the stack.  
- Context is product state, not a browser-history accident.

### 2.3 Progressive disclosure (MBPS P2-UX-04)

- Default family-facing UI stays simple (invitation / results / evidence).  
- Provider keys, raw confidence machinery, processing internals, and admin density stay secondary.  
- Reveal technical detail when the owner is deciding (e.g. why uncertain, what to correct, sync/queue state already proven in I1).

### 2.4 Shared / living-room posture (EVS-017 / EVS-199)

- Shell must not read as “solo admin console.”  
- Support a gathered / shared exploration posture (large readable results, quiet chrome, conversation-first Ask).  
- **EVS-242 TV cast** depth is gated by **Q3**.

### 2.5 Preserve I1 without regression

- I1 acceptance remains green on FlightSim after I2 lands.  
- No redesign that strips jump-to-timeslot, face evidence, queue observability, or owner-correct authority.

---

## 3. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Timeline-first high-volume explore (adaptive zoom/clustering/banding engine) | **P2-I4** |
| Archive Health redesign + TASK-004 Immich Photos inventory honesty | **P2-I3** |
| Full Settings maturity | **P2-I14** (001A) |
| Universal Person pickers on all surfaces | **P2-I5** |
| Kinship, SMS, richer email, spoken moments | **I6–I9** |
| Narrative / external history / views / campaigns / trust / portability | **I11–I17** |
| Multi-user / tone dial | Late |
| New providers / Immich sync redesign / HVRT recognition redesign | Not I2 (already I1) |
| Speech moments | I9 |
| Synthetic media | P3 |

**Explicit non-goals**

- Do not rebuild Archive Health “while we’re here.”  
- Do not ship the I4 timeline engine inside shell chrome.  
- Do not invent multi-user.  
- Do not replace I1 Ask proof with a dashboard-first home unless Q2 explicitly chooses hub-home.  
- Do not treat EVS-242 as requiring unscoped Home Assistant work without Q3.

---

## 4. MBPS / EVS traceability

| Source | I2 role |
|--------|---------|
| **P2-UX-01** Coherent product shell | Primary IN |
| **P2-UX-04** Progressive disclosure | Primary IN |
| **P2-UX-02 / P2-UX-03** High-volume timeline + refinement | **OUT → I4** (shell may leave Timeline reachable only) |
| **P2-AH-*** Archive Health | Entry only → **I3** |
| **EVS-017** Family gathered around TV exploring Christmas memories | Primary shared-experience validation |
| **EVS-199** Alias of EVS-017 | Same as 017 |
| **EVS-242** Show Peggy pictures on Family Room TV | Conditional on **Q3** |

---

## 5. Domain / services / UX

| Area | I2 expectation |
|------|----------------|
| **Shell / IA** | Shared navigation + product identity over existing MemoryBox surfaces |
| **Context service / stack** | Durable enough for open→return across Ask (and optionally other surfaces per Q5) |
| **Ask** | Remains primary conversation front door unless Q2 says otherwise; I1 behaviors preserved |
| **Review / People / Library / …** | Destinations inside the shell; no capability rewrite required for I2 |
| **Settings / Archive Health** | Routes/entries; content owned by later increments |
| **Experience Flows** | Formalize only if needed: Shell navigate→Ask→open→return; Shared explore Christmas/Peggy |

No new evidence providers required for I2.

---

## 6. Prerequisites

- P1 baseline on FlightSim.  
- **P2-I1 ACCEPTED** (`prove-p2-i1 --flightsim` green).  
- Existing P1 UIs remain available to wrap (Ask, People, Library, Review, Story, Journal, Artifact, Status, Export, Guided Capture as present).  
- Experience mockups under `mockups/` are **validation reference**, not a mandatory pixel match (unless Q6 chooses mockup language).

---

## 7. Acceptance corpus (minimum)

| Case | Requirement |
|------|-------------|
| One product | From a single entry URL/app, owner reaches Ask, People, Library, Review, Stories/Journal/Artifacts (as present), plus Settings and Archive Health **entries** |
| Context return | Ask → open Peggy photo or video moment → return restores prior Ask results/context |
| I1 preserved | “Show me Peggy” (or Peggy George) still returns photos + moments with jump `t=` inside the shell |
| Progressive disclosure | Default path does not force provider/admin chrome; advanced detail available when needed |
| Shared posture | Shell supports gathered exploration feel (EVS-017); not admin-dashboard-first |
| EVS-242 | Only if Q3 = A; otherwise deferred with explicit note in ACCEPTED record |
| Regression | `prove-p2-i1 --flightsim` still passes after I2 |

---

## 8. Acceptance gate (provisional until Q1–Q6 locked)

Pass **all** of the following on FlightSim with real-family material where practical:

1. **Single product feel:** Owner navigates MemoryBox as one product, not disconnected P1 tools.  
2. **Nav completeness:** All IN surfaces in §2.1 are reachable from the shell.  
3. **Context return:** Ask drill-down/return preserves meaningful context (Q5 minimum).  
4. **Progressive disclosure:** Family path stays simple; technical detail on demand.  
5. **I1 regression:** Person-in-media proof still works inside the shell.  
6. **Shared exploration:** EVS-017 posture validated (Christmas / family gather path — scripted OK).  
7. **No scope leak:** I3 Archive Health content and I4 timeline engine are not required to pass I2.  
8. **EVS-242:** Per locked Q3.

Proposed prove: `python -m memorybox prove-p2-i2` (harness) and `prove-p2-i2 --flightsim` (owner gate). Exact checks to be finalized when Q1–Q6 are answered and this definition is LOCKED.

---

## 9. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Shell becomes a rewrite of every P1 page | Wrap first; deepen only where context return requires it |
| Context scope creep into full app state machine | Lock Q5; Ask-path minimum for ACCEPTED |
| EVS-242 pulls Home Assistant / casting into shell | Lock Q3 before build |
| Dashboard-first home fights curator/Ask front door | Lock Q2; mockups favor Ask invitation |
| I3/I4 work sneaks into I2 | Hard OUT table; acceptance forbids requiring them |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A sequencing (I1→I2 Shell) | Approved |
| P2-I1 | **ACCEPTED** (2026-08-13) |
| **This I2 definition** | **DRAFT — awaiting founder answers to Q1–Q6** |
| Build / code / FlightSim implement | **NOT AUTHORIZED** until definition LOCKED + explicit build approval |

**No code for I2 until Tom signs off this definition (and answers §1).**
