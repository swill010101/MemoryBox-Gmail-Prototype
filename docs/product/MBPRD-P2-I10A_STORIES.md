# MBPRD-P2-I10A — Stories

**Status:** PRD **LOCKED** · **BUILD AUTHORIZED** 2026-08-21 (Tom: “Name PRD i10A - Stories…. it goes next and you are approved to build i10A - Stories”)  
**Date:** 2026-08-21  
**Increment definition:** [MBBS-P2_INCREMENT_10A_DEFINITION.md](MBBS-P2_INCREMENT_10A_DEFINITION.md)

**Visual baseline:** `docs/source/Screens/MBUX Story Screens/` (from commit `c95117b`; now on the I10A implementation branch)

`docs/source/Screens/MBUX Story Screens/`

| File | Screen |
|------|--------|
| `MBUX-Stories-Panel-v1.png` | Stories panel |
| `MBUX-Story-Detail-v1.png` | Story detail |
| `MBUX-Story-New-Editor-v2.png` | New Story editor |
| `MBUX-Story-Edit-Revision-v1.png` | Edit revision |
| `MBUX-Story-Add-Supporting-Memories-Modal-Draft-v1.png` | Add supporting memories |
| `MB Stories video detail rail.png` | Photo/video Story rail |

**Depends:** I1–I8A **ACCEPTED** · I9 Spoken Moments on the stacked tree · **I10 Cross-Source ACCEPTED** 2026-08-21 · MBQL-001 **ACCEPTED** · P1 Story service (`memorybox/story`, Increment 5) · MBUX-001 v0.4 · MBPS-002 · MBEVS-001 · MBCAP-001 v0.2

**Implementation branch:** `cursor/p2-i10a-stories-49da` from **I10 ACCEPTED**. Do not start I11.

**Does not start:** I11 narrative generation · “compose from selected memories” · Family dictation on Story unless an approved Story STT path is proved · multi-user access control · in-rail Story authoring · Story-as-evidence-for-Story · confidence UX · I8.5 face SoT · Place GIS

**Increment ID:** **P2-I10A — Stories.** This is **not** I11. I11 remains evidence-backed narrative synthesis (EVS-181/182). I10A is the human Story object (EVS-172–180 plus rail/picker).

**Legend used below**

| Label | Meaning |
|-------|---------|
| **Frozen** | Owner product decision in this PRD. Do not reopen in implementation without a new decision. |
| **Existing** | Confirmed in the current repository. |
| **Required** | Must be built for this slice. |
| **Recommendation** | Implementation choice. Change only with a recorded reason. |
| **Open** | Remaining technical question. Does not block PRD review; may block build start. |

---

## Frozen product decisions

Copied from owner lock (2026-08-21). These govern the six PNGs. Where a PNG conflicts, the lock wins.

1. All six screens are one Stories workflow and one PRD.
2. A saved Story may always be edited.
3. Editing a saved Story creates a mutable working draft derived from the current saved version.
4. The current saved version remains available to Ask while that draft is edited.
5. Save revision freezes the draft as a new saved version and atomically moves the Ask-current pointer.
6. Discard draft removes only the working draft.
7. Saved versions are immutable and retain revision history.
8. Ask retrieves only the current saved version. Drafts are never available to Ask.
9. Sharing and Ask availability are independent.
10. Status filters are **All / Drafts / Saved**.
11. Visibility is a separate filter: **All visibility / Private / Shared with family**.
12. Remove **Shared** from the status-tab row (panel PNG is superseded on that control).
13. People display the **full name** and **preferred Immich portrait** everywhere (panel first-name pills are superseded).
14. Story content is an ordered **block** structure: section headings, narrative paragraphs, supporting-memory references.
15. Supporting memories are mixed-type, ordered, removable **links**.
16. Selection includes photos, videos, email threads, SMS conversations, calendar events, artifacts, Journal entries, and audio when supported.
17. Supporting-memory relationships belong to the **Story version** so saved revisions keep original evidence and order.
18. Linking a memory never changes the source object.
19. A Story cannot support another Story in this increment.
20. Photo/video Story rail: Stories using this memory · Add to an existing Story · Create a new Story using this memory · Open Story detail. Not an authoring surface.
21. Remove “compose from selected memories.” That is I11 and must never auto-save.
22. Do not expose dictation unless an existing approved capability is proved. Otherwise placeholder **“Start writing your story…”**
23. Save draft, Save Story, and Save revision are explicit human actions.
24. Narrator and Editor are separate people/roles.
25. Cancel, Close, Back, Preview, Discard draft, and unsaved-change warnings must be specified.

**PNG supersessions (frozen over pixels)**

- Panel status tabs: **All / Drafts / Saved** only. Visibility is a separate control.
- People: full `display_name` + `GET /people/{id}/portrait` on panel, detail, editor, rail, picker chips.
- New-editor placeholder: **Start writing your story…** (no dictate, no compose).

---

## A. Scope and non-scope

### Problem

The family needs a durable, human-authored Story: written meaning supported by real archive objects, with drafts that are safe, saved versions that Ask can trust, and a rail that associates media without turning the viewer into an editor.

Today MemoryBox has a P1 Story service that publishes on first Save, treats the latest write as Ask-current, stores one `body_text`, and links only `evidence` UUIDs. That cannot represent the approved screens.

### Success criteria

1. Owner can create a Draft, leave, resume (**Continue writing**), and keep it out of Ask.
2. **Save Story** creates immutable saved version 1 and makes that version Ask-current.
3. **Edit** copies the current saved version into a working draft; Ask still returns the previous saved version.
4. **Save revision** freezes the next saved version and atomically moves Ask-current.
5. **Discard draft** restores the editor/panel to the last saved version (or removes a never-saved Story).
6. Supporting memories are mixed-type links; originals are unchanged; Stories cannot be attached as supporting memories.
7. Detail renders ordered blocks (heading / paragraph / memory) for the **current saved** version (or Preview of the working draft).
8. Photo/video Story rail lists Stories that use that memory and can add-to-existing or start new.
9. People always show full name + preferred portrait.
10. Visibility can change without changing Draft/Saved or Ask-current.
11. No I11 compose path. No auto-save of AI text as a Story.
12. Prove harness plus FlightSim owner pass of the five walkthroughs in the assessment.

### IN

- Stories panel, detail, new editor, edit revision, add-memories modal, photo/video Story rail.
- Draft / saved / working-revision lifecycle and Ask-current pointer.
- Ordered blocks + versioned supporting-memory links + optional in-section placement.
- Narrator vs Editor.
- Described date range, Place (named), visibility metadata, people associations.
- Mixed evidence picker with NL/keyword, person, date/range, place, type tabs, multi-select, one Add.
- Migration of existing `stories` / `story_versions` / `body_text` / `relationships` / note-field photo hacks.
- Ask retrieve of **current saved version only**, including block text for token match.
- Explore rail reverse lookup and associate/create.
- Cancel / Close / Back / Preview / Discard / unsaved warnings.

### OUT

- I11 narrative generation, summaries-from-archive, “compose from selected memories.”
- Story-as-supporting-memory; recursive/circular Story graphs.
- Multi-user enforcement of “Shared with family” (record the flag; do not build CAP-P2-022).
- In-rail rich text authoring.
- Confidence dials; `confidence_at_save` as family UX.
- Treating I10 everything-about packs as Stories.
- Full-text/semantic Story index beyond extending today’s SQL token retrieve (EVS-173 semantic search may follow).
- GIS Place picker (named Place / text is enough; CAP-P2-024 pin UI not required here).
- Dictation control on Story (see §E.3).
- Auto-save, mixed implicit persist, or silent Ask reindex of drafts.

---

## B. Complete user workflows

### B1. Panel → New Story → Draft → Save Story → Detail

1. Owner opens **Stories** (`/story/ui` panel).
2. **+ New story** opens the new editor. No server row yet (see §O unsaved). Badge: Draft · Not available to Ask.
3. Owner sets title/description/body/people/details. **Save draft** persists a Story with a working version and **no** Ask-current pointer. Panel **Continue writing** and **Drafts** filter show it.
4. **Save Story** (from new editor or from a persisted draft) freezes **saved version 1**, sets Ask-current, clears working draft. Detail shows Saved · Available to Ask · Version 1.
5. Ask may retrieve that version. Drafts must not.

### B2. Panel → Detail → Edit revision → Save revision / Discard

1. Open a saved Story. Detail reads **current saved version**.
2. **Edit story** creates (or resumes) a working draft cloned from that saved version. Banner: saved version N remains available to Ask.
3. Owner edits blocks, memories, narrator, dates, place, people.
4. **Save draft** updates the working row only. Ask unchanged.
5. **Save revision** freezes version N+1, moves Ask-current atomically, deletes working pointer. Detail shows Version N+1.
6. **Discard draft** deletes the working version only. Ask-current unchanged. Return to detail of saved N (or panel if never saved).

### B3. Photo/video rail → existing or new

1. Owner opens photo or video in the shared evidence viewer. **Story** tab.
2. Rail lists **Stories using this memory** (saved and draft), each openable.
3. **Add to story** picks an existing Story (see §E.6). Adds this memory to that Story’s **working draft** (create draft from current saved if needed). Does not open the full editor unless the owner continues there.
4. **Create a new story** opens New Story with this memory pre-linked in the working (client or saved-draft) supporting list. Original media unchanged.
5. Close returns to the Explore/Ask viewer stack (MBUX §8.2).

### B4. Editor → Add memories → Add → Editor

1. **+ Add memories** opens the modal. Search uses MemoryBox evidence, not generation.
2. Filters: query, person, date/range, place, type tabs, **+ Filters** (event/source when those slots exist).
3. Multi-select; **Add N memories** writes ordered links onto the working draft (client until first persist, then server). Duplicates ignored. Story type excluded.
4. Modal closes. Editor list updates. Rich text unchanged unless the owner later inserts a memory block.

### B5. Share without changing Saved/Ask

1. From detail **Share**, or editor Visibility, set Private or Shared with family.
2. Writes `stories.visibility` only. No new version. Ask-current unchanged. Draft unchanged.

### B6. Ask retrieves current saved Story

1. Owner asks e.g. Peggy Christmas traditions.
2. If `want_story` and tokens/person match, retrieve **current saved version** blocks + metadata.
3. Citations include `story_id`, saved `version_number`, narrator, provenance. Supporting memories are listed as linked sources, not recursively expanded into model context in this increment.

---

## C. State-transition table

Story identity states:

| Name | Meaning |
|------|---------|
| `ephemeral` | New editor, no `stories` row |
| `draft_only` | Row exists; `current_saved_version_id` IS NULL; working version exists |
| `saved` | Ask-current pointer set; no working version |
| `saved_with_draft` | Ask-current pointer set; separate mutable working version |
| `removed` | Soft-removed; not listed; not Ask-visible (**Existing** `status='removed'` unused today — **Required** to honor or keep unused) |

| # | UI event | Precondition | Validation | Writes | Result state | Ask |
|---|----------|--------------|------------|--------|--------------|-----|
| 1 | Open New story | — | — | none | ephemeral | none |
| 2 | Save draft (new) | ephemeral or draft_only | none required except UUID integrity | insert story + working version (blocks, people, memories) | draft_only | **no pointer** |
| 3 | Save draft (edit) | saved_with_draft or draft_only | working exists | update working version in place | same | unchanged |
| 4 | Save Story | ephemeral or draft_only | title required; body or ≥1 memory recommended (see Open) | freeze working as saved v1; set Ask-current; clear working | saved | v1 current |
| 5 | Open detail | saved or saved_with_draft | — | none | — | still current saved |
| 6 | Edit story | saved | — | clone current saved → new working version | saved_with_draft | **still previous saved** |
| 7 | Edit story | saved_with_draft | — | resume existing working | saved_with_draft | unchanged |
| 8 | Save revision | saved_with_draft | title required; same content rule as Save Story | freeze working as vN+1; **one transaction** move Ask-current; clear working | saved | **new** current |
| 9 | Discard draft | draft_only | confirm | delete working + story row | gone | none |
| 10 | Discard draft | saved_with_draft | confirm | delete working only | saved | unchanged |
| 11 | Add/reorder/remove memory | working or ephemeral | type ≠ story; source exists; authz = owner | mutate working (or client) | same | unchanged |
| 12 | Rail add to existing | target Story | create working clone if `saved` | insert memory on **working** | saved_with_draft or draft_only | saved pointer unchanged |
| 13 | Rail create new | media id | — | open new editor with pre-linked memory | ephemeral | none |
| 14 | Change narrator/people/dates/place | working | Person exists | update working | same | unchanged until freeze |
| 15 | Change visibility | any persisted Story | enum | update `stories.visibility` only | same lifecycle | unchanged |
| 16 | Ask | `want_story` | — | none | — | JOIN Ask-current saved version only |

**Atomic freeze (4 and 8):** insert or mark version `saved` + set `current_saved_version_id` + clear `working_version_id` + bump `updated_at` in **one** DB transaction. Failure rolls back; Ask pointer must not move without the frozen row.

**Failure:** 400 validation, 404 missing Story/source, 409 edit conflict if two working drafts (single-owner: last-write on working row is enough; no multi-tab merge in this increment — warn on stale `updated_at`).

---

## D. Navigation and return-stack behavior

**Frozen** with MBUX-001 v0.4 §§7.3, 8.2: Back returns to the prior meaningful context.

| From | Trigger | To | Preserve |
|------|---------|-----|----------|
| Shell Stories | nav | Panel | — |
| Panel | New story | New editor | panel filters in session |
| Panel | card / Continue writing | Detail or Edit (draft_only → editor) | panel filters, scroll |
| Detail | Edit story | Edit revision | detail id |
| Detail | Open memory | Shared evidence viewer | return to this detail |
| Detail | View all supporting memories | Modal or in-page list (Recommendation: same picker in read-only if not editing) | detail |
| Detail | Share | Share popover/sheet | detail |
| Detail | View revision history | History sheet; selecting vK opens **read-only historical detail** (not Ask-current unless it already is) | detail |
| New/Edit | Add memories | Modal over editor | editor dirty state |
| Modal | Cancel | Editor | no add |
| Modal | Add N | Editor | new links on working |
| New/Edit | Preview | Read-only preview of **working** content | editor |
| Preview | Close / Back | Editor | — |
| Rail | Open Story | Detail | viewer stack (result set, index `N of M`, rail tab) |
| Rail | Add to story | Story picker then stay on viewer (Recommendation) or optional toast + “Edit story” | viewer |
| Rail | Create a new story | New editor with memory pre-linked | viewer return target |
| Any editor | Cancel / Back / Escape | see §E.7 | — |
| Viewer Close | Close | Explore/Ask gallery | timeline, filters, density, playhead |

Deep links:

- `/story/ui` panel
- `/story/ui?id={story_id}` detail (current saved)
- `/story/ui?id={story_id}&edit=1` editor (creates/resumes working)
- `/story/ui?id={story_id}&version={n}` historical saved version, read-only
- `/story/ui?new=1` new editor
- `/story/ui?new=1&photo=` / `&video=` rail create-new

Do not keep stuffing Immich ids into `story_versions.note`.

---

## E. Detailed screen-by-screen requirements

Chrome on all Stories surfaces: MemoryBox mark, family nav (Ask, People, **Stories** active, Journal, Artifacts, Family Night). MBUX shell. Dark theme as in the PNGs.

People everywhere: `display_name` + `<img src="/people/{id}/portrait">` with initial fallback if 204 (**Existing** portrait endpoint; P2-BL-I5-01 may still 204 — show initial, not a random crop).

### E.1 Stories panel

**Entry:** nav Stories.  
**Purpose:** browse and start Stories.  
**Header:** “Stories” / “The meaning behind the memories.” **+ New story**.  
**Ask bar:** global Ask (“Ask about a person, memory, or family story”), not Story-scoped.  
**Continue writing:** most recently updated `draft_only` or `saved_with_draft`. Omit section if none.  
**Search stories:** title, description, block text of **working or saved display version** for owner browse (not Ask).  
**Status tabs (frozen):** All · Drafts · Saved.  
**Visibility filter (frozen):** All visibility · Private · Shared with family.  
**People filter:** MB Person.  
**Sort:** Recently updated (default); optional Oldest updated later.  
**Cards:** cover (first memory still, else placeholder), title, description/summary, people (full name + portrait; `+N`), described range, memory count, status **Saved** or **Draft** (green/orange). Do not use Shared as a status dot. If visibility is Shared with family, a separate quiet visibility cue is allowed, not a third status tab.  
**Footer:** “Stories are saved explicitly and retain author and revision history.”  
**Empty:** “No stories yet” + New story. Filter-empty: “No stories match these filters.”  
**Click:** `saved` / `saved_with_draft` → detail (detail is saved version; banner if working draft exists: “You have an unsaved revision — Continue editing”). `draft_only` → editor.

### E.2 Story detail

**Entry:** panel, rail, Library deep link.  
**Reads:** current **saved** version. If `draft_only`, redirect to editor.  
**Ask bar:** “Ask about this story” — **Required** scoped Ask: inherit `story_id` as constraint so retrieve prefers this Story; do not run I11 generation.  
**Breadcrumb:** Stories / {title}.  
**Actions:** Share; Edit story (primary).  
**Hero:** cover still; title; description; badges Saved + Available to Ask; Narrated by {full} · Edited by {full}; described range; linked memory count; Version N.  
**People in this story:** portraits + full names.  
**Body:** render ordered blocks. Heading → heading. Paragraph → text. Memory ref → card (type, title, date, duration/from-to as applicable, **Open memory**).  
**Sidebar About:** Narrator, Editor, Current version, Last saved, Visibility, View revision history.  
**Connections:** people count, memory count, artifact count if any, Place. View all supporting memories.  
**Note:** “Editing creates a new working draft. The saved version remains available until the revision is saved.”  
**If saved_with_draft:** non-blocking banner Continue editing / Discard.

### E.3 New Story editor

**Badges:** Draft · Not available to Ask.  
**Copy:** “Build a story from memories. Save when it is ready for MemoryBox.”  
**Fields:** Title; Description (optional); Story editor (paragraph + heading tools; **no** I11 compose). Placeholder **Start writing your story…**  
**Dictation:** **Out** of this increment. `POST /capture/transcribe` is Journal/capture (**Existing**) and “does not create a Journal entry”; it is not an approved Story-editor control. Do not show a Dictate button.  
**Supporting memories:** empty dashed state + Add memories. Helper: photos, videos, artifacts, communications, calendar, journal, audio.  
**Sidebar:** Narrator (Person picker, default owner); Editor (see §L — display owner, not a second identity mint); date range; Place; Visibility default Private; People + Add people.  
**Footer:** Cancel · Save draft · Save Story. Note: “Save Story makes this version available to Ask. Sharing is separate.”  
**Primary:** Save Story. Save draft secondary. Cancel quiet. No Delete on this screen.

### E.4 Edit revision

**Badges:** Working draft · Editing version N (N = current saved number being revised).  
**Banner:** “Saved version N remains available to Ask until this revision is saved.”  
**Same fields as new**, populated from working draft. Supporting list: drag handles, type, title, date, overflow (Open / Remove). Add memories.  
**Revision sidebar:** Current saved version N; Last saved; View revision history.  
**Footer:** Cancel · Discard draft (destructive, away from primary) · Preview · Save revision.  
**Note:** “Save revision creates version N+1 and makes it the version available to Ask.”  
**Primary:** Save revision.

### E.5 Add supporting memories modal

**Title:** Add supporting memories.  
**Subtitle:** Find evidence in MemoryBox to support this story.  
**Search + go.** Chips from person/date/place (+ Filters).  
**Tabs:** All · Photos · Videos · Communications · Calendar · Artifacts · Journal · Audio. **No Stories tab.**  
**Counts:** “{total} matches” from the **eligible set**, not a capped sample presented as complete (**Required**; Explore gallery caps must not be reused as the count — §K/S).  
**Sort:** Most relevant (default).  
**Cards:** checkbox, type, thumb or icon, title, date, extra (duration, from/to, message count, place).  
**Selected rail:** Selected · N; Clear all; originals-unchanged copy.  
**Footer:** Cancel · Add N memories (disabled at 0).  
**Add:** append unique links to working supporting list, default order = add order. Do not generate text.

### E.6 Photo/video Story rail

**Existing I4 shell** (People / Story / Artifact / Source / Learn). Replace Story panel content only.  
**Header:** STORIES USING THIS {PHOTO|VIDEO}. Sub: “This {type} supports N stories.”  
**Cards:** title, Saved/Draft, description, Narrated by / By, memory count, people portraits, chevron → detail (draft_only → editor).  
**+ Add to story:** picker of owner Stories excluding those that already include this source on the **working or saved** supporting list. Selecting one runs table row 12.  
**Create a new story:** B3.  
**Note:** Linking leaves the original unchanged.  
**Out:** rich text, Save Story, narrator editing inside the rail.

### E.7 Cancel, Close, Back, Preview, Discard, unsaved warnings

| Control | Surface | Behavior |
|---------|---------|----------|
| **Escape** | Modal, preview, share, history, add-to-story picker | Dismiss that surface. If dirty modal filters only, discard filter UI not Story. |
| **Escape / Back** | New/Edit with **no** dirty vs last persisted draft | Leave: new → panel; edit → detail. |
| **Escape / Back / Cancel** | New/Edit **dirty** | Modal: “You have unsaved changes.” Stay · Discard changes · Save draft (and then leave). Do not Save Story / Save revision from this warning. |
| **Cancel** | New/Edit | Same as Back. |
| **Close** | Evidence viewer | Pop viewer; restore Explore state. If rail add created a draft, do not warn here (draft already persisted or still in editor). |
| **Preview** | Edit (and New if content exists) | Full-width read-only render of **working** blocks. Close returns to editor. Does not freeze. Does not change Ask. |
| **Discard draft** | Edit; optional on draft_only from panel overflow | Confirm: “Discard this working draft? The saved version stays available to Ask.” draft_only: “Discard this draft? It has never been saved for Ask.” Then table rows 9–10. |
| **Browser unload** | Dirty editor | `beforeunload` warning. |
| **Shell nav away** | Dirty editor | Same unsaved modal as Cancel. |

MBUX §6.4: no autosave mixed with explicit Save. **Save draft / Save Story / Save revision** are the only persist commits besides visibility and rail-add (rail-add **does** persist a working draft so the link survives Close — explicit enough because the owner chose Add to story). **Recommendation:** rail-add is an explicit associate action, not a silent field autosave.

---

## F. Field-level data mapping

| UI | Meaning | Read | Write | Today | After |
|----|---------|------|-------|-------|--------|
| Story id | Identity | `stories.id` | insert | **Existing** | keep |
| Title | Title | version.title | working | `stories.title` | **version** (story may cache display title from Ask-current or working for panel) |
| Description | Short about | version.description | working | **none** | **Required** |
| Blocks | Narrative | `story_version_blocks` | working | `body_text` | **Required** |
| Draft/Saved | Lifecycle | pointers | freeze/discard | `status` active/removed | **Required** pointers |
| Ask available | Has Ask-current | `current_saved_version_id IS NOT NULL` | freeze only | implicit | **Required** |
| Narrator | Voice | version.narrator_person_id | working | `stories.narrator_person_id` | **version**; story may copy for list |
| Editor | Who froze/saved this version | version.editor_person_id | set on freeze; display on working as current owner | `actor_key` text | **Required** Person FK |
| Created | First persist | `stories.created_at` | insert | **Existing** | keep |
| Last saved | Last freeze or draft update | version.updated_at / stories.updated_at | | **Existing** | distinguish last **Ask freeze** vs last draft edit in UI (“Last saved” on detail = last freeze) |
| Date range | Described | version.described_start/end | working | note hack | **Required** (Journal pattern) |
| Place | Named place | version.place_id or text | working | **none** | **Required** |
| Visibility | Share metadata | `stories.visibility` | story row | **none** | **Required** on **story**, not version |
| People | About | version people | working | story-level rels | **versioned** |
| Supporting ids/types/order | Links | version memories | working | unordered evidence UUIDs | **Required** |
| Placement | Memory in a section | block → memory id | working | **none** | **Required** optional |
| Version number | Saved N | version.version_number | freeze | `current_version` int | saved versions only |
| Cover | Panel/detail still | first photo/video memory | derived | note thumb | derived |
| Audio | Recorded narration | version.audio_uri | not in this UX | column unused | keep column; no Dictate UI |

---

## G. Proposed schema changes · H. Versioned blocks · I. Versioned memories

### Alternatives compared

**Alt A — Keep `current_version` integer; add `draft_body` columns on `stories`.**  
Reject. Ask already joins `sv.version = s.current_version`. A draft write that bumps the integer leaks to Ask. Unversioned evidence links cannot freeze order per revision.

**Alt B — Separate `story_drafts` table duplicating version shape.**  
Workable. Ask cannot see drafts if `search_stories` never reads that table. Cost: two shapes to keep in sync (blocks, memories, people). Copy-on-edit and copy-on-freeze still required.

**Alt C — One `story_versions` table; `lifecycle` `working` \| `saved`; Ask pointer is UUID `current_saved_version_id`; working pointer is UUID `working_version_id`.**  
**Recommendation.** Matches the frozen pointer model. One block/memory/people schema. DB constraint: `search_stories` joins **only** `current_saved_version_id`. Working rows are mutable; saved rows are frozen (no UPDATE of content columns).

**Alt D — Event-sourced operations log as source of truth.**  
Reject for this increment. Too far from **Existing** Story service and prove-story.

### Recommended physical model (names are proposals, not existing tables)

**`stories` (identity + pointers + visibility)**

| Column | Role |
|--------|------|
| `id` | Identity (**Existing**) |
| `status` | `active` \| `removed` (**Existing**) |
| `visibility` | `private` \| `shared_with_family` default `private` |
| `current_saved_version_id` | UUID NULL → `story_versions(id)` Ask pointer |
| `working_version_id` | UUID NULL → `story_versions(id)` draft pointer |
| `created_at` / `updated_at` | **Existing** |
| Drop or stop using as Ask pointer: `current_version` integer, `title`, `narrator_person_id` on identity — **Recommendation:** keep `title` and `narrator_person_id` as **denormalized display cache** from Ask-current (or working if draft_only) so panel list stays one query; document they are not Ask source of truth |

**`story_versions` (one row per working or saved snapshot)**

| Column | Role |
|--------|------|
| `id` | Version UUID |
| `story_id` | FK |
| `lifecycle` | `working` \| `saved` |
| `version_number` | INTEGER NULL on working; 1..N on saved; UNIQUE (story_id, version_number) where saved |
| `title`, `description` | |
| `narrator_person_id` | FK people |
| `editor_person_id` | FK people — set on freeze; working displays current owner |
| `described_start_date`, `described_end_date`, `described_precision` | Journal-like |
| `place_id` | nullable FK `places` if present (I10); plus `place_label` text snapshot |
| `body_text` | **legacy flattened text** for Ask token match and migration (see §N) |
| `audio_uri`, `note` | **Existing**; stop using note as photo bus |
| `actor_key` | keep default `owner`; do not use as Editor |
| `frozen_at` | timestamptz NULL until save |
| `created_at`, `updated_at` | working `updated_at` mutates; saved frozen |

CHECK: saved ⇒ version_number NOT NULL AND frozen_at NOT NULL.  
CHECK: at most one working row per story (`working_version_id`).  
CHECK: `current_saved_version_id` must reference `lifecycle='saved'`.

**`story_version_blocks` (H)**

| Column | Role |
|--------|------|
| `id` | |
| `version_id` | FK cascade |
| `position` | INTEGER ordered 0..n |
| `kind` | `heading` \| `paragraph` \| `memory_ref` |
| `text` | heading or paragraph (plain text this increment; rich-text markup **Open**) |
| `memory_id` | nullable FK `story_version_memories` for `memory_ref` |

UNIQUE (version_id, position). Memory_ref does not copy media; it points at the version’s supporting-memory row.

**`story_version_memories` (I)**

| Column | Role |
|--------|------|
| `id` | |
| `version_id` | FK cascade |
| `position` | list order (Add memories / drag) |
| `source_kind` | `photo` \| `video` \| `email_thread` \| `sms_conversation` \| `calendar_event` \| `artifact` \| `journal` \| `audio` |
| `source_id` | text/uuid of that kind’s native id |
| `label_snapshot`, `occurred_on`, `thumb_url` | display cache at link time; not a substitute for the source |
| `attributes_json` | extra (duration, from/to) |

UNIQUE (version_id, source_kind, source_id) — duplicate prevention.  
CHECK source_kind ≠ `story`. Application + CHECK.

Optional placement: a `memory_ref` block references `story_version_memories.id`. Unplaced memories still count in “8 linked memories” and the supporting list.

**`story_version_people`**

`version_id`, `person_id`, `position`. Replaces unversioned `relationships` about_person for Stories. Migrate existing rels onto the saved version.

**Do not** use generic `relationships.cites_evidence` as the freezeable ordered list. Keep reading old rels only for migration.

**Editor vs Narrator:** Narrator is whose account/voice the Story represents (working field). Editor is the Person who performed the freeze (`editor_person_id` on saved versions). Working sidebar Editor = current owner Person, not a free-text mint. Changing Editor independently of who clicked Save is **Open** (single-user: display-only).

---

## J. Read and write API contracts

Replace/extend `memorybox/app.py` Story DTOs. All writes owner-only.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/story` | Panel list: filters status, visibility, person, q, sort; returns display fields + badges; **no** working body to Ask |
| POST | `/story/drafts` | Save draft from ephemeral or update working |
| POST | `/story` | **Save Story** (publish v1) — may start from ephemeral JSON or draft id |
| GET | `/story/{id}` | Detail: current **saved** version + `has_working_draft` |
| GET | `/story/{id}/working` | Working version or 404 |
| POST | `/story/{id}/edit` | Begin/resume working clone |
| POST | `/story/{id}/drafts` | Save draft on working |
| POST | `/story/{id}/revisions` | **Save revision** freeze+pointer |
| POST | `/story/{id}/working/discard` | Discard draft |
| PATCH | `/story/{id}` | Visibility only (and later innocuous identity fields) |
| GET | `/story/{id}/versions` | History list (saved only, no working body required) |
| GET | `/story/{id}/versions/{n}` | Historical saved snapshot |
| PUT | `/story/{id}/working` | Replace working title, description, blocks, memories, people, narrator, dates, place |
| POST | `/story/{id}/working/memories` | Add memories (ordered) |
| DELETE | `/story/{id}/working/memories/{memory_id}` | Unlink |
| PATCH | `/story/{id}/working/memories/order` | Reorder |
| GET | `/story/evidence-search` | Picker contract §E.5 |
| GET | `/story/by-media` | Rail: `source_kind` + `source_id` → Stories using it |
| POST | `/story/{id}/working/memories` from rail | Add this media; create working if needed |
| DELETE | `/story/{id}` | Not in PNG; out unless Archive Health needs it — use `removed` only if product asks later |

**Reject** `actor_key` in `{ai,llm,model,assistant}` on freeze (**Existing**). Also reject a client flag `composed_by_model=true` if present.

**Save Story / Save revision body (conceptual):**

```json
{
  "title": "…",
  "description": "…",
  "narrator_person_id": "uuid",
  "described_start_date": "1998-01-01",
  "described_end_date": "2021-12-31",
  "place_id": "uuid|null",
  "place_label": "Manchester",
  "visibility": "private",
  "person_ids": ["uuid"],
  "blocks": [
    {"kind": "heading", "text": "Christmas was never just a day"},
    {"kind": "paragraph", "text": "…"},
    {"kind": "memory_ref", "memory_client_key": "m1"}
  ],
  "memories": [
    {"client_key": "m1", "source_kind": "photo", "source_id": "immich-uuid"}
  ]
}
```

List/detail responses include `ask_available: boolean`, `lifecycle`, `current_saved_version_number`, `has_working_draft`.

Deprecate silent `source_photo_id` → `note` on `POST /story`. Rail create-new passes `memories: [{source_kind:photo, source_id}]`.

---

## K. Ask indexing and current-saved-version behavior

**Existing:** `search_stories` in `memorybox/ask/retrieve.py` joins `story_versions` on `sv.version = s.current_version` where `s.status = 'active'`. Token match on title+body+narrator+about names. Limit 12. No embeddings. Citations omit supporting `evidence_ids`. Planner `want_story` on exploratory / “stories” asks.

**Required changes**

1. Join **only** `stories.current_saved_version_id = story_versions.id` AND `story_versions.lifecycle = 'saved'`.
2. Never read `working_version_id` in Ask/retrieve/orchestrator/Explore `story_hits`.
3. Token blob: title, description, flattened `body_text` or concatenated paragraph/heading blocks of that saved version, narrator name, about-person names.
4. `draft_only` Stories: zero Ask hits.
5. After Save revision, next Ask sees vN+1; vN remains `GET` by version for history, not default retrieve.
6. No reindex job this increment (SQL on read). If embeddings are added later, trigger on freeze only.
7. Citations: `story_id`, `version_number`, narrator, `provenance_kind=owner_narrator_recollection`. **Recommendation:** add `supporting_memory_refs` (kind+id) on the citation for provenance UI; do **not** concatenate supporting transcripts/photos into the LLM prompt in this increment.
8. Scoped “Ask about this story”: planner note + constraint `story_id`; still no I11 synthesis.
9. I10 pack may include Story hits as today — those hits must be Ask-current saved versions only.

**Do not** set `current_saved_version_id` on Save draft.

---

## L. Sharing / visibility behavior

**Frozen:** independent of Draft/Saved and of Ask.

| Visibility | Meaning this increment |
|------------|------------------------|
| `private` | Default. Owner-only. |
| `shared_with_family` | Recorded intent. Panel visibility filter. Detail/editor display. **Does not** change Ask. **Does not** grant other accounts access (multi-user OUT). |

Share control on detail updates PATCH visibility. Editor visibility dropdown writes on Save draft / Save Story / Save revision **or** immediate PATCH if the Story row already exists. **Recommendation:** persisted Stories PATCH immediately on visibility change (lightweight, reversible, not authored content) — MBUX §6.2. Ephemeral new Story: visibility is client state until first Save draft.

Panel: status tabs All/Drafts/Saved; **separate** visibility filter. No Shared status tab.

---

## M. Existing component reuse

| Capability | Reuse |
|------------|--------|
| Story identity + immutable saved rows | `memorybox/story` — extend, do not replace the idea of `story_versions` |
| Explicit Save / reject AI actor | `create_story` / `save_new_version` guards |
| Narrator Person FK | `stories.narrator_person_id` → move to version |
| Ask `want_story` + `StoryHit` | Planner + retrieve; change JOIN only |
| Explore item `type=story` | `explore/find.py` — still from Ask hits (saved only) |
| Shared evidence viewer shell | I4 rail tabs; replace Story panel |
| Person list + portrait | `/people`, `/people/{id}/portrait` |
| Journal described dates | Copy precision vocabulary, not Journal UX |
| I10 `places` | Optional `place_id` |
| MBQL `plan_ask` | Picker **compile** (person/place/time/type) |
| Explore Find | **Do not** reuse gallery caps as picker totals |
| Artifact Story link | `REL_ABOUT_ARTIFACT` — migrate into `source_kind=artifact` on versions; keep artifact UI create-story as a caller of Save Story |
| Capture STT | **Do not** wire into Story editor this increment |
| Library Story cards | Point at detail; remain undated until described dates exist, then use them |
| `prove-story` | Rewrite expectations: v1 freeze, working draft not in Ask |

---

## N. Migration and backward compatibility for `body_text`

All current rows are **Ask-published by construction** (`create_story` inserts v1 active).

For each `stories` row with `status=active`:

1. Treat existing `story_versions` rows as `lifecycle=saved` with `version_number=version`.
2. Set `current_saved_version_id` to the row matching today’s `current_version`.
3. `working_version_id` NULL.
4. `visibility='private'`.
5. `description` NULL.
6. Blocks: one `paragraph` (or heading+paragraph if title duplicated — **Recommendation:** single paragraph from `body_text`).
7. Flatten cache: keep `body_text` as the paragraph text.
8. People: copy `relationships` about_person onto that saved version.
9. Memories:
   - `cites_evidence` → `source_kind` from `evidence.evidence_kind` mapping (communication → email_thread or sms by payload channel; calendar_event; else skip/unknown **Open**).
   - Artifact `to_type=artifact` → `artifact`.
   - Parse `note` `mb_source_photo=` → `photo` + Immich id; `mb_thumb` display cache. Then stop writing note hacks.
10. `narrator_person_id` / title copy onto the saved version; Editor = narrator or owner if narrator null.
11. Integer `current_version` can remain as a backfill cache but Ask must not use it.

Reads after migrate: old `GET /story/{id}` shape can keep `version.body_text` as flattened blocks for one release. New UI uses blocks.

Empty `body_text` cannot exist today (API min_length 1). No empty saved versions to migrate.

---

## O. Empty, loading, error, destructive-confirmation, permission

| State | Behavior |
|-------|----------|
| Panel empty | CTA New story |
| Panel loading | Skeleton cards; do not flash “no stories” |
| Picker loading | Spinner in grid; keep query |
| Picker zero | “No matching memories.” Filters persist |
| Picker source missing | Card “Unavailable” if id listed but fetch fails; cannot select |
| Rail zero Stories | Empty copy + Add to story + Create a new story (PNG empty vs two cards) |
| Portrait 204 | Letter initial, not a random face crop (**Existing** rule) |
| Save 400 | Inline error; stay in editor; do not clear dirty |
| Save 409 stale working | Reload working or “Another change was saved. Reload.” |
| Ask fail | Story surfaces still work; Ask bar error as Explore does |
| Discard | Confirm dialogs in §E.7 |
| Remove supporting memory | Confirm only if needed; Recommendation: instant remove on working with Undo toast (MBUX 6.2 lightweight) |
| Permission | Single owner. Unauthenticated 401. No other user. Visibility does not open data. |
| Story not found | 404 panel message |
| Historical version missing | 404 on version GET |

---

## P. Accessibility and keyboard

MBUX-001 §§7–8.

- New/Edit: initial focus **Title**.
- Tab order: title → description → editor → memories → sidebar → Save cluster.
- Enter in title does not submit Save Story (accidental publish). Enter in Ask bar submits Ask.
- Escape: §E.7.
- Modal: focus trap; return focus to Add memories.
- Cards and rail cards: keyboard activatable; portraits alt = full name.
- Status dots not color-only: include text Saved/Draft.
- Drag reorder: keyboard alternatives (Move up/down in overflow).
- Preview and detail: headings use real heading levels from `heading` blocks.
- Contrast: PNG dark theme must meet the same Explore contrast bar as I4.

---

## Q. Implementation slices (dependency order)

Not authorized until this PRD is signed off and an increment definition is approved. Sequence for the later Stories branch:

1. **Schema + migrate** — pointers, lifecycle, blocks, versioned memories/people, visibility; backfill `body_text`; stop Ask using integer `current_version`.
2. **Story service + APIs** — draft/freeze/discard/visibility; prove Ask cannot see working; prove freeze atomicity; reject Story source_kind; reject AI freeze.
3. **Panel + detail read** — list filters (corrected tabs), cards, detail block render, portraits, revision history read.
4. **New + edit writers** — explicit Save draft / Save Story / Save revision; unsaved warnings; Preview; no compose/dictate.
5. **Picker** — `/story/evidence-search` complete counts + pagination; type tabs; Add N; originals unchanged.
6. **Rail** — `/story/by-media`; Add to story; Create new; Open detail; I4 shell preserved.
7. **Ask citations + scoped Ask about this story** — supporting refs listed, not dumped into the model.
8. **Prove + FlightSim** — rewrite `prove-story`; five walkthroughs; Library/Archive Health undated → described dates.

Slice 1–2 are blocking for any UI. Slice 5–6 can overlap after 2.

---

## R. Test plan and acceptance criteria

### Harness (`prove-story` rewrite)

- Create draft → Ask miss; GET list Drafts hit; `ask_available=false`.
- Save Story → v1 saved; Ask hit current v1; working null.
- Edit → working clone; Ask still v1; GET working ≠ GET saved body.
- Save revision → v2 Ask-current; GET v1 body preserved.
- Discard working → Ask still v1; working 404.
- Add photo + video + artifact; reorder; remove; sources unchanged.
- Reject source_kind=story.
- Visibility patch does not change version_number or Ask pointer.
- Freeze with `actor_key=ai` rejected.
- Migration: existing prove fixtures become saved v1 with one paragraph block.

### UI / FlightSim

Walkthroughs 1–5 from the assessment, plus:

- Panel filters All/Drafts/Saved and visibility separate; no Shared status tab.
- Full names + portraits on panel, detail, editor, rail.
- Placeholder “Start writing your story…”
- Rail lists Stories using a real video; add-to-existing; create new; Close restores Explore.
- Unsaved Cancel warning; Discard confirm; Preview does not publish.
- Picker “N matches” is not an arbitrary 800-cap sample for the same query.

### EVS trace (this slice, not I11)

EVS-172, 173 (SQL find, not semantic), 175 (narrator), 177–180, 061/071 capture-without-auto-AI. EVS-181/182 remain I11.

---

## S. Risks, unresolved technical questions, repository evidence

### Repository evidence (current)

- Schema: `memorybox/migrations/001_domain_v0.sql` `stories`, `story_versions`.
- Service: `memorybox/story/__init__.py` (`create_story`, `save_new_version`, `associate_*`).
- UI: `memorybox/story/static/story.html`; route `GET /story/ui`.
- APIs: `memorybox/app.py` `StoryCreateRequest`, `POST /story`, `POST /story/{id}/versions`.
- Ask: `memorybox/ask/retrieve.py` `search_stories`; `memorybox/planner/__init__.py` `want_story`; `memorybox/ask/orchestrator.py` citations.
- Rail: `memorybox/explore/static/explore.js` Story tab + photo Add story query params.
- Portraits: `GET /people/{id}/portrait` — `fetch_person_portrait_bytes`.
- Journal dates: `memorybox/migrations/002_journal_i5a.sql`.
- Explore caps: `memorybox/explore/find.py` `_HIDDEN_SMS_CARD_SAMPLE = 800`, email/calendar 800.
- Capture STT: `POST /capture/transcribe` — not a Story save.
- PNG commit: `c95117b` on `origin/cursor/marvin-capture-v01-3344` only.
- I11 out: `docs/product/MBBS-P2_INCREMENT_10_DEFINITION.md`, `MBRM-001A`.

### Risks

| Risk | Why |
|------|-----|
| Ask leak | Any code path that joins working versions or bumps integer `current_version` on draft |
| `relationships` unversioned | Edit would mutate v1 evidence while Ask still points at v1 |
| Picker caps | Owner thinks 24 matches is the archive when retrieve truncated |
| Rich text vs plain blocks | PNG toolbar vs **Recommendation** plain heading/paragraph this increment |
| Rail add creating drafts | Proliferation of empty working drafts — require the target Story picker, not silent |
| Note-field photos | Dual links after migrate if both evidence UUID and Immich id exist |
| I11 creep | Editor placeholder/tools inviting compose |
| Stacked branch | Implementing on I10 would mix correlation with Stories |

### Open technical questions

1. **Increment number** after I10 (not I11).
2. **Save Story minimum content:** title-only allowed or require paragraph or one memory?
3. **Rich text:** persist plain text + heading kinds only, or HTML subset? Recommendation: plain text + heading/paragraph/memory_ref; toolbar Bold/Italic can wait.
4. **Picker complete counts** for Immich photos/HVRT videos vs SQL evidence. Need a count path that is not the Explore gallery cap.
5. **Email thread vs one email, SMS conversation vs one message** — native grain for `source_id`.
6. **Audio source_kind** vs spoken-moment spans vs `story_versions.audio_uri`.
7. **Editor dropdown** on edit PNG vs single-owner display-only.
8. **Place:** `places.id` vs label-only until Place UX exists.
9. **`+ Filters` Event and Source** exact chip set (not visible on the modal PNG).
10. **Historical detail** from revision history: read-only saved snapshot; confirm no “restore this version” in this increment (can Save revision from a clone later).
11. Whether **Library** should list `draft_only` Stories (Recommendation: no; Library is Ask-adjacent meaning).

---

## What can be reused / adapted / added / not built

| Reuse unchanged | Adapt | Add | Do not build |
|-----------------|-------|-----|--------------|
| Saved version rows idea; AI persist reject; `want_story`; viewer shell; portraits endpoint; Journal date fields as pattern | `search_stories` JOIN; Story APIs; rail panel; `prove-story`; Library undated once dates exist | Pointers, working clone, blocks, versioned mixed links, picker, panel/detail/editor, visibility, unsaved/discard/preview | I11 compose; dictation; Story-in-Story; Shared status tab; first-name pills; in-rail authoring; autosave; multi-user ACL; cherry-pick PNGs onto I10 |

---

## Decision status

PRD **draft**. **Not** build-authorized.

Owner sign-off needed on this document (and increment number) before a Stories implementation branch is cut from the accepted post-I10 baseline.

No code, schema, tests, or cherry-picks are included with this PRD.
