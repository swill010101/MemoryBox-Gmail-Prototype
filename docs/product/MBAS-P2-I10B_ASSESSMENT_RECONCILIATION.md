# P2-I10B — Assessment reconciliation

**Status:** Planning only · repository assessment **accepted** 2026-08-23 · PRD **revised after PR 39 review, not accepted** · **not build-authorized**  
**Does not implement** code, migrations, routes, or UI  
**Definition / PRD:** [MBBS-P2_INCREMENT_10B_DEFINITION.md](MBBS-P2_INCREMENT_10B_DEFINITION.md) · [MBPRD-P2-I10B_ARTIFACTS.md](MBPRD-P2-I10B_ARTIFACTS.md)  
**PR 39 files:** this assessment, I10B definition, I10B PRD, plus sequence edits in `MBBS_P2_BACKLOG_PLANNING.md`, `MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md`, and `MBBS-P2_INCREMENT_10A_DEFINITION.md`. Base: `cursor/p2-i10a-stories-49da` until I10A lands; rebase/retarget before merge.

This revises the I10B field-mapping assessment after owner lock. Screenshot text is still not proof of a backend field.

**Visuals reviewed:** `fe913a4` on `cursor/marvin-capture-v01-3344` under `docs/source/Screens/MBUX Story Screens/` (Artifact + Journal + Person Edit). Not yet copied into `docs/source/Screens/MBUX Artifact Screens/`.

---

## 1. Findings changed by the owner decisions

| Prior finding | Decision | Revised I10B stance |
|---|---|---|
| Panel chips All / Heirlooms / Documents / Recipes / Keepsakes conflict with `ARTIFACT_KINDS` | Filters are **All / Objects / Documents / Recipes / Other**; map honestly; drop overlapping Heirlooms + Keepsakes | **Frozen mapping** in the PRD. No new kind enum. |
| Approximate date Missing | One optional Artifact date; precision `day \| month \| year \| approximate \| unknown` | **Required** `described_start_date` + `described_precision` only. **No** `described_end_date`. |
| Place Missing; screens used free text | First-class Place only; no Artifact location string | **Required** `artifacts.place_id` as sole SoT. No runtime `about_place` dual-write. |
| Visibility Missing | Reuse I10A `private` \| `shared_with_family`. Private remains Ask-visible to the **owner**. Unauthorized users must not see it. | **Required column**. Multi-user ACL is still not I10B; persist intent and do not leak. |
| Draft vs Save / Ask badges Unclear | **No working draft.** Save = `active` + panel + Ask (subject to visibility). | Badges **derived**. Do not copy Stories `working_version_id`. Keep metadata **revisions** as silent history. |
| Zero-representation Artifact valid in code | Allowed. Show **Needs context / Needs representation**. | **Required** incomplete signal. Not a blocker. |
| Cigar Box “12 items inside” | Nested/container Artifacts **out of I10B** | Replace copy. Do not imply nesting. |
| Delete / Remove Missing; file GC risk | Soft-remove records/links. **Preserve uploaded originals.** GC out of scope. | **Required** soft-remove APIs. No byte delete. |
| Dual Story link (`about_artifact` vs `source_kind=artifact`) | Canonical = I10A `story_version_memories` `source_kind=artifact` | **Required** read/write path + compat for existing `about_artifact`. |
| Supporting memories Missing | Photo, video, communications, calendar, journal, audio. **No Artifact→Artifact** | **Required** association. Picker chips match this set. |
| Rail ⋮ Unclear | **Remove link from this Artifact** + confirm. Does not delete media or Artifact. | **Required** rail action. |
| Provenance “Added by Tom Will” Partial | Acting **owner/account**, not an ArtifactPerson | Resolve `MEMORYBOX_OWNER_PERSON_ID` / owner Person. Do not mint a people link. |
| Suggested memories Missing | **Out of I10B** | Honest search + filters + explicit select only. |
| Audio/video as representations | I10B representations = listed image/document MIME. Audio = supporting evidence. | Preview vs download/open-original per PRD §F. No universal document renderer. |
| New create vs Cancel vs upload | Stage locally; Save then upload; Cancel writes nothing; partial fail keeps Artifact | **Frozen** in PRD G.2 + prove. |
| Memory unique / relink | One active `(artifact_id, source_kind, source_id)`; UNIQUE all rows; reactivate | **Frozen**. |
| Person unlink | `relationships.status='superseded'` only | **Frozen**. No hard delete. |
| Story from Artifact = retire POC form | Must support **link existing Story**, **new Story prelinked**, and **Tell its story** via shared voice | POC STT/Story form **obsolete**. I10B must not ship a private recorder. Depends on **I10A.2**. |
| Sequence I10B immediately after I10A | I10A → **I10A.1 Person Profile** → **I10A.2 Unified Voice** (Stories first) → I10B → I10C → I11 | I10B **definition may proceed**. I10B **implementation of Tell its story waits for I10A.2**. |

Unchanged and still true:

- I9 Artifact ≠ file, N representations, SHA-256 originals, people associate, list/get/create/revise, thin Ask.
- Unlink person, delete representation, by-media rail, I10A chrome: still required build work.
- I9 `evidence_ref` stored **as a representation** is the wrong bucket for supporting memories.
- I10C Journal screens exist on `fe913a4`; Journal implementation stays after I10B.
- Person Edit PNG is **I10A.1**, not I10B.

---

## 2. Current microphone, audio storage, and transcription (repository)

Two separate speech stacks exist. Do not treat them as one product.

### A. Owner capture / STT (Journal I5A + Artifact I9 POC)

| Piece | Location | What it does |
|---|---|---|
| HTTP | `POST /capture/transcribe` in `memorybox/app.py` ~1405–1461 | Multipart `file`. **Does not** create Journal or Story. |
| Protocol | `memorybox/providers/capture/protocol.py` | `AudioHandle`, `TranscriptDraft`, `preserve_audio`, `transcribe`, `preserve_and_transcribe` |
| Factory | `memorybox/providers/capture/__init__.py` `build_capture_stt` | `MEMORYBOX_STT_PROVIDER`: auto / faster_whisper / whisper_http / fake |
| Local STT | `memorybox/providers/capture/faster_whisper.py` | Write original under `MEMORYBOX_CAPTURE_DIR` (or `.memorybox_capture`); ffmpeg → 16 kHz mono WAV; Whisper; **sync in-request** |
| HTTP STT | `memorybox/providers/capture/whisper_http.py` | Same preserve + remote transcribe |
| Fake | `memorybox/providers/capture/fake.py` | Prove/harness |
| Journal UI | `memorybox/journal/static/journal.html` | Duplicated `getUserMedia` + `MediaRecorder`; Record / Stop; device picker; level meter; upload fallback; fills **Journal body**; explicit Save Journal |
| Artifact UI | `memorybox/artifact/static/artifact.html` | **Copy of the same recorder**, then `POST /artifact/{id}/story` (`create_story_for_artifact`) |

**Preserve-then-transcribe (existing, reusable):**

1. `preserve_audio` writes bytes first (`audio_id` UUID, `audio_uri`, content_type, byte_count).
2. `transcribe(audio_id)` runs STT.
3. If STT fails: HTTP **422** with `detail.audio` handle and `persisted_as_journal: false`. Owner can still type a body.

**What this stack does *not* do today:**

- Pause / resume
- Review or play original audio **before** STT (auto-transcribe on Stop)
- Job states: uploading / queued / transcribing (request is synchronous; first Whisper load can block a minute)
- Shared UI component (two copied scripts)
- Story editor integration (`story.html` has **no** mic; I10A PRD forbade dictation)
- Max duration / size (only “too small < 256 bytes”; ffmpeg convert timeout 120s)
- Retry / cancel of an async job
- Narrator confirmation (Journal uses author; Artifact POC has a separate narrator select)
- Ask publication (correctly does **not** publish)

**Browser formats attempted:** `audio/webm;codecs=opus`, `audio/webm`, `audio/mp4`. Insecure origins block mic (http://flightsim vs localhost).

### B. Archive / video spoken moments (I9)

| Piece | Location | What it does |
|---|---|---|
| Queue | `memorybox/speech/queue.py`, `archive_pass.py`, `process.py` | Per-**video** transcribe jobs |
| Now | `POST /speech/transcribe-now`, Explore “Transcribe this video” | In-place video STT |
| Store | `memorybox/speech/store.py` | Video transcript persistence |

This is **archive video** speech, not owner testimony capture. I10A.2 may **reuse Whisper/ffmpeg**, not this queue UX, for mic clips.

### C. Story audio field

`story_versions.audio_uri` exists (I5 / I10A). I10A does not write it from the editor. I10A.2 should persist capture `audio_uri` on the **working** version and keep it on freeze. Transcription completion must not set `current_saved_version_id`.

---

## 3. Shared speech vs destination-specific behavior

### Reusable (I10A.2 foundation — one capability)

- Permission probe (secure context / HTTPS / localhost)
- Device list + persist last-good device (not VoiceMeeter-style virtual cables)
- Record / pause / stop / level meter
- Upload-audio fallback when mic is blocked
- Preserve original bytes (`CaptureSttProvider.preserve_audio`)
- Submit for transcription (`transcribe` or a job wrapper around it)
- States: recording, uploading, queued, transcribing, completed, failed
- Retry, cancel (abandon job; keep preserved audio unless user discards)
- Playback of original audio
- Editable transcript buffer (not yet a Story/Journal/Artifact)
- Duplicate-submit guard (same `audio_id`)
- Failure: recording OK + STT fail → keep audio, allow type-over
- Cancel after STT → discard destination draft only; do not Ask-publish; audio may remain on disk (GC out of I10B; I10A.2 may keep files)
- Accessibility / keyboard for controls
- **Never** Ask-visible because STT finished

### Story-specific (I10A.2 integration, consumed by I10B)

- Open in Story editor
- Transcript → Story **body blocks**
- Narrator identify/confirm (I10A narrator Person)
- Typed + dictated in the same editor
- Explicit Save Story / Save revision
- `audio_uri` on the version
- Supporting memories already on that version stay

### Artifact-specific (I10B — after I10A.2)

- Entry: **Tell its story** (not “dictate description”)
- Opens Story editor/capture with Artifact **prelinked** (`source_kind=artifact`)
- Does **not** write Artifact `description`
- Does **not** add the clip as a representation
- Does **not** keep testimony on the Artifact
- After explicit Story save, return to Artifact detail with the Story listed

### Journal-specific (I10C — contract only now)

- Transcript → Journal body
- Author / captured_at / described dates / versions (I5A already)
- Explicit Save Journal
- Journal visibility / Ask rules (I10C)
- Does **not** create a Story unless the user later converts or links

---

## 4. Conflicts with the current repository

1. **I10A lock vs new sequence:** I10A PRD frozen “do not expose dictation.” I10A.2 **reopens dictation inside the Story editor** as a new increment. Do not treat that as reopening I10A acceptance.
2. **Artifact POC** embeds the Journal recorder and `create_story_for_artifact`. I10B must **retire** that UI and stop using `POST /artifact/{id}/story` as the product path.
3. **`evidence_ref` representations** ≠ supporting memories. New memory table/API required. Do not show evidence_ref rows in the memory list unless they are reclassified (compat note in PRD).
4. **`associate_story` / `about_artifact`** is not the I10A versioned memory. New writes go to `story_version_memories`. Old rows stay readable until backfill.
5. **Story `?artifact=`** is **not found**. Photo/video query boot exists. I10B + I10A.2 add artifact (and capture) query params.
6. **Place on Stories** is still largely `place_label` text in `story.html`. Artifact must call `upsert_place` / `places.id` (I10 `memorybox/correlate/store.py`). Do not copy Story’s free-text-only habit.
7. **Capture is synchronous.** Required job states need I10A.2 (wrapper is enough if the worker is in-process).
8. **No representation `status`.** Soft-remove needs a column or equivalent; `ON DELETE CASCADE` must not be the product delete.
9. **Ask** indexes all `status=active` Artifacts with no visibility column. Add visibility; owner Ask still sees `private`.
10. **Panel kind filters** must not use screenshot Heirlooms/Keepsakes.

---

## 5. Compatibility for existing records

### Artifacts (I9)

- Keep `artifacts`, `artifact_metadata_revisions`, `artifact_representations`.
- Existing `active` rows remain panel + Ask visible. Default new columns: `visibility=private`, date/place null, unresolved flags as stored.
- Zero-rep rows stay valid; they **Needs representation**.
- `mb_managed` files: never delete on soft-remove.
- `evidence_ref` rows remain representations until an owner later reclassifies; I10B memory picker creates **new** links, not evidence_ref rows.
- `relationships` `about_person` unchanged; unlink **only** `status='superseded'`. Do not hard-delete the row. Person and media survive.
- `actor_key='owner'`: display “Added by {owner display_name}” via owner Person; do not backfill ArtifactPerson.

### Stories

- Existing `about_artifact` rows: still mean “this Story is about this Artifact.”
- I10B **read**: Story ids = distinct stories from  
  (a) `story_version_memories` where `source_kind='artifact'` on working **or** current saved version, **and**  
  (b) `relationships` `about_artifact` where status in (`candidate`,`confirmed`).
- I10B **write** (link existing / new Story / Tell its story): insert `story_version_memories` only (working version; freeze on Save Story / Save revision per I10A). **Do not** write a new `about_artifact` unless a repository constraint makes the memory insert impossible — not expected.
- **Backfill (I10B migrate):** for each confirmed `about_artifact`, if the Story’s current saved version (or working if draft_only) lacks `source_kind=artifact` + that artifact id, insert the memory row. Do not invent order beyond append. Do not create working drafts solely for backfill if a saved version exists — write onto the Ask-current saved version **only in migration**, then stop mutating saved versions at runtime.
- `create_story_for_artifact` remaining rows: already have `about_artifact` + I10A saved Story; backfill covers them.
- I10A already allowed `source_kind=artifact` in the picker. Artifact→Story is the inverse of Story→Artifact memory.

### Capture audio

- Existing `MEMORYBOX_CAPTURE_DIR` files and Journal `audio_uri` unchanged.
- I10A.2 must keep `POST /capture/transcribe` or a compatible successor so Journal POC does not break before I10C.

---

## 6. Final I10B boundary

### Required for I10B

- I10A chrome: panel, new, detail, edit
- Filters All / Objects / Documents / Recipes / Other
- Needs context / Needs representation (including zero-rep)
- One optional date + precision; no end date
- Place via `artifacts.place_id` (picker / upsert), not free-text SoT; no runtime `about_place` write
- Visibility I10A enum; owner Ask sees private; unauthorized retrieve fails closed
- No draft; Save = active
- New: browser-local stage → Save → upload; Cancel writes nothing; partial fail + retry
- Representations: accepted MIME only; type + label/caption; list; soft-remove; originals kept; no product bytes for `removed`
- People add + unlink (`superseded` only)
- Supporting memories (six kinds) + unique triple + reactivate + modal search (no suggestions) + remove
- Photo/video rails: list, add to existing, create new as **supporting evidence**, overflow **Remove link**
- Stories: link existing; new Story prelinked; **Tell its story** through I10A.2 (no Artifact recorder)
- Soft-remove Artifact
- Ask on label/description/kind after Save
- Retire Artifact POC Story/mic form
- Compat read + migrate `about_artifact`

### Safe follow-up

- Suggested memories
- Nested/container Artifacts
- Video representation playback / audio-as-representation
- File GC
- Family ACL beyond stored visibility
- Representation primary as a separate column if sort_order=0 is enough
- Kind vocabulary rename

### Explicitly out

- I10A.1 Person Profile implementation (separate increment)
- I10A.2 implementation **inside** I10B (I10B **consumes** it)
- I10C Journal UI/implementation
- I11 narrative
- Artifact-to-Artifact memories
- Working draft on Artifacts
- Second Story editor / testimony on Artifact
- Face SoT

### Sequence

1. I10A Stories **ACCEPTED**  
2. I10A.1 Person Profile Editor  
3. I10A.2 Unified Voice Capture & Transcription (Stories first)  
4. I10B Artifacts (Tell its story uses I10A.2)  
5. I10C Journal (same speech)  
6. I11 only after those plus required transcription/recognition work  

I10B **planning/PRD: now**. I10B **build of Tell its story: after I10A.2**. Other I10B slices must still not invent a private Artifact recorder while waiting.

---

## 7. Remaining product questions

**None blocking** for writing the I10B definition/PRD.

Non-blocking Open items remain only in the PRD §O (I10A.2 duration/size/jobs, primary vs sort_order, PATCH vs POSTs, Place list API vs upsert, revision history UI, HEIC decoder reuse). Kind-filter SQL, `place_id` SoT, unlink `superseded`, memory unique+reactivate, and New staging are **Frozen**.

---

**Stopped at documents.** No code.
