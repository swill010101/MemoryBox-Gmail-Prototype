# P2-I14 Phase B step 2 — duplicate audit, logical keys, ingest transactions

**Status:** Assessment / PRD. **Not authorized to seed, backfill, ingest, merge, or delete evidence.**  
**Date:** 2026-09-12 (revised; preview tooling)  
**Branch:** `codex/p2-i14-communications`  
**Depends on:** Phase B step 1 complete — migration **035 applied** on FlightSim; six `comms_*` tables empty; no production `logical_key` rows.  
**Runtime at last verify:** HEAD `c4fd641c148f592523fee2fff997edfa2e85b970`; 035 blob `345bd26fa337cb159626c70fbd9e741fa010506f`.  
**Controlling product:** [P2-I14-COMMUNICATIONS-AND-UNIFIED-GALLERY-PRD.md](../P2-I14-COMMUNICATIONS-AND-UNIFIED-GALLERY-PRD.md) (SRC-8, ING-2, ING-8, ING-9).  
**Schema lock:** [PHASE-B-035-SCHEMA-DECISION.md](PHASE-B-035-SCHEMA-DECISION.md).

This document is the product request for **step 2 only**. Implementation of ingest/UI/tasks remains out of scope until founder sign-off on this PRD **and** a later, separate authorization to build.

**Founder locks (2026-09-12):** Visual Thread Review gate accepted. Logical keys: `household_email`, `household_calendar`, `household_sms`. Competing historical duplicates: **map neither**. Calendar identity remains **unlocked** pending revision/version design. SMS `evidence_kind` is **`communication`** (`sms_export` / csv). Duplicate audit completed on FlightSim (SHA `47c45f7`, 47.1s). Source→stream mapping is recorded in [PHASE-B-STEP-2-AUDIT-RESULTS.json](PHASE-B-STEP-2-AUDIT-RESULTS.json): assign only large non-test extracts; hold tiny/testish/empty landings. Identity fixtures proven on disposable Postgres. **No production seed.** Next: read-only Peggy reconstruction preview (gitignored HTML; counts-only git report).

---

## 1. Problem and why it matters now

Step 1 created lineage tables. They are empty on purpose. Historical `evidence` still uses extract-scoped identity:

- `sources` uniqueness in code is `(uri, source_kind)` (`upsert_source`).
- Duplicate skip is `evidence_exists_by_hash(source_id, payload_json->>'content_hash')`.
- There is **no** UNIQUE on `evidence.content_hash` or on payload hash.

A later Takeout/ICS/SMS file with a new path or filename is a **new** `sources.id`. The same message can already exist as another `evidence` row under the old URI. Mapping or ingest that inserts because aliases are empty will create a **second copy**. Mapping that auto-picks a survivor among duplicates will do so without policy.

A previous live `content_hash` count on FlightSim hit `QueryCanceled`. That timeout **does not** block 035 (already applied). It **does** block: backfill of `comms_record_identities`; choosing a canonical among duplicates; merge/delete; uniqueness on existing `evidence`; claiming the archive is duplicate-free.

Three production streams (email, calendar, SMS) also still have **no** `logical_key`. Membership cannot be attached until those keys are named. Keys name **durable streams**, not the current landing format (mbox, ICS, CSV, API).

Empty lineage tables mean **all current production communication evidence is unmapped**. New ingest must not treat “no alias yet” as “new record.”

---

## 2. Success criteria

Step 2 is complete when all of the following are true:

1. **Cross-extract duplicate audit** finished on FlightSim as **read-only**, with per-batch statement timeouts: sanitized **counts only** (no bodies, addresses, Message-IDs, phone numbers, calendar titles, paths, or hash values).
2. Founder **locks three** `logical_key` strings that match `^[a-z][a-z0-9_]{1,62}$` and are not a mailbox, path, filename, or file format.
3. **Ingest transaction** is specified: concurrency-safe alias lookup; multi-alias conflict; historical unmapped cases; no orphan `evidence` on rollback.
4. **Fixture suite** on disposable Postgres (never dbname `memorybox`) proves those rules **before** any FlightSim seed or backfill.
5. **Founder Visual Thread Review** is specified as a **blocking acceptance gate** (section 10): read-only Peggy reconstruction preview on FlightSim, gitignored private HTML, counts-only git report. No production seed, lineage backfill, prepared-thread load, generation publication, or Gallery comms until Tom **Accept**s Peggy, then a second Person, then a **separate** load/publication authorization.
6. No production `comms_logical_sources` seed and no `comms_record_identities` backfill until that later go-ahead.

---

## 3. Scope

### In

- Read-only FlightSim audit design (timeouts, temp table of **full** hashes, batched copy, sanitized JSON counts).
- Proposed three production logical keys (email / calendar / sms streams).
- Ingest transaction design against **existing** 035 tables.
- Synthetic fixtures + tests (tiny mbox/ICS/CSV or constructed payloads).
- Calendar **revision** alternatives (no 035 change in this step).
- Founder Visual Thread Review gate (read-only preview design; no production I14 writes).
- Update this PRD with audit **numbers** once the audit runs (separate authorized run).

### Out

- Seeding `comms_logical_sources` on FlightSim.
- Backfilling mappings onto historical evidence.
- Writing preview threads into production I14 tables.
- Prepared-generation **publication**, prepared-thread **load**, or Gallery communications exposure.
- Merge/delete of `evidence`.
- UNIQUE on live `evidence`.
- Ask/UI product changes, Windows tasks, live extract ingest of production files as a published generation.
- Changing 035 SQL bytes (any catalog gap is recorded only).
- RRULE **occurrence expansion** (Q2 remains open and out of this step).
- Committing message bodies, personal addresses, or private review annotations.

---

## 4. Constraints and dependencies

| Constraint | Detail |
| --- | --- |
| Identity reuse | `communication_rfc_ids` and `person_contact_points.retrieval_trust` stay the RFC/trust sources. Do not copy RFC tables. |
| Alias uniqueness | `UNIQUE (logical_source_id, identity_method, record_key)`. The same key may exist under another logical source. |
| Canonical | One `comms_record_identities` row maps to one `evidence_id` (`UNIQUE(evidence_id)`, `ON DELETE RESTRICT`). |
| Extract vs logical | `sources.id` is a landing file. Membership is one file to one stream. Extract `source_id` is not unique. |
| Checkpoint | Progress only; not a skip filter (ING-2). |
| Timezone | Closed day `America/Chicago` unless overridden. |
| Privacy | Audit JSON is counts and coarse classes only. Never emit hash values, RFC tokens, paths, or payloads. |
| Interpreter | FlightSim serve: `C:\MemoryBox\.venv\Scripts\python.exe`. |
| Timeouts | `SET LOCAL statement_timeout` per batch (for example 30s). Copy into a temp table; do not `GROUP BY` full `payload_json`. |
| Hash equality | Compare the **complete normalized** `content_hash` string. Do not use `hashtext` (32-bit; false collisions). |

**Existing indexes:** `evidence` has kind and `source_id` indexes, not a payload-hash index. A single-statement `GROUP BY payload_json->>'content_hash'` over the live table canceled. The audit copies hashes into a **temporary table** in source_id (or pk) batches, then aggregates that table.

---

## 5. Cross-extract duplicate audit (design)

**Goal:** sanitized **source inventory** plus hash/RFC duplicate **counts**. Do **not** assume every mbox, ICS, or SMS `sources` row belongs to one household stream until that inventory says so.

### 5.1 Population (read-only)

Include `evidence` whose `evidence_kind` is in the observed communication/calendar set. The first query **counts by `evidence_kind`**; do not hard-require `calendar_event` if production used `communication` for ICS. Join `sources` for `source_kind` and a **coarse uri class** (`mbox`, `ics`, `csv`, `other`) derived without writing the path.

### 5.2 Temporary working table

Create `TEMP TABLE` (session-local), for example:

| Column | Type | Notes |
| --- | --- | --- |
| evidence_id | uuid | From `evidence.id` |
| source_id | uuid | From `evidence.source_id` |
| evidence_kind | text | As stored |
| source_kind | text | From `sources.source_kind` |
| uri_class | text | `mbox` / `ics` / `csv` / `other` only |
| content_hash | text | Complete normalized payload hash, or empty if missing |
| hash_status | text | `ok` / `missing` / `invalid` |

**Normalization for comparison:** trim; lowercase hex if the value is hex. **Shape check (separate from grouping):** `ok` means the normalized value matches the expected SHA-256 hex form (`^[a-f0-9]{64}$`). `missing` means null or empty. `invalid` means non-empty but not that shape. Invalid rows are counted; they are **not** grouped as duplicates of `ok` hashes.

**Fill:** batched `INSERT INTO temp … SELECT` keyed by `source_id` (or `evidence.id` ranges), each batch under `statement_timeout`. Never `SELECT summary` or `payload_json` as a document; extract only `payload_json->>'content_hash'`.

**Index after load (if helpful):** `(content_hash)` where `hash_status = 'ok'`; `(source_id, content_hash)`; `(source_id)`.

**Do not emit `content_hash` values** in JSON, logs, or git.

### 5.3 Source inventory (before stream assignment)

Sanitized rows: `source_id` may be omitted from git in favor of **counts per (`source_kind`, `uri_class`)** plus distinct-source counts. If `source_id` is needed operationally, keep it in a **local** operator file, not the repo.

Do not attach `household_email` / `household_calendar` / `household_sms` to sources until this inventory is reviewed. Extra Takeout files, smoke URIs, or a second mailbox remain possible.

### 5.4 Reports (JSON, git-safe, counts only)

| ID | Name | What to count |
| --- | --- | --- |
| A | Kind inventory | Rows and distinct `source_id` by `evidence_kind` and `sources.source_kind`. |
| B | Uri-class inventory | Distinct sources and row counts by `uri_class` (no paths). |
| C | Missing hash | Rows with `hash_status = missing`. |
| D | Invalid hash | Rows with `hash_status = invalid` (wrong shape). |
| E | Within-source duplicates | For `hash_status = ok`, hashes with `COUNT(*) > 1` **inside one `source_id`**. Emit: colliding-hash count; extra-row count (`sum(n-1)`); distinct sources affected. |
| F | Cross-source duplicates, same proposed stream | After founder/inventory maps sources → at most one proposed logical stream, hashes with `ok` status on **≥2 `source_id`** in that stream. Emit: colliding-hash count; extra-row count; sources affected. If mapping is not yet approved, emit this as **provisional** keyed by `uri_class`/`source_kind` clusters, labeled `unassigned_cluster`. |
| G | Same hash, different logical streams | `ok` hashes that appear in **two or more** assigned streams (or unassigned clusters that will not share a stream). Emit counts only. |
| H | RFC-own fan-out | If `communication_rfc_ids` exists: normalized `role=own` tokens that point at **≥2 `evidence_id`**. Emit: token-group count; extra evidence rows. Never emit the RFC token. |

**Pass/fail for gating backfill:**

- Audit **completes** (no session cancel).
- Counts recorded in a sibling `PHASE-B-STEP-2-AUDIT-RESULTS.json` (counts only).
- Backfill stays blocked while E, F, or H is material, or while source→stream mapping is unconfirmed, until a canonical/backfill policy is signed.
- Production seed, prepared-thread load, generation publish, and Gallery comms stay blocked until section 10 (Peggy visual Accept + second Person + separate load authorization).

---

## 6. Three production logical-source keys (proposal)

035: `UNIQUE (source_kind, logical_key)`. Keys must not be addresses, paths, filenames, or **formats**. An mbox, ICS, API, CSV, or future transport is an **extract/landing format**, stored on `sources` / extract fingerprint — not on `logical_key`.

**Locked (2026-09-12):**

| source_kind | logical_key | label | landing_alias |
| --- | --- | --- | --- |
| email | household_email | Household email | household_email |
| calendar | household_calendar | Household calendar | household_calendar |
| sms | household_sms | Household SMS | household_sms |

`landing_alias` is Admin/status only (same CHECK class as `logical_key`). Exact URI stays on `sources`.

Membership still maps each `sources.id` to **one** stream after inventory. A second mbox is not automatically `household_email`.

**Inventory decision (2026-09-12, counts only; no seed):** assign the large non-testish extracts only: one mbox (91275) → `household_email`; ICS 5745 and ICS 50 → `household_calendar`; one SMS CSV (91557) → `household_sms`. Hold tiny/testish/empty mbox, ICS, and SMS landings and all `artifact_upload` / annotation filesystem rows. Details: [PHASE-B-STEP-2-AUDIT-RESULTS.json](PHASE-B-STEP-2-AUDIT-RESULTS.json).

---

## 7. Ingest transaction design

One logical record, one database transaction. Do **not** use `evidence_exists_by_hash(source_id, …)` as the I14 duplicate barrier.

### 7.1 Once per extract (outside the per-record loop)

1. Resolve configured landing → validate file (SRC-7).
2. SHA-256 fingerprint of bytes.
3. `upsert_source` for that URI (existing `(uri, source_kind)`).
4. Membership: this `source_id` → the **inventory-approved** logical source; fail if already a member of a different stream.
5. Unchanged fingerprint → `checked_unchanged`; no record loop (ING-4).
6. Else insert `comms_extract_instances` (same `source_id` allowed for successive fingerprints).

### 7.2 Alias candidates

Skip missing candidates. Calendar UID+DTSTART is **not locked** (section 8). Methods below are 035-allowed names; ingest must not rely on a locked calendar identity until revision semantics are chosen.

| Kind | identity_method | record_key source |
| --- | --- | --- |
| Email | email_rfc_message_id | `communication_rfc_ids` `role=own` (normalized). Not a second RFC table. |
| Email | email_vendor_message_id | Vendor id if present. |
| Email | email_full_sha256 | Full-message SHA-256 (complete hex). |
| Calendar | (unlocked) | See section 8. `calendar_full_sha256` remains a content alias only. |
| SMS | sms_provider_id | Export GUID if present. |
| SMS | sms_normalized_sha256 | Normalized body+participants+time hash. |

### 7.3 Multi-alias resolution (required)

Inside the transaction, after the concurrency lock (7.4), `SELECT` canonical ids for this `logical_source_id` whose `(identity_method, record_key)` matches **any** candidate.

| Distinct canonicals | Action |
| --- | --- |
| 0 | Follow historical-evidence rules (7.5). Do not insert a duplicate merely because aliases are still empty. |
| 1 | Reuse that canonical. Do not insert `evidence`. **Atomically insert every missing valid candidate alias** for that canonical. Commit. |
| 2 or more | `ROLLBACK`. Record `alias_conflict`. Never pick a winner. |

**Uniqueness conflict:** `UNIQUE (logical_source_id, identity_method, record_key)` violation means that alias already belongs to a canonical. If that canonical is not the one this transaction is bound to, **roll back** and record `alias_conflict`. Adding missing aliases is **required**, not optional. A conflict while adding aliases is not “skip that alias.”

### 7.4 Concurrency

`SELECT` then `INSERT` without a lock can create two `evidence` rows for one identity under concurrent workers.

**Required:** `pg_advisory_xact_lock` for the transaction, keyed by `logical_source_id` plus a stable encoding of the **sorted candidate alias keys** (full strings, not 32-bit `hashtext` of the payload). Hold the lock for the whole per-record transaction.

Then:

1. Re-read aliases (7.3).
2. Apply 7.3 / 7.5.
3. If inserting aliases after new evidence, any unique violation → **rollback the entire transaction** (evidence insert included). No orphan `evidence`. No canonical without aliases if the insert set was non-empty.

**Retry:** a serialization or unique failure that is **not** `alias_conflict` (for example two workers, one won the lock) may retry the record once after rollback. `alias_conflict` does not retry as a merge.

### 7.5 Historical unmapped evidence (three cases)

Lineage tables are empty, so production rows have **no** aliases yet. Matching uses complete `content_hash` (`hash_status = ok`) and/or RFC-own links, **restricted to `source_id`s that inventory assigns to this logical stream** (or an explicit unassigned hold). Do not match “the same hash in a different stream” as the same household record.

| Case | Meaning | Ingest action now |
| --- | --- | --- |
| No matching historical evidence | Identity/hash is absent on assigned sources for this stream. | Insert new `evidence`, canonical, and all valid aliases in one transaction (7.3/7.4). |
| Exactly one unambiguous historical evidence row | One unmapped `evidence.id` matches this identity/hash in the stream. | Do **not** treat as ordinary new ingest. Do **not** insert another `evidence` copy. Do **not** write `comms_record_identities` until backfill is authorized. Record `eligible_for_backfill`. Leave the row unchanged. |
| Multiple historical evidence rows | Two or more unmapped rows match the identity/hash in the stream. | Record `needs_canonical_policy`. Map none. Insert none. |

**Recommendation:** when multiple historical rows compete, **map neither** until a dedicated merge/backfill increment.

Late records still enter 7.3–7.5; checkpoint is not a skip filter.

### 7.6 Immutable evidence

- Do not update `payload_json` / `summary` on an already-mapped `evidence_id`.
- Missing aliases on an **already mapped** canonical are added (7.3, exactly one canonical).
- `first_extract_instance_id` is set only when the canonical is inserted.

---

## 8. Calendar mutation and identity (unlocked)

A calendar **UID** names an event family. Time, title, attendees, recurrence, and cancellation can change across extracts. 035 allows **one** canonical row and **one** `evidence_id` (`UNIQUE(evidence_id)`). Overwriting that evidence is forbidden. Storing a later revision as a second canonical **cannot** reuse the same unique UID alias without `alias_conflict`.

**Do not lock `calendar_uid_dtstart` (or `calendar_uid_recurrence`) in this step.** RRULE **occurrence expansion** stays out of scope (Q2).

| Alternative | How later revisions are kept | 035 gap? |
| --- | --- | --- |
| A. Stable canonical event plus immutable evidence revisions | One canonical keeps first-seen `evidence_id`. Later extracts insert **additional** immutable `evidence` rows linked as revisions (new table or equivalent), not as new canonicals. UID aliases stay on the one canonical. | **Yes.** 035 has no revision/child evidence list; only `first_extract_instance_id` and one `evidence_id`. |
| B. Each revision is its own canonical, plus an event-family relation | Each changed extract inserts new evidence + new canonical. Family grouping is a separate parent/key. UID cannot be a unique alias on every revision. | **Yes.** 035 has no family/parent column; unique aliases cannot be shared by two canonicals in one logical source. |
| C. Content-hash-only canonicals (`calendar_full_sha256`) | Each byte-identical snapshot is its own record; UID is not unique. Gallery would group later. | Partial: allowed methods exist, but UID-as-identity is abandoned; prepared layer must reconstruct the event. No new table strictly required for ingest, but product identity is weaker. |

**Recommendation:** **Alternative A** (stable event canonical + immutable revision evidence). That preserves UID as the event identity and never overwrites first evidence. It is a **035 schema gap**. Do **not** alter 035 in step 2; calendar ingest identity stays unlocked until a separately reviewed additive migration (or an explicit founder choice of C).

Until that review, fixture ingest for calendar may exercise `calendar_full_sha256` only, or skip calendar record insert.

---

## 9. Fixture prove (before FlightSim seed/backfill)

Disposable Postgres only (pattern: `tests/test_p2_i14_lineage_pg.py`). Never dbname `memorybox`.

| Fixture case | Expect |
| --- | --- |
| Same RFC + hash in two files / two `sources.uri`, aliases already populated | One evidence; one canonical; missing aliases added; two extract instances; same logical source. |
| Candidate aliases point at two canonicals | `alias_conflict`; rollback; no new evidence. |
| Uniqueness hit on an alias owned by another canonical | `alias_conflict`; full rollback. |
| No aliases yet; exactly one historical evidence with this hash in-stream | `eligible_for_backfill`; no second evidence row. |
| No aliases yet; two historical evidence rows with this hash in-stream | `needs_canonical_policy`; map none. |
| No historical match | Insert evidence + canonical + all aliases. |
| Concurrent two workers, same aliases | One winner; loser retries or no-ops; never two evidence rows. |
| Unchanged extract fingerprint | Zero new evidence; `checked_unchanged`. |
| Alias exists only under a different logical source | No collision; this stream follows 7.5 independently. |
| Same hash in two streams | Not merged (report G). |

Parser fixtures: tiny synthetic mbox/ICS/CSV in `tests/fixtures/` with non-family addresses (`user@example.test`). No production Takeout in git.

Synthetic fixtures do **not** replace the Founder Visual Thread Review (section 10). Fixtures prove identity/transaction rules; Peggy preview proves reconstruction on real evidence.

---

## 10. Founder Visual Thread Review (blocking gate)

**Mandatory** before any of: production logical-source seed, lineage backfill, prepared-thread load, generation publication, Gallery communications integration.

This gate is **not** a production write path. Reconstruction runs as a **disposable / read-only preview** process. Preview results **must not** be written into production I14 tables (`comms_logical_sources`, memberships, extracts, checkpoint, `comms_record_identities`, aliases, or any future prepared-thread/generation tables).

### 10.1 Preview process

1. Build reconstructed email threads in a disposable or read-only preview only (local FlightSim; existing `evidence` / RFC tables may be **read**).
2. Do not persist preview threads as I14 lineage or prepared rows.
3. Render founder-reviewable **UTF-8 TXT packets** from real Peggy email evidence, locally on FlightSim (gitignored). Do **not** emit a monolithic HTML or one enormous TXT file.
4. Keep the fixture **private and gitignored**. Do not commit message bodies, personal addresses, or founder annotations that contain them.
5. After Peggy is explicitly accepted, **repeat** the same gate for a **second canonical Person** before general production publication.

**Two products (do not collapse):**

| Product | Contents | Use |
| --- | --- | --- |
| Canonical communication thread | Every reconstructed message, any sender, chronological | MemoryBox communications, Gallery context, visual review |
| Peggy-authored voice corpus | Only messages whose **From address** is a confirmed unique Peggy contact | Later Peggy narrative / Words of a Life. Mail **to** Peggy is not her voice. |

Authentication is **address-ledger only** (`person_contact_points` / confirmed `communication_identities`, unique person). Display names and nicknames (Peggy / Peggo / PegLeg) are labels **after** authentication. Unverified senders stay unverified.

### 10.1a Private review tree (FlightSim, gitignored)

Proposed path: `working/i14-thread-review/` (never commit).

| File | Role |
| --- | --- |
| `README.txt` | Navigation + founder marks |
| `INDEX.txt` | One searchable line per thread (no bodies/addresses in the git report; private INDEX may include date range only plus counts) |
| `packet-NNN.txt` | About **25** canonical threads each; full prepared From/To/Cc/Date/Subject/authorship/cleaned text |
| `originals/T-NNNN-M-NN.txt` | One immutable original; open by Evidence-ref only |
| `MARKS.txt` | Accept / Split / Merge / Incorrect participant / Incorrect ordering / Quoted text removed incorrectly / Missing message / Needs investigation |

Production generation of this tree requires a **separate** founder authorization (`MEMORYBOX_I14_REVIEW_EMIT_PRIVATE=1`). Census-only counts may run without emitting the tree.

Each prepared message must show: From (display + address), To (all), Cc when present, Date (local America/Chicago + timezone), Subject, authorship status (authenticated Peggy / authenticated other Person / unverified), cleaned authored text, attachment filename/type when present, Evidence-ref. Each thread shows BEGIN/END THREAD, stable review id, chronology, date range, participants, evidence/duplicate/excluded counts, threading and identity confidence, warnings.

Visually distinguish Peggy-authored messages (`Voice corpus: yes`) without dropping non-Peggy messages from the canonical thread.

### 10.2 Representative cases (must appear in the Peggy set)

| Case | What the founder must see |
| --- | --- |
| Normal two-person thread | Ordinary back-and-forth, two participants. |
| Long thread | Many turns; scrolling/order still correct. |
| Forwarded message | Forward boundaries visible; not flattened into one authored blob incorrectly. |
| Quoted-reply stripping | Quoted prior text removed from the cleaned authored view when that is the intended compaction. |
| Changed subject | Same thread despite subject change, or a warning if the threader split/joined. |
| Missing or malformed Message-ID | Thread still reviewable; warning shown; no silent drop. |
| Duplicate message across extracts | One displayed message or an explicit duplicate omission; counted in reconciliation. |
| Attachment indicators | Attachments flagged without requiring Gallery. |
| Ambiguous participant identity | Handle shown; not silently bound to a Person. |
| Threader split or combine | Messages the threader separated or combined, with a review warning. |

### 10.3 Each preview thread must show

| Field | Requirement |
| --- | --- |
| Chronological order | Message order in the reconstructed thread. |
| Attribution | Sender and recipient (as handles; Person only if already fail-closed trusted — do not invent). |
| Date/time | With source timezone/provenance when known. |
| Cleaned authored text | Compaction result used for the preview, not a silent omit. |
| Immutable original | Expandable reference to the underlying `evidence` (id/count only in git report; body stays in the gitignored UI). |
| Source evidence count | How many evidence rows fed this thread. |
| Omitted/duplicate count | Deliberate duplicates and excluded/problem records. |
| Confidence / warning | Review warning when Message-ID is missing, identity is ambiguous, or the threader split/combined. |

### 10.4 Completeness reconciliation (no unexplained loss)

For the eligible Peggy (then second-Person) population:

`original eligible messages = displayed thread messages + deliberate duplicates + excluded/problem records`

Unexplained loss is a **gate fail**. The gitignored UI and the counts-only report must both show these three buckets plus a zero unexplained remainder.

### 10.5 Founder marks (required UI actions)

| Mark | Meaning |
| --- | --- |
| Accept thread | This reconstruction is good enough to proceed (for this thread). |
| Split here | Thread should break at a marked message. |
| Merge with another thread | This thread belongs with another preview thread. |
| Incorrect participant | Attribution or Person binding is wrong. |
| Incorrect ordering | Chronology is wrong. |
| Quoted text removed incorrectly | Compaction stripped or kept the wrong quoted text. |
| Missing message | An eligible message is absent from display, duplicates, and excluded buckets. |
| Needs investigation | Do not accept; park for follow-up. |

Overall Peggy (and later second-Person) **Accept** is Tom’s explicit action. Per-thread marks feed that decision. A single `Needs investigation` or unexplained loss blocks publication.

### 10.6 Reports and privacy

| Artifact | Location | Contents |
| --- | --- | --- |
| Private TXT packets + originals + marks | FlightSim `working/i14-thread-review/`, **gitignored** | Real bodies, addresses, marks. Never commit. HTML preview is retired. |
| Counts-only review report | Git-suitable JSON | Case coverage; eligible / displayed / duplicate / excluded / unexplained; authorship census; no bodies, addresses, or Message-IDs. |

### 10.7 Blocking rule

Do **not** load reconstructed threads into production I14/prepared tables, publish a prepared generation, or expose communications in Gallery until:

1. Tom explicitly accepts the **Peggy** reconstruction, and
2. The same gate **passes** for a **second canonical Person**, and
3. Founder issues a **separate** authorization for production load/publication.

---

## 11. Build sequence

Authorized order (each arrow is a founder gate unless already signed):

duplicate audit → logical-source decision → ingest/identity fixtures → read-only Peggy reconstruction preview → founder visual review → second-Person proof → separate authorization for production load/publication

| Step | What happens | Writes production I14? |
| --- | --- | --- |
| Duplicate audit | Read-only temp-table hash/RFC counts; source inventory. | No |
| Logical-source decision | Lock keys; map sources to streams from inventory. | No seed until later authorization |
| Ingest/identity fixtures | Disposable Postgres only; transaction/alias/historical rules. | No |
| Read-only Peggy preview | Reconstruct threads; gitignored TXT packets after separate emit auth. | No |
| Founder visual review | Marks in section 10.5; counts-only git report. | No |
| Second-Person proof | Repeat preview + visual review for a second Person. | No |
| Production load/publication | Seed, backfill, prepared load, generation publish, Gallery. | **Only after separate founder authorization** |

**This documentation revision:** duplicate audit, mapping, and identity fixtures are complete. Next **build** is the read-only Peggy reconstruction preview (section 10): gitignored HTML, counts-only git report, founder marks. Do not seed, backfill, or load production.

---

## 12. Open questions and recommendations

| ID | Question | Recommendation |
| --- | --- | --- |
| Q-keys | Which three `logical_key` values? | **Locked:** `household_email`, `household_calendar`, `household_sms`. |
| Q-multi | Multiple historical rows for one identity/hash? | **Locked:** map **neither** (`needs_canonical_policy`) until a merge increment. |
| Q-cal | Lock `calendar_uid_dtstart` now? | **Locked no.** Unlock until revision semantics (recommend alternative A; 035 gap; separate review). |
| Q-sms | What `evidence_kind` is SMS today? | **Locked:** `communication` (`sms_export` / csv). |
| Q-next | What to build next? | **Locked:** founder **authorizes private TXT generation** after reviewing this redesign. No production seed, backfill, prepared load, or Gallery. |
| Q-map | Which landing files join the three streams? | **Locked:** large non-testish mbox + two non-testish ICS + large SMS CSV. Hold the rest (see audit results JSON). |
| Q-visual | When may Gallery show comms? | Only after Peggy visual Accept, second-Person proof, and a separate production-load authorization. |

---

## 13. Explicit non-goals this pass

Ask/Gallery product changes, prepared-generation **publication**, live nightly ingest, Windows task, email send, I13 jobs, changing HC-2, RRULE occurrence expansion, altering 035, committing private preview HTML, production seed/backfill/prepared-thread load.
