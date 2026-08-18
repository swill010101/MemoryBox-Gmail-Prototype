# MBBS-P2 Increment 8A — Unified Communications Gallery & Timeline Precision

**Status:** **BUILD AUTHORIZED** 2026-08-18 (founder: “approved…. build it.”) · Q1–Q6 **LOCKED** · visual baseline **ACCEPTED** · conflict resolution **LOCKED**  
**Date:** 2026-08-18 (written) · 2026-08-18 (founder revise) · 2026-08-18 (visual verification + conflict locks — this document)  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) — after **P2-I8 ACCEPTED**, **before P2-I9**. Face Evidence Ownership / Immich decoupling is **later**, not next after I8A.  
**Thin PRD:** [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md)  
**Visual baseline (approved):** [`docs/source/mockups/i8A/`](../source/mockups/i8A/) commit `3d46a86` and this document’s screen-authority rule. Product implementation **must not** reproduce **DRAFT · NOT YET FOR CURSOR**.  
**Authority:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-COM-01 / P2-COM-02 / P2-COM-03** · [MBUX-001 v0.4](MBUX-001_v0.4.md) **§22** (mixed-media Gallery, unified Timeline, shared viewer, Back restores context) · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) **CAP-P2-018 / CAP-P2-019** · I4 Mixed-Media Explore **ACCEPTED** · I7 SMS **ACCEPTED** · I8 Richer Email **ACCEPTED** 2026-08-18 · **this founder visual/conflict lock**  
**Depends:** P2-I8 **ACCEPTED** (2026-08-18) · I7 **ACCEPTED** · I4 **ACCEPTED** · MBQL-001 **ACCEPTED** · existing ICS path (`ingest-calendar` / `calendar_event`)  
**Does not reopen / does not absorb:** I7/I8 evidence parsers as a product rewrite · **P2-BL-I7-01** SMS attachment bytes · live Gmail / sending mail · new Email / messaging / Calendar **app** · **I8.5** face-evidence (moved later) · **I9** spoken product · **I10** correlation · **I11** narrative **generation** · I13/I14 Settings · multi-user · **P2-BL-I4-01** general Explore chrome (I8A is combined-card / density-aware aggregation / filter / drill-down behavior, not mockup pixel polish)

**I8 follow-up in this increment:** **P2-BL-I8-02** — Ask email/SMS counts lock canonical Person (Peggy George) before retrieve. Behavioral, not a required persistent Person-lock screen. Does not reopen I8.

**Build rule:** Founder **authorized I8A build** 2026-08-18. Implement this definition. Do not start I9, I8.5, I10, or I11 as part of this increment.

---

## 0. Product intent

> **Email, SMS/Text, and Calendar already exist (or will be minimally ingested) as honest dated Evidence. I8A makes them livable on one shared Ask/Explore canvas: they stay off a broad Gallery until presentation is requested, then appear as density-aware grouped presentation — including a combined Communications & Calendar day card when mixed high-volume evidence is on — not a flood of unusable rows, not a mail/messaging/calendar product, and not a new Evidence object.**

I8 shipped archive understanding (mbox → Evidence, MIME files, RFC/vendor threads, identity ladder, Ask retrieve). I7 shipped SMS retrieve. I4 shipped Timeline/Gallery shared state for photos/video. FlightSim I8 owner pass (2026-08-18) accepted the evidence/Ask contract and parked high-volume comms UX, Person-lock, and viewer polish here.

I8A is **Gallery + density-aware aggregation for dated evidence**, plus Communications and Calendar **filters**, Attachments-only presentation, and the shared Email/SMS/Calendar **viewer stack**. It is not a mail client, not a messenger, not a Calendar redesign, and not I10/I11.

End-to-end (when built, **after** authorization):

1. Broad **Show me Peggy** does **not** flood the Gallery with Email/Text (or Calendar). Those types stay **eligible** for Ask counts, retrieve, correlation, and later synthesis.  
2. Explicit Ask sets the **initial** presentation (e.g. texts with Peggy → Text on). Later **explicit UI** (Memory chip, Communications filter, Calendar filter, Attachments only) changes presentation **without rewriting the Ask string**. Person, Timeline, and evidence eligibility stay.  
3. **Communications filter** = Email + Text only. **Calendar filter** = Calendar only. Mixed Gallery may have Communications **and** Calendar active together.  
4. When Email, SMS/Text, and/or Calendar occupy a **usable daily bucket** in the mixed Gallery, Explore may show **one combined day card** with per-type counts (E / T / C). Grouping is presentation only — **no new Evidence object**, **no reclassification**.  
5. Aggregation follows **Timeline precision and evidence density**. Sparse All-Time results may show daily cards; high-volume results must aggregate/sample and disclose **Showing N of M**.  
6. Drill-down: combined day card → **~500 ms** representative-group rollover → **Open Day** → Email / Text / Calendar **tabs** → channel list → selected detail → **Back** list → **Back/Close** exact Gallery + Timeline.  
7. Shared viewer: structured quoted turns; image-attachment presentation when bytes exist; participants as sender/recipient identity. **No Reply / Reply all / Forward.**  
8. **P2-BL-I8-02:** “How many times did I send an email to Peggy?” resolves **Peggy George** (or clarifies) **before** count + Gallery. No required dedicated lock screen when resolution is unique.  
9. Calendar stays `calendar_event`. If FlightSim has no ingested calendar Evidence, I8A includes **minimum** ingest of the staged ICS source (existing `ingest-calendar`). Originals untouched. No Calendar product.  
10. No invented thread membership. No auto-Immich. Explicit Artifact copy only.  
11. Screen 07 narrative **generation** is **not** I8A. Combined Communications & Calendar cards must remain **reusable later** as Supporting Evidence (I11).

---

## 0.1 Approved visual baseline — screen authority

| Asset | Authority |
|-------|-----------|
| `00_Contact_Sheet_12_Draft_Screens.png` | Approved **overview / contact sheet**. Calendar-filter frames that appear **only** here establish the **intended Calendar-filter concept** (Events / Attachments only / Events + attachments). They are **not** missing standalone assets and are **not** pixel-level implementation authority. |
| `01`–`09` named PNGs | Approved **individual original screens**. |
| `10_11 drill down.png` | Approved **drill-down extension** (Screen 10 list, Screen 11 detail). |
| Historical **DRAFT · NOT YET FOR CURSOR** badges on 01–09 | **Stale.** Founder approval of the committed set supersedes them. Do **not** ship those badges. |

Where prose and screens disagreed, **founder conflict resolution 2026-08-18** (this document §2.1) wins. One visual supersession: Screen 11 **Reply / Reply all / Forward** are **not** implementation targets.

---

## 1. Why now (sequence — LOCKED)

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15 |
| 2 | **P2-I8** Richer Email | **ACCEPTED** 2026-08-18 (FlightSim §9) |
| 3 | **P2-I8A** Unified Communications Gallery & Timeline Precision | **This increment** |
| 4 | **P2-I9** Spoken Moments | **Next after I8A** (not I8.5) |
| later | **P2-I8.5** Face Evidence Ownership & Immich decoupling | **Moved later.** After photo/video recognition, correction, merge/review, and relearning are operationally solid. Not the immediate next increment after I8A. |
| later | I10 / I11 | Correlate; narrate — **not I8A** (I8A only preserves combined-card reuse for later Supporting Evidence) |

Near-term: **I8 ACCEPTED → I8A → I9**.

---

## 2. Founder decisions (Q1–Q6) — LOCKED 2026-08-18

| # | Topic | Lock |
|---|--------|------|
| **Q1** | Sequence | **I8 ACCEPTED → I8A → I9.** Face-ownership / Immich decoupling is **later**, not next after I8A. |
| **Q2** | Gallery noise | **Do not delete or silently suppress Evidence.** Do **not** add an AI promo/newsletter classifier in I8A unless trustworthy **source metadata already exists**. High volume is solved by **combined day cards**, **density-aware aggregation**, **caps/sampling**, honest **Showing N of M**, Communications/Calendar filters, and **Attachments only** where stored evidence exists. Newsletter/promo sophistication = **P2-BL-I8A-01**. |
| **Q3** | Gallery default | In a **normal broad Memory Gallery: Email OFF visually, SMS/Text OFF visually, Calendar OFF visually** until presentation is requested. All remain first-class Evidence and remain eligible for retrieval, counts, correlation, and later synthesis. **Explicit Ask** sets **initial** presentation (e.g. “show me texts with Peggy” → Text on). A later **explicit UI command** (Memory chip, Communications filter, Calendar filter, Attachments only, Show everything) **may change presentation** without rewriting the Ask string. Person + Timeline + query context remain. **Gallery visibility must not restrict evidence eligibility.** |
| **Q4** | Threads | **Do not invent thread membership.** Preserve RFC/vendor relationships from I8 when valid. Quoted `On … wrote:` is **display of one message body**, not proof of membership. Thread/detail lives in the **drill-down** (§4.5). Incomplete membership **disclosed honestly**. |
| **Q5** | Calendar | **IN I8A as its own evidence/filter dimension** (`calendar_event`; **do not reclassify as communication**). **Communications filter = Email + Text only.** **Calendar filter = Calendar only** (concept from contact sheet 00: Events / Attachments only / Events + attachments, where attachment evidence exists). Mixed Gallery may have **both** filters active. Combined **day card may show E / T / C counts**. Click path is **not** “click Email count on the card → list”; see §4.5. **Before coding:** inspect FlightSim ICS/Calendar state. Reuse ingested `calendar_event` if present. If not ingested, I8A includes **minimum** ingest of the **existing staged ICS** via `ingest-calendar`. No new Calendar product or redesign. Preserve originals and provenance. |
| **Q6** | Build gate | **BUILD AUTHORIZED** 2026-08-18. Implement this definition. |

### Additional rules (LOCKED)

1. Do not reopen I7 or I8 parsers except as needed to **display** already-stored fields, or the **minimum** Calendar ingest in Q5.  
2. Combined cards are **presentation grouping only**. They do not create Evidence, People, Events, or Threads.  
3. Do not invent RFC thread membership. Quoted history ≠ thread reconstruction.  
4. Do not auto-Artifact / auto-Immich.  
5. Do not start I9 / I8.5 / I10 / I11 **generation** in this increment. Preserve combined-card reuse for later Supporting Evidence.  
6. **P2-BL-I4-01** (Explore chrome polish) stays parked. I8A may change **comms/calendar combined-card, filters, aggregation, and drill-down** behavior on the I4 canvas.  
7. **P2-BL-I7-01** (SMS attachment bytes) stays its own item. I8A **Attachments only** operates on **stored** bytes; missing bytes **disclosed**.  
8. **P2-BL-I8-02** is **in I8A**. Ambiguous first-name Ask is lock-or-clarify, not a silent union of every matching display name. Unique canonical Person may lock **without** a special persistent lock screen.  
9. Any model-assisted person disambiguation uses **I7A traces**. Deterministic Person lock first (MBQL + existing People index).  
10. **One shared exploration state** (I4 / MBUX §22.3 / MBQL-001): Ask **establishes or mutates** Explore state. Gallery, Timeline, filters, combined cards, and drill-down are **the same** experience — not a separate Ask-results app and Explore app.  
11. Do **not** implement Reply / Reply all / Forward. I8A does not send mail. Attachment open/download is evidence access. **More** only if it contains real MemoryBox actions.

### 2.1 Visual-conflict resolution — LOCKED 2026-08-18

| # | Conflict | Lock |
|---|---------|------|
| 1 | Screen 07 narrative | **Park the capability, keep the visual pattern.** I8A does **not** generate I11 narrative. Combined Communications & Calendar card must be **reusable later** in a Supporting Evidence area. |
| 2 | Screen 06 Memory vs explicit SMS Ask | **Accept.** Explicit SMS Ask initially shows Text. Subsequent **Memory** is a new presentation command. Peggy + All Time remain. Communications stay eligible but disappear visually. Ask string need not rewrite. |
| 3 | Calendar chip/filter | **Include.** Calendar is its own evidence/filter dimension. Communications filter ≠ Calendar. Both may be active; combined day card may include E/T/C. Contact sheet 00 Calendar-filter frames define **concept**. Minimum existing ICS ingest if FlightSim has no `calendar_event`. |
| 4 | All-Time SMS daily cards vs coarse buckets | **Accept screen behavior.** Do **not** mechanically equate Timeline scale with bucket size. Aggregation = Timeline precision **and** evidence density. 22 active SMS days across 20 years may be 22 daily cards. 5,000 active days must aggregate/sample. Disclose **Showing N of M**. |
| 5 | Hover then Open Day then tabs | **Screen wins.** Combined card → ~500 ms representative-group rollover → Open Day → Email/Text/Calendar tabs → list → detail. **Not** click Email count directly → list. |
| 6 | Attachments only | **Include** as first-class presentation/filter for Communications (Messages vs Attachments only) and Calendar where stored attachment evidence exists. Do **not** pull **P2-BL-I7-01** into I8A. |
| 7 | Grouping | **Lock from screens.** Explicit comms presentation: Email → **thread**; Text → **day then conversation**; Calendar → **event**. Mixed Gallery: high-volume E/T/C may aggregate into a combined **day** card when daily presentation is usable. Thread membership remains I8 evidence-backed. |
| 8 | Ask/Results vs Explore | **Not two products.** Ask mutates shared Explore state. One underlying state model. |
| 9 | Screen 11 mail actions | **Supersede.** Do **not** implement Reply / Reply all / Forward (including as dead buttons). Preserve layout, participants, timestamps, quoted turns, attachments, modal stack, exact return. |
| 10 | Contact sheet 00 vs 01–11 | **Documented in §0.1.** No invented missing files. |
| 11 | DRAFT badges | **Stale.** Do not ship. |

---

## 3. EVS (retrieve/display, not narrative)

| EVS | Ask (short) | I8A bar |
|-----|-------------|--------|
| **EVS-047** | Peggy + Christmas in emails **and** texts | Person-lock; Communications presentation shows combined card / lists in the Christmas window. **No** joint story generation. |
| **EVS-107 / 108** | Counts by Person / sister | **P2-BL-I8-02** before count. Gallery visibility OFF does **not** zero the count. |
| **EVS-109** | Holiday-season email extract | Retrieve + cited extract; drill-down opens the message. |
| **EVS-002 / 184** | Christmas mixed media | Photos remain I4; Email/Text/Calendar join via filters + combined card when presentation is on. Not I11. |
| **EVS-070** | 2024 across mail, texts, pictures, video | **Not an I8A narrative gate.** Combined cards + density-aware aggregation must not pretend to be a year story. |

---

## 4. Scope IN

### 4.1 Shared viewer (still in)

- Shared Email/SMS communications viewer (channel disclosed); Calendar event detail in the same modal stack.  
- Structured quoted-turn display (`On … wrote:` = one body).  
- Image-attachment presentation / hover when stored bytes exist; open/download is evidence access.  
- Sender/recipient identity (participants). No `Re:` / `Fwd:` / subject-as-person.  
- Canonical Person resolution before communication **counts** (**P2-BL-I8-02**).  
- No invented threads; incomplete membership disclosed.  
- Honest caps/sampling (**Showing N of M**) inside lists and high-volume galleries.  
- No auto-Immich; explicit Artifact copy only.  
- **Do not** implement Reply / Reply all / Forward.

### 4.2 Combined high-volume day card (core)

When Email, SMS/Text, and/or Calendar items occupy a **usable daily bucket** in the **mixed** Gallery (Communications and/or Calendar presentation on), Explore **may** represent them as **one combined day card** rather than flooding the Gallery with individual records.

The card:

- shows **counts by evidence type** (Email · Text · Calendar as present), plus thread/conversation/event grouping labels as on screens 08–10;  
- is **presentation grouping only**;  
- **does not** create a new Evidence object;  
- **must** reflect the active query, Person, filters, and Timeline range.

Example (screens): **Dec 23, 2001 — Communications & calendar** with E / T / C counts and raw-record + meaningful-group summary.

Types with count 0 are omitted or shown disabled — do not invent rows.

The combined card is the object later I11 may place in **Supporting Evidence**. I8A does not write that narrative.

### 4.3 Density-aware aggregation (core)

Communications/calendar aggregation **adapts as temporal precision and evidence density change**.

Behavioral rule (**locked**; do not hard-code a single bucket table in this definition):

> **Aggregation follows both active Timeline precision and evidence density. Do not mechanically derive grouping granularity from Timeline scale alone.**

- Sparse results (e.g. 22 active SMS days across ~20 years All Time) **may** show **22 daily cards**. That is correct.  
- High-volume results (e.g. thousands of active days) **must** aggregate and/or sample until the Gallery stays usable, and must disclose **Showing N of M**.  
- Tightening the Timeline **must** change combined-card counts/results appropriately.  
- Explicit communication presentation grouping: Email by **thread**; Text by **day then conversation**; Calendar by **event**.  
- Mixed Gallery: high-volume E/T/C **may** roll into a combined **day** card when a daily presentation is usable.

### 4.4 One shared state (core)

Ask, Timeline, Gallery, filter chips/modals, combined-card counts, and drill-down results represent the **same** active query/time/Person/filter set.

**Ask establishes or modifies Explore state.** Do not build a second results canvas.

Opening and closing a card / modal **must not reset**:

- Person focus;  
- active query (Ask string may remain while presentation chips change — Screen 06);  
- evidence-type filters (Communications, Calendar, Memory, Attachments only, etc.);  
- Timeline range;  
- scroll / Gallery return context.

This is the I4 / MBUX §22 / MBQL-001 continuity rule applied to the combined-card stack.

### 4.5 Drill-down modal stack (core) — visual sequence authoritative

Prove:

1. Gallery combined **day** card  
2. **~500 ms** representative-group rollover (threads / conversations / events; not a flood of raw rows)  
3. **Open Day**  
4. Day modal: **Email | Text | Calendar** channel **tabs**  
5. Channel **list** (email threads / text conversations / calendar events)  
6. Selected **detail** modal **above** the list  
7. **Back** to list  
8. **Back / Close / Back to Day** to **exact** Gallery + Timeline context  

Do **not** implement “click Email count on the combined card → that list” as the primary path.

UX target: committed screens 08–11 + I4 Explore / MBUX §22 shared canvas. Do **not** reinterpret as a separate Email app, messaging app, or Calendar app.

Thread/detail for email is **inside this stack** (Q4). Calendar detail is the event, not a mail thread.

### 4.6 Communications filter and Calendar filter (core)

**Communications filter** (screens 02–05):

- Sources: **Email**, **Text** (independent checkboxes; counts shown).  
- Show: **Messages** (attachments stay with parent thread/conversation) **or** **Attachments only** (attachment content as first-class results when stored bytes exist).  
- Current context: Person + Timeline **unchanged** on Apply.

**Calendar filter** (concept from contact sheet 00; no extra PNG required unless implementation is ambiguous):

- Calendar **only** (not Email/Text).  
- Mode concept: **Events** / **Attachments only** / **Events + attachments**, **where attachment evidence actually exists**.  
- Missing bytes disclosed; do not invent attachments.

Memory chip (screen 06): presentation command that can hide Communications while leaving eligibility, Person, and Timeline intact.

### 4.7 Calendar ingest (minimum, Q5)

- Inspect FlightSim Calendar/ICS **before coding** (`inspect-calendar` / Archive Health staged vs ingested; `evidence_kind=calendar_event`). `prove-p2-i8a --flightsim` prints the same slice under `inspect` / check `i8a_calendar_inspect`.  
- If already ingested **at archive scale**: **reuse**. No parallel ingest.  
- If not ingested, **or inspect `coverage` is `smoke_or_partial`** (PG rows are a smoke `--limit`, not the Takeout ICS): **minimum** `ingest-calendar` on the staged Sources ICS **folder** (`P:\photos\memorybox\sources\calendar` or env). Parser already exists (`i3-calendar-1`). Originals untouched; existing hashes skip.  
- Real staged/ingested evidence only for ACCEPTED. **No synthetic test rows** as the owner gate.  
- Do not expand into a Calendar product.

### 4.8 After authorization only

`prove-p2-i8a` structural harness + FlightSim owner pass (§11).

---

## 5. Scope OUT

| Out | Home |
|-----|------|
| Re-ingest mbox / SMS CSV; change spam-trash skip rules | I8 / I7 (done) |
| SMS attachment **bytes** ingest | **P2-BL-I7-01** |
| Deleting or silently dropping Evidence (newsletters or otherwise) | Forbidden |
| New AI promo/newsletter classifier | **P2-BL-I8A-01** unless source metadata already exists |
| Live Gmail, send, IMAP | Never |
| Reply / Reply all / Forward (active or dead) | Forbidden in I8A |
| New Email / SMS / Calendar family-nav app | Never |
| Separate Ask-results implementation vs Explore | Forbidden — one shared state |
| Reclassify calendar as communication | Forbidden |
| Invented thread membership | Forbidden |
| Evidence-backed **narrative generation** (Screen 07 capability) | **I11** (visual pattern / combined-card reuse only in I8A) |
| “Alaska trip” correlation across mail + texts + photos | **I10** |
| Face evidence / Immich decoupling | **I8.5 later** |
| Spoken / STT product | **I9** (next after I8A, not inside I8A) |
| General Explore mockup pixel polish; shipping DRAFT badges | **P2-BL-I4-01** / stale art |
| Recreating contact-sheet Calendar-filter frames as standalone PNGs | Not required |
| I8A code / `prove-p2-i8a` before **final lock + build authorization** | Forbidden |

---

## 6. Constraints / edge cases

- Combined card ≠ Evidence. Counts are of **eligible items in the active bucket/state**, not a stored rollup table that can drift.  
- Q3 visual OFF ≠ retrieve OFF. Curator counts and Ask retrieve still see Email/SMS/Calendar.  
- **Quoted history ≠ thread.** RFC / `X-GM-THRID` from I8 when valid; incomplete disclosed.  
- HTML-only: disclose; do not invent plain text.  
- Missing attachment bytes: disclose. Attachments only must not pretend bytes exist.  
- Caps: **Showing N of M**. Unavailable ≠ 0.  
- People: I7/I8 identity ladder. Never merge on display name. Never treat subject as a Person.  
- **P2-BL-I8-02:** several People named Peggy → clarify or lock owner-preferred; do not substring-match every Peggy. Unique Peggy George may lock silently then count.  
- MBQL: no third planner. Add communications / Only email / Memory / Calendar / Attachments only / Show everything compile on MBQL-001 + I4 filter commands.  
- Calendar originals untouched; hash skip; no Immich dump of ICS.  
- I10/I11: a combined card is not correlation or narrative generation.

---

## 7. FlightSim leftovers I8A owns

| Leftover | I8A bar |
|----------|---------|
| Gallery flood (All Mail + photos) | Q3 default OFF + combined day cards + density-aware aggregation + filters |
| Email visible / SMS hidden mismatch | **Both OFF** visually until explicit Ask or filter (Q3); Memory can hide again (Screen 06) |
| Structured email vs quoted blob | Shared viewer; quoted turns in **detail** |
| Hover 📎 filename only | Hover / preview **image** when bytes exist |
| Subject in People rail | Participants only (sender/recipient) |
| **P2-BL-I8-02** first-name Peggy count | Resolve **Peggy George** (or clarify) before count + Gallery; no mandatory lock screen when unique |
| Calendar missing on canvas | Q5 Calendar filter + combined card + minimum ICS ingest if needed |
| Mail-client chrome | **Do not** ship Reply / Reply all / Forward |

---

## 8. Discovery (reuse — do not rebuild)

| Area | Finding |
|------|---------|
| Explore canvas | I4 `explore/find.py` + `explore.js` — Timeline/Gallery shared state **ACCEPTED**; Ask must **mutate this**, not fork it |
| Email attach today | `_attach_visible_email`; emails were **visible** on mixed Gallery in I8 — **I8A Q3 changes presentation default to OFF** |
| SMS hide today | `gallery_default_hidden` — keep eligibility; align visual default with Email (both OFF) until explicit presentation |
| Email viewer | `explore/email_attach.py` · `/explore/api/email/{id}` · quoted turns in `explore.js` — strip/omit send actions |
| Attachments | `/explore/api/email-attachment` · `/explore/api/sms-attachment` — Attachments only uses stored bytes only |
| Ask retrieve | `search_email_messages` / `search_sms_messages` in `ask/retrieve.py` |
| Calendar ingest | `ingest-calendar` · `ingest/comms_calendar.py` · `providers/calendar/ics.py` · `evidence_kind=calendar_event` · parser `i3-calendar-1` |
| Calendar Explore | `find.py` currently forces `want_calendar=False` on some attach paths — I8A must include calendar when **Calendar presentation** is on and in the combined card |
| Staged ICS | Sources `calendar/` under `P:\photos\memorybox\sources` (same root as email/SMS); Archive Health already distinguishes staged vs `calendar_event` counts |
| UX authority | MBUX-001 v0.4 §22.2–22.4; I4 Back/return; **committed I8A screens 00–11** + §0.1 / §2.1 |
| Harness | `prove-p2-i8` exists; **do not add `prove-p2-i8a` until build is authorized** |

**P2-BL-I8-02 root cause (do not fix until authorized):** `search_email_messages` keeps a message if `plan.person_ids` match **or** first-name tokens in `plan.person_names`. A “Peggy” Ask can include mail that is not **Peggy George**.

**Calendar inspect (do not skip at build time):** confirm FlightSim `calendar_event` count vs staged ICS **before** writing a second ingest path.

---

## 9. Surfaces (when built)

| Surface | I8A change |
|---------|------------|
| Ask | Mutates shared Explore state; Person resolution before counts; initial presentation from explicit Ask; chip/filter commands afterward |
| Curator | Honest counts and presentation-state copy (e.g. Screen 01 / 06). **No I11 narrative generation** |
| Explore Gallery | Combined day card; Q3 defaults; Memory / Communications / Calendar chips; Attachments only; drill-down stack |
| Communications filter | Email + Text; Messages vs Attachments only |
| Calendar filter | Calendar only; Events / Attachments modes where evidence exists (concept from 00) |
| Timeline | Same state as Gallery; density-aware aggregation (not scale-equals-bucket) |
| Person gallery | Same rules under Person focus |
| Email/SMS/Calendar detail | Shared stack; no send controls |
| Archive Health | Unchanged honesty; ingest job only if Q5 minimum ICS needed |
| Settings / family nav | None |

---

## 10. Honesty / trust

- Channel / type always visible (email vs sms/imessage/mms vs calendar).  
- Presentation grouping is labeled as grouping, not a new object.  
- Truncation / **Showing N of M** disclosed.  
- Quoted history ≠ RFC thread. Incomplete thread disclosed.  
- Missing attachment bytes disclosed.  
- Unavailable ≠ 0.  
- Visual OFF ≠ deleted and ≠ ineligible.  
- Ambiguous Person Ask discloses ambiguity; unique Person may lock without extra chrome.  
- Calendar in the card is real ingested events, not placeholders.  
- Combined card in a future Supporting Evidence area is still evidence grouping, not a generated story.

---

## 11. ACCEPTED gate (FlightSim) — after build only

Pass **all**. Harness ≠ ACCEPTED. Not runnable until build is authorized.

1. Broad **Show me Peggy** does **not** flood Gallery with Email/Text/Calendar.  
2. Explicit **texts with Peggy** Ask initially shows **Text** presentation (Screen 01 pattern).  
3. Subsequent **Memory** chip (Screen 06) hides Communications visually, **preserves** Person / Timeline / Ask context, and **does not** make Email/SMS ineligible.  
4. **Communications filter** can select Text only, Email only, Email+Text, Messages vs **Attachments only**, without resetting Person/Timeline.  
5. **Calendar filter** can be on independently of Communications; mixed Gallery may show **Memory + Communications + Calendar**.  
6. A **real** period containing Email + Text + Calendar with mixed presentation on shows a **combined day card** with **correct per-type counts**.  
7. Combined card **~500 ms** rollover shows representative groups (threads / conversations / events), then **Open Day**.  
8. Day modal has **Email / Text / Calendar tabs**. Email tab shows **thread** list. Text tab shows **day-then-conversation** list. Calendar tab shows **events**.  
9. Email **detail** opens **above** the list (quoted turns, participants, timestamps, attachments). **No** Reply / Reply all / Forward.  
10. **Back** returns detail → list → **exact** Gallery + Timeline. Close / Back to Day same Gallery return.  
11. Same stack works for **Text** conversation detail and **Calendar** event detail.  
12. Sparse All-Time SMS (on the order of tens of active days) **may** show **daily** cards; must **not** be forced into year buckets solely because Timeline spans years.  
13. High-volume results aggregate/sample until usable and disclose **Showing N of M**.  
14. Timeline narrowing changes communication/calendar results appropriately (finer or fewer groups as density/range change).  
15. Timeline, Gallery, combined-card counts, filters, and drill-down contents remain **synchronized** (one shared state mutated by Ask).  
16. Attachment hover/preview shows the **image** when stored bytes exist. Attachments only does not invent missing SMS bytes (**P2-BL-I7-01** still open).  
17. Identity chrome uses **participants only** (no subject-as-person).  
18. **P2-BL-I8-02:** “How many times did I send an email to Peggy?” resolves **Peggy George** when uniquely resolvable (or discloses ambiguous) **before** count + Gallery; extra non–Peggy-George mail is not included. Counts still work when Gallery presentation is OFF. No requirement for a persistent lock screen when unique.  
19. No invented thread membership.  
20. No Evidence is deleted or reclassified merely for presentation.  
21. Calendar evidence is **real staged/ingested** evidence, not synthetic test rows.  
22. Originals untouched; no Immich dump; Artifact still explicit.  
23. **No I9 / I10 / I11 generation.** Combined card remains usable later as Supporting Evidence. **No I8.5** face-SoT.  
24. Implemented UI does **not** show **DRAFT · NOT YET FOR CURSOR**.

---

## 12. Build (only after final lock + authorization)

Do **not** start I9 / I8.5 / I10 / I11 in this increment. I8A build is authorized.

1. FlightSim Calendar inspect: staged ICS vs `calendar_event`; minimum `ingest-calendar` only if needed.  
2. Q3 presentation defaults (Email OFF, SMS OFF, Calendar OFF) without changing eligibility.  
3. Ask mutates shared Explore state (no forked Ask-results app).  
4. Communications filter + Calendar filter + Memory presentation command + Attachments only (stored bytes).  
5. Combined day card + per-type counts bound to shared Timeline/query/Person/filter state.  
6. Density-aware aggregation (§4.3).  
7. Drill-down: rollover → Open Day → tabs → list → detail → Back ×2 (§4.5).  
8. Shared viewer: quoted turns, image attachments, participants; **omit** send controls.  
9. **P2-BL-I8-02** Person resolution before retrieve/count.  
10. `prove-p2-i8a` + FlightSim §11.  
11. **Stop.** Do not start I9, I11 narrative generation, or I8.5 in this increment.

---

## 13. Authorization stop-line

| Step | Status |
|------|--------|
| I8 Richer Email | **ACCEPTED** 2026-08-18 |
| I8A Q1–Q6 | **LOCKED** 2026-08-18 |
| I8A screens 00–11 | **ACCEPTED visual baseline** 2026-08-18 (`docs/source/mockups/i8A/`, `3d46a86`) |
| Visual-conflict resolution | **LOCKED** 2026-08-18 (this document §2.1) |
| I8A definition | **LOCKED** — this document — founder approved 2026-08-18 |
| I8A PRD | **LOCKED** — [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md) |
| P2-BL-I8-02 | **In I8A** (behavioral; not a required lock screen) |
| P2-BL-I8A-01 (promo classifier) | **Parked** |
| P2-BL-I7-01 (SMS attachment bytes) | **Not in I8A** — disclose missing bytes |
| I8A build | **AUTHORIZED** 2026-08-18 |
| I9 Spoken | **NOT STARTED** (next after I8A) |
| I8.5 Face ownership | **LATER** (not next after I8A) |
| I10 / I11 | **NOT STARTED** (I8A preserves combined-card reuse only) |

**Stop after I8A.** Do not start I9 / I8.5 / I10 / I11 in this increment.
