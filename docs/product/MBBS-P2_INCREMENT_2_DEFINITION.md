# MBBS-P2 Increment 2 — Product Shell & Context Maturation

**Status:** **FlightSim prove PASSED** (2026-08-13: `prove-p2-i2 --flightsim` → `ok: true`) · **Owner UX acceptance PENDING** (Tom flow review) · Definition **LOCKED** · **Not ACCEPTED** until Tom explicitly accepts  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority:** Locked MBPS-002 · MBEVS-001 v1.0 · founder I2 clarifications below · prior I1 ACCEPTED baseline  
**Depends on:** **P2-I1 ACCEPTED** (Show me Peggy / Person-in-Media)  
**CLI prove:** `python -m memorybox prove-p2-i2` · `prove-p2-i2 --flightsim`  
**Gate:** Automated FlightSim prove passed; **ACCEPTED** only after founder UX acceptance.

---

## 0. Product intent

I1 proved the first meaningful P2 vertical:

> **Show me Peggy** — photos + face-appearance moments, jump-to-timeslot, correct→reuse, durable full-archive queue.

I2 wraps that proof (and the existing P1/P2 surfaces) into **one coherent MemoryBox product**:

> **MemoryBox feels like one product, not a set of disconnected tools.**

End-to-end outcomes:

1. **Ask/Home is the front door** — an invitation, not a dashboard: Ask is prominent; authentic family content, suggested journeys, and continuation of recent exploration lead; administrative status is subordinate.  
2. Owner moves among family exploration surfaces under **light shared shell/chrome** without losing product coherence.  
3. **Open → inspect/act → return** preserves meaningful context across Ask, Library, People, and contextual Review & Learn.  
4. **Global Ask** is reachable from major surfaces and inherits current context where practical.  
5. Family-navigation chrome stays **visually distinct** from owner/system destinations (Archive Health, Settings).  
6. Shared / living-room viewing posture is first-class; **device cast / Home Assistant is deferred**.  
7. Visual language follows **MBUX**: warm, calm, modern, premium, quiet-curator (mockups = validation/reference, not pixel-match).  
8. I1 Peggy path remains coherent inside the shell.

I2 is **product maturation (UX/shell)**, not a new provider capability wave.

---

## 1. Locked clarifications (2026-08-13)

### 1.A Shell depth (Q1 = A)

- Use **light shared shell/chrome** and consistent navigation around **existing** P1/P2 surfaces.  
- **Do not** broadly rewrite individual screens in I2.  
- Rewrite/adjust a screen only where required for **context continuity** or **MBUX consistency**.

### 1.B Front door (Q2)

- **Ask/Home is the primary front door.**  
- Home is an **invitation**, not a dashboard.  
- Ask is prominent, with authentic family content, suggested journeys, and continuation of recent exploration.  
- Administrative / status content is **subordinate**.

### 1.C Shared viewing vs cast (Q3 = B)

- I2 **must** support a shared / living-room viewing posture (EVS-017 / EVS-199).  
- **Actual TV casting / Home Assistant / device integration is deferred** (EVS-242 cast path out of I2).

### 1.D Settings & Archive Health (Q4)

- Require **coherent, reachable entry points only**.  
- Archive Health **content** = **I3**; mature Settings = later (**I14**).  
- Both are **owner/system destinations**, not equal primary family-navigation destinations.

### 1.E Context stack (Q5)

- Broader than Ask-only.  
- Preserve meaningful open→inspect/act→return across main exploration paths: **Ask, Library, People, and contextual Review & Learn**.  
- Need not perfect every legacy P1 workflow in this increment.  
- Return should preserve relevant **result set, selection, filter / scroll / timeline state** where applicable.

### 1.F Visual language (Q6)

- Bring forward the **MBUX visual language**: warm, calm, modern, premium, quiet-curator.  
- Mockups under `mockups/` are **validation/reference**, not pixel-match specs.  
- **Do not** simply preserve development-style thin shells when they conflict with MBUX.

### 1.G Additional locked requirements

- **Global Ask** reachable throughout major MemoryBox surfaces; inherits current context where practical.  
- **Primary family experience navigation** remains visually distinct from owner/system destinations (Archive Health, Settings).

---

## 2. IN scope

### 2.1 Light coherent shell (MBPS P2-UX-01)

| Surface | Role in I2 |
|---------|------------|
| **Ask / Home** | Primary front door; invitation; I1 Peggy path; suggested journeys; recent continuation |
| Library / Timeline | Family exploration path; context return; **not** I4 timeline engine |
| People | Family exploration path; context return |
| Review & Learn | Contextual destination; teach/correct continuity from exploration |
| Stories / Journal / Artifacts | Reachable family destinations under shared chrome |
| Settings | Owner/system **entry only** (visually distinct) |
| Archive Health / Status | Owner/system **entry only** (visually distinct); content = I3 |

Shared chrome: product identity, family primary nav, Global Ask affordance, distinct owner/system entries, consistent return-to-context.

### 2.2 Context maturation

- Opening a result must not orphan the owner.  
- Return restores meaningful prior context on Ask, Library, People, and contextual Review paths (§1.E).  
- I1 correction/teach remains available without breaking the stack.  
- Context is product state, not browser-history accident.  
- Global Ask may inherit active person / place / filters / selection when practical.

### 2.3 Progressive disclosure (MBPS P2-UX-04)

- Default family path: invitation, journeys, results, evidence.  
- Provider keys, raw confidence machinery, processing internals, admin density stay secondary.  
- Reveal technical detail when the owner is deciding (uncertainty, correction, sync/queue already proven in I1).

### 2.4 Shared / living-room posture (EVS-017 / EVS-199)

- Not solo-admin chrome.  
- Large readable results, quiet chrome, conversation-first Ask/Home.  
- Suitable for gathered viewing; **no device cast required** (§1.C).

### 2.5 MBUX visual language

- Warm, calm, modern, premium, quiet-curator.  
- Apply shell-wide; touch individual screens only as needed for consistency (§1.A).  
- Mockups guide feel; not pixel slavery.

### 2.6 Preserve I1 without regression

- `prove-p2-i1 --flightsim` remains green after I2.  
- Jump-to-timeslot, face evidence, queue observability, owner-correct authority preserved.

---

## 3. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Timeline-first high-volume explore engine | **P2-I4** |
| Archive Health redesign + TASK-004 inventory | **P2-I3** |
| Mature Settings | **P2-I14** |
| TV cast / Home Assistant / device integration (EVS-242 cast) | Later (post-I2) |
| Broad rewrite of every P1 screen | Not I2 |
| Universal Person pickers on all surfaces | **P2-I5** |
| Kinship, SMS, richer email, spoken moments | **I6–I9** |
| Narrative / external history / views / campaigns / trust / portability | **I11–I17** |
| Multi-user / tone dial | Late |
| New providers / Immich or HVRT redesign | Not I2 |

**Explicit non-goals**

- Do not rebuild Archive Health or Settings content “while we’re here.”  
- Do not ship the I4 timeline engine inside shell chrome.  
- Do not invent multi-user.  
- Do not make Home a status/admin dashboard.  
- Do not require Home Assistant / TV cast for I2 ACCEPTED.  
- Do not pixel-match mockups; do not keep thin-dev chrome that fights MBUX.

---

## 4. MBPS / EVS traceability

| Source | I2 role |
|--------|---------|
| **P2-UX-01** Coherent product shell | Primary IN |
| **P2-UX-04** Progressive disclosure | Primary IN |
| **P2-UX-02 / P2-UX-03** High-volume timeline + refinement | **OUT → I4** |
| **P2-AH-*** Archive Health | Entry only → **I3** |
| **EVS-017** Family gathered around TV exploring Christmas memories | Shared-posture validation (no cast required) |
| **EVS-199** Alias of EVS-017 | Same as 017 |
| **EVS-242** Peggy on Family Room TV | **Cast deferred**; living-room posture only in I2 |

---

## 5. Domain / services / UX

| Area | I2 expectation |
|------|----------------|
| **Shell / IA** | Light shared chrome; family nav vs owner/system destinations |
| **Ask / Home** | Invitation front door; Global Ask; context inheritance |
| **Context stack** | Ask, Library, People, contextual Review return state |
| **Visual system** | MBUX tokens/language applied to shell (+ targeted screen consistency) |
| **Review / People / Library / …** | Existing surfaces wrapped; rewrite only for context/MBUX necessity |
| **Settings / Archive Health** | Distinct entries; thin destinations |
| **Experience Flows** | Ask/Home → explore → open → return; shared Christmas/Peggy gather path |

No new evidence providers required for I2.

---

## 6. Prerequisites

- P1 baseline on FlightSim.  
- **P2-I1 ACCEPTED**.  
- Existing P1/P2 UIs available to wrap.  
- `mockups/` as MBUX validation reference.

---

## 7. Acceptance corpus (minimum)

| Case | Requirement |
|------|-------------|
| Invitation home | Ask/Home is front door; not dashboard-first; status subordinate |
| One product | Shared chrome reaches family surfaces + distinct Settings/Archive Health entries |
| Global Ask | Reachable from major surfaces; inherits context where practical |
| Context return | Ask, Library, People, contextual Review: open→return preserves result set / selection / filter-scroll-timeline state where applicable |
| I1 preserved | Show me Peggy (George) still returns photos + moments with jump `t=` |
| Shared posture | Gathered / living-room viewing feel validated (EVS-017); no cast required |
| Visual language | Shell reads as MBUX quiet-curator; not thin-dev admin chrome |
| Nav distinction | Family primary nav visually distinct from owner/system destinations |
| Regression | `prove-p2-i1 --flightsim` still passes |

---

## 8. Acceptance gate

Pass **all** on FlightSim with real-family material where practical:

1. **Invitation front door:** Ask/Home invites; not an admin dashboard.  
2. **Single product feel:** Light shared chrome; coherent navigation.  
3. **Family vs system:** Primary family nav distinct from Archive Health / Settings entries.  
4. **Global Ask:** Available on major surfaces; context inheritance demonstrated at least once.  
5. **Context return:** Demonstrated on Ask, Library, People, and contextual Review paths (§1.E).  
6. **Progressive disclosure:** Family path simple; technical detail on demand.  
7. **Shared posture:** EVS-017 living-room gather path validated without device cast.  
8. **MBUX language:** Warm/calm/premium quiet-curator shell (reference mockups; not pixel-match).  
9. **I1 regression:** Person-in-media proof still works inside the shell.  
10. **No scope leak:** I3 Archive Health content, I4 timeline engine, and EVS-242 cast not required.

Prove: `python -m memorybox prove-p2-i2` (harness) · `prove-p2-i2 --flightsim` (live shell + I1 regression).

---

## 9. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Shell becomes a rewrite of every P1 page | §1.A wrap-first; change only for context/MBUX |
| Context stack overbuilt | §1.E main exploration paths only; not every legacy workflow |
| Cast/HA sneaks in via EVS-242 | §1.C deferred; acceptance forbids requiring cast |
| Dashboard-first home | §1.B invitation locked |
| Thin-dev chrome survives | §1.F MBUX required |
| Owner/system mixed into family nav | §1.G visual distinction required |
| I3/I4 sneak-in | Hard OUT; acceptance item 10 |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A sequencing (I1→I2 Shell) | Approved |
| P2-I1 | **ACCEPTED** (2026-08-13) |
| Founder I2 clarifications (§1) | **LOCKED** (2026-08-13) |
| **This I2 definition** | **LOCKED** |
| Build authorization | **AUTHORIZED** (2026-08-13 — Tom: “approved to build”) |
| Implementation | **COMPLETE** on `cursor/p2-iteration-roadmap-3061` |
| FlightSim owner gate (`prove-p2-i2 --flightsim`) | **ACCEPTED** (2026-08-13 · `ok: true` · I1 regression green) |

P2-I2 is **ACCEPTED**. Next roadmap increment per MBRM-001A is **I3 Archive Health & Provider Honesty** (+ TASK-004).
