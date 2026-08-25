# MBAS-P2-I11 — Narration + Saved Ask / Living Views

**Status:** Planning assessment **LOCKED** 2026-08-24 · **final evidence-prep LOCKED** · I10C **ACCEPTED** · **do not build** until explicit authorization  
**Direction:** Narration is Ask output; Save View ≠ Save as Story ≠ Snapshot; **Saved View** not Living Album; claim-specific presence ≠ photographer/purpose  
**Prep assessment:** [MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md](MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md)  
**Does not start:** I13 Save View UI · Narration app · Journal redesign · I12 · tell-LLM until authorized  
**Depends on:** I10A Stories **ACCEPTED** · I10A.2 **ACCEPTED** · I10B **ACCEPTED** · I10C Journal **ACCEPTED** 2026-08-24 · MBQL-001 **ACCEPTED** · I10 pack/coverage **ACCEPTED** · I7A

Journal screens are **ACCEPTED**. I10C work stays closed unless a contract defect appears.

---

## Verdict

**No new Narration screen required.**

Narration belongs in existing Explore/Ask: context chips → Ask row → curator → representative gallery/timeline. The curator is a short count line in a compact card today; I11 should **grow that component**, not fork a product area.

**Do not pull I13 into I11.** Freeze persistable Ask-state now. Ship **Save View** reopen, Curated Collection, and Snapshot under **P2-I13**. Do **not** add a disabled Save View control. User-facing names: **Save View** / **Saved View** (live recompute). Do not use **Living Album**.

---

## Recommended implementation boundary

### I11 (Narrative & Summaries) — definition locked; prep/LLM waits for build authorization

**In**

1. **Output mode** on the existing `QueryPlan` (do not fork a second intent object). Keep MBQL `act` as find/refine/navigate/clarify. Add a sibling slot, e.g. `output_mode: show | play | tell` — do **not** overload `act`.
2. Semantic compile: SHOW/FIND → `show`; PLAY → `play`; TELL/SUMMARIZE/WHAT DO YOU KNOW/WHAT HAPPENED/WHAT WAS X LIKE → `tell`. Natural language, not a phrase table.
3. **`tell` uses Narrative Evidence Preparation** (comms, media observation, travel, calendar, journal, story, artifact, place/event, spoken) then LLM synthesis. Hierarchical volume **IN**. Spam/Trash out before the model. Claim-specific trust.
4. **One shared** long-form curator component (Explore + Person Explorer) — not merely unhide. Copy and Save as Story.
5. Provenance in the prose (facts vs recollection vs inference vs missing) — readable, not a citation dump per sentence.
6. **Copy** = clipboard. No durable object.
7. **Save as Story** = working draft + `composed_by_model`; owner Save Story for Ask-current.
8. Keep `Show me Peggy` as `show`.
9. Emit persistable Saved View JSON. I13 stores/reopens. No Save View UI in I11. Relative language → general semantic constraints on `plan`.
10. Deterministic prep; model **only** for `tell` (provider-neutral, I7A). Fail closed if the model is down (no stitch-as-narrative).

**Out**

- New `/narration/ui` or family-nav destination.
- Journal chrome redesign.
- I12 / P2-NAR-04 world-history weave.
- Curated Collection membership UI.
- Snapshot frozen ID lists as default save.
- Sending every Ask to a model (only `tell`, and only the prepared pack).
- Treating generated prose as Ask-current family fact.
- Disabled Save View chrome.
- Stitch fallback that looks like narration when the model is down.
- First-N as the primary broad-volume strategy.
- Filename / SMS-timestamp as photographer / location.

### I13 (Dynamic Views) — later

Persist named **Save View** / **Saved View**: rerun Ask + normalized state against the current archive. Distinct Curated Collection and Snapshot. Not “Save narrative.” Not Living Album.

---

## Assessment (prompt §16)

### 1. How SHOW/FIND vs TELL/SUMMARIZE is represented today

There is an `output_mode` field on `QueryPlan` on the current tree. The **authorized** synthesizer (prepared pack + LLM) is **not** implemented. A deterministic stitch and Explore Copy/Save as Story may exist as scaffolding only.

| Family phrasing | Compile / curator today |
|---|---|
| `Show me Peggy` | `SHOW_ME_RE` → broad visual `QueryPlan` (`visual_scope=broad`, photos+video). Curator is a **count of visible gallery items**. |
| `Tell me about Peggy` / `What do you know about…` | `EXPLORATORY_RE` → multimodal retrieve (`exploratory_multimodal_i4`), including Story/Journal/Artifact **unless** other flags fire. Still a **hit-count curator**, not synthesis. |
| `Summarize…` / `What happened…` / `What was X like?` | **No dedicated compile.** Falls through ordinary find + count summary. |
| `What did X say` / `said about` | `SAID_ABOUT_RE` → **communication-focus**; **turns off** `want_story` / `want_journal` / `want_artifact`. |
| Explicit “write a narrative” | Compiles `tell`. Authorized synthesizer = prepared pack + LLM (not stitch). |

MBQL `act` is session mechanics (`find` / `refine` / `navigate` / `clarify`), not SHOW vs TELL vs PLAY. Mixing those would break refine-vs-new-find.

`answer_kind` today is retrieve disposition (`evidence_backed`, `journal_backed`, `mixed`, `insufficient`, `clarification`, …), not “narrative.”

### 2. Can MBQL / planner represent narrative output cleanly?

**Yes, as a new field on `QueryPlan`, not a new language.**

`QueryPlan` already carries original/effective Ask, people/place/time/windows, modalities, `want_*`, gallery presentation flags, `want_cross_source`. That is the MBQL record (MBQL-001 lock: extend this object).

Add `output_mode` (and keep `act`). `tell` should **force-on** retrieval flags for relevant modalities unless the user narrowed sources (`Only photos.` remains a refine of evidence scope, not a silent gallery hide).

Do not create a parallel saved-query schema.

### 3. Where Curator output is rendered

Explore: `#mb-explore-curator` / `#mb-explore-curator-title` / `#mb-explore-curator-body` in `explore.html` + `explore.js` `applyPayloadToState` / render. CSS: `explore.css` `.mb-explore-curator` — compact 3-column card; body is a **single `<p>`**, muted, ~0.95rem, **no max-height clip today**, but also **no paragraph width / collapse / actions**.

Person Explorer reuses the same ids (`person-explore.html`) and **hides** the Explore curator card in person mode.

Ask JSON `answer_text` is produced in `memorybox/ask/orchestrator.py` `_build_answer` (count/provenance sentences, I10 `coverage.summary` prepended).

### 4. Can that component support long-form without a new screen?

**Yes, with layout work on the same card** — not a new route.

Gaps (not blockers):

- Explore **throws away** orchestrator `answer_text` unless `answer_kind == clarification`:

```1122:1129:memorybox/explore/find.py
    answer_for_curator = result.get("answer_text")
    if result.get("answer_kind") != "clarification":
        answer_for_curator = None
    title, summary = curator_from_items(
```

  I11 `tell` must pass `answer_text` through (or a dedicated `narrative_text`) and stop rebuilding the curator solely from **visible** tiles.
- Body is `textContent` on one `<p>` — need wrap, readable measure, optional collapse, Copy / Save as Story.
- Grid `align-items: center` and chip column `max-width: 14rem` will fight long prose; change alignment and let the copy column grow. Gallery/timeline below stay.

If a later owner pass proves unreadability at extreme length, expand-in-place first. Do not invent `/narration/ui` in the definition.

### 5. How supporting evidence is associated

- Orchestrator: `citations[]` and `statements[]` on the Ask result (evidence/photo/video/story/journal ids, provenance labels).
- I10: `coverage` pack (counts + missing + conflicts) → `#mb-explore-coverage`.
- Explore gallery: `items[]` from `find.py`, then client `matchesType` / timeline.
- Stories/Journals already have versioned memory links for **Save as Story** carry-forward.

Inspectability today is **gallery + coverage strip**, not inline sentence citations. I11 should keep gallery reachable and optionally surface a short “From N sources” line; do not require numbered footnotes in the first build.

### 6. Copy

**Not present** on the curator. Need `navigator.clipboard.writeText` of the narrative string. No API, no Story row, no Ask mutation.

### 7–8. Save as Story / can the editor take proposed text + evidence?

Story editor **can** take proposed text via `POST /story/drafts` (`save_draft`) and memories/person_ids/place/dates. `composed_by_model` already exists and is rejected as authoritative until owner Save Story.

**Gap:** boot from URL only knows `new=1`, `photo`, `video`, `artifact`, `title`, `person` — **not body**. I11 should:

1. `POST /story/drafts` with narrative as `body_text` / blocks, memories from citations, people/place/time from the plan;
2. redirect `/story/ui?id=<draft>&edit=1`.

Do not auto-call `save_story`. Do not invent a second editor.

### 9. Persistable normalized Ask/filter state

**Mostly yes, not assembled into one saved record.**

| Layer | What exists | Persist? |
|---|---|---|
| `QueryPlan.to_dict()` | Ask, act, modalities, people/ids, place, events/trips, time, windows, gallery_show_*, want_cross_source | Yes — canonical MBQL |
| `AskContext` | Session inherit (people/place/time/modalities). In-memory `ContextStore`; comment already says persistence can implement the protocol later | Partial; too thin alone |
| `explore_state` in find payload | place, windows, visual_scope, gallery_show_* | Yes |
| Explore client `state.domain` / `timeline` / `gallery` | typeFilter, includeTexts/Email/Calendar, density, sort, viewMode, range, playhead | Yes — presentation; must travel with Save View |

There is **no** `saved_views` table. Age-relative language is **not** a phrase-specific column. I11 stores generic semantic constraints (Person, `age_band`, interpretation/version); birth or other sufficient evidence converts to dates, else ask.

### 10. Future Living View without rework

Define **one JSON document** now (I11 contract, I13 storage):

- `original_ask`
- `output_mode`
- `plan` = `QueryPlan.to_dict()` (interpreted meaning)
- `presentation` = domain + timeline + gallery (visibility, sort, density, map)
- `schema_version`

Reopen = `plan_ask` is **not** re-parsed from words only; load stored plan, re-retrieve against current archive, re-run `tell` synthesizer if `output_mode=tell`. Prose is **not** the saved object.

Do not invent a narration-only query struct.

### 11. Evidence scope vs Gallery filters (the real contradiction)

**Gallery hide ≠ retrieve exclude** is already an I7/I8A rule, and it is **half-implemented**.

- Retrieve: exploratory / I10 `want_cross_source` still pulls email/SMS/calendar.
- `find.py` marks comms `gallery_default_hidden` unless presentation says show them.
- Client `matchesType` hides them on All unless `includeEmail` / `galleryShowSms` / etc.
- Curator summary is built from **visible** items, so hidden comms **do not shape the essay** — only a footer (“N texts are in the archive”).

For `Summarize our Alaska trip` with Email/SMS hidden, I11 must synthesize from the **retrieved pack**, not `visible_items`. Gallery can stay hidden. That is the main product bug to fix in I11, not a new screen.

`tell me about` currently **does** retrieve Journal/Story; `said about` **does not**. Do not confuse those.

### 12. Contradictions with MBQL, MBUX, capabilities, Saved Views

| Source | Says | vs this direction |
|---|---|---|
| MBQL-001 | Normalize intent only; **no I11 narrative** in that increment | Compatible — I11 consumes MBQL, does not replace it |
| MBPS P2-NAR-01..03 / CAP-P2-013 | Evidence-backed synthesis; not authoritative; owner review to persist | **Aligns** |
| MBPS P2-VIEW-01..03 / CAP-P2-014 / MBUX §22.9 | **Living Album** in older catalogs | Founder: **Save View** / **Saved View**, Curated Collection, Snapshot. Do not use Living Album as the family name. |
| MBRM I11 vs I13 | I11 = P2-NAR-01..03; I13 = P2-VIEW-01..03 | **Keep split.** I11 must not absorb I13 UI |
| I10 | Coverage pack, not narrative save | Keep; I11 writes prose **from** the pack |
| I10A | Human Story; AI cannot be Story truth without Save | Save as Story path **aligns** |
| Explore I4 lock | Do not redesign Explore | I11 **enhances curator + actions**; does not replace the canvas |
| Planner comment `Guided Capture Responses (I11)` | Mislabel | GC is not I11 narration |

---

## Directional acceptance (when I11 is built)

Map 1:1 to founder §17. Harness should prove at least:

- `Tell me about Peggy` → `output_mode=tell` + synthesis that can cite Journal/Story/photo/comms even if comms are gallery-hidden.
- `Show me Peggy` → `output_mode=show` + result set, not an essay.
- Long curator is readable in Explore; evidence tiles remain.
- Copy does not create rows.
- Save as Story opens a **working draft**; Ask prose is not `current_saved` until owner Save Story.
- Persistable view JSON includes original Ask + plan (for I13). I11 need not ship reopen chrome.

---

## Open questions for Tom

See [evidence prep §13](MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md). **BUILD AUTHORIZED** 2026-08-24.

---

## Explicitly out of this planning note

Journal UI changes, I13 tables, I12, Face SoT, guided-capture campaigns, tell-LLM until authorized.
