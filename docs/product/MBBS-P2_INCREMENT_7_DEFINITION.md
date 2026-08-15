# MBBS-P2 Increment 7 — SMS/Text Evidence

**Status:** **ACCEPTED** (2026-08-15 — Tom: “i7 is accepted”)  
**Date:** 2026-08-14 (build) · 2026-08-15 (accepted)  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) § P2-I7 (SMS/Text · A)  
**Authority:** Locked [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) P2-COM-01 / P2-COM-03 · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) CAP-P2-018 · [MBEVS-001 v1.0](MBEVS-001_EVS_CATALOG_v1.0.md) · I1–I6 **ACCEPTED**  
**Thin PRD:** [MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md](MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md)  
**Depends:** P2-I6 **ACCEPTED** · I4 Explore already has an SMS/text card type (engine not connected)  
**Does not reopen / does not absorb:** I4 Explore redesign · I5 portrait **P2-BL-I5-01** · I6 kinship **P2-BL-I6-01** · SMS attachment bytes **P2-BL-I7-01** · **I8 richer email** (incl. **P2-BL-I8-01** attachment files up front) · I8.5 face-evidence · **I9 spoken** · **I10 cross-source correlation** · **I11 narrative** · I13/I14 Settings · multi-user · **I7A / MBQL-001**

P2-I7 is **ACCEPTED**. SMS **attachment files** were not in the staged export (CSV-only; `inspect-sms` 2026-08-15: 7,212 names, 0 files). That gap is **P2-BL-I7-01** — do not reopen I7. [P2-I7A](MBBS-P2_INCREMENT_7A_DEFINITION.md) is **ACCEPTED** 2026-08-15. Next: **[MBQL-001](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) BUILD AUTHORIZED** 2026-08-15.

---

## What shipped (ACCEPTED)

- Header-driven ingest of the FlightSim iMazing CSV → communication Evidence (90,784 inserted; originals untouched)
- Ask retrieve / Person / date / keyword / last-N / outbound + bidirectional + inbound counts with scope
- Explore / Person reuse Email/Text cards; default Gallery hides texts unless Add/Only/explicit
- Unique phone → confirmed People contact; ambiguous Review; unmapped retained
- PowerShell-style Ask history (Up/Down in the box; last 100)
- Attachment **names/types** linked on the message; not Immich-promoted

## Carry-forward / backlog (not ACCEPTED blockers)

| ID | Item | Notes |
|----|------|-------|
| **P2-BL-I7-01** | SMS / iMessage **attachment bytes** | CSV lists 8,644 rows / 7,212 unique names; `sms` folder has only the CSV. iMazing **Export Attachments** (or `MEMORYBOX_SMS_ATTACHMENTS_DIR`) then `ingest-sms` backfill. Not I7A. Not Immich. |

---

## 0. Product intent

> **Imported SMS / iMessage / MMS / text messages become first-class MemoryBox communication evidence — searchable, Person-linked, dated, provenance-preserved — in the existing Ask / Explore / Person surfaces. Missing coverage is disclosed. Messages are never invented.**

I7 is **archive understanding**, not a messaging application, not a new family nav item, and not a parallel SMS product.

End-to-end:

1. The staged FlightSim export is **ingested without modifying originals**.  
2. Each message is **Evidence** (`evidence_kind=communication`) with channel/service identifying sms / text / imessage / mms as the source allows.  
3. **All meaningful source metadata is preserved** even when I7 UI does not show it (so later Place/Event/Trip/narrative work does not re-import).  
4. Participants resolve to **canonical MB People** via normalized phone/handle identity.  
5. Ask can retrieve, filter (Person / date window / keyword), count (outbound and bidirectional), date-order, and open evidence — with **scope disclosure**.  
6. Explore / Person All Memories show SMS as **communication cards** on the existing mixed-media canvas; dated items participate in Timeline.  
7. Archive Health distinguishes **staged vs ingested vs unavailable** (unavailable ≠ 0).

Future use I7 must **enable**, not perform: *“Include all Alaska texts in the narrative of my Alaska trip.”* That correlation/narrative is **I10/I11**. I7 must leave timestamp, text, thread, participants, attachments, and any explicit location metadata intact.

---

## 1. Q1–Q6

| # | Topic | Status | Resolution |
|---|--------|--------|------------|
| **Q1** | Export path / format | **OPENED ON FLIGHTSIM 2026-08-14** | `inspect-sms` on `\\media-server\photos\MemoryBox\Sources\sms\Messages - 1085 chat sessions.csv`. See §1.1. Header-driven parser matches these columns. |
| **Q2** | Acceptance people / years | **SELECTION RULES LOCKED; NAMES PENDING Q1 SAMPLE** | Prefer Peggy / 2020 / Denny Pizzani / “3D printing” **only if they exist in the real export**. Otherwise pick real equivalents and map them to EVS intent (§1.2). Do not invent a convenience corpus. |
| **Q3** | Group threads | **LOCKED** | Ingest/preserve group threads when the source contains them. **No “Core 4” domain object.** EVS-117 is not a hard I7 gate unless the sampled corpus supports it. |
| **Q4** | MMS / attachments | **LOCKED** | Preserve attachment references, metadata, and original bytes/files when the export provides them. Show in the message/thread evidence experience where practical. **Do not auto-promote to Immich or standalone Explore photo/video cards.** Later explicit promote/correlate is not I7. |
| **Q5** | Phone/handle → Person | **LOCKED** | Normalize, then: unique confirmed match → auto-map; ambiguous → Review; no match → unmapped participant (source display name / raw handle). Never silent duplicate People. Never merge on similar display name alone. |
| **Q6** | Summaries | **LOCKED** | Hard gate = retrieve / count / Person / date-window / keyword / date-order / open / scope disclosure. Summary EVSs = short **evidence-backed** summary or cited extract; underlying messages remain reachable. Full trip/year/multi-source narrative stays **I10/I11**. |

**Build authorized** 2026-08-14. Q1 file-open recorded from FlightSim `inspect-sms` (same day). Message bodies were not copied into git.

### 1.1 Q1 — FlightSim inspect-sms (2026-08-14)

`original_untouched: true`. Parser version `i7-sms-1`. No sample bodies returned.

| Item | Finding | Confidence |
|------|---------|------------|
| Canonical Sources root | `\\media-server\photos\MemoryBox\Sources` | Documented |
| Full UNC | `\\media-server\photos\MemoryBox\Sources\sms\Messages - 1085 chat sessions.csv` | **Opened** |
| Bytes | 15,903,315 | Inspect |
| Format | Comma CSV, one row per message, UTF-8 | Inspect |
| Headers | Chat Session, Message Date, Delivered Date, Read Date, Edited Date, Deleted Date, Service, Type, Sender ID, Sender Name, Status, Replying to, Subject, Text, Reactions, Attachment, Attachment type | **Opened** |
| Row count | 91,798 | Inspect |
| Thread count | 1,036 (filename says 1085 sessions — empty/omitted sessions possible) | Inspect |
| Date min / max | 2008-12-14 … 2026-07-26 (UTC ISO from Message Date) | Inspect |
| Services | `imessage`, `mms`, `sms`, `text` (no RCS in this file) | Inspect |
| Attachment rows | 8,644 (filename/type columns; not auto-promoted) | Inspect |
| Location columns | **None** (`location_rows: 0`). No Latitude / Longitude / Shared Location headers. Later Alaska-style correlation uses time/thread/text/attachments, not SMS GPS. | Inspect |
| Thread encoding | `Chat Session` — sample values are E.164 phone handles. No separate Recipients / Group Name column. Group threads still preserved as a Chat Session id when the source uses one. | Inspect |
| Participants | Sender ID + Sender Name + Chat Session (phone/handle). No Recipients column. | Inspect |
| Richer Apple fields | Service, Type (Incoming/Outgoing), Delivered/Read/Edited/Deleted Date, Replying to, Reactions, Attachment + type | Inspect |
| Not in this export | Recipients, Group Name, Tapback-as-own-column (Reactions instead), lat/lng, Shared Location | Inspect |

**Adapter/parser follows the actual source after inspect.** Do not lock “CSV columns = …” until the header row is recorded.

#### Q1 inspect protocol (FlightSim, read-only — not I7 ingest)

Run on FlightSim **before writing a parser**. Do not modify files.

```powershell
$root = "\\media-server\photos\MemoryBox\Sources"
Get-ChildItem -LiteralPath "$root\sms" -Force | Format-Table Name, Length, LastWriteTime
Get-Content -LiteralPath "$root\MANIFEST.json" -TotalCount 80
# Header + a few rows only — do not dump family message bodies into git:
Get-Content -LiteralPath "$root\sms\Messages - 1085 chat sessions.csv" -TotalCount 3
```

Record into an I7 Q1 addendum (or this §1.1 table) **before implementation**:

1. Exact path(s) and filename(s) actually present (CSV plus any attachments / HTML / DB / folders).  
2. Format (delimiter, encoding, header names, whether one-row-per-message).  
3. Source system if determinable (exporter name, Apple Messages, mixed).  
4. Fields/columns available (full header list).  
5. Date min/max (from timestamp column — no invented range).  
6. How participants, phone numbers, and Apple-account handles are represented.  
7. How thread / conversation / group name / group membership are represented.  
8. How attachments are represented (filename, relative path, MIME, GPS-in-attachment).  
9. Whether richer Apple metadata exists (service, reply, Tapback/reaction, edit, unsend, read/delivered).  
10. Whether the export is SMS, iMessage, MMS, RCS, or mixed — **from a service/channel field or equivalent, not from the folder name**.  
11. Any explicit location fields (shared location, address text, attachment GPS).  
12. Notable limitations (iCloud-offloaded attachments, truncated bodies, missing numbers, timezone).

Q1 file-open is **recorded** (inspect-sms 2026-08-14). Do not commit message bodies. Sibling attachment files on disk were not inventoried by inspect-sms (CSV attachment *columns* only).

### 1.2 Q2 — real corpus selection (after Q1 sample)

Do **not** require Peggy / 2020 / Denny if the export does not support them cleanly.

After sampling (counts, not harvesting message bodies into git):

| Fixture needed | Prefer if present | Else |
|----------------|-------------------|------|
| Known Person with a meaningful **two-way** thread | Peggy (EVS-220 / 223 / 224) | Another confirmed MB Person with real two-way texts |
| Known **year/date window** | 2020 (EVS-065) | A year that actually has messages |
| Known **keyword** in corpus | “3D printing” + Denny Pizzani (EVS-118) | A real keyword + Person pair |
| Owner **outbound** count | Tom Will / active owner (EVS-221 / 222) | Same owner, state the year/scope used |
| **Bidirectional** count | Peggy ↔ owner (EVS-220) | The two-way Person above |
| EVS-106 earn-in | Sister + distinctive sign-off if present | Disclose gap; do not invent |

Map whatever is chosen **back to EVS intent** in the Q1 addendum (table: EVS → fixture Person/year/keyword). That mapping is part of lock, not a silent substitution.

---

## 2. Locked product rules

### 2.A Import-only

- I7 ingests the **staged export**. It does not replace Messages.app, carrier SMS, or live phone sync.  
- Originals stay untouched (same rule as mbox email ingest).  
- Multi-user / family-contributed SMS is **out**.

### 2.B One evidence model

Do **not** invent a parallel `sms_messages` SoT unless communication Evidence **cannot** preserve required source/thread metadata. Default: it can.

| Existing | I7 use |
|----------|--------|
| `evidence` + `evidence_kind=communication` | One row (or equivalent) per source message |
| `payload_json` | Normalized fields **plus** a preserved source-metadata bag for unused columns |
| `sources` | Import source path/file, hash, account/scope |
| `evidence_channel` / service | `sms` / `text` / `imessage` / `mms` (and RCS if present) as the **source** distinguishes — do not collapse everything to a single label if the export is richer |
| `provider_identities` `identity_kind=phone` (and handle/email-as-handle if that is how Apple IDs appear) | Map to MB Person |
| Profile `CONTACT_KINDS` includes `phone` | Unique confirmed contact match |
| Ask `want_communication` → `search_evidence_pg` | Teach SMS/iMessage channel + Person/year/keyword/count |
| Explore mapper `sms` / `text` | Communication cards — **no SMS app, no new nav** |
| Archive Health `staged_sms` | Staged vs ingested vs unavailable; never `0` for “not connected” |

Email ingest (`memorybox/ingest/comms_email.py`) is the **pattern** (Source + Evidence, originals untouched, hash skip). I7 does not become I8 richer email.

### 2.C Preserve source fidelity (more than the first EVSs)

Normalize fields I7 needs now. **Do not discard** source metadata merely because I7 UI does not expose it.

When the export provides them, preserve at least:

- original / source message ID  
- original text / body  
- sent / received timestamp(s)  
- direction / from-owner state  
- sender handle  
- recipient handles  
- participants  
- phone numbers and/or Apple-account handles  
- service / channel: iMessage / SMS / MMS / text (and RCS if present)  
- thread / conversation ID  
- group name  
- group participants / membership as available  
- attachment references (and bytes/files when present and ingest can store them without rewriting the export)  
- reply relationships  
- reaction / Tapback metadata  
- edit / unsend metadata if present  
- import source path / file  
- import provenance  
- ingest timestamp  
- source coverage / account scope  

Store unused-but-present columns in a structured **source_metadata** object (names as in the file). Losing a column because “Ask doesn’t need it yet” is a defect.

### 2.D Location / correlation readiness (not I10)

Preserve any **explicit** location-related evidence in the source, including where present:

- shared-location content  
- place / address text  
- attachment metadata  
- location-bearing attachment metadata  
- other source fields relevant to later Place / Event / Trip inference  

Even when a message has **no GPS**, preserve timestamp, participants, thread, attachment, text, and source metadata so later increments can correlate.

**Absence of direct SMS GPS does not prevent later inferred location through correlation.**

Later increments may infer that a text belongs to a Place / Event / Trip using timestamp, message text, GPS-bearing photos/videos, calendar, known trip windows, and other evidence. That inferred location is **not source fact**: preserve method / provenance / confidence. It must **not overwrite** explicit source location evidence.

I7 **does not** run Alaska (or any) Place/Event/Trip inference or narrative.

### 2.E Person linking

- Canonical **MB Person IDs** only.  
- Phone number / Apple handle is a **provider/contact identity**, never `people.id`.  
- Normalize phone numbers before matching.  
- Unique normalized number/handle matching **one confirmed** Person contact → **auto-map**.  
- Ambiguous matches → **Review**.  
- No match → retain **unmapped** participant using source display name / raw handle.  
- Never create silent duplicate People.  
- Never merge based only on similar display name.

### 2.F Group threads

- **IN** when the source contains them.  
- Preserve thread/conversation identity, participants, group name when present, group membership as available.  
- Do **not** throw away group structure because EVS-117 Core 4 is not a hard gate.  
- Do **not** create a special Core 4 domain object.

### 2.G MMS / attachments

- Attachments stay **linked to the source message**.  
- Preserve reference + metadata; preserve original bytes/files when the export provides them and ingest can do so **without rewriting Sources**.  
- Show attachments in the message/thread evidence experience where practical.  
- **Do not** silently promote attached photos/videos into Immich.  
- **Do not** automatically create standalone Explore photo/video cards solely because they were attached to an SMS.  
- Later workflows may explicitly promote/correlate them as first-class MB objects — **not I7**.

### 2.H Ask (hard vs summary)

Hard I7 Ask:

- retrieve messages  
- Person filtering  
- year / date-window filtering  
- keyword filtering  
- count messages  
- outbound count  
- bidirectional count  
- date ordering  
- evidence opening  
- scope disclosure  

Summary EVSs (065 / 118 / 224): short evidence-backed summary **or** cited extract. Underlying messages remain reachable. Never summarize without evidence access. Full trip/year/multi-source narrative stays later (**especially I10/I11**).

### 2.I Surfaces (reuse, do not redesign)

- Ask  
- Explore mixed-media gallery  
- Person All Memories  
- shared communication / evidence detail shell  
- Archive Health  

SMS/text appears as **communication evidence** inside the existing mixed-media product. **Do not redesign I4 Explore.** No new top-level SMS navigation.

**Gallery default (I7 clarification, 2026-08-14):** SMS/Text is first-class evidence after ingest, but it is **not** automatically visible in the default Gallery for broad Person / Event / Trip / ordinary memory queries. High-volume communications stay eligible for retrieve, counts, correlation, summaries, and later narrative even when cards are visually suppressed. Gallery visibility is **not** evidence exclusion.

Explicit communication intent overrides the default (existing Explore refine style — not a query language):

| Ask / refine | Gallery |
|--------------|---------|
| “Show me Peggy” | Normal memory Gallery; Text **hidden** by default |
| “Add texts” | Text **joins** the current Gallery without clearing context |
| “Only texts” | Text-only Gallery |
| “Show me all my texts with Peggy” | Text **automatically visible** |

A separate **P2-I7A** (AI Model Trace) is **ACCEPTED** 2026-08-15; **MBQL-001** follows **after I7A**, not immediately after I7. Do not broaden I7 into either. See [I7A definition](MBBS-P2_INCREMENT_7A_DEFINITION.md).

### 2.J Archive Health honesty

After ingestion:

- staged vs ingested distinguishable  
- unavailable ≠ zero  
- missing source ≠ zero messages  
- unsupported date range ≠ zero  
- unmapped participants disclosed  
- source / account / date coverage disclosed  
- do not imply completeness beyond ingested source scope  

---

## 3. Scope IN

- Read-only ingest of the **actual** FlightSim staged export (after Q1 file-open).  
- Communication Evidence + full source-metadata preservation (§2.C–2.D).  
- Phone/handle → Person (§2.E).  
- Group-thread structure when present (§2.F).  
- Linked attachments, not Immich promotion (§2.G).  
- Ask hard capabilities + short cited summaries (§2.H).  
- Explore / Person communication cards + Timeline for dated messages.  
- Archive Health staged / ingested / unavailable.  
- Source-fidelity check of at least one real message against the export.  
- Correlation-readiness check of preserved metadata (no Alaska inference).  
- `prove-p2-i7` structural harness **plus** FlightSim owner ACCEPTED.

## 4. Scope OUT

| Out | Home |
|-----|------|
| Richer email (threads-as-email-product, attachments-as-email-artifacts, email places) | **P2-I8** |
| Spoken moments / STT | **P2-I9** |
| Inferring Place / Event / Trip from texts + photos/calendar; “Alaska texts in the Alaska trip” | **P2-I10** (correlation) then **I11** (narrative) |
| Year / trip / person **multi-source narrative** (EVS-047, 070, 211–213, 235–236) | **I8 + I11** as mapped |
| Live carrier / iMessage sync, sending texts | Never I7 |
| Replacing Messages / SMS apps; new SMS nav | Never |
| Core 4 special object | Out (group threads still preserved) |
| Auto-promote MMS into Immich / Explore media library | Out |
| I6 kinship reopen / family tree | Closed |
| Immich preferred portrait | **P2-BL-I5-01** |
| Face-evidence ownership / Learn-rail Immich writes | **I8.5 after I8** |
| Mature Settings / provider catalog | **I13 / I14** |
| I4 Explore chrome redesign | Closed |
| Invented messages or silent completeness | Forbidden |
| Multi-user SMS contribution | Late / I15 |

---

## 5. EVS coverage (I7 homes)

Canonical homes from MBRM-001A Appendix A.1. Aliases are not separate acceptance.

| EVS | Ask (short) | I7 bar |
|-----|-------------|--------|
| **EVS-220** | How many times did Peggy and I text each other? | Bidirectional count + scope; **or** mapped equivalent Person after Q1 sample |
| **EVS-221** | How many text messages did I send in 2024? | Outbound count for owner + year that **exists** (2024 if present; else disclosed substitute year) |
| **EVS-222** | How many total text messages have I sent? | Outbound count + coverage |
| **EVS-223** | Show me all my text messages with Peggy. | Retrieve dated originals; **or** mapped equivalent Person |
| **EVS-224** | Summarize all my text messages with Peggy. | Cited summary/extract; messages reachable |
| **EVS-065** | Summarize texts Peggy and I sent in 2020 | Year window + cite if that year exists; else mapped year |
| **EVS-118** | Summarize texts with “3D printing” and Denny Pizzani | Keyword + person **if corpus has it**; else mapped keyword fixture |
| **EVS-106** | Find messages where my sister and I signed off with a funny name | **Earn-in if** corpus permits; else disclose gap — do not invent |

**Not I7 ACCEPTED:**

- EVS-047 / 070 → richer communications + narrative (**I8 / I11**)  
- EVS-117 Core 4 → not a hard gate; preserve groups anyway  
- EVS-211–213 / 235–236 → **I11** narrative  
- Email-only counts (EVS-107 / 108) → **I8**

---

## 6. Discovery (reuse — do not reinvent)

| Area | Finding |
|------|---------|
| Staged original | Checkpoint: `Sources\sms\Messages - 1085 chat sessions.csv` (iMessage/SMS export; ingest deferred 2026-08-09) |
| Email ingest pattern | `memorybox/ingest/comms_email.py` — copy Source + Evidence, do not rewrite originals |
| Evidence schema | `evidence_kind=communication` already in `001_domain_v0.sql` |
| Phone identity | `provider_identities.identity_kind` includes `phone`; Profile contacts include `phone` |
| Ask | `want_communication` already searches PG communication Evidence (email-shaped today) |
| Explore | `explore/find.py` already maps `sms` / `text` onto comms cards |
| Archive Health | `staged_sms` probes `sms/`; ingested SMS still **unavailable** / “CSV staged — ingest deferred in P1” |
| I4 | Full SMS engine deferred to I7; display/link OK |

---

## 7. Build plan (implemented this revision)

1. Header-driven parser (`memorybox/ingest/sms_parse.py`) — aliases + full `source_metadata`.  
2. Ingest (`ingest-sms`) — Source + communication Evidence; hash skip; originals untouched.  
3. Phone/handle → Person (`memorybox/person/phone_map.py`) — unique auto / ambiguous Review / unmapped retained.  
4. Ask retrieve / Person / date / keyword / outbound + bidirectional count / date order / scope disclosure.  
5. Explore mapper: dated `sms` cards on existing Email/Text filter (no SMS app).  
6. Archive Health: staged vs ingested vs unavailable (unavailable ≠ 0).  
7. Fixture harness `prove-p2-i7` + FlightSim owner §8 gate.  
8. FlightSim: `inspect-sms` the real 1085-session CSV; do not commit bodies.

---

## 8. ACCEPTED gate (FlightSim, after build is authorized)

Pass **all**. Structural `prove-p2-i7` does **not** equal ACCEPTED.

1. Real staged export is ingested **without modifying originals**.  
2. At least one imported **real** message is fidelity-checked against the source export: displayed/normalized **text, timestamp, direction, participants, thread/conversation association** match the source.  
3. “Show me all my text messages with **[known Person from Q2]**” returns **real dated messages**.  
4. Person filtering works.  
5. Year / date-window filtering works.  
6. Keyword filtering works.  
7. Bidirectional Person count matches the ingested corpus and **states scope**.  
8. Owner outbound count matches the ingested corpus and **states scope**.  
9. Unique phone/handle identity maps to canonical MB Person correctly.  
10. Ambiguous / unmapped identities remain visible / reviewable and are **not silently merged**.  
11. Group-thread structure is preserved when present in the source.  
12. Attachments remain linked / provenance-preserved and are **not** silently promoted to Immich or standalone Explore media.  
13. Rich source metadata useful for later correlation is preserved (§2.C).  
14. At least one message demonstrates preserved metadata sufficient for later Place / Event / Trip correlation (§2.D). I7 does **not** infer Alaska (or any trip) to pass.  
15. SMS appears as communication evidence in Ask / Explore / Person **without a new SMS app**. Default Gallery **hides Text** on broad Person/Event/Trip/ordinary memory asks; **Add texts** / **Only texts** / explicit text asks override. Hidden cards are not evidence exclusion.  
16. Dated SMS participates in the existing Timeline / Explore model **when visible** (explicit text ask, Add texts, Only texts, or Email/Text filter).  
17. Archive Health reports staged / ingested / unavailable honestly.  
18. Missing years, missing participants, unavailable source, or unsupported coverage **never** become false zero / completeness.  
19. Short SMS summaries, if tested, are evidence-backed and underlying messages are reachable.  
20. **No I8 richer-email work** is pulled into I7.  
21. **No I10/I11 trip/year multi-source narrative** is pulled into I7.  
22. **No I4 Explore redesign** is pulled into I7.  
23. Existing accepted behavior from prior increments remains green (I1–I6 prove / owner surfaces).  
24. Structural prove/harness passes, but **manual FlightSim owner acceptance remains required**.

---

## 9. Authorization stop-line

| Step | Status |
|------|--------|
| I1–I6 ACCEPTED | **Yes** |
| Q3 group threads | **LOCKED** (preserve when present; no Core 4 object) |
| Q4 MMS / attachments | **LOCKED** (linked; no Immich/Explore auto-promote) |
| Q5 Person mapping | **LOCKED** (unique auto-map / ambiguous Review / unmapped retained) |
| Q6 summaries | **LOCKED** (retrieve/count/filter hard; cited extract OK; narrative later) |
| Q1 file-open (headers, siblings, dates, people, keywords, location columns) | **OPENED** 2026-08-14 via `inspect-sms` — §1.1. No GPS columns. 91,798 rows. |
| Q2 named fixtures | **RULES LOCKED**; harness uses in-repo Peggy/Denny/2020/3D-printing fixture; remap if real export differs |
| Build | **AUTHORIZED** 2026-08-14 (Tom) |
| Implementation | **THIS REVISION** (`ingest-sms`, `inspect-sms`, `prove-p2-i7`) |
| FlightSim ingest | **DONE** 2026-08-14 — job `7f763b4e-7ef0-40b5-804b-07ca10e18c34`; inserted **90,784**; skipped **1,014** duplicate hashes; processed **91,798** (= inspect row_count); `original_untouched: true` |
| Owner notes 2026-08-14 | §8 items **1–8 pass**. Item **10 understood**. Item **9 still the remaining gate** (confirmed phone must show on People). Year / Peggy / FL selection works. Follow-up: Explore theme still mixed (shell `--mb-ink` overrode filters); All emptied texts; attachments listed but not viewable. |
| FlightSim bugs this revision | Silent **5000 oldest-first** cap hid 2020–2025 and froze the header at 5000; mixed light/dark wiped SMS text; Ask→Explore/People dropped context; Email/Text filter stayed on All; hover did not expand text; no attachment indicator. |
| ACCEPTED | **Yes** (2026-08-15 — Tom: “i7 is accepted”) |
| Attachment bytes | **BACKLOG P2-BL-I7-01** (CSV-only export; do not reopen I7) |
| Next | [P2-I7A](MBBS-P2_INCREMENT_7A_DEFINITION.md) **ACCEPTED** 2026-08-15; [MBQL-001](MBBS-P2_INCREMENT_MBQL_001_DEFINITION.md) **BUILD AUTHORIZED** 2026-08-15 |

`prove-p2-i7` is structural + fixture assist only. It is **not** P1 `prove-video`.

## 10. FlightSim deploy (this branch)

`C:\memorybox` often tracks another increment (e.g. settings-thin). A plain `git pull` on that branch will **not** install `prove-p2-i7` / `ingest-sms` / `inspect-sms`. Check out this branch:

```powershell
cd C:\memorybox
git fetch origin
git checkout cursor/p2-i7-sms-definition-3061
git pull origin cursor/p2-i7-sms-definition-3061
python -m memorybox prove-p2-i7
# Backfill People confirmed phones from the already-ingested unique auto-maps:
python -m memorybox repair-sms-identities
# do NOT re-run ingest-sms unless you want an idempotent skip of the same file
# restart python -m memorybox serve, then Ctrl+F5
```

Real export ingest on FlightSim **succeeded** 2026-08-14 (90,784 inserted / 1,014 hash-skips / original untouched).

After this revision: Explore tokens are locked so shell `--mb-ink` cannot wipe filter labels. **All** keeps texts already in the result and can join Person photos. Open a text to **see** the attachment; **Add to MemoryBox library** copies it into Artifact storage (no Immich write). Ask fields keep the last **100** asks in `localStorage` (survives shutdown); Up/Down cycles them.

Confirm the CLI lists `prove-p2-i7`, `ingest-sms`, `inspect-sms`, and `repair-sms-identities` before treating the tree as I7.
