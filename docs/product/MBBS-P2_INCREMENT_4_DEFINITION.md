# MBBS-P2 Increment 4 — Mixed-Media Find / Explore (Timeline-first)

**Status:** **BUILD AUTHORIZED** (Tom 2026-08-13 — I4 UX Implementation Directive) · Definition aligned to **MBUX-001 v0.4** · **Not ACCEPTED** until FlightSim acceptance test (§8)  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) (sequencing authority)  
**Authority (product):** Locked MBPS-002 · Locked MBEVS-001 v1.0 · MBRM-001A · **P2-I1..I3 ACCEPTED**  
**Authority (UX — Mixed-Media Find / Explore):** **[MBUX-001 v0.4 I4 Mixed-Media Exploration Addendum](MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md)** — where more specific than MBUX-001 v0.3 or earlier I4 drafts, **the addendum governs**  
**Depends on:** P2-I1 (moments) · P2-I2 (shell/context) · P2-I3 (honest coverage / undated)  
**CLI prove (proposed):** `python -m memorybox prove-p2-i4` · `prove-p2-i4 --flightsim`  
**Gate:** Build authorized. **ACCEPTED only when visible UX conforms to MBUX-001 v0.4** + acceptance sequence.

---

## 0. Product intent

I1–I3 proved person-in-media, product shell, and archive honesty.

I4 delivers the primary **Mixed-Media Find / Explore** experience:

> **The Curator explains the find. The mixed-media Library/result canvas is where the owner experiences and works with the find — in one coherent exploration context.**

Governing loop ([MBUX-001 § PURPOSE](MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md)):

**Ask → Refine → Browse → Inspect → Teach/Learn when useful → Close → Continue**

Not: Curator narrative with a small evidence strip beneath it.  
Not: an isolated Timeline page to redesign later.  
Not: separate Photo / Video / Email apps as the default find experience.

---

## 1. Governing UX decisions (from MBUX-001 v0.4 — for definition approval)

These are treated as **approved UX direction** for I4 visible acceptance. Confirm any overrides before build.

### 1.1 Top-level navigation

Primary family destinations (working set):

**Ask · People · Stories · Journal · Artifacts · Family Night · Teach**

Not primary top-level: System Health/Status, provider controls, metadata/transcript panels, Timeline-as-app, Library-internals-as-app.

Archive Health / system issues: surface **contextually** when action is useful (I3 entry may remain reachable from system chrome, not family primary nav).

Stories stay top-level but exist to give meaning/context around people, artifacts, evidence, events, places, moments — not orphan narratives.

### 1.2 Ask = question and command

Typed Ask and STT share one state/command model. Ask may change filters, context, date range, navigation, and result membership; UI must reflect interpretation immediately. Voice is not a separate mode.

### 1.3 Ask visual treatment

After results exist, Ask stays highly visible without dominating vertical space: brand + tagline **“Life doesn’t live in folders.”**; prefer one horizontal row for prompt + field; current query remains visible unless cleared/replaced.

### 1.4 Curator + Library/result canvas

Concise Curator summary orients (counts by media kind, people, stories).  
**Principal working surface** = mixed-media result canvas beneath. Evidence is not a footnote region.

### 1.5 Mixed-media gallery

One gallery of result objects by default (photos, video moments, audio moments, email, SMS, calendar, recipes, documents, artifacts, stories, … as available). Coherent card grammar + media-type cues. Default order newest→oldest unless intent says otherwise.

Density: ~**12+** visible objects on 13″ / iPad landscape when practical; **two rows** current target; user density control (more/smaller vs fewer/larger) **independent** of timeline range / filters / membership.

### 1.6 Quick preview + lightweight filters

Lightweight hover preview; full inspect in modal.  
Small filter set (All / Photos / Video / Audio / Email·Text / Artifacts / Stories / More) + quiet context chips. No permanent advanced filter panel. Direct UI, typed Ask, and STT all mutate the same state.

### 1.7 Unified Timeline / scrub

**One** control: temporal map **and** gallery scrub/navigation (density dots/clusters, active range, playhead, band, L/R handles, **Reset**). No redundant separate timeline + scrubber.

Scrub feel ≈ media scrub (small move = slow gallery advance; larger = faster). Timeline ↔ gallery always synchronized.

### 1.8 Range and precision

Initial range = temporal extent of **matched result set** (not invented life-span padding).  
**Reset** = restore full result extent (not “Full Range”).  
Band inward = explore that period (narrow + raise precision + reapply gallery).  
Handles outward = broaden. Granularity adapts: decades → years → months → days.

### 1.9 Evidence detail modal

Open object in large in-context modal (~85–95% desktop canvas). Do not normally route to a different app screen. Close restores exact explore state (query, context, filters, timeline range/playhead, density, gallery position, scroll).

Media-specific shells per MBUX-001 §12 (photo, video moment @ timeslice, audio, email selectable text → Story/Artifact, etc.).

### 1.10 Contextual Teach / Learn

Teach while inspecting. Photo faces; **video faces only on paused still frames**; voice via transcript span selection. Provenance preserved; Learn/background reprocess must not trap the owner in admin flow.

### 1.11 I4 implementation principle (critical)

> Functionality and UX must be implemented as **one synchronized exploration model**.  
> Timeline must **not** be completed as an isolated timeline page that later needs redesign around mixed-media exploration.  
> Services/state may be built independently; **visible accepted UX must conform to this addendum.**

---

## 2. Clarifications to confirm on approval (light)

| # | Topic | Default under MBUX-001 v0.4 |
|---|--------|-------------------------------|
| Q1 | Host surface for canvas | **Ask result / explore canvas** is primary working find surface; Library is not a separate competing default. Deep links land in the same explore state. |
| Q2 | I2 shell nav vs MBUX top-level | Align family primary nav toward Ask / People / Stories / Journal / Artifacts / Family Night / Teach; demote Status/Timeline/Library-as-app from family primary (system chrome may still reach Archive Health). |
| Q3 | Family Night / Teach in I4 | **Entry points + explore integration** required for nav honesty; deep Family Night program and full Teach productization may be thin if not already built — must not block canvas loop. |
| Q4 | Modal vs Review route | Prefer modal; Review/jump `t=` may power video inside modal or as controlled escape with return-to-exact-state. |
| Q5 | Communications / recipes in gallery | Show when present in result set; empty kinds omit cards (no fake zeros). |
| Q6 | Saved views | Still **OUT → I13** unless pulled later. |

---

## 3. IN scope

### 3.1 Synchronized explore model (required)

- Shared explore state: query, curator summary, filters/chips, result membership, timeline range/playhead, gallery density/position, modal stack.  
- Ask (type + STT commands) mutates that state.  
- Unified timeline scrub ↔ gallery.  
- Mixed-media gallery + density control.  
- Evidence modal with close→exact restore.  
- Contextual Teach/Learn hooks on inspect (I1 face/correct paths reused where possible).  

### 3.2 Scale and honesty

- Windowed/virtualized loading at Immich-scale photo corpora.  
- Undated items reachable without fake dates (group or chip; timeline does not invent extent).  
- Unavailable media kinds omitted or honest — never false empty completeness.  

### 3.3 Preserve I1–I3

Moments + jump `t=` · shell coherence · Archive Health remains owner/system (contextual surface, not family primary).

---

## 4. OUT of scope / deferred

| Deferred | Home |
|----------|------|
| Isolated Timeline app page as ACCEPTED UX | **Forbidden** (MBUX-001 §16) |
| Curator-with-small-evidence-strip as primary find UX | **Forbidden** |
| Full Ask invitation polish / journey chips productization | Separate UX follow-on (Ask command model **is** in I4) |
| Mature Settings / provider admin | **I14** / contextual only |
| Full Dynamic Views | **I13** |
| Kinship inference product | **I6** |
| SMS/email engines beyond gallery/modal when data exists | **I7–I8** (display/link OK) |
| Full spoken-moment STT product | **I9** (voice teach hooks when transcript exists) |
| Cast / multi-user | Deferred / late |

---

## 5. Traceability

| Source | I4 role |
|--------|---------|
| **MBUX-001 v0.4 addendum** | Governs Mixed-Media Find / Explore UX |
| **P2-UX-02 / 03 / 04** | Timeline-first, refine, progressive disclosure |
| **P2-VID-03 / I1** | Moments + jump + face teach |
| **EVS-002** et al. (MBRM-001A I4 set) | Explore acceptance scenarios |
| **P2-I2 shell** | Adjust family primary nav toward MBUX top-level |
| **P2-I3** | Contextual health; honesty |

---

## 6. Prerequisites

- P2-I1..I3 **ACCEPTED**.  
- FlightSim Immich + HVRT moments.  
- Founder **approval of this I4 definition** (incorporating MBUX-001 v0.4).  
- Explicit **Build P2-I4**.

---

## 7. Acceptance corpus (minimum)

Supporting scenarios (still required). **Pass/fail authority is §8.**

| Case | Requirement |
|------|-------------|
| Loop | Ask→Refine→Browse→Modal→Close→Continue without context loss |
| Curator + canvas | Concise curator; gallery is principal work surface |
| Scale | Immich-scale navigable (windowed) when live corpus is used |
| Regression | I1–I3 `--flightsim` green when claiming full FlightSim ACCEPTED |
| Scope | No isolated timeline page ACCEPTED; no evidence-footnote find UX |

---

## 8. Exact acceptance gate (authoritative pass/fail)

**This table is the I4 ACCEPTED gate** — separate from the long UX implementation directive.  
All rows must **pass** on FlightSim for **ACCEPTED**. Fail any row → not ACCEPTED.

| Area | I4 acceptance |
|------|----------------|
| **Ask** | Prompt + entry on one line where practical; Ask remains visible but compact |
| **Gallery** | Mixed-media, two rows, target 12+ visible objects at 13" class viewport |
| **Density** | User can easily show more/smaller or fewer/larger cards |
| **Filters** | Lightweight, immediately applied, common state for mouse/Ask/STT |
| **Timeline** | One unified graphical Timeline/scrubber |
| **Banding** | Dragging a period narrows result and increases precision |
| **Handles** | Widen/narrow current temporal range |
| **Reset** | Restores complete result temporal range |
| **Synchronization** | Timeline changes immediately update Gallery |
| **Scrub** | Timeline can navigate Gallery position |
| **Detail** | Large modal, not new screen |
| **Return** | Closing modal restores exact exploration context |
| **Extensibility** | Same modal shell supports mixed evidence types |
| **Teach-ready** | Photo/paused-video face and transcript/voice learning can plug into modal |
| **Health** | Not top-level |
| **Context** | Query/filter/date/gallery state remain coherent and reusable by Ask/STT |

### 8.1 Demo path (FlightSim)

1. Pull branch; **restart serve** (port **8790**).  
2. Open `/explore/ui?demo=peggy-christmas` (or Ask → Peggy around Christmas).  
3. Walk each §8 row; mark pass/fail.  
4. Optional automated assist: `MEMORYBOX_P1_RUNTIME_HOST=1 python -m memorybox prove-p2-i4 --flightsim` (structural checks only — **manual §8 walk is required for ACCEPTED**).

### 8.2 Out of gate (must not block ACCEPTED)

Perfect visual polish · full Family Night · full Stories redesign · complete Teach product · every evidence-type renderer · full STT engine · full biometric recognition · Archive Health redesign.

---

## 9. Risks & watch items

| Risk | Mitigation |
|------|------------|
| Build isolated timeline first | MBUX-001 §16; ACCEPTED forbids it |
| Curator narrative dominates | Canvas is principal surface |
| Dual scrubber + timeline | Unified control only |
| Modal navigates away | In-context modal + exact restore |
| Nav thrash vs I2 shell | Explicit Q2 align on approval |
| Scope into I7–I9 engines | Display/teach hooks only |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A I3→I4 | Approved direction |
| P2-I1..I3 | **ACCEPTED** |
| MBUX-001 v0.4 I4 addendum | **Approved UX direction** (founder); recorded in-repo |
| **This I4 definition (reworked to MBUX-001)** | **LOCKED** under MBUX-001 v0.4 + Implementation Directive |
| Build / code | **AUTHORIZED** (2026-08-13 — I4 UX Implementation Directive) |
| FlightSim ACCEPTED | **PENDING** — authoritative gate is **§8** (pass/fail table) |

Build is authorized. Do **not** mark ACCEPTED until the Mixed-Media Find acceptance sequence passes.
