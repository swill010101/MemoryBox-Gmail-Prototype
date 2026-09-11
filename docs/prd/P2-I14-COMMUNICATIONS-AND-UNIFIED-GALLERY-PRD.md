# P2-I14 — Communications and Unified Gallery

**Status:** Phase A complete (founder review + documentation commit `067e27dfa1493fa3274f9c0d662bda4442f3bbc3`). **Implementation remains unauthorized** until explicit **Phase B** authorization.  
**Date:** 2026-09-11  
**Owner:** Tom (founder)  
**Branch:** `codex/p2-i14-communications` (pushed: `origin/codex/p2-i14-communications`)  
**Phase A commit:** `067e27dfa1493fa3274f9c0d662bda4442f3bbc3`  
**Base HEAD (HC-2 acceptance record):** `673676bacf74e213b2d5c866518105a79b959b84`  
**HC-2 runtime SHA:** `743c76712cb286ccdae3ad1108fb260dbd04770d`  
**HC-1 accepted SHA:** `f777832cb4581344b294fcbd961eea5a0ecc4e10`

This Markdown file is the controlling I14 product request. Implementation, migrations, ingest, Peggy reconstruction, and deploy are **forbidden** until explicit Phase B authorization.

---

## 1. Document control and authoritative status

| Field | Value |
| --- | --- |
| Increment | P2-I14 |
| This document | `docs/prd/P2-I14-COMMUNICATIONS-AND-UNIFIED-GALLERY-PRD.md` |
| Assets | `docs/prd/p2-i14/assets/` |
| Phase | A complete — assessment + PRD committed |
| Code / implementation | Unauthorized pending explicit Phase B authorization |
| Phase A commit | `067e27dfa1493fa3274f9c0d662bda4442f3bbc3` |

**Controlling later-document rule:** If this I14 brief conflicts with an older roadmap row, **this I14 brief wins for I14 scope** and the conflict is recorded in §30. Do not silently drop either statement.

---

## 2. Increment purpose

Deliver a **complete coordinated Gallery** for Person Asks such as `Show me Peggy`, including photos, videos, email, SMS, and calendar evidence, without reconstructing raw email threads at Ask time, without false or stale communication memories, and without new top-level screens.

I14 creates and atomically publishes a **separate optimized communications representation** across every canonical MemoryBox Person, using existing I11/I11A algorithms (no LLM for thread reconstruction). Nightly ingest of three independent source extracts (Gmail email, Gmail calendar, SMS) maintains that representation. Ask/Gallery **consumes the published generation only**.

---

## 3. Background and superseded decisions

### 3.1 Controlling documents found (repository)

| Document | Path | Role |
| --- | --- | --- |
| Post-I12 roadmap | `docs/product/MBRM-001C_P2_POST_I12_ROADMAP.md` | I14 named “Unified Person Evidence & Timeline” after I13 |
| Comms / Gallery lock | `docs/decisions/2026-09-03-comms-preparation-and-unified-gallery.md` | Immutable archive + optimized store + unified Gallery |
| I11 evidence prep | `docs/product/MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md` | Prep contract |
| I11A | `docs/product/MBPRD-P2-I11A_INFERENCE.md`, `MBAT-P2-I11A_ACCEPTANCE.md` | Inference hold; chunk/observation machinery |
| Person-email identity | `docs/ops/PERSON_EMAIL_IDENTITY_PLAYBOOK.md`, `docs/ops/PRD_ADDRESS_CENTRIC_EMAIL_IDENTITY.md` | Fail-closed identity |
| HC-2 cadence | `docs/ops/HISTORIAN_CAPTURE_HC2_CADENCE.md` | Background-service pattern **not** to copy into I13 job queues |
| Older roadmaps | `MBRM-001`, `001A`, `001B` | I14 ID historically meant Capture Deepen or Settings — **superseded numbering** |

### 3.2 Implemented reality (not docs)

- Family mail/SMS/calendar already persist as immutable `evidence` (`communication` / `calendar_event`).
- Thread fields, authored cleanup, SMS episodes, and L1 chunking **already run at Ask/diagnostic time**. There is **no** durable prepared-index generation.
- `Show me Peggy` is **visual-first**: photos/videos in Gallery; email/SMS/calendar retrieved as archive-eligible and **gallery-hidden** until Communications/Calendar chips or “Add texts/email/calendar.”
- HC-2 five-minute tick is **accepted and enabled** on FlightSim. I14 must not collide with that scheduler or I13 admission-scoped queues.

### 3.3 Superseded

| Prior | Status under I14 |
| --- | --- |
| Show last-successful **stale** communication index in Gallery | **Superseded.** No stale/partial comms in Gallery. |
| 2026-09-03: pictures first, ~45s background insert, abandon on new Ask, present Gallery as complete | **Superseded** as a silent/complete story. A **visible** photo-first fallback is allowed only if mixed-media cannot meet ~10s (§6.2). |
| MBRM-001 / 001A / 001B “I14 = Capture Deepen or Settings” | **Superseded numbering.** Settings is I17; Capture Deepen is not this increment. |

---

## 4. Goals

1. Nightly, independently ingest three configured full extracts (email, calendar, SMS) with closed-date checkpoints.
2. Persist a deterministic optimized thread/conversation/event representation linked to immutable evidence IDs.
3. Publish generations atomically; never mix generations or serve a half-built index.
4. Person Ask Gallery includes applicable photos, videos, email, SMS, and calendar when those prepared sources are current.
5. Target ~10 seconds for a complete mixed-media Person Ask (cold after restart and warm).
6. Founder Peggy reconstruction gate before all-Person publication; then one additional Person proof.
7. Exact return from communication detail and Story; entire-thread Save as Story without attachments.

---

## 5. Non-goals

Explicitly out of I14:

- Words of a Life / word-cloud generation
- Comprehensive Person narrative generation
- I11A/I11B model runs (reuse **algorithms**, do not reopen inference)
- Historian Capture behavior changes
- I15 External Historical Context / cross-screen stabilization
- Settings & Controls expansion
- Unrelated face, voice, transcript, or Learn work
- Archive-wide mutation of original evidence
- Live production ingest during definition
- New top-level screens
- Calendar “Save as Story” (requires later founder approval)
- Copying I13 screenshots into this PRD

---

## 6. Locked founder decisions

### 6.1 Screens

- I14 creates **no new top-level screen**.
- Reuse/modify: Ask/Gallery (`/explore/ui`), unified timeline/cards, communication/calendar drill-down (existing day-stack overlay), email-thread detail (existing modal), SMS-conversation detail (existing day-stack thread), Story editor (`/story/ui`), breadcrumbs/return, operational status where necessary.
- **Do not change** photo detail, video detail, People, Learn, or I13 face/voice teaching screens unless an implementation dependency is proven and founder-approved.
- Missing **standalone URLs** (`/email/...`, `/sms/...`, `/calendar/...`) are **not** a license to invent new top-level screens. I14 keeps Explore overlays. Shareable deep-links are out of scope unless founder later requires them.

### 6.2 Gallery behavior and performance

- Desired: complete coordinated Gallery (photos, videos, email, SMS, calendar) in **~10 seconds**.
- Measure **cold** (first Person Ask after application restart) and **warm** separately.
- If complete mixed-media cannot meet 10 seconds: show photos/videos first; continue loading **only valid prepared** communication/calendar results while that Ask remains active; **visibly** indicate communications still loading; cancel/ignore obsolete work when a new Ask begins.
- Photo-first is an **honest fallback**, not a substitute for the complete-Gallery objective and **not** an unconditional performance pass (§15, §25).
- **I14-REQ-PERF-FALLBACK-MAX-MS = 30000.** Approximately **10 seconds** remains the complete-Gallery target. If communications are unfinished at 10 seconds, show the visible photo-first loading state. At **30 seconds total**, stop that Ask’s unfinished source retrieval, **omit** the unfinished source, mark it **unavailable for that Ask**, record **`gallery_settled_ms`**, leave **`gallery_complete_ms` null**, record a **performance failure**, and **ignore** any late result. Photos/videos and other **successfully loaded current** sources remain visible.
- **Never** reconstruct raw email threads during Ask.
- **Never** silently omit communications while presenting the Gallery as complete.
- Instrument cold-start and warm performance separately.

**Relation to 2026-09-03 §4:** the complete coordinated Gallery remains the objective. Visible photo-first loading is a degraded path when the 10-second target is missed, not a contradiction of that objective. Silent/stale insertion remains superseded.

### 6.3 No stale or partial communications

If the prepared communications index for a source is stale, incomplete, corrupt, or its latest update failed:

- do not put that affected communication/calendar evidence into the Gallery;
- do not publish a partially rebuilt index;
- do not mix generations **within the same source** (never combine generation N and N+1 of email, or of SMS, or of calendar);
- show a concise unavailable/not-current status rather than misleading memories;
- photos, videos, and **other sources with a valid published generation** may still be returned;
- retain diagnostic detail on the operational surface (Archive Health and/or a Scheduled Services card).

**Governing rule: no false memories.**

Index publication is atomic **per source**: build and validate a complete **generation for that source**, then promote it. Email, SMS, and calendar **do not** share one bundle generation.

### 6.4 Sources

Three independently checked sources:

1. Gmail email full extract  
2. Gmail calendar full extract  
3. SMS export (separate source)

Email and calendar are **separate files** even though both originate from Google data. All three configured landing locations are checked **nightly**.

### 6.5 Normalized representation

Separate optimized store across every canonical Person. Preserve immutable originals. Link only through canonical or explicitly reviewed Person identity. Do not silently assign uncertain communications to a Person. No LLM required to reconstruct the communication database.

### 6.6 Calendar

- Multi-day event appears **once** at start date.
- Display complete start-to-end range.
- Do not duplicate count across every covered day.
- Aggregate cards by available year/month/day precision.

### 6.7 Save as Story

From an email or SMS thread: always the **entire cleaned thread**; no message-selection controls; editable Story draft; provenance from every source message; never modify originals; attachments remain on the original thread and are **not** copied/linked/auto-added to the draft. Calendar Save as Story is **not** approved.

### 6.8 Navigation

Return from communication detail or Story must restore Ask text, Person, filters, timeline/date position, aggregation/density, Gallery scroll, and selected communication context when technically available.

### 6.9 Peggy gate then second Person

No broader publication or all-Person processing until founder approves Peggy reconstruction quality. Then prove generalization on at least one additional canonical Person. Do not tune production solely to Peggy.

---

## 7. Personas and primary workflows

| Persona | Workflow |
| --- | --- |
| Owner (Tom) | Ask `Show me Peggy` and see a complete honest Gallery; drill into a thread; return to the same Ask; Save as Story from a whole thread. |
| Owner (ops) | Nightly extracts land; ingest runs; failures visible; one source fail does not poison another; Gallery never shows a bad generation. |
| Founder (gate) | Inspect Peggy reconstructed threads vs immutable source before all-Person publish. |

---

## 8. Source-file contracts

Landing locations today (`config/memorybox_sources.env.example`; production values live in gitignored `config/memorybox_sources.env`):

| Source | Env / convention | Example landing (template only) |
| --- | --- | --- |
| Email mbox | `MEMORYBOX_MBOX_URI` / `MEMORYBOX_SMOKE_MBOX_URI` | `P:\photos\memorybox\sources\email\*.mbox` |
| Calendar ICS | **`MEMORYBOX_ICS_URI` (first-class I14 contract)**; today the example file only lists `MEMORYBOX_SMOKE_ICS_URI`; code also reads `MEMORYBOX_CALENDAR_URI` | `P:\photos\memorybox\sources\calendar\ics\*.ics` |
| SMS CSV | `MEMORYBOX_SMS_URI` / `MEMORYBOX_SMOKE_SMS_URI` (optional); tree `…/sources/sms\` | `P:\photos\memorybox\sources\sms\*.csv` (+ `sms-attachments`) |

**I14-REQ-SRC-1.** Each source has its own configured landing directory or exact file path in gitignored env. I14 source contract: `MEMORYBOX_MBOX_URI`, **`MEMORYBOX_ICS_URI`**, `MEMORYBOX_SMS_URI` (plus existing smoke aliases). No live Gmail/Google API in I14.

**I14-REQ-SRC-2. File-selection rule (per source):** among files matching the configured glob, select the ingest candidate by (a) operator-pinned filename if set, else (b) newest `LastWriteTime` among files that pass validation. Record the chosen path.

**I14-REQ-SRC-3. Source fingerprint:** SHA-256 of file bytes (or streaming hash), size, mtime, path. Store with the checkpoint.

**I14-REQ-SRC-4. Last successful ingest:** timestamp + generation id + fingerprint of the extract that produced the currently **published** generation for that source.

**I14-REQ-SRC-5. Last fully ingested source date:** the latest **closed** calendar date in the **configured household/source timezone**. **Production default: `America/Chicago`.** Keep configurable (`MEMORYBOX_HOUSEHOLD_TIMEZONE` and optional per-source override). Store normalized timestamps **with their source timezone/provenance**. **Do not hard-code UTC as the closed-day policy.** (Naive ICS dates today are coerced to UTC midnight in `ics_parse._to_dt` — inspect in Phase B; do not treat that as the I14 closed-day rule.) Checkpoint advances only through fully closed dates. The checkpoint records **completeness/progress**. It is **not** the discovery barrier: a later extract may still contain a record dated on or before D that was absent before; that record **must** be ingested if its stable identity is new (§9).

**I14-REQ-SRC-6. Source-specific checkpoint row** (proposed table `comms_source_checkpoint`): `source_kind`, `landing_path`, `fingerprint`, `last_success_at`, `last_closed_source_date`, `published_generation_id`, `building_generation_id`, `last_failure_category` (sanitized).

**I14-REQ-SRC-7. Validation before ingest:** readable file; non-zero size; parse probe (mbox magic / ICS `BEGIN:VCALENDAR` / SMS header aliases); reject truncated tails (mbox: last message parse; ICS: balanced VEVENT; SMS: CSV row count vs header). Failure = do not ingest, do not advance checkpoint, do not publish.

**I14-REQ-SRC-8. Idempotent rerun:** must not duplicate `evidence` rows. **Phase B deduplication gate (before schema implementation):** verify whether successive full exports share one stable **logical** `source_id`. Today `store.upsert_source` keys `sources` by `(uri, source_kind)` and `evidence_exists_by_hash(source_id, content_hash)` is **scoped to that `source_id`**. If `source_id` is an individual extract/import (new path/filename/run) rather than the logical mailbox/calendar/SMS source, **do not** uniqueness-scope solely to `source_id`. Define a **stable logical source lineage** (mailbox/calendar/SMS identity that survives changed filenames, paths, import runs, and export timestamps) **plus** record identity/`content_hash` **before** implementing I14 schema. Cross-extract dedupe must survive those filename/path/run/timestamp changes. Prepared rows key by `generation_id` + evidence ids.

**I14-REQ-SRC-9. Failure/recovery:** sanitized category on checkpoint + operational card. Next nightly retries. Do not roll back another source’s published generation.

---

## 9. Initial and nightly incremental ingest

Each delivery is a **full extract**. A date checkpoint must **not** be the only duplicate or discovery barrier. Starting at `last_closed_source_date + 1` **alone would skip** late records dated on or before that checkpoint. That conflict is resolved as follows.

**I14-REQ-ING-1. Initial ingest** processes the full approved extract for that source; records last fully ingested **closed** date and source fingerprint; does not alter immutable originals (`sources.authoritative_original_mode` remains referenced).

**I14-REQ-ING-2. Preferred subsequent ingest (complete-extract scan).** Receive another full extract. After validation:

1. If the **fingerprint is unchanged**, short-circuit: no evidence insert, no new generation, record “checked, unchanged” (§9 ING-4).
2. Otherwise **scan the complete validated extract**. For every record, compute record identity (`content_hash` and any RFC/UID/stable ids) against the **logical source lineage** (§8 SRC-8 / ING-9), not solely against an extract-specific `source_id`. Insert if absent. Skip if present (do not duplicate). **A late record dated on or before `last_closed_source_date` is still ingested if its stable identity is absent.**
3. Rebuild/publish the prepared generation for that source from the resulting evidence set when new identities were inserted or `algo_version` requires it.
4. Advance `last_closed_source_date` only through dates that are fully closed **in this extract** (boundary rules in ING-3). Never use the checkpoint as a skip-filter over the extract.

**I14-REQ-ING-2b. Alternate (not preferred).** An overlap/rescan window (e.g. rescan from `last_closed_source_date − W` through extract end) plus the same stable-ID dedupe is allowed **only if** Phase B proves complete-extract scanning is operationally unreasonable (documented size/time evidence). Until then, implement **ING-2**.

**I14-REQ-ING-3. Boundary-day:** the checkpoint must **not** advance to date D until D is fully closed and successfully processed in the extract under consideration. If an extract’s “as-of” is mid-day D, D is **not** closed; checkpoint stays at D−1. **Do not skip** a day because a later day appeared first. Closed D never authorizes ignoring a **new** identity whose source date is ≤ D.

**I14-REQ-ING-4. Unchanged extract short-circuit:** fingerprint unchanged → no rebuild, no new generation, success recorded as “checked, unchanged.”

**I14-REQ-ING-5. Changed extract, already-loaded material:** fingerprint changed (Takeout rewrite) → full scan; hashes that already exist skip insert; a **single historical addition** must insert exactly that identity; may rebuild prepared generation if new rows or parser/compaction version changed.

**I14-REQ-ING-6. One-source failure** must not write the other sources’ checkpoint or unpublish their valid generations.

**I14-REQ-ING-7. Interrupted rebuild:** leave `building_generation_id` unpromoted; next run discards or resumes that generation; Gallery continues to use previous **published** generation **only if it is still valid**; if the previous generation is stale/corrupt, Gallery omits that source (no false memories). Default after crash: previous published remains valid unless validation now fails.

**I14-REQ-ING-9. Logical source lineage (Phase B gate, before schema).** Confirm how `sources.id` behaves across Takeout replacements. If each new file URI creates a new `source_id`, uniqueness must be **lineage + content_hash** (and/or RFC Message-ID / calendar UID as recorded in payload), not `(source_id, content_hash)` alone.

**I14-REQ-ING-8. Required ingest tests** (in addition to §28):

| Case | Expected |
| --- | --- |
| Late record dated before the closed-date checkpoint, new `content_hash` | Inserted; checkpoint may stay at D; Gallery generation includes it after publish |
| Changed extract containing only one historical addition | Exactly one new evidence row; no duplicates of prior hashes |
| Unchanged extract short-circuit | Zero inserts; no new generation |
| Duplicate historical record in extract | Not reinserted |
| Same historical record in two different full-extract files / import runs (different path, filename, or export timestamp) | **One** immutable `evidence` record |

---

## 10. Proposed normalized data model

**Do not replace `evidence`.** Originals stay there. I14 adds a **derived** store.

**I14 migration number TBD after migration-history reconciliation.** This clone’s files jump from `025_historian_capture_i12.sql` to `030_p2_i13_scope_admission.sql`. FlightSim `/health` has listed `026`–`029` (retrieval trust / RFC ids) that **are not in this repository**. **No I14 migration file may be created** until those 026–029 rows are compared with repository history and their schema effects are **recovered, represented, or explicitly retired**. That reconciliation is a **Phase B entry gate**. Do not assign an I14 migration number until that gate passes.

### 10.1 Proposed tables (names indicative)

| Table | Purpose |
| --- | --- |
| `comms_source_checkpoint` | Per `email` / `calendar` / `sms` ingest cursor and fingerprints |
| `comms_prepared_generation` | `generation_id`, `source_kind`, `status` (building, validated, published, superseded, failed), `algo_version`, `item_count`, `checksum`, timestamps |
| `comms_prepared_thread` | Email thread or SMS conversation unit for one generation |
| `comms_prepared_turn` | Dated turns inside a thread (cleaned text, speaker handle, `evidence_id`) |
| `comms_prepared_calendar` | One row per event occurrence policy (multi-day = one row at start) |
| `comms_prepared_link` | `generation_id`, prepared id, `evidence_id` (N:N provenance) |
| `comms_prepared_person` | Explicit Person links: `person_id` or `uncertain` flag; never implicit |

### 10.2 Thread row (minimum)

- `channel` (`email` \| `sms`)
- `thread_key` (vendor thread id or deterministic RFC cluster key — **same as** `mbox_parse.thread_fields`; never subject-invented)
- `t_start`, `t_end`, `date_precision` (`day` \| `month` \| `year` \| `undated`)
- `participant_handles[]`, `resolved_person_ids[]`, `uncertain_participants[]`
- `completeness` (from existing `thread_completeness`)
- `noise_marks` (transactional, signature_stripped, quotes_compacted) — marks, not deletes
- `token_estimate`, `algo_version`
- links to every immutable `evidence.id`

### 10.3 Calendar row (minimum)

- `event_uid` / `content_hash` / `evidence_id`
- `start_at`, `end_at` (range displayed; **counted once** at start date)
- attendees as handles + optional resolved Person ids (uncertain kept separate)

### 10.4 Reuse of existing payload fields

Email payload already has `vendor_thread_id`, `thread_id`, `thread_status`, `rfc_message_id`, `in_reply_to`, `references`, `header_provenance`, `content_hash`. SMS has `thread_id` / handles. Calendar has `event_uid`, start/end. I14 prepared store **projects** these; it does not invent a second RFC truth.

---

## 11. Identity and canonical Person linkage

**I14-REQ-ID-1.** Use `communication_identities` + confirmed `person_contact_points` (existing fail-closed pipeline in `memorybox/person/comm_identity.py`, `comm_address_index.py`, `phone_map.py`).

**I14-REQ-ID-2.** Gallery Person filter includes a communication **only if** at least one participant is a **confirmed** contact for that Person.

**I14-REQ-ID-3.** Uncertain/unresolved participants remain visible on thread detail as handles, not as that Person’s memories.

**I14-REQ-ID-4.** No first-name-only or quoted-body auto-attach (already proven; do not regress).

**I14-REQ-ID-5.** Generalize Peggy fixtures to **all canonical People** — no Peggy-only address lists in production retrieve.

---

## 12. Thread reconstruction and cleanup

**I14-REQ-THR-1.** Reconstruction is **deterministic**. An LLM must not be required.

**I14-REQ-THR-2. Prohibit duplication** of I11A logic unless founder-approved. Required reuse:

| Capability | Path | Symbol | Responsibility | I14 strategy | Generalize | Tests today | Missing tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Raw email normalize | `memorybox/providers/email_read/mbox_parse.py` | `extract_bodies`, `addr_records`, `header_provenance`, `parse_date`, `content_hash` | mbox → DTO | **Reuse unchanged** | Already generic | I8 prove: `i8_inspect_mbox_cli`, attachments, NUL, spam/trash | pytest unit file for parse helpers |
| Vendor thread id | same | `vendor_thread_id`, `thread_fields` | `X-GM-THRID` / `Thread-Index` | **Reuse unchanged** | Generic | `i8_rfc_vendor_thread` | Persist prepared grouping test |
| RFC reconstruction | same | `parse_message_ids`, `thread_fields` | Message-ID / IRT / References; **never subject** | **Reuse unchanged** | Generic | `i8_quoted_turns_not_invented_rfc`, `i8_incomplete_thread_honesty` | Prepared-index incomplete-thread fixture |
| Thread completeness | `memorybox/ingest/comms_email.py` | `_apply_thread_completeness` | Mark incomplete vs known IDs | **Reuse unchanged** | Generic | I8 incomplete honesty | Generation checksum includes completeness |
| Persist email | `comms_email.py` | `ingest_mbox` | Immutable evidence insert | **Reuse unchanged** | Generic | `i8_ingest_ok`, `i8_original_untouched` | Closed-date checkpoint tests (new) |
| SMS parse/ingest | `memorybox/ingest/sms_parse.py`, `comms_sms.py` | `iter_sms_messages`, `ingest_sms` | CSV → evidence | **Reuse unchanged** | Generic | I8A SMS prove | Checkpoint + episode persist tests |
| Calendar ingest | `memorybox/providers/calendar/ics_parse.py`, `ingest/comms_calendar.py` | `iter_vevents`, `ingest_ics` | ICS → `calendar_event` | **Reuse unchanged** | Generic | I8A calendar retrieve/inspect | Multi-day single-count test (new) |
| Quoted turns (UI) | `memorybox/explore/email_attach.py` | `split_quoted_email`, `load_email_view` | Structured turns; no invented RFC members | **Reuse unchanged** for detail | Generic | `i8_structured_email_view` | Entire-thread Save as Story uses cleaned thread not one MIME body |
| Authored cleanup | `memorybox/ask/authored.py` | `authored_email_text` | Quote/signature strip at Ask | **Refactor into shared service** used by **prep generation**, not Ask hot path | Generic; remove Ask-time 8k as the only cleaner | diagnostic uncap twin | Persist cleaned text + mark; Ask reads prepared |
| Compaction / SMS episodes / group threads / L1 pack | `memorybox/ask/i11a/full_evidence_l1_chunker.py` | `compact_email_item`, `apply_safe_compaction`, `segment_sms_episodes`, `group_email_threads`, `build_l1_units`, `pack_model_chunks`, `prove_chunk_completeness` | Deterministic units; no LLM (`no_llm` check) | **Refactor into shared prep service**; Ask **must not** re-run | Generic algorithms; Peggy is corpus **driver** only | `full_evidence_benchmark_acceptance.py`: `normal_threads_not_split`, `sms_episode_split_on_gap`, `completeness_proof_ok`, `no_llm` | Persist units per generation; all-Person not just Peggy export |
| Identity | `memorybox/person/comm_identity.py`, `comm_address_index.py`, `phone_map.py` | discover / corroborate / expand | Address/phone ↔ Person | **Reuse unchanged** | Already generic; Peggy is fixture | `comm_identity_acceptance.py` (e.g. `retrieve_has_no_peggo_hardcode`) | Prepared-person link table tests |
| Retrieve (today) | `memorybox/ask/retrieve.py` | `search_email_messages`, `search_sms_messages`, `search_calendar_events` | Raw evidence retrieve | **Replace Gallery path** with prepared-index read; keep evidence retrieve for audit/detail | Generic | I8/I8A/I11A retrieve | Prepared Gallery retrieve + stale exclusion |
| Peggy corpus driver | `memorybox/ask/i11a/full_evidence_diagnostic.py` | `resolve_peggy_plan`, `run_full_evidence_diagnostic*` | Peggy export | **Reuse for founder gate only**; not production publish | Peggy-specific **entrypoint** | `full_evidence_diagnostic_acceptance.py` | Gate package artifacts in `docs/prd/p2-i14/` after authorization |
| HC reply extract | `application/marvin_capture/reply_extract.py` | `extract_reply_text` | Capture replies | **Do not** use as archive prep (different pipeline) | HC | HC tests | n/a |

**I14-REQ-THR-3.** Cleanup **marks** noise; it does not delete evidence rows.

---

## 13. Immutable evidence and provenance

**I14-REQ-EV-1.** I14 writes **no** updates that rewrite `evidence.payload_json` bodies, headers, timestamps, or source files. Parser-upgrade payload patches already in ingest stay ingest-owned, not Gallery-owned.

**I14-REQ-EV-2.** Every prepared thread/turn/event stores complete `evidence_id` lists and generation checksum.

**I14-REQ-EV-3.** Detail views continue to load **immutable** evidence (existing `/explore/api/email/{id}`) for inspection; cleaned text is an overlay.

**I14-REQ-EV-4.** Historian Capture items remain a separate immutable pipeline. I14 does not ingest HC mailbox into the family Takeout index.

---

## 14. Prepared-index generation and atomic publication

**I14-REQ-PUB-1. Per-source generations.** Email, SMS, and calendar publish **independently**. They may have **different** `published_generation_id` values and **different** publication timestamps. That is legitimate. They do **not** share one bundle generation.

**I14-REQ-PUB-2. Coordinated Gallery honesty.** The Gallery is “complete” for communications only when **every source that is configured and expected** is either (a) included from its current published valid generation or (b) explicitly marked unavailable. Never imply SMS is present if the SMS generation is unpublished.

**I14-REQ-PUB-3. Promote algorithm (per source):** insert rows under that source’s `generation_id = N+1` with `status=building`; validate counts, checksum, completeness proof (`prove_chunk_completeness` analogue); set `validated`; in **one transaction** point that source’s `checkpoint.published_generation_id = N+1` and mark N `superseded`. Readers use only `published` for that source.

**I14-REQ-PUB-4. No mixed generations** means: never combine generation N and N+1 **within the same source** in one Gallery response. It does **not** require email, SMS, and calendar to be the same generation id.

**I14-REQ-PUB-5.** If validation fails for a source, `status=failed`, that source’s published pointer unchanged (unless the published generation is itself invalid). An **invalid source is omitted and marked unavailable**. Other sources’ valid published generations **remain usable**.

**I14-REQ-PUB-6.** Every Gallery / find response **must identify**, for each configured source (email, SMS, calendar): `generation_id` (or null), freshness (`published_at` / age), and status (`current` \| `unavailable` \| `loading` \| `not_configured`).

---

## 15. Ask/Gallery retrieval and performance

**I14-REQ-ASK-1.** Planner change: Person visual Ask (`Show me Peggy` / `Show me Peggy George`) **includes** email, SMS, and calendar in the **coordinated Gallery contract**, not hidden-by-default. (Today `visual_scope=broad_show_me_person` does not set `want_email`/`want_sms`/`want_calendar`.)

**I14-REQ-ASK-2.** Orchestrator reads **published prepared** rows for that Person + date filters. **Zero** calls to `authored_email_text` / L1 chunker on the Ask path.

**I14-REQ-ASK-3.** Photos/videos continue via existing Immich/library retrieve.

**I14-REQ-ASK-4.** Target **approximately 10 seconds** for a **complete current-source Gallery** (photos, videos, and every configured source that is `current`). Invoking photo-first fallback is **not** an unconditional performance pass.

**I14-REQ-ASK-5.** Cold = first Person Ask after process start (no prepared rows in process memory; DB allowed). Warm = subsequent Ask.

**I14-REQ-ASK-6.** Photo-first fallback only if complete assembly exceeds the 10-second target; communications stream in with a visible “Communications still loading” state; each attached source still uses its **published valid** generation (never a partial rebuild). **I14-REQ-PERF-FALLBACK-MAX-MS = 30000.** At 30 seconds total, stop unfinished source retrieval for that Ask, omit those sources, mark them unavailable **for that Ask**, record **`gallery_settled_ms`**, set **`gallery_complete_ms` null**, record a performance failure, and ignore late results. Photos/videos and other successfully loaded current sources remain visible. Never set `complete=true` while a configured current source was omitted without an unavailable mark.

**I14-REQ-ASK-7.** New Ask cancels in-flight communication fetch for the previous Ask id. Instrument cancellation latency.

---

## 16. Loading, unavailable, stale, cancellation, and failure behavior

| State | Gallery | Copy (concise) | Ops |
| --- | --- | --- | --- |
| Loading comms (fallback) | Photos/videos shown; comms pending | Communications still loading | Progress API |
| Complete | All current sources present | No “loading” chrome | — |
| Source unavailable / stale / failed | That source omitted | Communications (email/SMS/calendar as applicable) aren’t current | Scheduled Services / Archive Health detail |
| Empty genuine | Person has no prepared threads in published gen | No emails in the current index | — |
| Ask cancelled | Ignore late results | — | — |
| Error | Photos/videos may remain | Couldn’t load communications | Sanitized category |

**I14-REQ-UX-1.** Do not label the Gallery complete while comms are loading or omitted.

---

## 17. Calendar aggregation

**I14-REQ-CAL-1.** Multi-day event: one card at start date; subtitle/range shows end.

**I14-REQ-CAL-2.** Year/month/day buckets follow existing Explore precision rules; calendar counts unique events, not day-spans.

**I14-REQ-CAL-3.** Recurring instances: **do not lock cardinality in Phase A.** Current ICS ingest (`memorybox/providers/calendar/ics.py`) yields **one evidence row per VEVENT component**, stores `recurrence` (RRULE text) on the payload, and does **not** expand RRULE into occurrence rows. Hash is `uid|start|summary|location|description`. Inspect production ICS row counts in Phase B before locking prepared-store cardinality. Do not invent a second expansion in the prepared store until that inspection.

---

## 18. Save as Story

**I14-REQ-ST-1.** From email or SMS **thread** detail: one control, entire cleaned thread body, all member `evidence_id`s as Story memories (`email_thread` / `sms_conversation`).

**I14-REQ-ST-2.** No per-message checkboxes.

**I14-REQ-ST-3.** Draft is editable on `/story/ui?id=&edit=1`.

**I14-REQ-ST-4.** Attachments stay on the thread APIs; not in draft `memories` as media.

**I14-REQ-ST-5.** Today’s Explore “Save as Story” uses the **Ask pack** (`composed_by_model: true`) and mixed memories — **must change** for the thread entry point without breaking photo Save as Story.

---

## 19. Navigation and exact return state

**I14-REQ-NAV-1.** Persist an Explore snapshot (already `snapshotExplore` / `restoreExplore` for modal close) across **Story** round-trip: Ask text, Person ids, type filters, timeline range, density, `gallery.scrollTop`, day-stack selection.

**I14-REQ-NAV-2.** Story return: `mb_return=/explore/ui` plus a short-lived server or `sessionStorage` snapshot key — prefer existing shell `mb_return` + Explore snapshot; do not require retyping the Ask.

**I14-REQ-NAV-3.** Day-stack back already closes detail then stack — keep.

---

## 20. Screen-impact matrix

**No new top-level screen is proposed.** Required drill-downs already exist as Explore overlays.

| Surface | Route | Source | Current behavior | I14 change | Data/API | Loading | Empty | Stale/unavailable | Error | Return | Acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ask/Gallery | `/explore/ui` | `memorybox/explore/static/explore.html`, `explore.js` | Visual-first Person Ask; comms hidden | Include prepared comms/calendar; completeness chrome; cancel | `POST /explore/api/find`, ask-progress | Searching + comms-loading | Existing empty ask | Banner if source unpublished | Existing curator/provider | Snapshot | Cold/warm Peggy 10s; no silent omit |
| Unified timeline/cards | same | `explore.js` | Dated cards; comms day/thread cards | Cards from prepared units; calendar once at start | find `items[]` | same | none | omit stale source | same | same | y/m/d aggregation |
| Communication drill-down | overlay `#mb-day-stack` | `explore.js` | Email/Text/Calendar tabs | Bind to prepared thread keys; still open immutable detail | existing items + email API | tab empty copy | empty tab | hide tab if source unavailable | — | close stack restores gallery | drill-down + return |
| Email thread detail | modal; **no** `/email` page | `explore.js`, `email_attach.py` | Structured quoted turns | Show cleaned thread + link to originals; Save as Story whole thread | `GET /explore/api/email/{id}` | — | — | n/a (immutable) | fetch fail | restore Explore | entire-thread Story; originals unchanged |
| SMS conversation | day-stack thread; **no** `/sms` page | `explore.js` | Messages oldest→newest | Prepared episode/thread | sms attachment APIs | — | — | omit if SMS gen invalid | — | restore | whole-thread Story; no attachments in draft |
| Calendar detail | modal/day-stack; **no** calendar API | `explore.js` | Thin title/when | Range display; single count | find item; optional later `GET /explore/api/calendar/{id}` **on Explore**, not a new screen | — | — | omit if cal gen invalid | — | restore | multi-day once |
| Story editor | `/story/ui` | `story/static/story.html` | Drafts from Ask pack / media | Thread-sourced draft; no attachment memories | `/story/drafts` | in-page | empty list | n/a | save failed | **must** return to Explore snapshot | provenance all messages |
| Breadcrumbs | shell `mb_return`, Explore chips | `shell.js`, `explore.js` | Modal snapshot; HC→Admin `mb_return` | Persist snapshot through Story | sessionStorage or context API | — | — | — | — | exact Ask | return without re-Ask |
| Archive Health | `/status/ui` | `status/static/status.html` | Staged vs ingested comms | Show prepared generation freshness per source | `/status/summary` | loadErr | — | not-current | — | existing | ops visibility |
| Admin Scheduled Services | `/admin/jobs/ui` | `admin/static/jobs.html` | HC-2 card only | **One additional** `kind:recurring_service` for nightly comms ingest — same pattern as HC-2, **not** I13 job rows | `GET /admin/api/scheduled-services` | — | — | Error/Delayed/Disabled | sanitized | — | does not break HC-2 card |
| People / Learn / photo / video / I13 | various | various | Teaching, media detail | **No I14 change** | — | — | — | — | — | — | regression: unchanged |

**Confirmation:** communication drill-down, email detail, SMS detail, calendar detail, and Story entry **already exist**. Calendar is thin. No conflict that forces a new top-level screen.

---

## 21. Operational status and observability

**I14-REQ-OPS-1.** Nightly ingest is a **Scheduled Service** (HC-2 pattern: heartbeat, last 20 runs, Disabled/Active/Error/Delayed, `schtasks` not on every browser parse). Do **not** enqueue I13 `recognition_queue_items`.

**I14-REQ-OPS-2.** Archive Health summarizes per-source: last closed date, published generation age, last failure category.

**I14-REQ-OPS-3.** Windows task (when authorized): disabled-first, like HC-2; name distinct (`MemoryBox Communications Ingest`). **Use the same Windows account and execution pattern as the accepted HC-2 task.** Verify the **actual** FlightSim account, permissions, working directory, interpreter, and state path **during deployment**. Do not assume those values solely from documentation. Do not overload `MemoryBox Historian Capture Tick`.

**I14-REQ-OPS-4.** No secrets in task arguments or Admin JSON.

---

## 22. Security and privacy

- Family mailbox extracts stay on configured private storage; not committed.
- Prepared store contains personal communications — same host DB controls as `evidence`.
- Uncertain Person links are not published as that Person’s Gallery memories.
- Sanitized failure categories only (HC-2 precedent).
- Do not log message bodies in tick/ingest logs.

---

## 23. Migration, rollback, and rerun safety

**I14-REQ-MIG-1.** **I14 migration number TBD after migration-history reconciliation.** Additive derived tables only, once numbered. Derived tables droppable. **Phase B entry gate:** compare FlightSim-reported migrations 026–029 with repository history; recover, represent, or explicitly retire their schema effects. **No I14 migration file may be created until that gate passes.**

**I14-REQ-MIG-2.** Rollback: unpublish (clear that source’s `published_generation_id`) → Gallery omits that source with unavailable status; other valid sources and photos/videos remain. Disable Windows ingest task. Immutable `evidence` untouched.

**I14-REQ-MIG-3.** Rerun ingest is idempotent on `content_hash`. Rebuild prepared generation from evidence without re-reading mbox if fingerprints match and algo_version bump requested.

---

## 24. Test strategy

| Layer | What |
| --- | --- |
| Unit | Checkpoint closed-date; generation promote transaction; stale exclusion; multi-day calendar count; Ask cancel token |
| Ingest | Late record before checkpoint; one historical addition; unchanged fingerprint short-circuit; duplicate historical not reinserted; **same record in two full-extract files → one evidence row** |
| Reuse | Existing I8/I8A/I11A/identity/L1 `no_llm` proves still pass |
| Contract | Planner Person Ask requests comms; find payload per-source `generation_id` / freshness / status; `gallery_complete` vs `comms_loading` vs `comms_unavailable` |
| Gate | Peggy reconstruction report (authorized later) |
| Perf | Cold/warm timers; `gallery_complete_ms` only on full complete-Gallery; `gallery_settled_ms` on honest settle including 30s timeout; cancellation time |
| UX | Explore return snapshot; Save as Story memories = all thread evidence ids, zero attachments |

Do not use live production extracts during definition.

---

## 25. Performance measurement

Instrument **cold** and **warm** separately.

**I14-REQ-PERF-1.** Required timers (milliseconds):

| Metric | Meaning |
| --- | --- |
| `ttfa_visual_ms` | Time to first applicable visual result (photo or video) |
| `gallery_complete_ms` | Set **only** when every configured **current** source is included under the complete-Gallery contract. Otherwise **null**. |
| `gallery_settled_ms` | Time when the UI finishes in an honest complete-or-unavailable state (no further source attach expected for this Ask) |
| `source_attached_ms.email` / `.sms` / `.calendar` | Time each prepared source was attached to the active Ask |
| `ask_cancel_ms` | Time from new Ask start until prior communication work is cancelled/ignored |

Also record `item_counts` by type and per-source `generation_id` / status.

**I14-REQ-PERF-2.** Cold: bounce serve, first `Show me Peggy`. Warm: immediate second Ask.

**I14-REQ-PERF-3. Complete-Gallery pass:** `gallery_complete_ms` is **not null**, `gallery_complete_ms <= 10000`, and all configured current sources are included **without** timeout omission.

**I14-REQ-PERF-4. Fallback / 30s timeout:** If communications are unfinished at 10 seconds, show photo-first loading. At **30 seconds** total: stop unfinished source retrieval for that Ask; omit those sources; mark them unavailable for that Ask; **ignore late results**. Record **`gallery_settled_ms`**. Set **`gallery_complete_ms = null`**. That outcome is a **performance failure** with honest UI. Photos/videos and other successfully loaded current sources remain visible.

**I14-REQ-PERF-5.** Fail if Gallery `complete=true` while a configured current source was omitted. Fail if a superseded Ask’s comms attach after cancel. Fail if `gallery_complete_ms` is set when any configured current source timed out.

---

## 26. Peggy founder-gate package

**Before publishing prepared representation broadly:**

1. Run I11A-derived reconstruction (`group_email_threads`, `thread_fields`, compaction, completeness) on the **approved Peggy email scenario** (existing `resolve_peggy_plan` / full-evidence diagnostic inputs).
2. Produce a reviewable sample/report (Markdown + cited evidence ids) under `docs/prd/p2-i14/gate-peggy/` **only after implementation is authorized**.
3. Include examples: normal threads; missing-thread-ID reconstruction; quoted-reply cleanup; signatures/boilerplate; forwards; malformed dates/participants; duplicates; uncertain Person; retained provenance.
4. Cleanup counts and exceptions.
5. Direct comparison to immutable `evidence` (side-by-side ids).
6. **Stop for founder inspection.**

No all-Person processing until approval. Analogous to I11A Peggy chunk-review.

---

## 27. Second-Person generalization gate

After Peggy approval: pick one additional **canonical** Person with confirmed email and/or SMS contacts. Rebuild prepared generation with the **same algo_version**. Prove retrieve is address-ledger based (`retrieve_has_no_peggo_hardcode` class of checks). Do not add Peggy-only branches.

---

## 28. Acceptance criteria

Minimum scenarios (must have explicit tests or prove checks before founder I14 accept):

1. Initial full email ingest  
2. Initial calendar ingest  
3. Initial SMS ingest  
4. Nightly run, no new files  
5. New full extract, only already-loaded evidence  
6. Extract with new material after the last closed date **and** late material dated on or before the checkpoint (stable-id insert)  
7. Partial/current-day boundary (checkpoint does not skip/close D)  
8. Source file replacement (new fingerprint)  
9. Malformed or truncated export (fail closed)  
10. Duplicate historical record not reinserted  
10a. Unchanged extract short-circuit  
10b. Changed extract containing only one historical addition  
10c. Same historical record in two different full-extract files/import runs → one immutable evidence record  
11. One-source failure (other sources’ published generations intact)  
12. Interrupted rebuild (no mixed generation **within** a source)  
13. Rerun after failure  
14. Stale/invalid generation excluded from Gallery; response names each source’s generation/status  
15. Peggy reconstruction founder review  
16. Second canonical Person (named after Peggy; not chosen in Phase A)  
17. Cold-start `Show me Peggy`  
18. Warm `Show me Peggy`  
19. Complete Gallery within approximately 10 seconds (primary pass)  
20. Photo-first fallback with active loading indicator (honest UI); at 30s omitted sources unavailable, `gallery_settled_ms` recorded, `gallery_complete_ms` null, late results ignored; performance fail  
21. New Ask cancels prior communication loading (measure `ask_cancel_ms`)  
22. Year/month/day aggregation  
23. Multi-day calendar event (once, full range)  
24. Communication drill-down and exact return  
25. Entire-thread Save as Story  
26. Story excludes attachments  
27. Immutable evidence unchanged  

Plus: no new top-level screen; HC-2 Scheduled Services still healthy; I13 jobs unchanged.

---

## 29. Proposed build phases

All implementation phases **blocked** until founder authorizes **Phase B**.

| Phase | Work | Founder gate |
| --- | --- | --- |
| **A** | Assessment + PRD | **Complete.** Commit `067e27d` on `origin/codex/p2-i14-communications`. |
| **B** | **Entry gates:** (1) reconcile FlightSim 026–029 vs git; (2) **logical source lineage / cross-extract dedupe** (§8 SRC-8, §9 ING-9) before schema. Then I14 migration number TBD; derived tables; checkpoint; no Ask change | Schema review after both gates |
| **C** | Complete-extract scan ingest; closed-date progress; three-source nightly CLI; disabled Windows task | No live ingest until authorized |
| **D** | Shared prep service (move compaction/grouping off Ask path); persist **per-source** generation; atomic per-source publish | — |
| **E** | Peggy reconstruction report | **Peggy gate — stop** |
| **F** | Second Person proof (Person named after Peggy) | **Stop** |
| **G** | Explore planner/find/UI: unified Gallery, per-source status in payload, loading/unavailable, return snapshot, thread Save as Story | UX review |
| **H** | Perf cold/warm; `gallery_complete_ms` vs `gallery_settled_ms`; 10s complete; 30s timeout | Performance evidence |
| **I** | Scheduled Services card; Archive Health freshness | Ops |
| **J** | Founder I14 acceptance | Enable nightly task only after accept |

Implementation branch: `codex/p2-i14-communications` (pushed). No further documentation-commit proposal for Phase A.

---

## 30. Open questions and documented tensions

| ID | Item | Resolution rule |
| --- | --- | --- |
| T1 | **MBRM-001C I14** is “everything MemoryBox knows” (Stories, Artifacts, Journal, spoken). **This brief** is the communications/calendar slice of Unified Person Evidence and Gallery. | I14 **this PRD**. Broader Stories/Artifacts/Journal/spoken expansion is **post-I14** unless separately authorized. |
| T2 | **2026-09-03 §4** wants one assembled result. **This brief** allows visible photo-first if ~10s is missed. | Complete Gallery remains the objective. Photo-first is an honest fallback, not a contradiction. Silent omit remains forbidden. |
| T3 | FlightSim health listed migrations **026–029**. **This clone has 025 then 030.** | **Phase B entry gate.** I14 migration number TBD. No I14 migration file until 026–029 are recovered, represented, or explicitly retired. |
| T7 | Today’s `evidence_exists_by_hash` is `(source_id, content_hash)` and `sources` uniqueness is `(uri, source_kind)`. Successive full exports may **not** share one logical `source_id`. | **Phase B entry gate before schema.** Define stable logical source lineage + record identity/`content_hash`. Cross-extract dedupe must survive changed filenames, paths, import runs, and export timestamps. Do not uniqueness-scope solely to extract `source_id`. |
| T4 | `Show me Peggy` **hides** comms today. I14 **includes** them in the coordinated Gallery. | Intentional. Old hidden-comms Person Ask tests **must be replaced**, not preserved as regressions. |
| T5 | Save as Story today is Ask-pack-wide, not entire thread. | Thread entry point is new behavior on existing control. |
| T6 | Bundle vs per-source generations. | **Locked here:** independent per-source generations and timestamps; no mixed N/N+1 **within** a source; Gallery names each source’s generation/status. |
| Q1 | Closed-day timezone. | **Locked:** production default **America/Chicago**; configurable (`MEMORYBOX_HOUSEHOLD_TIMEZONE`, optional per-source override). Store timestamps with source timezone/provenance. Do **not** hard-code UTC as the closed-day policy. |
| Q2 | Recurring ICS cardinality. | **Open — engineering.** Inspect current persistence (one VEVENT row + RRULE text; not expanded) and production counts before schema lock. |
| Q3 | Exact second Person for §27. | **Open — founder selection after Peggy.** |
| Q4 | Nightly task identity. | **Locked:** same Windows account and execution pattern as accepted HC-2. **Verify on FlightSim at deploy** (account, permissions, working directory, interpreter, state path). Do not assume values from docs alone. |
| Q5 | `MEMORYBOX_ICS_URI` | **Locked for I14 source contract:** first-class env (alongside smoke ICS). Example file update is implementation-phase docs, not this commit’s runtime change. |
| Q6 | **I14-REQ-PERF-FALLBACK-MAX-MS** | **Locked = 30000.** On timeout: `gallery_complete_ms` is null; `gallery_settled_ms` is recorded; omitted sources unavailable; late results ignored. |

---

## Appendix A — Repository / git checkpoint

| Item | Value |
| --- | --- |
| Path | `E:\MemoryBox-dev\p2-i13-stage-a` |
| Branch | `codex/p2-i14-communications` (**pushed** `origin/codex/p2-i14-communications`) |
| Phase A commit | `067e27dfa1493fa3274f9c0d662bda4442f3bbc3` |
| Base (HC-2 acceptance record) | `673676bacf74e213b2d5c866518105a79b959b84` |
| HC-1 accepted | `f777832cb4581344b294fcbd961eea5a0ecc4e10` |
| HC-2 | **ACCEPTED 2026-09-11**, runtime `743c76712cb286ccdae3ad1108fb260dbd04770d` |

No worktree. No second clone. Implementation unauthorized pending Phase B.

---

## Appendix B — Screen assets

Authoritative capture rules: [`p2-i14/assets/README.md`](p2-i14/assets/README.md).

**Baseline (“before”) evidence** — PNG files **not** in git until captured; **complete before I14 UI changes**. Planned Markdown is **literal** (backticks / fenced examples), not rendered images, until each sanitized file is committed. Do not overwrite with acceptance shots. Fixture or sanitized live data only.

| Planned file | PRD reference |
| --- | --- |
| `baseline-explore-ask-gallery.png` | `![Ask/Gallery baseline](p2-i14/assets/baseline-explore-ask-gallery.png)` |
| `baseline-explore-comms-chip-hidden.png` | `![Communications hidden](p2-i14/assets/baseline-explore-comms-chip-hidden.png)` |
| `baseline-explore-day-stack-email.png` | `![Day-stack email](p2-i14/assets/baseline-explore-day-stack-email.png)` |
| `baseline-explore-email-detail-modal.png` | `![Email detail](p2-i14/assets/baseline-explore-email-detail-modal.png)` |
| `baseline-explore-sms-thread.png` | `![SMS thread](p2-i14/assets/baseline-explore-sms-thread.png)` |
| `baseline-explore-calendar-card.png` | `![Calendar card](p2-i14/assets/baseline-explore-calendar-card.png)` |
| `baseline-explore-save-as-story.png` | `![Save as Story](p2-i14/assets/baseline-explore-save-as-story.png)` |
| `baseline-admin-jobs-scheduled-services.png` | `![Admin Scheduled Services](p2-i14/assets/baseline-admin-jobs-scheduled-services.png)` |

Acceptance screenshots (`acceptance-*.png`) are a **later** set. No fabricated images in Phase A.
