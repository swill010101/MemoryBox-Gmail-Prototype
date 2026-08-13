# MBBS — P2-I5 Universal Person Surfaces · Product Request Document

**Status:** DRAFT — awaiting Tom sign-off · **No build until approved**  
**Date:** 2026-08-13  
**Owner:** Tom  
**Increment:** P2-I5 (MBRM-001A) — Universal Person Surfaces · F+U  

**Authority**
- Visual / interaction lock: approved mockup *Universal Person Surfaces* (Peggy Smith exemplar, 2026-08-13)
- Roadmap home: [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) § P2-I5
- UX language: [MBUX-001 v0.4](MBUX-001_v0.4.md) (§4.3 People as anchors; Context Explorer)
- Capability: TASK-001 remainder across Story/Journal/Library/Artifact; CAP-P2 person identity surfaces
- Reuse: I4 shared Explore state (Ask chips, Gallery, Timeline, Map) — **do not fork a Person-only search path**

---

## 1. Problem

I4 delivered high-volume Explore (Ask → Gallery / Timeline / Map) with composable WHO/WHEN/WHERE.  
People remain a second-class surface: `/people/ui` is a light admin/profile form, not the Person-as-anchor experience MBUX requires.

Owners think in people (“Show Peggy at Christmas”), not folders. Without a Person surface that reuses the same exploration model, Person work stays split across Ask, Immich teach, and thin profile pages.

**Why now:** I4 is accepted. I5 is the next MBRM-001A increment. The visual/interaction model is now locked.

---

## 2. Visual & interaction lock (non-negotiable)

The approved mockup is the **interaction architecture**. Do **not** redesign it.

| Locked | Rule |
|--------|------|
| Dark theme | Preserve dark Person surface look (not Explore light chrome unless Tom revisits) |
| Compact Person header | Avatar, name, relationship + life span, memory-count summary; Edit / Relationships / Learn |
| Person-scoped Ask | Labeled “Ask about {Person}”; chip locks Person; same Ask interpretation as Explore |
| Mixed-media gallery | Photos, Video, Audio, Email/Text, Artifacts, Stories in one grid |
| Synchronized Timeline | Same band ↔ gallery contract as I4 |
| Gallery / Map modes | Same shared exploration state |
| Compact footer | About · Family · Learn — secondary to exploration, not a dashboard of competing cards in the hero |
| Highlights / All Memories | View mode toggle above filters |

**Allowed:** minor responsive layout tweaks (stacking, density, breakpoints).  
**Not allowed:** changing the interaction model, introducing a separate Ask-only path, or turning the first viewport into a multi-panel dashboard.

---

## 3. Success criteria

How we’ll know I5 works:

1. Opening a Person shows the locked layout (header → Person Ask → gallery/filters → Timeline → About/Family/Learn).
2. `Ask about Peggy` + `Show Peggy at Christmas` uses the **same** query plan / chips / temporal windows / gallery-timeline-map sync as Explore I4 (Person chip pre-scoped).
3. Mixed-media types appear in one gallery with type filters (All / Photos / Video / Audio / Email/Text / Artifacts / Stories / Location where Map is available).
4. Timeline range and holiday/year filters update the gallery immediately (I4 contract).
5. About / Family / Learn show real MB Person / relationship / teach stats when data exists; empty states are honest (no invented facts).
6. Edit / Relationships / Learn navigate to existing Person profile / teach flows without breaking the surface.
7. FlightSim manual acceptance of the locked interaction (cases below) passes.

---

## 4. Scope

### In (I5)

- Person page shell matching the locked mockup (dark theme).
- Person-scoped Ask wired to existing `plan_ask` + Explore find/retrieve (Person pre-filled / locked).
- Mixed-media gallery + type filters + Gallery/Map + Timeline sync (reuse I4 Explore modules where practical).
- Compact About (name, relationship, birth, place when recorded).
- Compact Family row (relationship edges when recorded; + Add family → existing relationship UX).
- Compact Learn (confirmed faces / video appearances / voice examples when available; Explore/Learn CTA).
- Highlights vs All Memories (Highlights may be a thin ranked subset or “recent + holiday-dense” v1 — must be defined in acceptance).
- Park approved mockup asset under `docs/source/mockups/` when PNG is available.

### Out (do not block I5)

- Full kinship tree visualization (I6)
- Complete Living Album product UI
- Full visual setting → Place inference
- Redesign of global shell / Explore light theme to match Person dark (unless Tom explicitly expands)
- New Ask parser (reuse I4)
- Multi-user personal context (CAP-P2-022)
- Automatic Trip inference

---

## 5. Constraints & dependencies

| Constraint | Detail |
|------------|--------|
| Shared state | Person Ask **must** mutate the same exploration state model as Explore (chips, temporal windows, place, media type) |
| No inventing | About / Family / Learn only from MB People facts, relationships, life events, Immich mappings |
| I4 reuse | Prefer extracting shared gallery/timeline/map widgets from Explore rather than copying with drift |
| MBUX | People are anchors, not folders; evidence may involve many people |
| Responsive | Compact header and footer may stack; Ask + gallery + timeline stay primary |

**Dependencies:** I4 Ask/Explore accepted; MB Person + relationships + facts (I9A); Immich person mapping (I1).

---

## 6. Edge cases

- Person with zero media → honest empty gallery; Ask still works.
- First-name Ask inside Person scope (`Show me at Christmas`) → Person chip stays locked; do not open “Me {Name}” place pin regression.
- Holiday without year → all-years windows (I4 behavior).
- Missing birth / relationship / place → omit or “Not recorded,” never fabricate.
- Ambiguous family edges → disclose; don’t pick silently.
- Highlights with sparse archive → fall back to All Memories honestly.

---

## 7. Build plan (sequencing — after sign-off only)

1. Park mockup PNG + this PRD as authority.
2. Person route shell (dark): header + Ask + empty gallery/timeline chrome.
3. Wire Person-scoped find to I4 Explore state (reuse JS modules or shared bundle).
4. Type filters + Gallery/Map + Timeline sync.
5. About / Family / Learn data bindings.
6. Highlights v1 policy + acceptance.
7. FlightSim prove + manual gate.

---

## 8. Acceptance cases (draft)

| # | Action | Expect |
|---|--------|--------|
| A | Open Peggy Person | Locked layout; Person chip / scope = Peggy |
| B | Ask `Show Peggy at Christmas` | Christmas all-years windows; gallery + timeline sync; no fake place pin |
| C | Filter Photos / Stories | Type filter updates gallery; Timeline follows dated eligible set |
| D | Map mode | Map reflects current result set when GPS exists |
| E | About / Family / Learn | Real data or honest empty; no invention |
| F | Edit / Relationships / Learn | Reach existing flows; return to Person surface |

---

## 9. Open questions for Tom

1. **Highlights v1:** What ranks into Highlights for I5 — recent N, holiday-dense, owner-pinned, or defer Highlights to “same as All” until a later increment?
2. **Theme:** Person surface stays dark while Explore stays light — intentional dual chrome for I5, or converge later?
3. **Audio filter:** Include only when Spoken Moments (I9) data exists, or show empty Audio tab now?
4. **Location pill:** Same as Explore Map entry, or a Place chip filter?
5. **Mockup asset:** Confirm filename/path to park under `docs/source/mockups/` (image was approved in chat; PNG should be filed).
6. **Route:** `/people/ui?person=…` evolve in place, or new `/people/{id}` Person surface with list remaining at `/people/ui`?

---

## 10. Sign-off

**Visual/interaction lock:** ACCEPTED by Tom (2026-08-13) via approved mockup.  

**Build authorization:** ☐ Not yet · ☐ Approved to build I5 per this PRD  

Tom: reply with answers to §9 (or “defaults OK”) and explicit **approve build** / **revise PRD** / **park only**.
