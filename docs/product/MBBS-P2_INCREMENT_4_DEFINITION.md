# MBBS-P2 Increment 4 — Mixed-Media Find / Explore

**Status:** **FOR REVIEW** · Functionality + UX combined in one definition · **NO BUILD** on this revision  
**Prior code / prior build authorization:** May exist on branch for earlier directive work; **this document supersedes fragmented I4 drafts for product review.** Do not treat this revision as a new build order.  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)  
**Authority (product):** Locked MBPS-002 · Locked MBEVS-001 v1.0 · MBRM-001A · **P2-I1..I3 ACCEPTED**  
**Authority (UX):** [MBUX-001 v0.4 I4 Mixed-Media Exploration Addendum](MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md) — where more specific, the addendum governs UX detail  
**Visual anchor:** Mixed-Media Find mockup (hierarchy / density / calm aesthetic — **not** pixel-perfect spec)  
**Depends on:** P2-I1 (moments) · P2-I2 (shell/context) · P2-I3 (honest coverage / undated)  
**CLI prove (assist only):** `python -m memorybox prove-p2-i4` · `prove-p2-i4 --flightsim`  
**ACCEPTED gate:** §8 only (manual FlightSim walk). Structural prove does not equal ACCEPTED.

---

## 0. Product intent (one sentence)

> **The Curator explains the find. The mixed-media Gallery is where the owner experiences and works with the find — in one coherent exploration context, with a unified Timeline that both maps time and scrubs the Gallery.**

Governing loop:

**Ask → Refine → Browse → Inspect → Teach/Learn when useful → Close → Continue**

### What I4 is not

| Forbidden as ACCEPTED UX | Why |
|--------------------------|-----|
| Isolated Timeline app page | Would force later redesign around exploration |
| Curator narrative with a small evidence strip | Gallery is the work surface, not a footnote |
| Separate primary Photo / Video / Email result apps for this find | One mixed-media canvas |
| Voice-only state logic separate from typed Ask | One command/state model |
| Archive Health / Status as family top-level | Contextual / system only |

---

## 1. Combined model — functionality and UX are one surface

I4 is **not** “backend timeline first, UX later” and **not** “pretty gallery without shared state.”

| Layer | Responsibility | Must stay coherent with |
|-------|----------------|-------------------------|
| **Domain / query** | Ask text, curator summary, context chips, type filters, result membership | Ask (typed + future STT), filter UI |
| **Timeline** | Result date extent, active range, playhead, precision (years→months→days) | Gallery membership + position |
| **Gallery presentation** | Density (size), sort, scroll/visible window | Must **not** change query, filters, membership, or timeline range |
| **Modal / detail** | Open evidence in shared shell; type-specific body | Close restores **exact** explore snapshot |

Services and providers may remain modular underneath. **Visible accepted UX must present one synchronized exploration model** (MBUX-001 §16).

---

## 2. Visible experience (UX + required behavior)

### 2.1 Branding and family navigation

- **MemoryBox** brand + tagline: **“Life doesn’t live in folders.”**
- Family primary destinations:

  **Ask · People · Stories · Journal · Artifacts · Family Night · Teach**

- **Not** family primary: Archive Health / Status, provider admin, Timeline-as-app, Library-internals-as-app.
- Stories remain reachable as **contextual meaning** tied to people / evidence / artifacts / events — not a disconnected story-writing product inside I4.
- Family Night / Teach: honest **entry points** required; deep FN / full Teach product **out of I4 acceptance** if thin stubs.

### 2.2 Ask (question + command)

**UX**

- After a find exists: Ask stays obvious but compact.
- **“What would you like to see?”** and the Ask entry share **one horizontal row** where screen width permits (wrap only on narrow viewports).
- Current query remains visible unless cleared/replaced.

**Functionality**

- Typed Ask and future STT manipulate the **same** domain/timeline/navigation state.
- Example commands (non-exhaustive):

  - “Only photos.” / “Add video.” / “Clear filters.” / “Show everything.”
  - “Show 2005 through 2011.”
  - “Clear context and go to People.”

- UI must reflect interpretation immediately. No separate voice-only state machine.

### 2.3 Curator result

**UX**

- Concise summary **above** the Gallery (orients; does not replace browsing).
- Context chips (e.g. Peggy · Christmas · 1998–2021).
- Visual hierarchy matches mockup: curator/result relationship is secondary to Gallery as work surface, but clearly present.

**Functionality**

- Summary reflects current find (counts by kind when known).
- Chips are part of shared context state (Ask/STT can clear/change later).
- Fixtures/demo data may prove UX; **do not hard-code Peggy into product logic.**

Example fixture orientation:

> Peggy around Christmas  
> “I found 23 memories of Peggy around Christmas, including 14 photos, two video moments, six emails, and a story Rick told.”

### 2.4 Mixed-media Gallery (principal canvas)

**UX**

- One gallery of mixed result cards (not separate primary result pages per type).
- Target: **~12+ visible objects in two rows** on 13″ / iPad-landscape class when practical; larger viewports may show more.
- Coherent card grammar with media-type cues (photo, video moment, email/text, artifact, story, …).
- Default order: newest → oldest (user may change sort without leaving explore).
- Lightweight hover/focus preview; **not** full detail.
- Calm aesthetic and density language from the Mixed-Media Find mockup (anchor, not pixel spec).

**Functionality**

- Result membership driven by domain query + filters + active timeline range.
- Architecture must allow additional evidence types without redesigning the Gallery.
- I4 demo must visibly prove at least: **Photo · Video moment · Email/Text · Artifact · Story**.

### 2.5 Gallery Size (density)

**UX**

- Simple control: **minus** = more/smaller · **plus** = fewer/larger (e.g. Small / Medium / Large).

**Functionality**

- Presentation state **only**. Changing density must **not** alter: query, filters, result membership, Timeline range, or context.

### 2.6 Filters

**UX**

- Lightweight type row (initial): **All · Photos · Video · Email/Text · Artifacts · Stories**
- No large permanent advanced-filter sidebar.

**Functionality**

- Filters live in shared domain state so mouse, typed Ask, and future STT all mutate the same filters.
- Apply immediately to Gallery (and Timeline density dots as appropriate).

### 2.7 Unified Timeline / scrubber

**UX**

- **One** graphical control beneath the Gallery (not Gallery scrubber + separate Timeline).
- Shows: result date extent, density dots/clusters, current range, range handles, playhead, **Reset**.
- Helper affordance OK (e.g. nudge / hint text). Labels: use **Reset** — not “Full Range” or “Life Span.”

**Functionality**

| Behavior | Required effect |
|----------|-----------------|
| Initial extent | Date range of **current result set** (e.g. demo 1998–2021) |
| Band a period (e.g. 2005–2011) | Set active explore period; raise precision as appropriate; **immediately** update Gallery; preserve other query/context |
| Handles | Broaden or narrow selected range |
| Reset | Restore complete temporal extent of current query/result |
| Precision | Progressive: years → months → days where data permits |
| Scrub / playhead | Navigate Gallery position (small move ≈ slow; farther ≈ faster) |
| Sync | Timeline and Gallery are two views of the same result state — **no drift** |

### 2.8 Evidence detail (modal)

**UX**

- Clicking a Gallery item opens a **large in-context modal** (~85–95% of usable canvas on desktop), not a new top-level page.
- Closing returns to the **exact** prior exploration state.

**Functionality — restore on close (required)**

Same Ask/query · context chips · filters · Timeline range · playhead/scrub · Gallery density · Gallery location · reasonable scroll.

**Modal architecture**

- One shared evidence-detail shell; type-specific content bodies.
- Must not prevent later: Photo, Video, Audio, Email, SMS, Calendar, Recipe, Artifact, Document, Story.
- I4 need not complete every renderer.

**Teach / Learn readiness (not full Teach product)**

- Preserve room for contextual Teach/Learn on the modal.
- Photos and **paused video frames**: face boxes assign/reassign/unassign/adjust/remove/add; Learn from confirmed evidence.
- Continuous face tracking during video playback **not** required.
- Video/audio: permit time-aligned transcript, speech-span selection, speaker ID, Learn from voice.
- Do not architect the modal so these become difficult later.

---

## 3. Implementation discipline (when build is later re-authorized)

1. Reuse working backend/domain/provider behavior; do not rewrite services merely to match visuals.  
2. Separate domain, timeline, gallery presentation, and modal state (§1).  
3. Do not hard-code demo fixtures into product logic.  
4. Do not implement the mockup as static cards — synchronized interaction is required.  
5. If a constraint makes an accepted §8 behavior materially impractical: **stop and report** constraint, affected behavior, smallest architectural change, tradeoff — do **not** silently redesign UX.

---

## 4. IN / OUT

### 4.1 IN for I4 acceptance

- Synchronized explore surface (Ask + curator + gallery + unified timeline + modal restore).  
- Shared state usable by mouse, typed Ask, and future STT.  
- Family nav alignment; Health not top-level.  
- Teach-ready modal hooks (not full Teach UX).  
- Demo/fixture path sufficient to prove §8 on FlightSim.  
- Scale/honesty direction: windowed loading; undated items without invented timeline dates; no false empty completeness (full Immich-scale polish may continue after ACCEPTED if §8 passes on demo + live smoke).

### 4.2 OUT (must not block ACCEPTED)

| Out | Notes |
|-----|--------|
| Perfect final visual polish | Mockup is hierarchy anchor |
| Full Family Night UX | Entry OK |
| Full Stories redesign | Contextual stories OK |
| Complete Teach workflow | Hooks only |
| All future evidence-type renderers | Shell must allow them |
| Complete STT engine | Same command path as typed |
| Full biometric recognition | Face/voice teach paths prepared |
| Archive Health redesign | Remains I3 / contextual |
| Saved views / Dynamic Views | → I13 |
| Kinship product | → I6 |
| Full SMS/email engines | Display/link OK → I7–I8 |

---

## 5. Traceability

| Source | Role in I4 |
|--------|------------|
| MBUX-001 v0.4 addendum | UX authority for Mixed-Media Find / Explore |
| Mixed-Media Find mockup | Visual hierarchy / density / calm aesthetic anchor |
| I4 UX Implementation Directive | Interaction model (do not redesign without approval) |
| §8 gate (this doc) | Authoritative ACCEPTED pass/fail |
| P2-I1 | Moments, jump `t=`, face teach paths |
| P2-I2 | Shell / context stack |
| P2-I3 | Honesty; Health contextual |
| EVS-002 et al. (MBRM-001A) | Explore scenarios |

---

## 6. Prerequisites

- P2-I1..I3 **ACCEPTED**.  
- FlightSim Immich + HVRT moments available for live regression when claiming full ACCEPTED with live media.  
- Founder **approval of this combined definition**.  
- Explicit **Build** (or continue-build) order — **not implied by this FOR REVIEW revision**.

---

## 7. Supporting acceptance corpus

Supporting scenarios; **pass/fail authority remains §8.**

| Case | Requirement |
|------|-------------|
| Loop | Ask→Refine→Browse→Modal→Close→Continue without context loss |
| Curator + canvas | Concise curator; Gallery is principal work surface |
| Scale | Immich-scale navigable (windowed) when live corpus is used |
| Regression | I1–I3 `--flightsim` green when claiming full FlightSim ACCEPTED |
| Scope | No isolated timeline page; no evidence-footnote find UX |

---

## 8. Exact acceptance gate (authoritative pass/fail)

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

### 8.1 FlightSim walk (after a future build approval)

1. Pull agreed branch; **restart serve** (port **8790**).  
2. Open Mixed-Media Find (e.g. `/explore/ui?demo=peggy-christmas` or Ask → Peggy around Christmas).  
3. Walk each §8 row; mark pass/fail.  
4. `prove-p2-i4 --flightsim` is structural assist only — **manual §8 walk required for ACCEPTED**.

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Treat Timeline as separate app | Forbidden for ACCEPTED; unified control only |
| Curator dominates canvas | Gallery is principal surface |
| Dual scrubber + timeline | One control |
| Modal navigates away | In-context modal + exact restore |
| Density coupled to filters/range | Density is presentation-only |
| Silent UX redesign for convenience | Stop condition (§3.5) |
| Scope into Teach / STT / FN / engines | Out of gate (§4.2) |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A I3→I4 | Approved direction |
| P2-I1..I3 | **ACCEPTED** |
| MBUX-001 v0.4 | Approved UX direction (recorded) |
| Mixed-Media Find mockup | Visual hierarchy anchor (not pixel spec) |
| **This combined I4 definition** | **FOR REVIEW** |
| Build on this revision | **NO BUILD** — review only |
| FlightSim ACCEPTED | **PENDING** — §8 after agreed build/review cycle |

**Review ask:** Approve, amend, or reject this combined functionality+UX definition.  
**Do not** issue a new build from this document until Tom explicitly authorizes build (or continue-build) against the approved text.
