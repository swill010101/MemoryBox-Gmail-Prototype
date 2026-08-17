# MBBS-P2 Increment 4 — Mixed-Media Find / Explore

**Status:** **LOCKED** · Combined functionality + UX · Founder clarifications incorporated · **BUILD AUTHORIZED** (2026-08-13) · **Not ACCEPTED** until §8 + §8.1 pass on FlightSim  
**Owner-pass order (Tom 2026-08-17):** When FlightSim / Immich / the box are stable again, **I4 §8 + §8.1 is the first owner pass.** It must **actually work**. Do **not** skip it for MBQL-001, I8, comms LOD, or attachments. Attachments are **not** the I4 holdout (SMS files = P2-BL-I7-01; email files = P2-BL-I8-01).  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md)  
**Authority (product):** Locked MBPS-002 · Locked MBEVS-001 v1.0 · MBRM-001A · **P2-I1..I3 ACCEPTED**  
**Authority (UX):** [MBUX-001 v0.4](MBUX-001_v0.4.md) full baseline (§22 exploration patterns) · historical addendum: [I4 Mixed-Media Exploration Addendum](MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md)  
**Authority (capabilities):** [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) — especially CAP-P2-001 / 025 / 026; planning delta: [MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md](MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md)  
**Visual hierarchy anchor:** Mixed-Media Find mockup (density / calm aesthetic — **not** pixel-perfect spec) · drill-down SoT: [Shared Evidence Viewer + preview inventory](mockups/P2_SHARED_EVIDENCE_VIEWER_AND_PREVIEW.md)  
**Interaction reference (binding):** The **current Explore screen** (`/explore/ui`, branch implementation as of founder confirmation 2026-08-13) is the **accepted interaction reference for I4**. Implementation may improve underneath (providers, data, performance, honesty). **Do not redesign the experience** while wiring it up.  
**Depends on:** P2-I1 (moments + identity correction) · P2-I2 (shell/context) · P2-I3 (honest coverage / undated)  
**CLI prove (assist only):** `python -m memorybox prove-p2-i4` · `prove-p2-i4 --flightsim`  
**ACCEPTED gate:** §8 + §8.1 manual cases. Structural prove does not equal ACCEPTED.

**Founder direction:** Combined I4 direction approved with clarifications. Top-level learn destination labeled **Review & Learn**. **Build authorized.** Current on-screen Explore interaction is the reference — wire/improve implementation without redesigning the UX.

**I4 UI amendment (2026-08-13):** Shared Evidence Viewer + gallery rollover/focus preview authorized (MBUX §22.4–22.6 · CAP-P2-026). Named Places and Living Albums remain out of I4.

---

## 0. Product intent (one sentence)

> **The Curator explains the find. The mixed-media Gallery is where the owner experiences and works with the find — in one coherent exploration context, with a unified Timeline that both maps the dated portion of the eligible result set and scrubs Gallery position.**

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
| Invented Timeline dates presented as real capture dates | Undated off-axis left of Timeline; Undated filter is explicit (§2.7.1) |
| Reset that clears query or type filters | Reset is temporal extent only |

---

## 1. Combined model — functionality and UX are one surface

I4 is **not** “backend timeline first, UX later” and **not** “pretty gallery without shared state.”

### 1.1 Result / Timeline / Gallery state hierarchy (clarification — binding)

| Layer | Defines | Constrains |
|-------|---------|------------|
| **Query + context + type filter** | The **eligible result set** | Everything below |
| **Timeline** | Represents the **dated portion** of that eligible result set (extent, density dots, active range, playhead) | Does not invent membership outside the eligible set |
| **Active Timeline range** | Further constrains which eligible dated items appear in the Gallery | After banding/handles; undated handled per §2.7.1 |
| **Gallery presentation** | Density (size), sort, scroll/visible window | Must **not** change query, filters, membership rules, or Timeline range |
| **Modal / detail** | Shared evidence shell; type-specific body; Teach/Learn on inspect | Close restores explore snapshot, then applies correction consequences (§2.8) |

Services and providers may remain modular underneath. **Visible accepted UX must present one synchronized exploration model** (MBUX-001 §16).

---

## 2. Visible experience (UX + required behavior)

### 2.1 Branding and family navigation

- **MemoryBox** brand + tagline: **“Life doesn’t live in folders.”**
- Family primary destinations (working set):

  **Ask · People · Stories · Journal · Artifacts · Family Night · Review & Learn**

- Top-level learn destination label: **Review & Learn** (founder preference; locked with this build authorization). Backing surface may remain `/review/ui` (I1 Review paths).
- **Not** family primary: Archive Health / Status, provider admin, Timeline-as-app, Library-internals-as-app.
- Stories remain reachable as **contextual meaning** tied to people / evidence / artifacts / events — not a disconnected story-writing product inside I4.
- Family Night: honest **entry point** required; deep FN product **out of I4 acceptance** if thin stub.

### 2.2 Ask (question + command)

**UX**

- After a find exists: Ask stays obvious but compact.
- **“What would you like to see?”** and the Ask entry share **one horizontal row** where screen width permits (wrap only on narrow viewports).
- Current query remains visible unless cleared/replaced.

**Functionality**

- Typed Ask and future STT manipulate the **same** domain/timeline/navigation state as mouse/UI controls.
- Example commands (non-exhaustive):

  - “Only photos.” / “Add video.” / “Clear filters.” / “Show everything.”
  - “Show 2005 through 2011.”
  - “Clear context and go to People.”

- UI must reflect interpretation immediately. No separate voice-only state machine.
- **Equivalence:** clicking a type filter and typing the corresponding Ask command (e.g. Photos vs “Only photos.”) must produce the **same visible filter state** and the **same result interpretation** (§8.1 case E).

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
- **Density target (non-brittle):** the default Gallery should feel **information-rich rather than oversized-card sparse**. On a **13-inch landscape-class** viewport, when the result mix permits: approximately **two rows** and about **10–14** visible objects. Not a hard pixel count; not an artificial cap at the mockup’s exact card count. Larger viewports may expose more.
- Coherent card grammar with media-type cues (photo, video moment, email/text, artifact, story, …).
- Default order: newest → oldest (user may change sort without leaving explore).
- Lightweight hover/focus preview; **not** full detail.
- Calm aesthetic from the Mixed-Media Find mockup (anchor, not pixel spec).

**Functionality**

- Gallery membership = eligible result set (§1.1) further constrained by **active Timeline range** for dated items; undated per §2.7.1.
- Architecture must allow additional evidence types without redesigning the Gallery.
- I4 demo / acceptance must visibly prove at least: **Photo · Video moment · Email/Text · Artifact · Story** (plus undated behavior when present).

### 2.5 Gallery Size (density)

**UX**

- Simple control: **minus** = more/smaller · **plus** = fewer/larger (e.g. Small / Medium / Large).

**Functionality**

- Presentation state **only**. Changing density must **not** alter: query, type filters, result membership, Timeline range, or context (§8.1 case C).

### 2.6 Filters

**UX**

- Lightweight type row (initial): **All · Photos · Video · Email/Text · Artifacts · Stories**
- No large permanent advanced-filter sidebar.

**Functionality**

- Filters live in shared domain state so mouse, typed Ask, and future STT all mutate the same filters.
- Apply immediately to the eligible result set; Timeline updates to the **dated distribution of the filtered eligible set**; Gallery follows (§8.1 case A).

### 2.7 Unified Timeline / scrubber

**UX**

- **One** graphical control beneath the Gallery (not Gallery scrubber + separate Timeline).
- Shows: dated result extent, density dots/clusters, current range, range handles, playhead, **Reset**.
- May show an **“Undated”** indication/count **outside** the dated axis (not on a fake year).
- Helper affordance OK (e.g. nudge / hint text). Labels: use **Reset** — not “Full Range” or “Life Span.”

**Functionality**

| Behavior | Required effect |
|----------|-----------------|
| What Timeline represents | The **dated portion** of the current eligible result set (query + context + type filter) |
| Initial extent | Full temporal extent of **dated** items in that eligible set |
| Band a period (e.g. 2005–2011) | Active explore period; raise precision as appropriate; **immediately** update Gallery to matching dated items in range; preserve query/context/type filter |
| Handles | Broaden or narrow selected range |
| **Reset** | Restore the **full temporal extent** of the **current** query + context + type-filter result set. **Does not** clear the query. **Does not** clear type filters. |
| Precision | Progressive: years → months → days where data permits |
| Scrub / playhead | See §2.7.2 |
| Sync | Timeline and Gallery are two views of the same exploration state — **no drift** |

#### 2.7.1 Undated evidence (clarification — binding)

Founder confirmation 2026-08-13 (updated — off-axis filter):

- Undated evidence that otherwise matches query/context/type filter **always remains in the Gallery** when the Undated filter is off. Date-banding must **not** drop it.
- Undated items sort to the **oldest end** of the gallery group (lower / left end of the chronological order).
- Undated are **not** plotted on the dated Timeline axis.
- An **Undated** control sits **to the left of the Timeline** (off-axis). Clicking it **sets the Undated filter** (gallery = undated only). Click again clears it.
- The same **Undated** filter appears in the **filter area** when undated results exist or the filter is active.
- Ask/STT: `Only undated.` / `Clear undated.` / `Clear filters.` share the same state.
- If the eligible set has **no** dated peers, undated stay in the Gallery; the axis does not invent a calendar day.
- Reset restores full temporal extent without clearing type/place/undated filters (§8.1 case B).

**Person library honesty (founder 2026-08-13):** Older Immich assets with real EXIF/taken metadata must not be dropped because Ask only fetched the newest page. Person finds paginate Immich toward the full person library (photos + videos as Immich returns them) so Timeline extent matches Immich life span (e.g. mid-century → present), not a fake “recent years only” window. **Do not trust Immich `assets.total` as an early-stop** — it often mirrors page size (~100–250) and falsely capped Explore near 120. Cap may still apply on extremely large libraries; undated remain available via the Undated control left of Timeline + filter bar.

**Person library scope (founder 2026-08-13):** A person Ask must not exceed that person’s Immich person-page count by padding with newest unfiltered library pages (e.g. Eugene Immich 661 ending 2013 must not become ~912 with 2026 gallery dates). Successful `personIds` retrieval stands alone; name fallback is only for empty/stale mappings and must resolve Immich person ids — never bare text/metadata search.

#### 2.7.2 Proportional scrub (clarification — binding)

Dragging the Timeline playhead **continuously** moves the Gallery through **chronological result position**.

Movement should feel **proportional and controllable** across both dense and sparse periods.

What matters for acceptance:

- **No drift** between Timeline position and Gallery neighborhood  
- **No huge unexpected jumps**  
- Moving into **2010** gets you to the **2010 neighborhood** of results  
- Gallery movement and Timeline position remain **synchronized**

Gesture implementation may choose the technically appropriate model; the user mental model above is required.

### 2.8 Evidence detail (modal) + Teach/Learn proof

**UX**

- Clicking a Gallery item opens a **large in-context modal** (~85–95% of usable canvas on desktop), not a new top-level page.
- Closing returns to exploration **without dumping the user into a new default state**.

**Functionality — correction-aware restore on close (clarification — binding)**

1. Restore the **prior exploration state and position** (Ask/query, context chips, filters, Timeline range, playhead, density, Gallery location, reasonable scroll).  
2. **Then** incorporate any consequences of the just-completed correction (e.g. updated face identity) so the result can reflect the correction **without resetting** exploration to Home or a fresh default find.

**Modal architecture**

- One shared evidence-detail shell; type-specific content bodies.
- Must not prevent later: Photo, Video, Audio, Email, SMS, Calendar, Recipe, Artifact, Document, Story.
- Shared structure must **not** require a separate top-level detail architecture for future voice/transcript teaching.

**Teach / Learn acceptance (clarification — replaces “architecture-only Teach-ready”)**

- I4 **must demonstrate at least one visible contextual Teach/Learn affordance** using an **already-supported I1 identity-correction path** (photo and/or paused video moment as I1 supports).
- Continuous face tracking during video playback is **not** required.
- Full Teach product, full biometric suite, and complete voice/transcript teaching UI remain **out of gate**; the modal must stay structurally open to them.
- Acceptance: §8 row **Teach proof** + §8.1 case D.

---

## 3. Implementation discipline (when wiring / improving under the locked experience)

1. **Do not redesign** the Explore interaction, layout hierarchy, or control model relative to the **accepted interaction reference** (current Explore screen). Wire live data and harden behavior underneath it.  
2. Reuse working backend/domain/provider behavior; do not rewrite services merely to change visuals.  
3. Honor state hierarchy §1.1; separate gallery presentation from domain/timeline.  
4. Do not hard-code demo fixtures into product logic.  
5. Synchronized interaction is required — static mock cards are not enough.  
6. If a constraint makes an accepted §8 / §8.1 behavior materially impractical: **stop and report** constraint, affected behavior, smallest architectural change, tradeoff — do **not** silently redesign UX.

---

## 4. IN / OUT

### 4.1 IN for I4 acceptance

- Synchronized explore surface (Ask + curator + gallery + unified timeline + modal restore).  
- State hierarchy §1.1; Reset / undated / scrub / density clarifications.  
- Shared state usable by mouse, typed Ask, and future STT (with filter equivalence).  
- Family nav alignment; Health not top-level; Teach vs Review & Learn label per founder lock.  
- **Visible** I1 identity-correction Teach/Learn proof in modal + correction-aware return.  
- Demo/fixture and/or live path sufficient to prove §8 and §8.1 on FlightSim.  
- Scale/honesty direction: windowed loading; undated without invented dates; no false empty completeness.

### 4.2 OUT (must not block ACCEPTED)

| Out | Notes |
|-----|--------|
| Perfect final visual polish | Mockup is hierarchy anchor |
| Full Family Night UX | Entry OK |
| Full Stories redesign | Contextual stories OK |
| Complete Teach / Review & Learn product | One visible I1 correction proof required; rest deferred |
| All future evidence-type renderers | Shell must allow them |
| Complete STT engine | Same command path as typed |
| Full biometric recognition | I1 path reused for proof |
| Continuous face tracking in playing video | Not required |
| Archive Health redesign | Remains I3 / contextual |
| Saved views / Dynamic Views | → I13 |
| Kinship product | → I6 |
| Full SMS/email engines | Display/link OK → I7–I8 |

---

## 5. Traceability

| Source | Role in I4 |
|--------|------------|
| MBUX-001 v0.4 full | UX authority for Mixed-Media Find / Explore (§22); addendum historical |
| Mixed-Media Find mockup | Visual hierarchy / density / calm aesthetic (not pixel spec) |
| **Current Explore screen** | **Accepted I4 interaction reference** — do not redesign while wiring |
| Founder clarifications 2026-08-13 | State hierarchy, Reset, undated, density, scrub, correction-aware restore, Teach proof, Review & Learn |
| §8 / §8.1 (this doc) | Authoritative ACCEPTED pass/fail |
| P2-I1 | Moments, jump `t=`, **identity correction path for Teach proof** |
| P2-I2 | Shell / context stack |
| P2-I3 | Honesty; Health contextual; undated honesty |
| EVS-002 et al. (MBRM-001A) | Explore scenarios |

---

## 6. Prerequisites

- P2-I1..I3 **ACCEPTED**.  
- FlightSim Immich + HVRT moments available for live Teach-proof and regression when claiming full ACCEPTED with live media.  
- Founder **LOCK** of this revised combined definition (including Teach vs Review & Learn label).  
- Explicit **Build** order — **not implied** until LOCKED.

---

## 7. Supporting acceptance corpus

Supporting scenarios; **pass/fail authority remains §8 + §8.1.**

| Case | Requirement |
|------|-------------|
| Loop | Ask→Refine→Browse→Modal→Close→Continue without context loss |
| Curator + canvas | Concise curator; Gallery is principal work surface |
| Hierarchy | Query/filter defines eligible set; Timeline = dated portion; range constrains Gallery |
| Scale | Immich-scale navigable (windowed) when live corpus is used |
| Regression | I1–I3 `--flightsim` green when claiming full FlightSim ACCEPTED |
| Scope | No isolated timeline page; no evidence-footnote find UX |

---

## 8. Exact acceptance gate (authoritative pass/fail)

All rows must **pass** on FlightSim for **ACCEPTED**. Fail any row → not ACCEPTED.

| Area | I4 acceptance |
|------|----------------|
| **Ask** | Prompt + entry on one line where practical; Ask remains visible but compact |
| **Gallery** | Mixed-media; information-rich default; ~two rows and ~10–14 objects on 13″ landscape-class when mix permits (non-brittle) |
| **Density** | User can show more/smaller or fewer/larger; presentation-only |
| **Filters** | Lightweight, immediately applied, common state for mouse/Ask/STT |
| **Timeline** | One unified graphical Timeline/scrubber representing dated eligible results |
| **Banding** | Dragging a period narrows dated Gallery results and increases precision; preserves query/filters |
| **Handles** | Widen/narrow current temporal range |
| **Reset** | Restores full temporal extent of **current** query + context + type-filter set; does **not** clear query or type filters |
| **Undated** | Always in Gallery (filter off); off-axis left of Timeline; click sets Undated filter (also in filter bar) |
| **Synchronization** | Timeline changes immediately update Gallery; no drift |
| **Scrub** | Playhead continuously moves Gallery through chronological neighborhood; proportional/controllable; no huge unexpected jumps |
| **Detail** | Large modal, not new screen |
| **Return** | Close restores prior exploration state/position, then applies correction consequences without dumping to a new default |
| **Extensibility** | Same modal shell supports mixed evidence types; no separate top-level detail architecture required for future voice/transcript teach |
| **Teach proof** | At least one visible contextual Teach/Learn affordance via existing **I1 identity-correction** path |
| **Health** | Not top-level |
| **Context** | Query/filter/date/gallery state remain coherent and reusable by Ask/STT |
| **Nav label** | Family primary includes **Review & Learn** |

### 8.1 Five mandatory manual gate cases

#### A. Filter + Timeline interaction

1. Start with Peggy (or equivalent person) results.  
2. Select **Videos**.  
3. Timeline updates to the **dated video-result** distribution.  
4. Band a range.  
5. Gallery immediately shows only matching **video moments in that range**.  
6. **Reset** restores full temporal extent **without clearing** the Videos filter.

#### B. Undated evidence

1. A matching undated object remains discoverable in the Gallery (**including** when date-banded).  
2. It sorts to the **oldest end** of the gallery group.  
3. It is **not** plotted on the dated Timeline axis; **Undated** appears **left of the Timeline**.  
4. Clicking **Undated** (timeline-left or filter bar) sets the Undated filter; gallery shows undated only.  
5. Banding must **not** drop undated from the Gallery when the Undated filter is off.

#### C. Density independence

1. Change Gallery Size **Small → Large → Small**.  
2. Query, filter, Timeline range, and result membership remain **unchanged**.

#### D. Teach and return

1. Open a **real** photo or video moment.  
2. Correct an **I1-supported** face identity.  
3. Close modal.  
4. Return to the **same exploration context** (position/state preserved).  
5. Updated identity can influence the result **without resetting** exploration.

#### E. Ask command equivalence

1. Click **Photos** filter.  
2. Clear it.  
3. Type **“Only photos.”**  
4. Both paths produce the **same visible filter state** and the **same result interpretation**.

### 8.2 FlightSim walk (after LOCK + Build)

**When the box is back up, do this walk before any other owner pass.** Do not rubber-stamp. Fail any §8.1 case → not ACCEPTED.

1. Pull agreed branch; **restart serve** (port **8790**). Immich/HVRT must stay up long enough for **case D** (real photo or video identity correction).  
2. Open Mixed-Media Find.  
3. Walk every §8 row and every §8.1 case; mark pass/fail.  
4. `prove-p2-i4 --flightsim` is structural assist only — **manual gate required for ACCEPTED**.

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Treat Timeline as separate app | Forbidden for ACCEPTED; unified control only |
| Reset clears filters | Explicitly forbidden (§2.7) |
| Invented capture dates presented as fact | Undated stays off the dated axis; filter is explicit |
| Brittle “exactly 12 cards” density | Non-brittle 10–14 / two-row target (§2.4) |
| Scrub jumps / drift | Proportional continuous neighborhood sync (§2.7.2) |
| Modal close dumps to Home/default | Correction-aware restore (§2.8) |
| Teach-ready in name only | Mandatory visible I1 correction proof (§2.8, §8.1 D) |
| Dual scrubber + timeline | One control |
| Scope into full Teach / STT / FN / engines | Out of gate (§4.2) |

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| MBRM-001A I3→I4 | Approved direction |
| P2-I1..I3 | **ACCEPTED** |
| MBUX-001 v0.4 full + MBCAP-001 v0.2 | Approved UX + capability catalogs (ingested 2026-08-13) |
| Mixed-Media Find mockup | Visual hierarchy / density / calm aesthetic (not pixel spec) |
| **Current Explore screen** | **Accepted I4 interaction reference** (founder 2026-08-13) |
| Combined I4 direction | **Approved** with clarifications |
| **This revised definition** | **LOCKED** |
| Teach vs Review & Learn label | **Review & Learn** (locked) |
| Build | **AUTHORIZED** (2026-08-13) |
| FlightSim ACCEPTED | **PENDING** — §8 + §8.1 · **first owner pass** when box is stable (Tom 2026-08-17); must work, do not skip |

Build is authorized against this locked text. **Do not redesign** the Explore experience while wiring implementation underneath it. Do **not** mark ACCEPTED until §8 and §8.1 pass on FlightSim.
