# MBAS-P2-I11 — Narration + Saved Ask / Living Views

**Status:** Planning assessment **2026-08-24** · **not build-authorized**  
**Direction:** Founder lock in this increment’s prompt (Narration is Ask output; Save View ≠ Save as Story ≠ Snapshot)  
**Does not start:** I11 implementation · I13 Dynamic Views UI · a Narration app · Journal screen redesign · I12 external history  
**Depends on:** I10A Stories **ACCEPTED** · I10A.2 **ACCEPTED** · I10B **ACCEPTED** · I10C Journal **built, owner-pass pending** · MBQL-001 **ACCEPTED** · I10 pack/coverage **ACCEPTED**

Journal screens are treated as **complete**. I10C work stays data/Ask/tests unless a contract defect appears.

---

## Verdict

**No new Narration screen required.**

Narration belongs in existing Explore/Ask: context chips → Ask row → curator → representative gallery/timeline. The curator is a short count line in a compact card today; I11 should **grow that component**, not fork a product area.

**Do not pull I13 into I11.** Freeze a persistable Ask-state shape now. Ship Save View reopen, Curated Collection, and Snapshot under **P2-I13** (MBUX Living Album / P2-VIEW-01..03), unless Tom later authorizes a thin “Save View” control in I11 that writes the same record.

---

## Recommended implementation boundary

### I11 (Narrative & Summaries) — when authorized

**In**

1. **Output mode** on the existing `QueryPlan` (do not fork a second intent object). Keep MBQL `act` as find/refine/navigate/clarify. Add a sibling slot, e.g. `output_mode: show | play | tell` (names can be `find` / `play` / `tell` if we must reuse vocabulary — do **not** overload `act`).
2. Semantic compile: SHOW/FIND → `show`; PLAY/moment → `play`; TELL/SUMMARIZE/WHAT DO YOU KNOW/WHAT HAPPENED/WHAT WAS X LIKE/DESCRIBE FROM WHAT WE HAVE → `tell`. Natural language, not a phrase table. Deterministic first; residual model only to fill this slot when ambiguous (I7A).
3. **`tell` retrieval uses the full supported evidence pack** (photos, video/moments, Stories, Journal, artifacts, email, SMS, calendar, documents, audio/spoken, relationships, places, events/trips). Gallery visibility must not shrink that pack.
4. Curator renders **long-form evidence-backed prose** for `tell`, with Copy and Save as Story. Gallery/timeline stay for drill-down.
5. Provenance in the prose (facts vs recollection vs inference vs missing) — readable, not a citation dump per sentence. Citations/`coverage` already on the Ask result remain inspectable.
6. **Copy** = clipboard of the current narrative text. No durable object.
7. **Save as Story** = existing `/story/ui` editor: proposed body + people/place/time + supporting memory links; `composed_by_model` stays true until owner Save Story. Never auto-persist Ask prose as Story.
8. Keep `Show me Peggy` as a **result set** (`show`), not an essay.
9. Document the persistable Living View JSON (original Ask + `QueryPlan.to_dict()` + Explore domain/timeline/gallery presentation). I11 may emit it; I13 stores and reopens it.

**Out**

- New `/narration/ui` or family-nav destination.
- Journal chrome redesign.
- I12 / P2-NAR-04 world-history weave.
- Curated Collection membership UI.
- Snapshot frozen ID lists as default save.
- Sending every Ask to a model.
- Treating generated prose as Ask-current family fact.

### I13 (Dynamic Views) — later

Persist named **Save View** (Living View / MBUX Living Album): rerun Ask+normalized state against the current archive. Distinct Curated and Snapshot modes (P2-VIEW-03). User-facing verbs: **Save View**, not “Save narrative.”

---

## Assessment (prompt §16)

### 1. How SHOW/FIND vs TELL/SUMMARIZE is represented today

There is **no output-mode slot**.

| Family phrasing | Today |
|---|---|
| `Show me Peggy` | `SHOW_ME_RE` → broad visual `QueryPlan` (`visual_scope=broad`, photos+video). Curator is a **count of visible gallery items**. |
| `Tell me about Peggy` / `What do you know about…` | `EXPLORATORY_RE` → multimodal retrieve (`exploratory_multimodal_i4`), including Story/Journal/Artifact **unless** other flags fire. Still a **hit-count curator**, not synthesis. |
| `Summarize…` / `What happened…` / `What was X like?` | **No dedicated compile.** Falls through ordinary find + count summary. |
| `What did X say` / `said about` | `SAID_ABOUT_RE` → **communication-focus**; **turns off** `want_story` / `want_journal` / `want_artifact`. |
| Explicit “write a narrative” | `SMS_NARRATIVE_RE` / Explore `find.py` **refuse** generation and say I11 is not implemented. |

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

There is **no** `saved_views` table. Age-relative “when he was young” is **not** a planner slot today — residual MBQL fill + durable interpretation field required for Living View (prompt §9).

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
| MBPS P2-VIEW-01..03 / CAP-P2-014 / MBUX §22.9 | **Living Album**; live / curated / snapshot | Same three objects. Founder user-facing names: **Save View**, Living View, Curated Collection, Snapshot. Treat **Living Album = Living View** (I13 customer name to confirm) |
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

1. **I11 vs I13 Save View control:** I11 ship Copy + Save as Story only, or also a disabled/hidden Save View that writes the JSON for I13?
2. **Living Album vs Living View / Save View** as the family label on I13.
3. **Synthesizer:** deterministic stitching from statements/coverage for v1 vs residual LLM (I7A) for `tell` only?
4. **Person Explorer:** same long curator, or Explore-only for I11?
5. **I10C owner-pass:** I11 build waits for Journal ACCEPTED plus remaining transcription/recognition, per MBRM — confirm still true.

---

## Explicitly out of this planning note

I11 code, Journal UI changes, I13 tables, I12, Face SoT, guided-capture campaigns.
