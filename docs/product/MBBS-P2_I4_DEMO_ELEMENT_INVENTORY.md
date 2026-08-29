# P2-I4 Explore — Demo element inventory (pre-wiring)

**Status:** Analysis only · **No redesign** · Interaction reference remains current Explore screen  
**Branch context:** `cursor/p2-i4-mixed-media-explore-3061`  
**Demo path:** `/explore/ui?demo=peggy-christmas` → `GET /explore/api/demo/peggy-christmas`  
**Purpose:** Classify every demo element before coding live wiring.

**Classification key**

| Class | Meaning |
|-------|---------|
| **A — Real-backed** | Explore (or shared product) already uses live MemoryBox functionality for this behavior |
| **B — Backend exists; Explore uses fixture** | Production APIs/services exist; Explore still loads demo/fixture data for this element |
| **C — Partial** | Some live path + some fixture/stub; incomplete for acceptance on live corpus |
| **D — Missing** | No usable product path yet; would need new work to back the element |
| **E — Deferred by I4** | Explicitly out of I4 acceptance gate; stub/entry OK |

---

## 1. Surface chrome & navigation

| Element | Class | Notes |
|---------|-------|-------|
| MemoryBox brand + tagline | **A** | Product chrome; Explore page + shell |
| Family nav: Ask, People, Stories, Journal, Artifacts | **A** | Live routes (`/ask/ui`, `/people/ui`, `/story/ui`, `/journal/ui`, `/artifact/ui`) |
| Family nav: Review & Learn → `/review/ui` | **A** | Live Review surface (I1 teach/box paths) |
| Family nav: Family Night | **E** | Thin stub page only; full FN out of I4 |
| Explore page hides dark shell bar / uses own light chrome | **A** | Intentional Explore presentation (interaction reference) |
| System: Library, Archive Health, Settings, Export | **A** / **E** | Live routes; not family primary (Health intentionally not top-level) |
| Ask → “Peggy around Christmas” redirect to Explore demo | **C** | Real Ask UI exists; this journey **bypasses** `POST /ask` and hard-routes to fixture Explore |

---

## 2. Ask (on Explore)

| Element | Class | Notes |
|---------|-------|-------|
| Ask prompt + field one horizontal row | **A** | UI behavior real (interaction reference) |
| Typed commands mutate Explore state (“Only photos.”, date range, clear filters, etc.) | **A** | Client command architecture real; same path reserved for STT |
| Global Ask on Explore → `mbExploreApplyAsk` | **A** | Wired to same command function |
| STT engine | **E** | Deferred; same command path required later |
| Natural-language find that **loads** Peggy/Christmas from corpus | **B** | `POST /ask` + planner/retrieve exist; Explore does **not** consume Ask hits — fixture payload only |
| Soft Ask that only renames title on unknown text | **C** | Client-only over fixture; not real retrieval |

---

## 3. Curator / context

| Element | Class | Notes |
|---------|-------|-------|
| Curator title “Peggy around Christmas” | **B** | Fixture string; Ask `_build_answer` can produce count-style answers but Explore doesn’t use it |
| Curator count narrative (N photos, video moments, emails, …) | **B** | Fixture-authored; Ask has template counts for live hits — not connected |
| Context chips: Peggy / Christmas / 1998–2021 | **B** | Fixture chips; live person/context exist in Ask session/breadcrumb, not Explore chips |
| Curator avatar initial | **C** | Derived from chip label client-side; no person photo from Immich |
| Live curator rewrite when filters/range change | **A** | Client summary over current visible set (real UI behavior on whatever membership exists) |

---

## 4. Result membership (gallery data)

| Element | Class | Notes |
|---------|-------|-------|
| Entire result set for demo | **B** | 100% from `peggy_christmas_fixture()` via `/explore/api/demo/...` |
| Photo cards (14+ undated) | **B** | Immich photo search + `/library/media/photo/{id}` exist; Explore shows gradient/text cards, not thumbs |
| Video moment cards (2) | **B** | HVRT + Ask video search + appearances exist; fixture `video_external_id`s are demo IDs (`vid-demo-*`), not live HVRT ids |
| Email cards (4) | **B** | Email ingest → Evidence + Ask communication search exist; Explore uses synthetic emails |
| Artifact cards (2) | **B** | Artifact CRUD + Ask `search_artifacts` exist; Explore fixture only |
| Story cards (2) | **B** | Story CRUD + Ask `search_stories` exist; Explore fixture only |
| SMS / calendar / recipe / audio / document cards | **E** / **D** | Shell allows types later; SMS ingest not connected (**D** for SMS); others deferred display when absent (**E**) |
| Real mixed-media assemble into Explore item contract | **D** | No Explore “search → items[]” API yet (would wire Ask and/or Library) |

---

## 5. Gallery presentation & controls

| Element | Class | Notes |
|---------|-------|-------|
| Mixed-media two-row gallery, density Small/Medium/Large | **A** | Real UI presentation state (interaction reference) |
| Type filter row (All / Photos / Video / …) | **A** | Real client filter over current eligible set |
| Sort newest/oldest | **A** | Client sort |
| Hover/focus quick preview | **A** | Client UX |
| Card media as real photo/video pixels | **B** | Backends for media URLs exist; Explore not using them |
| Video duration / play badge on cards | **C** | Fixture fields drive UI; live moments have duration/t in Ask/appearances |

---

## 6. Unified Timeline

| Element | Class | Notes |
|---------|-------|-------|
| Timeline UI (extent, dots, band, handles, playhead, Reset, nudges) | **A** | Real client control model (interaction reference) |
| Timeline driven by dated eligible set; Reset keeps filters | **A** | Real client state hierarchy |
| Undated count outside axis; exclude when date-bounded | **A** | Real client rules; proven on fixture undated item |
| Live corpus dates / Immich timeline buckets as Explore source | **B** / **D** | Library `date_from`/`date_to` + undated bucket exist (**B** capability); no MemoryBox `/timeline` Explore API (**D** for dedicated service); Immich buckets used for Archive Health counts only |
| Proportional scrub ↔ gallery neighborhood | **A** | Client scrub behavior |

---

## 7. Evidence modal

| Element | Class | Notes |
|---------|-------|-------|
| Large in-context modal + close restores explore state | **A** | Real UI architecture |
| Photo detail workspace | **C** | Modal shell real; content is fixture text + CSS face box, not Immich asset |
| Video paused-frame + transcript panel | **C** | Shell/teach-ready layout real; no Review media player; transcript is placeholder copy |
| Email body detail | **B** | Would map to Evidence communication; fixture body only today |
| Artifact / story detail | **B** | Live entities exist elsewhere; fixture copy in Explore |
| Correction-aware restore after teach | **A** | Client restore + consequence merge real |

---

## 8. Review & Learn / Teach proof

| Element | Class | Notes |
|---------|-------|-------|
| Visible “Confirm identity” affordance in modal | **A** / **C** | UI real; demo people ids `demo:peggy` etc. apply **local** correction |
| People picker options | **C** | Tries `GET /people/picker-options` (**A** when DB has people); falls back to demo labels |
| `POST /recognition/appearances/correct` | **C** | **A** when live `person_id` + real `video_external_id`; fixture videos won’t hit HVRT successfully |
| Face box on photo / paused video | **C** | Fixture coordinates; not Immich/HVRT face geometry |
| Full Review box-face / create candidate flow inside Explore | **E** | I1 Review remains full path; Explore needs one visible proof, not full Review product |
| Voice / transcript span Learn | **E** | Architecture reserved; not I4 gate beyond shell openness |

---

## 9. Fixture-specific content (Peggy Christmas)

| Element | Class | Notes |
|---------|-------|-------|
| Query text “Tell me about Peggy around Christmas” | **B** | Could be real Ask; currently seed for demo |
| Synthetic people names Peggy / Rick | **B** | Real MB People / Immich people exist on FlightSim; not bound to fixture ids |
| Places “Oak Street” | **D** / **E** | No Explore place model; deferred richness |
| Undated scan photo `ph-undated` | **B** | Rule **A** in UI; item itself fixture — Library undated handling exists for live assets |
| Demo video external ids | **D** for playback | Not real HVRT ids; replace when wiring |

---

## 10. Intentionally deferred (I4) — do not block wiring

| Element | Class |
|---------|-------|
| Perfect visual polish / pixel match to mockup | **E** |
| Full Family Night product | **E** |
| Full Stories redesign / disconnected story writer | **E** |
| Complete Teach/Review product inside Explore | **E** |
| Complete STT engine | **E** |
| Continuous face tracking during video play | **E** |
| Full SMS/email engines beyond display when data exists | **E** (email display can use existing ingest) |
| Archive Health redesign / Health as family primary | **E** |
| Saved views / Dynamic Views | **E** |
| LLM prose curator | **E** (template/count curator from Ask is enough if wired) |

---

## Summary counts (approx.)

| Class | Role in next wiring |
|-------|---------------------|
| **A — Real-backed** | Keep; do not redesign. Interaction reference. |
| **B — Backend exists; fixture in Explore** | Primary wiring targets: Ask/Library/media → Explore `items[]`, chips, curator counts, thumbs, live moments |
| **C — Partial** | Finish bridges (Ask→Explore, teach with real ids, media in modal) without UX redesign |
| **D — Missing** | Explore live search API / item mapper; real video ids for demo teach; SMS if ever shown |
| **E — Deferred** | Leave stubs; don’t expand scope |

---

## Suggested wiring order (when coding is authorized)

1. **Map live Ask (or Library cards) → Explore item contract** — replaces fixture membership while keeping current UI.  
2. **Photo thumbs + video posters** via existing `/library/media/...`.  
3. **Curator/chips from live counts + person context** (template, not new UX).  
4. **Teach proof on a real photo or HVRT moment** with real `person_id`.  
5. Keep fixture demo as fallback prove path (`?demo=peggy-christmas`) until live path is green.

**Stop line:** This inventory is for review before coding. No Explore redesign while wiring.
