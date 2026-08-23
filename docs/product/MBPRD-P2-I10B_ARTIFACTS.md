# MBPRD-P2-I10B — Artifacts

**Status:** Increment **ACCEPTED** 2026-08-23 (Tom: “i10B is accepted”) · FlightSim prove-artifact **ok**  
**Date:** 2026-08-23  
**Base (this PR):** `cursor/p2-i10a-stories-49da`. Before merge, rebase or retarget onto the accepted integration branch after I10A lands.  
**Increment definition:** [MBBS-P2_INCREMENT_10B_DEFINITION.md](MBBS-P2_INCREMENT_10B_DEFINITION.md)  
**Assessment reconciliation:** [MBAS-P2-I10B_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10B_ASSESSMENT_RECONCILIATION.md)

**Visual baseline:** Artifact drafts on commit `fe913a4` (`cursor/marvin-capture-v01-3344`):

| File (under `docs/source/Screens/MBUX Story Screens/`) | Screen |
|---|---|
| `MBUX-Artifacts-Panel-Draft-v1.png` | Artifacts panel |
| `02_MBUX_Artifact_New_Draft_v1.png` | New Artifact |
| `03_MBUX_Artifact_Detail_Draft_v1.png` | Artifact detail |
| `04_MBUX_Artifact_Edit_Draft_v1.png` | Edit Artifact |
| `05_MBUX_Artifact_Add_Representation_Draft_v1.png` | Add representation modal |
| `06_MBUX_Artifact_Add_Supporting_Memories_Draft_v1.png` | Add supporting memories modal |
| `07_MBUX_Artifact_Rail_Photo_Draft_v1.png` | Photo Artifact rail |
| `08_MBUX_Artifact_Rail_Video_Draft_v1.png` | Video Artifact rail |

Copy these into `docs/source/Screens/MBUX Artifact Screens/` before implementation. Journal and Person Edit PNGs on the same commit are **not** this increment.

**Depends:** I1–I8A **ACCEPTED** · I9 Artifact domain · I10 **ACCEPTED** · I10A Stories **ACCEPTED** · I10 `places` · owner Person (`MEMORYBOX_OWNER_PERSON_ID`) · **I10A.2 Unified Voice Capture** before Tell its story

**Does not start:** I10C Journal build · I11 · nested Artifacts · Artifact-private recorder · file GC · suggested memories · Artifact→Artifact memories · family multi-user ACL · Face SoT

**Increment ID:** **P2-I10B — Artifacts.** This is **not** I11.

**Legend**

| Label | Meaning |
|---|---|
| **Frozen** | Owner decision. Do not reopen without a new decision. |
| **Existing** | Confirmed in the repository. |
| **Required** | Must be built for this slice. |
| **Recommendation** | Implementation choice. Change only with a recorded reason. |
| **Open** | Technical question. Does not block PRD review. |

---

## Frozen product decisions

Owner lock 2026-08-23.

1. Panel filters: **All / Objects / Documents / Recipes / Other**. Map to existing kinds. Do not keep Heirlooms and Keepsakes together.
2. Optional Artifact date with precision: exact day, month, year, or approximate year.
3. Place uses MemoryBox Place (`places`). No free-text Artifact location SoT.
4. Visibility reuses I10A: `private` | `shared_with_family`. Private remains Ask-available to the **owner**. Authorization must not expose Artifacts to unauthorized users.
5. **No** Artifact working draft. Save Artifact creates `active` — visible in the panel and Ask (subject to visibility).
6. Save without a representation is allowed. Show **Needs context / Needs representation**.
6a. **New Artifact representation staging (Frozen):** files chosen on New stay **browser-local** until Save. Save creates the active Artifact first, then uploads representations against that id. Upload failure keeps the Artifact, shows Needs representation plus a recoverable error, and allows retry. Cancel before Save creates **no** Artifact row, representation row, or server-preserved file.
7. Nested/container Artifacts are **out**. Remove “12 items inside.”
8. Delete Artifact and remove representation: **soft-remove** records/links; **preserve** original uploaded files. GC out of scope.
9. Canonical Story↔Artifact link is I10A `story_version_memories` `source_kind=artifact`. Do not add a second competing write path. Compat-read existing `about_artifact`.
10. Supporting memories: photo, video, communications, calendar, journal, audio. Artifact→Artifact **out**.
11. Photo/video rail overflow: **Remove link from this Artifact** + confirm. Does not delete source media or the Artifact.
12. Creator provenance is the acting owner/account. Show “Added by {name}” when resolvable. Do not create ArtifactPerson for data entry.
13. Suggested memories **out**. Honest search, filters, explicit selection.
14. Representations in I10B: **images and documents**. Audio is supporting evidence. Video-as-representation playback is not required unless already low-risk.
15. Must support: link existing Story; create new Story with Artifact prelinked; **Tell its story** by microphone via the **shared** I10A.2 workflow.

**PNG supersessions (frozen over pixels)**

- Filter chips: not Heirlooms / Keepsakes.
- Cigar Box card must not say “12 items inside” (use people/memories/stories/place/needs-context only).
- Description helper wins over the New-Artifact placeholder that invites testimony. Helper: describe the **object**; recollections are Stories.
- Add-memories chips: Memory (all) / Photos / Video / Communications / Calendar / Journal / **Audio**. No Artifacts chip.
- No Draft badge on Artifacts. Saved + Available to Ask are derived from `active` + Ask eligibility.
- Tell its story is a compact Artifact action that **opens the shared Story editor** with the Artifact prelinked, not an embedded Story form. I10B must not implement an Artifact-specific `MediaRecorder`.
- New Artifact may *stage* files in the browser; they are not server objects until after Save (supersedes any reading that uploads on Add before Save).

---

## A. Scope and non-scope

### Problem

I9 proved Artifact ≠ file, but the UI is a light-theme POC with an embedded Story/mic form. Families need a first-class object: multiple preserved views, people and Place, Stories for meaning, supporting evidence from the archive, and honest photo/video rails.

### Success

1. Owner can create, open, edit, and soft-remove Artifacts in I10A chrome.
2. Multiple image/document representations; originals survive metadata edit and soft-remove.
3. Supporting memories link without altering sources.
4. Stories attach only as I10A versioned memories; Tell its story never writes Artifact description.
5. Photo/video rails list links, add to existing, create new (photo/video as **evidence**), remove link.
6. Ask retrieves the owner’s active Artifacts (including Private) by label/description/kind.
7. No Artifact-specific recorder ships.

### In

Panel, New, Detail, Edit, representation modal, memory modal, photo/video Artifact rails, Story link/create/Tell its story (via I10A.2), schema/API listed below, `about_artifact` compat.

### Out

See definition. I10A.2 **implementation** is a prior increment; this PRD only **consumes** its contract.

---

## B. Existing reusable capability

| Capability | Where | I10B use |
|---|---|---|
| Artifact identity, kinds, label, description, status, unresolved flags, metadata revisions | `004_artifact_i9.sql`, `memorybox/artifact` | Extend; do not replace |
| MB-managed representations + hash + `MEMORYBOX_ARTIFACT_MEDIA_ROOT` | `add_mb_managed_representation`, `/bytes` | Image/document uploads |
| `evidence_ref` representation | `add_evidence_ref_representation` | **Do not** use as the supporting-memory list |
| People associate + Immich lazy-teach | `associate_person*` | Keep; add unlink |
| List/get/create/revise APIs | `GET/POST /artifact`, `POST …/revise` | Extend DTOs |
| Ask `search_artifacts_for_ask` | `artifact/__init__.py`, `ask/retrieve.py` | Add visibility owner rule |
| I10A chrome, people picker, memory search | `story.html`, `story/search.py` | Adapt persist target |
| I10A Story editor, draft/save, `source_kind=artifact` | `memorybox/story` | Prelink + link existing |
| I10A rail pattern | `explore.js` `renderStoryRail` | Artifact rail analog |
| Places upsert/get | `correlate/store.py` `upsert_place`, `POST /correlate/place` | Artifact Place |
| Visibility enum | `stories.visibility` | Same strings on Artifact |
| Described-date precision | `story_versions` / Journal | Subset for Artifact date |
| Owner Person | `profile/owner.py` | “Added by …” |
| Capture preserve + STT | `POST /capture/transcribe`, `providers/capture` | **Only via I10A.2 UI** |
| Soft-remove pattern | Stories `status=removed` | Artifact + representation + links |

---

## C. Required extension

- I10A-style Artifact surfaces (replace POC HTML).
- Columns: visibility, **one** optional `described_start_date` + `described_precision` (no `described_end_date`), `place_id`, representation `status`, representation `view_kind`, optional caption; Artifact supporting-memory table with unique `(artifact_id, source_kind, source_id)`.
- Person unlink via `relationships.status='superseded'` only; soft-remove Artifact; soft-remove representation.
- Memory add/remove; `/artifact/by-media`.
- Story query `artifact=` (+ I10A.2 `capture=`); stop `POST /artifact/{id}/story` as UX.
- Place picker bound to `places`.
- Needs context / Needs representation on panel + cards.
- Kind filter mapping.
- Owner Ask + visibility (no unauthorized leak).

---

## D. Obsolete POC behavior to retire

| Item | Action |
|---|---|
| `artifact.html` light single-page form | Replace with I10A chrome |
| Embedded mic / STT / narrator / Story body / Save Story + link | **Delete from Artifact UI** |
| `POST /artifact/{id}/story` and `create_story_for_artifact` as product path | Retire UI callers. Optional internal wrapper that only calls I10A Save + memory insert — **Recommendation:** delete the HTTP route once I10A.2 + prelink exist |
| Explore Artifact rail placeholder (`artifact_title` / Browse only) | Replace with real rail |
| Heirlooms + Keepsakes chips | Do not implement |
| “12 items inside” | Do not implement |
| Suggested-from-this-artifact ranking | Do not implement |
| Dictating Artifact description | Forbidden |

---

## E. I10A.2 dependency (Unified Voice Capture & Transcription)

I10B **must not** implement a private Artifact recorder while waiting for I10A.2.

I10A.2 is a **new increment** after I10A.1. It does **not** reopen I10A acceptance. I10A froze “no dictation”; I10A.2 adds dictation **inside the Story editor**.

### I10A.2 must deliver (Stories first)

1. Start / pause / stop recording.  
2. Review / play original audio.  
3. Submit for transcription (not auto-publish).  
4. States: recording, uploading, queued, transcribing, completed, failed.  
5. Review and edit transcript before Story save.  
6. Place transcript into Story body blocks.  
7. Preserve original audio + provenance (`audio_uri` / capture handle).  
8. Identify or confirm narrator.  
9. Explicit Save Story / Save revision; STT completion does **not** publish.  
10. Reuse `CaptureSttProvider` + `POST /capture/transcribe` (or a job API that still preserve-then-transcribe).  
11. Shared UI so Journal (I10C) and Artifact (Tell its story) do not fork recorders.

### I10B consumption

- Artifact action **Tell its story** → `/story/ui?new=1&artifact={id}&capture=1` (names **Recommendation**).  
- Artifact prelinked as `source_kind=artifact`.  
- Return to Artifact detail after successful **Save Story**.  
- Cancel/discard in Story editor: no new Ask-visible Story; Artifact unchanged.

### Journal contract (define now, build in I10C)

Same shared capture. Transcript → Journal body. Author/date/provenance/versions. Explicit Save Journal. Does not create a Story.

### Shared speech requirements (I10A.2 owns numbers)

Browser permission; formats (existing webm/opus, webm, mp4); `MEMORYBOX_CAPTURE_DIR` originals; max duration/size (**Open** in I10A.2; do not invent in I10B); async job vs long sync (**Recommendation:** keep preserve-then-transcribe; add queued/transcribing if the request cannot stay open); retry; cancel; duplicate `audio_id` guard; recording-ok/STT-fail keeps audio and allows typing; STT-ok/user-cancel does not Save; a11y/keyboard.

**Existing vs I10A.2**

| Need | Existing | I10A.2 |
|---|---|---|
| Preserve then STT | **Existing** | wrap |
| 422 + audio handle | **Existing** | keep |
| Record/Stop/device/level | Duplicated in Journal + Artifact HTML | **one component** |
| Pause, playback before STT, job states | **Missing** | **Required** |
| Story editor wiring | **Missing** | **Required** |
| Video archive queue | Different stack | do not conflate |

---

## F. Data model

### `artifacts` — Existing + Required

| Column | Role |
|---|---|
| `id`, `kind`, `label`, `description`, `status`, `current_metadata_revision`, `unresolved_context_json`, `attributes_json`, `created_at`, `updated_at` | **Existing** |
| `visibility` | **Required** `private` \| `shared_with_family` default `private` |
| `described_start_date` | **Required** nullable DATE — the **only** Artifact date value |
| `described_precision` | **Required** `day` \| `month` \| `year` \| `approximate` \| `unknown` |
| `place_id` | **Required** nullable FK `places(id)` ON DELETE SET NULL — **sole** editable and display SoT for Place |

**Do not** add `described_end_date`. I10B is one optional date, not a range.

**Frozen precision UI:** exact day → `day`; month → `month`; year → `year`; approximate year → `approximate` (store that year on `described_start_date`, e.g. 1999-01-01, display “about 1999”). Empty → `unknown` + null `described_start_date`.

**Place SoT (Frozen):** create/edit/display/Ask hydration read and write **`artifacts.place_id` only**. I10B runtime **must not** dual-write `relationships` `about_place`. If `about_place` is retained later for graph compatibility, it is **derived** data rebuilt from `place_id` and is never a competing value. I10B does not require that rebuild.

**Do not** add `location_text`.

### Kind filter (**Frozen** mapping)

| Chip | `artifacts.kind` IN |
|---|---|
| All | (no kind predicate) |
| Objects | `keepsake_object`, `photograph_of_object` |
| Documents | `letter`, `document`, `clipping` |
| Recipes | `recipe_card` |
| Other | `other` |

Create/edit Kind dropdown still uses the **Existing** seven kinds with human labels (Keepsake / object, Letter, …).

### Needs context / Needs representation (**Frozen**)

An Artifact **needs context** if any of:

- `unresolved_context_json.person` is true (and no people links), **or**
- `unresolved_context_json.place` is true (and `place_id` is null), **or**
- `unresolved_context_json.event` is true, **or**
- zero **active** representations (**needs representation**)

Panel chip **Needs context • N** counts those rows. Cards may show Needs context and/or Needs representation. Clearing people/place sets the matching unresolved flag false (**Existing** person behavior).

### `artifact_metadata_revisions`

**Existing.** Revise still inserts a revision. Include new metadata columns in the revision row (**Required** extend). Not a user-facing version browser in I10B.

### `artifact_representations` — Existing + Required

| Column | Role |
|---|---|
| storage fields (`representation_kind`, uri, hash, mime, filename, byte_size, sort_order, evidence_id, media_object_id) | **Existing** |
| `label` | **Existing** optional display label (e.g. “Engraving on back”) |
| `view_kind` | **Required** `front` \| `back` \| `detail` \| `engraving` \| `document` \| `other` (I10B image/document). Audio/video values reserved, not required in UI. |
| `caption` | **Required** optional text (`attributes_json.caption` acceptable if a column is deferred — **Recommendation:** column) |
| `status` | **Required** `active` \| `removed` default `active` |

Primary representation: **Recommendation:** lowest `sort_order` among `active`. No extra flag unless UX needs an explicit “Make primary.”

**I10B representation formats (Frozen).** Accept and preserve original bytes for this set only as *new* uploads. Do not imply universal document rendering.

| Class | MIME | Extensions | Product presentation |
|---|---|---|---|
| Image | `image/jpeg` | `.jpg`, `.jpeg` | **Inline preview** (`<img>` via `/bytes`) |
| Image | `image/png` | `.png` | **Inline preview** |
| Image | `image/webp` | `.webp` | **Inline preview** |
| Image | `image/gif` | `.gif` | **Inline preview** |
| Image | `image/heic`, `image/heif` | `.heic`, `.heif` | **Preserve original.** Inline preview **only** if an already-reusable decoder exists; otherwise honest fallback card + **download / open original** |
| Document | `application/pdf` | `.pdf` | **Download / open original** only. No I10B PDF renderer. |
| Document | `text/plain` | `.txt` | **Download / open original** (optional short text excerpt is not required) |

Reject other MIME on I10B upload with an honest error (including Office `.doc`/`.docx` unless later authorized). Serving a pre-I10B `mb_managed` file of another MIME may use the same **download / open original** fallback — no new player.

**No** I10B requirement for a representation video player or audio-as-representation.

Soft-remove: set `status=removed`. **Do not** delete the file. List/detail omit `removed`. **`GET …/bytes` for a `removed` representation must not return product-visible bytes** (404 or equivalent). The original file remains on `MEMORYBOX_ARTIFACT_MEDIA_ROOT`. Integrity hash check **Existing**.

### Artifact supporting memories — **Required** new table

**Recommendation** name: `artifact_memories`

| Column | Role |
|---|---|
| `id` | UUID |
| `artifact_id` | FK cascade (row delete only if Artifact row hard-deleted — product uses soft-remove) |
| `position` | order |
| `source_kind` | `photo` \| `video` \| `email_thread` \| `sms_conversation` \| `calendar_event` \| `journal` \| `audio` |
| `source_id` | native id (Immich photo/video id, evidence id, journal id, capture/audio id) |
| `label_snapshot`, `occurred_on`, `thumb_url`, `attributes_json` | display cache |
| `status` | `active` \| `removed` |
| `created_at` | |

**Uniqueness and relink (Frozen):**

- One row per `(artifact_id, source_kind, source_id)` for the life of the Artifact.
- Database: `UNIQUE (artifact_id, source_kind, source_id)` on `artifact_memories` (all statuses). Not a partial unique-on-active-only index.
- Add when no row exists: `INSERT` `status='active'`.
- Remove: `UPDATE status='removed'`. Do not `DELETE` the row. Person/media/journal/audio sources are untouched.
- Re-add a previously removed source: **reactivate** that row (`status='active'`; refresh snapshots/position as needed). **Do not INSERT** a second row. The unique constraint makes a duplicate insert fail; the service must UPDATE instead.
- Product lists and `/artifact/by-media` count **`status='active'` only**.
- CHECK `source_kind` ≠ `artifact` and ≠ `story`.

Linking never updates the source object. Soft-remove the link only.

Communications grain: same as I10A (`email_thread` / `sms_conversation` via evidence ids).

### People

**Existing** `relationships` `about_person`. **Frozen unlink:** set `relationships.status='superseded'` (canonical soft-unlink on `001_domain_v0.sql` CHECK: `candidate | confirmed | rejected | superseded`). **Do not** hard-delete the relationship row. **Do not** treat DELETE as an equal option. The Person and all source media survive. `_load_links` already ignores non-`candidate`/`confirmed` rows. Do not use people links for creator.

### Stories

Canonical: `story_version_memories.source_kind='artifact'`, `source_id` = Artifact UUID.

Compat: read `relationships` `about_artifact` until backfill (see §J).

Runtime link existing Story: add memory on that Story’s **working** version (create working from saved if needed) — **same as I10A “add to story.”** Artifact list shows Stories with the memory on working or current saved, plus leftover `about_artifact`. Draft Stories display as Draft.

### Visibility and Ask

| Visibility | Panel | Owner Ask | Other users |
|---|---|---|---|
| `private` | Yes | Yes | **No** (no other user in this increment; do not add public routes) |
| `shared_with_family` | Yes | Yes | Intent only; **no** ACL grant in I10B (same as I10A) |

`ask_available` on Artifact **derived**: `status=active`. Visibility does not hide from **owner** Ask.

### Creator provenance

Display `Added by {owner.display_name} · {created_at date}` when owner Person resolves. Else omit the name, keep the date. `actor_key` stays `owner`.

---

## G. Screen contracts

Chrome on all Artifact surfaces: MemoryBox mark, family nav (Artifacts active), Ask bar. Dark I10A theme.

### G.1 Panel

- Search → `GET /artifact?q=` (**Existing** ILIKE).
- Filters: All / Objects / Documents / Recipes / Other; Needs context; People; sort Recently updated (**Existing**).
- + Add artifact → New.
- Card: primary thumb (`/bytes` or honest empty), Name (`label`), subtitle from date **or** kind label (not container counts), people (hydrated), memory count, story count, place name, needs badges.
- Open card → Detail (`?id=`).

### G.2 New / Edit

- Name, description (object metadata only).
- Sidebar: Kind, **one** approximate date + precision (no end date), Place picker (`place_id`), Visibility, People, provenance.
- New may save with empty representations.

**New — representation staging (Frozen):**

1. Add representation on New stages files **in the browser only** (name, type, caption, local preview). No `POST /artifact`, no `POST …/representations`, no write under `MEMORYBOX_ARTIFACT_MEDIA_ROOT`.
2. **Save artifact** `POST /artifact` creates the `active` Artifact first.
3. The client then uploads each staged file with that `artifact_id`.
4. If any upload fails: Artifact **remains saved**; show **Needs representation** (if zero active reps) **and** a recoverable per-file error; owner may retry those uploads without creating a second Artifact.
5. **Cancel** before Save: no Artifact row, no representation row, no server-preserved file. Browser memory is discarded.

**Edit:** Artifact already exists. Add representation uploads immediately (`POST …/representations`). Remove is soft (`status=removed`). Cancel Edit does not revise metadata and does not undo uploads already completed in that session (**Recommendation:** say so in the UI). Stories stay in the Story editor.

### G.3 Detail

- Derived Saved + Available to Ask (if `active` and owner Ask-eligible).
- Delete artifact (confirm) → soft-remove.
- Edit artifact.
- Representation viewer (active only); tabs by `view_kind`.
- Kind • date • place; description; people; Stories (title, narrator, Saved/Draft) + **Add story** + **Link existing story** + **Tell its story**.
- About / Connections counts.
- Supporting memories cards (open source, do not alter).

### G.4 Add representation modal

- Drop/browse **accepted** image or document MIME only (table in §F).
- Type (`view_kind`), optional label, optional caption.
- Preservation copy (**Existing** semantics) applies **after** the file is stored on Save (New) or immediate upload (Edit).
- On New: Add representation stages locally; modal Cancel drops that staged file only.
- On Edit: Add representation uploads to the existing Artifact.

### G.5 Add supporting memories modal

- Search + chips (all + six kinds). No suggestions block (or replace with “Search results” empty until query).
- Multi-select; Add memories / Cancel.
- Helper: evidence vs representation.

### G.6 Photo / video rails

- Linked Artifacts where this media is an **active supporting memory**. Badge: supporting evidence.
- Open artifact.
- Overflow: Remove link + confirm.
- Choose artifact + Add to existing (writes memory; not a representation).
- + Create new artifact: New with this media prelinked as memory (`?photo=` / `?video=` analog). Help text: begins as supporting evidence.
- Footer: linking preserves original.

---

## H. APIs (**Required** unless noted Existing)

| Method | Path | Purpose |
|---|---|---|
| GET | `/artifact/ui` | I10B chrome (**Existing** path, new HTML) |
| GET | `/artifact` | List: q, kind_group, person_id, needs_context, visibility, limit |
| POST | `/artifact` | Save new (active) |
| GET | `/artifact/{id}` | Detail DTO (hydrated people, place, memories, stories) |
| POST | `/artifact/{id}/revise` | Metadata revision (**Existing**, extend body) |
| PATCH | `/artifact/{id}` | Visibility / place / date / people convenience — **Recommendation** |
| POST | `/artifact/{id}/removed` | Soft-remove Artifact |
| POST | `/artifact/{id}/representations` | Upload image/document (**Existing**) |
| POST | `/artifact/{id}/representations/{rid}/removed` | Soft-remove representation |
| GET | `…/representations/{rid}/bytes` | **Existing**; **must 404 (or equivalent) if `status=removed`**; file remains on disk |
| POST | `/artifact/{id}/persons/{pid}` | **Existing** |
| POST | `/artifact/{id}/persons/{pid}/removed` | Unlink: `status='superseded'` only — **not** HTTP DELETE of the row |
| GET/POST | `/artifact/{id}/memories` | List / add |
| POST | `/artifact/{id}/memories/{mid}/removed` | Unlink memory |
| GET | `/artifact/by-media` | Rail: kind + source_id |
| GET | `/story/ui?new=1&artifact=` | I10A editor prelink (**Required** Story boot) |
| POST | `/story/.../memories` | Link existing Story (**Existing** I10A) |
| POST | `/artifact/{id}/story` | **Obsolete** |

Reject AI `actor_key` on Artifact revise if that guard exists on Story (**Recommendation** copy).

---

## I. Workflows

1. **Create** — Panel → New → Save → Detail. Immediate `active`. Staged files upload after Save (G.2).  
2–3. **Representations** — after Artifact exists: modal upload; hash idempotent (**Existing**). New-before-Save is browser-local only.  
4. **Open** — `GET` by id; 404 if removed.  
5. **Edit metadata** — new revision; bytes untouched.  
6. **People** — add; unlink = `superseded`.  
7. **Memories** — add / soft-remove (`removed`); relink = reactivate same unique row; originals unchanged.  
8. **Link existing Story** — picker of I10A Stories; add `source_kind=artifact` to working; confirm if that creates a draft.  
9. **New Story** — Story editor, artifact prelinked; explicit Save Story; return.  
10. **Tell its story** — I10A.2 capture in Story editor; same save; return.  
11–13. **Rails** — as G.6.  
14. **Delete Artifact** — confirm; `status=removed`; hide from panel/Ask; keep files and child rows.  
15. **Remove representation** — confirm; `status=removed`; keep file.

Cancel New before Save: no Artifact, no representation, no server file. Cancel Edit: no metadata revise. Cancel Story/capture: Artifact unchanged.

---

## J. Migrations and compatibility

1. ALTER `artifacts` add visibility (default `private`), `described_start_date`, `described_precision` default `unknown`, `place_id`. **Do not** add `described_end_date`.  
2. ALTER `artifact_representations` add `view_kind` (backfill from `label` when it matches front/back/detail/engraving/document, else `other`), `caption`, `status='active'`.  
3. CREATE `artifact_memories` with `UNIQUE (artifact_id, source_kind, source_id)` and `status`.  
4. Backfill `about_artifact` → `story_version_memories` on current saved version (or working if draft_only). See assessment §5.  
5. Existing Artifacts stay `active`. Unresolved flags unchanged.  
6. Do not delete `about_artifact` rows in I10B (read-compat). **Recommendation:** stop new writes.  
7. Do not move `evidence_ref` into `artifact_memories` automatically.  
8. Capture files and Journal audio untouched.

---

## K. Ask and Explore

- Retrieve `status=active` only. Owner may see `private`.  
- **Unauthorized retrieval (Frozen):** list/get/Ask/bytes must not return another principal’s Artifacts. This increment is single-owner; do not add unauthenticated or cross-account Artifact read routes. Any future non-owner request must fail closed (401/403 / empty). `shared_with_family` does not grant access in I10B.  
- Token match: label, description, kind (**Existing**). Date/place names **Recommendation** add if cheap.  
- Deep link `/artifact/ui?id=`.  
- Explore Artifact type filter **Existing**; rail **Required**.  
- Library cards **Existing**; point at new detail.

Do not Ask-index `removed`. Do not Ask-index representation filenames as meaning (**Existing** comment).

---

## L. UI work

- Replace `memorybox/artifact/static/artifact.html` (or inject I10A shell).  
- Story.html: parse `artifact` (and I10A.2 `capture`) on boot.  
- explore.js: Artifact rail parity with Story rail, different persist.  
- Reuse people picker, confirm dialogs, thumbs.  
- Remove duplicated Artifact mic script.

---

## M. Acceptance criteria (when build-authorized)

1. Create Artifact with name+kind, no file → panel card + Needs representation; Ask can match label (owner).  
2. **New Save then upload (success):** stage two allowed files on New (browser-local); Save creates one Artifact; both uploads succeed as active representations; originals preserved; no second Artifact.  
3. **Partial upload failure:** Save succeeds; one staged upload fails; Artifact remains `active`; Needs representation if zero active reps; recoverable error; **retry** of the failed file creates the missing representation without a duplicate Artifact.  
4. **Cancel before Save:** after staging files locally, Cancel → zero Artifact rows, zero representation rows, zero new files under `MEMORYBOX_ARTIFACT_MEDIA_ROOT` for that attempt.  
5. Add two image/document representations on Edit; metadata edit does not rewrite bytes.  
6. Soft-remove one representation; **file still on disk**; UI hides it; **`GET …/bytes` does not return product-visible bytes**.  
7. Soft-remove Artifact; gone from panel/owner Ask; files remain.  
8. Kind chips return only mapped kinds.  
9. One optional date + precision persist; **no** `described_end_date`; Place persists as `place_id` only; visibility persists; no location string.  
10. People unlink sets `relationships.status='superseded'`; Person row and media survive; hard-delete of the relationship is not used.  
11. Add photo + journal as memories; sources unchanged; Artifact→Artifact rejected.  
12. **Relink:** remove a supporting memory; re-add the same `(source_kind, source_id)` → exactly one active link (reactivation); unique constraint holds; prove this.  
13. Link existing Story writes `source_kind=artifact`; Artifact detail lists it; `about_artifact`-only legacy Story still lists after migrate or compat read.  
14. New Story from Artifact opens I10A editor with prelink; Save Story required for Ask.  
15. Tell its story (after I10A.2): opens shared Story editor; mic path creates a Story, not Artifact description or representation; no Artifact `MediaRecorder`; cancel does not publish.  
16. Photo rail: list, add, create-new as evidence, remove link; photo and Artifact survive.  
17. Video rail: same.  
18. **Owner visibility:** owner Ask/list/get sees `private` and `shared_with_family` when `active`. **Unauthorized:** no cross-account or unauthenticated Artifact retrieve; `shared_with_family` does not open a public API.  
19. Document upload: accepted MIME only; PDF/txt are download/open-original; images listed as previewable preview inline; unknown MIME rejected honestly.  
20. No suggested-memory ranking.  
21. POC Story/mic form absent from `/artifact/ui`.  
22. `prove-artifact` covers: create; Save-then-upload success; partial fail + retry; Cancel before Save; representation soft-remove + bytes hidden + file kept; memory remove + reactivate uniqueness; person `superseded`; owner vs unauthorized retrieve; story memory; by-media.

---

## N. Implementation sequence (after authorization and I10A.2 for voice)

1. Schema + DTO + compat migrate.  
2. Artifact APIs (no voice).  
3. Panel / detail / edit / representation modal.  
4. Memory modal + rails.  
5. Story prelink + link existing.  
6. Tell its story hook to I10A.2.  
7. Retire POC.  
8. Ask/Explore honesty + prove.

I10B slices 1–5 **must not** add an Artifact `MediaRecorder`. Tell its story **only** opens the shared Story editor with the Artifact prelinked.

---

## O. Open (non-blocking)

Resolved by this review (no longer Open): `described_end_date` (omitted); New staging/Cancel; memory unique + reactivate; person unlink = `superseded` only; `place_id` sole SoT (no runtime `about_place` dual-write); document MIME/preview vs download.

Still Open:

1. I10A.2 max duration / file size / whether transcription is a `jobs` row.  
2. Explicit “Make primary” vs `sort_order`.  
3. PATCH convenience vs multiple POSTs.  
4. Whether a Place **list** API is needed or upsert-on-type is enough (I10 has `upsert_place` + `get_place`).  
5. History UI for metadata revisions (out of I10B; Open only if owner wants it later).  
6. HEIC inline preview: use a reusable decoder if one already exists at build time; otherwise fallback — do not add a new HEIC stack in I10B.

---

**This increment is ACCEPTED. Next: I10A.1 Person Profile Editor. I10A.2 Unified Voice remains before Artifact mic and I10C voice. Do not reopen I10B for aesthetic polish.**
