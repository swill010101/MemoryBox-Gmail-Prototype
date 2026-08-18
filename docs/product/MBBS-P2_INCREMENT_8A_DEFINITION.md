# MBBS-P2 Increment 8A — Unified Communications Gallery & Timeline Precision

**Status:** **REVISED for founder lock** · Q1–Q6 **LOCKED** (founder review 2026-08-18) · **not BUILD AUTHORIZED** · **no I8A runtime**  
**Date:** 2026-08-18 (written) · 2026-08-18 (founder revise — this document)  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) — after **P2-I8 ACCEPTED**, **before P2-I9**. Face Evidence Ownership / Immich decoupling is **later**, not next after I8A.  
**Thin PRD:** [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md)  
**Authority:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-COM-01 / P2-COM-02 / P2-COM-03** · [MBUX-001 v0.4](MBUX-001_v0.4.md) **§22** (mixed-media Gallery, unified Timeline, shared viewer, Back restores context) · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) **CAP-P2-018 / CAP-P2-019** · I4 Mixed-Media Explore **ACCEPTED** · I7 SMS **ACCEPTED** · I8 Richer Email **ACCEPTED** 2026-08-18  
**Depends:** P2-I8 **ACCEPTED** (2026-08-18) · I7 **ACCEPTED** · I4 **ACCEPTED** · MBQL-001 **ACCEPTED** · existing ICS path (`ingest-calendar` / `calendar_event`)  
**Does not reopen / does not absorb:** I7/I8 evidence parsers as a product rewrite · **P2-BL-I7-01** SMS attachment bytes · live Gmail / sending mail · new Email / messaging / Calendar **app** · **I8.5** face-evidence (moved later) · **I9** spoken product · **I10** correlation · **I11** narrative · I13/I14 Settings · multi-user · **P2-BL-I4-01** general Explore chrome (I8A is combined-card / Timeline-precision behavior, not mockup pixel polish)

**I8 follow-up in this increment:** **P2-BL-I8-02** — Ask email counts lock canonical Person (Peggy George) before retrieve. Does not reopen I8.

**Build rule:** This revision is for **final founder lock**. Do **not** implement I8A, add `prove-p2-i8a`, or change Ask/Explore/Timeline runtime until Tom reviews **this** document and then says **“I8A build is authorized.”** Do not start I9, I8.5, I10, or I11 as part of this increment.

---

## 0. Product intent

> **Email, SMS/Text, and Calendar already exist (or will be minimally ingested) as honest dated Evidence. I8A makes them livable on the I4 mixed-media canvas: they stay off a broad Gallery until asked for, then appear as one Timeline-aware combined presentation — not a flood of rows, not a separate mail/messaging/calendar product, and not a new Evidence object.**

I8 shipped archive understanding (mbox → Evidence, MIME files, RFC/vendor threads, identity ladder, Ask retrieve). I7 shipped SMS retrieve. I4 shipped Timeline/Gallery shared state for photos/video. FlightSim I8 owner pass (2026-08-18) accepted the evidence/Ask contract and parked high-volume comms UX, Person-lock, and viewer polish here.

I8A is **Gallery + Timeline precision for dense dated evidence**, plus the shared Email/SMS viewer already sketched. It is not a mail client, not a messenger, not a Calendar redesign, and not I10/I11.

End-to-end (when built, **after** authorization):

1. Broad **Show me Peggy** does **not** flood the Gallery with Email/Text (or Calendar). Those types stay **eligible** for Ask counts, retrieve, correlation, and later synthesis.  
2. Explicit intent (**Add communications** / Add email / Add texts / Only email / Only texts / Show everything, and calendar equivalents when asked) adds presentation to the **current** Person / query / Timeline context.  
3. When Email, SMS/Text, and/or Calendar occupy the **current temporal bucket**, Explore may show **one combined presentation card** with per-type counts (e.g. `March 14, 2024` · Email 7 · Text 19 · Calendar 2). Grouping is presentation only — **no new Evidence object**, **no reclassification**.  
4. As Timeline precision tightens, that aggregation **reveals finer groups/items** instead of staying one giant aggregate or flooding the Gallery.  
5. Drill-down: combined card → channel list modal (Email / Text / Calendar) → item / conversation / thread / event detail → **Back** list → **Back** exact Gallery/Timeline context.  
6. Shared Email/SMS viewer: structured quoted turns; hover matches zoom; image-attachment hover when bytes exist; People rail = participants only.  
7. **P2-BL-I8-02:** “How many times did I send an email to Peggy?” locks **Peggy George** (or clarifies) **before** count + Gallery.  
8. Calendar stays `calendar_event`. If FlightSim has no ingested calendar Evidence, I8A includes **minimum** ingest of the staged ICS source (existing `ingest-calendar`). Originals untouched. No Calendar product.  
9. No invented thread membership. No auto-Immich. Explicit Artifact copy only.

---

## 1. Why now (sequence — LOCKED)

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15 |
| 2 | **P2-I8** Richer Email | **ACCEPTED** 2026-08-18 (FlightSim §9) |
| 3 | **P2-I8A** Unified Communications Gallery & Timeline Precision | **This increment** |
| 4 | **P2-I9** Spoken Moments | **Next after I8A** (not I8.5) |
| later | **P2-I8.5** Face Evidence Ownership & Immich decoupling | **Moved later.** After photo/video recognition, correction, merge/review, and relearning are operationally solid. Not the immediate next increment after I8A. |
| later | I10 / I11 | Correlate; narrate — **not I8A** |

Near-term: **I8 ACCEPTED → I8A → I9**.

---

## 2. Founder decisions (Q1–Q6) — LOCKED 2026-08-18

| # | Topic | Lock |
|---|--------|------|
| **Q1** | Sequence | **I8 ACCEPTED → I8A → I9.** Face-ownership / Immich decoupling is **later**, not next after I8A. |
| **Q2** | Gallery noise | **Do not delete or silently suppress Evidence.** Do **not** add an AI promo/newsletter classifier in I8A unless trustworthy **source metadata already exists**. High volume is solved by **combined time-bucket cards**, **timeline-aware aggregation**, **caps/sampling inside drill-downs**, honest **Showing N of M**, and optional **existing** metadata filters where reliable. Newsletter/promo sophistication = **P2-BL-I8A-01**. |
| **Q3** | Gallery default | In a **normal broad Memory Gallery: Email OFF visually, SMS/Text OFF visually.** Both remain first-class Evidence and remain eligible for retrieval, counts, correlation, and later synthesis. Explicit intent overrides: **Add communications**, **Add email**, **Add texts**, **Only email**, **Only texts**, **Show everything**. **Gallery visibility must not restrict evidence eligibility.** Calendar follows the same **presentation** rule for the combined card (OFF on a broad photo Gallery until communications/calendar presentation is requested). |
| **Q4** | Threads | **Do not invent thread membership.** Preserve RFC/vendor relationships from I8 when valid. Quoted `On … wrote:` is **display of one message body**, not proof of membership. Thread/detail lives in the **drill-down**: combined card → channel list → selected message/conversation/thread detail. Incomplete membership **disclosed honestly**. |
| **Q5** | Calendar | **IN the combined time-bucket card.** Calendar remains its own evidence type (`calendar_event`); **do not reclassify as communication.** Example counts: Email 7 · Text 19 · Calendar 2. Click Email / Text / Calendar → that channel’s **list modal**; select item → **detail modal**; Back = detail → list → exact Gallery/Timeline context. **Before coding:** inspect FlightSim ICS/Calendar state. Reuse ingested `calendar_event` if present. If not ingested, I8A includes **minimum** ingest of the **existing staged ICS** via `ingest-calendar`. No new Calendar product or redesign. Preserve originals and provenance. |
| **Q6** | Build gate | **This revision is for final founder lock. No runtime yet.** After Tom accepts **this** definition, explicit **“I8A build is authorized”** starts implementation. |

### Additional rules (LOCKED)

1. Do not reopen I7 or I8 parsers except as needed to **display** already-stored fields, or the **minimum** Calendar ingest in Q5.  
2. Combined cards are **presentation grouping only**. They do not create Evidence, People, Events, or Threads.  
3. Do not invent RFC thread membership. Quoted history ≠ thread reconstruction.  
4. Do not auto-Artifact / auto-Immich.  
5. Do not start I9 / I8.5 / I10 / I11 in this increment.  
6. **P2-BL-I4-01** (Explore chrome polish) stays parked. I8A may change **comms/calendar combined-card and drill-down** behavior on the I4 canvas.  
7. **P2-BL-I7-01** (SMS attachment bytes) stays its own item; I8A may **display** bytes when present.  
8. **P2-BL-I8-02** is **in I8A**. Ambiguous first-name Ask is lock-or-clarify, not a silent union of every matching display name.  
9. Any model-assisted person disambiguation uses **I7A traces**. Deterministic Person lock first (MBQL + existing People index).  
10. One shared exploration state (I4 / MBUX §22.3): Timeline, Gallery, combined-card counts, filters, and drill-down results are the **same** active query/time/Person/filter set.

---

## 3. EVS (retrieve/display, not narrative)

| EVS | Ask (short) | I8A bar |
|-----|-------------|--------|
| **EVS-047** | Peggy + Christmas in emails **and** texts | Person-lock; Add communications (or equivalent) shows combined card / lists in the Christmas window. **No** joint story. |
| **EVS-107 / 108** | Counts by Person / sister | **P2-BL-I8-02** before count. Gallery visibility OFF does **not** zero the count. |
| **EVS-109** | Holiday-season email extract | Retrieve + cited extract; drill-down opens the message. |
| **EVS-002 / 184** | Christmas mixed media | Photos remain I4; Email/Text/Calendar join via combined card when presentation is on. Not I11. |
| **EVS-070** | 2024 across mail, texts, pictures, video | **Not an I8A narrative gate.** Combined cards + Timeline precision must not pretend to be a year story. |

---

## 4. Scope IN

### 4.1 Shared viewer (still in)

- Shared Email/SMS communications viewer (channel disclosed).  
- Structured quoted-turn display (`On … wrote:` = one body).  
- Hover preview derived from the viewer; image-attachment hover when stored bytes exist.  
- Participant-only People rail (no `Re:` / `Fwd:` / subject-as-person).  
- Canonical Person lock before communication **counts** (**P2-BL-I8-02**).  
- No invented threads; incomplete membership disclosed.  
- Honest caps/sampling (**Showing N of M**) inside drill-downs.  
- No auto-Immich; explicit Artifact copy only.

### 4.2 Combined high-volume evidence card (core)

When multiple Email, SMS/Text, and/or Calendar items occupy the **current temporal bucket**, Explore **may** represent them as **one combined presentation card** rather than flooding the Gallery with individual records.

The card:

- shows **counts by evidence type** (Email · Text · Calendar as present);  
- is **presentation grouping only**;  
- does **not** create a new Evidence object;  
- **must** reflect the active query, Person, filters, and Timeline range.

Example (founder):

`March 14, 2024` — Email 7 · Text 19 · Calendar 2

Clicking a type opens that channel’s **list modal**. Selecting a row opens **detail**. Types with count 0 are omitted or shown disabled — do not invent rows.

### 4.3 Timeline precision (core)

Communications/calendar aggregation **adapts as temporal precision changes**.

Behavioral rule (**locked**; do not hard-code an arbitrary bucket algorithm in this definition):

> **As the active Timeline becomes more precise, high-volume evidence progressively reveals finer-grained groups/items rather than remaining one giant aggregate or flooding the Gallery.**

Conceptually:

- broad multi-year view → coarse aggregation;  
- year/month view → finer aggregation;  
- day-level view → finer-grained evidence;  
- sufficiently narrow ranges may expose individual items when usable.

Narrowing the Timeline **must** change combined-card counts/results appropriately.

### 4.4 One shared state (core)

Timeline, Gallery, combined-card counts, filters, and drill-down results represent the **same** active query/time state.

Opening and closing a card / modal **must not reset**:

- Person focus;  
- active query;  
- evidence-type filters (including Q3 presentation overrides);  
- Timeline range;  
- scroll / Gallery return context.

This is the I4 / MBUX §22 continuity rule applied to the combined-card stack.

### 4.5 Drill-down modal stack (core)

Prove:

1. Gallery combined card  
2. Select Email / Text / Calendar  
3. Channel **list** modal  
4. Item / detail / thread / event modal  
5. **Back** to list  
6. **Back** to **exact** Gallery context  

UX target: the **previously developed screen set** (MBUX §22 shared viewer + I4 Explore). Do **not** reinterpret as a separate Email app, messaging app, or Calendar app.

Thread/detail for email is **inside this stack** (Q4). Calendar detail is the event, not a mail thread.

### 4.6 Calendar ingest (minimum, Q5)

- Inspect FlightSim Calendar/ICS **before coding** (`inspect` / Archive Health staged vs ingested; `evidence_kind=calendar_event`).  
- If already ingested: **reuse**. No parallel ingest.  
- If not ingested: **minimum** `ingest-calendar` on the staged Sources ICS tree (`P:\photos\memorybox\sources\calendar` or env). Parser already exists (`i3-calendar-1`).  
- Real staged/ingested evidence only for ACCEPTED. **No synthetic test rows** as the owner gate.  
- Do not expand into a Calendar product.

### 4.7 After authorization only

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
| New Email / SMS / Calendar family-nav app | Never |
| Reclassify calendar as communication | Forbidden |
| Invented thread membership | Forbidden |
| Joint email+SMS **narrative** | **I11** |
| “Alaska trip” correlation across mail + texts + photos | **I10** |
| Face evidence / Immich decoupling | **I8.5 later** (after recognition/correction/merge/relearn are solid) |
| Spoken / STT product | **I9** (next after I8A, not inside I8A) |
| General Explore mockup pixel polish | **P2-BL-I4-01** |
| I8A code / `prove-p2-i8a` before **final lock + build authorization** | Forbidden |

---

## 6. Constraints / edge cases

- Combined card ≠ Evidence. Counts are of **eligible items in the active bucket/state**, not a stored rollup table that can drift.  
- Q3 visual OFF ≠ retrieve OFF. Curator counts and Ask retrieve still see Email/SMS/Calendar.  
- **Quoted history ≠ thread.** RFC / `X-GM-THRID` from I8 when valid; incomplete disclosed.  
- HTML-only: disclose; do not invent plain text.  
- Missing attachment bytes: disclose.  
- Caps inside list modals: **Showing N of M**. Unavailable ≠ 0.  
- People: I7/I8 identity ladder. Never merge on display name. Never treat subject as a Person.  
- **P2-BL-I8-02:** several People named Peggy → clarify or lock owner-preferred; do not substring-match every Peggy.  
- MBQL: no third planner. Add communications / Only email / Show everything compile on MBQL-001 + I4 filter commands.  
- Calendar originals untouched; hash skip; no Immich dump of ICS.  
- I10/I11: a combined card is not correlation or narrative.

---

## 7. FlightSim leftovers I8A owns

| Leftover | I8A bar |
|----------|---------|
| Gallery flood (All Mail + photos) | Q3 default OFF + combined cards + Timeline precision |
| Email visible / SMS hidden mismatch | **Both OFF** visually until explicit intent (Q3) |
| Structured email vs quoted blob | Shared viewer; quoted turns in **detail** |
| Hover 📎 filename only | Hover **image** when bytes exist |
| Subject in People rail | Participants only |
| **P2-BL-I8-02** first-name Peggy count | Lock **Peggy George** (or clarify) before count + Gallery |
| Calendar missing on canvas | Q5 combined card + minimum ICS ingest if needed |

---

## 8. Discovery (reuse — do not rebuild)

| Area | Finding |
|------|---------|
| Explore canvas | I4 `explore/find.py` + `explore.js` — Timeline/Gallery shared state **ACCEPTED** |
| Email attach today | `_attach_visible_email`; emails were **visible** on mixed Gallery in I8 — **I8A Q3 changes presentation default to OFF** |
| SMS hide today | `gallery_default_hidden` — keep eligibility; align visual default with Email (both OFF) |
| Email viewer | `explore/email_attach.py` · `/explore/api/email/{id}` · quoted turns in `explore.js` |
| Attachments | `/explore/api/email-attachment` · `/explore/api/sms-attachment` |
| Ask retrieve | `search_email_messages` / `search_sms_messages` in `ask/retrieve.py` |
| Calendar ingest | `ingest-calendar` · `ingest/comms_calendar.py` · `providers/calendar/ics.py` · `evidence_kind=calendar_event` · parser `i3-calendar-1` |
| Calendar Explore | `find.py` currently forces `want_calendar=False` on some attach paths — I8A must include calendar in the **combined card** when presentation is on |
| Staged ICS | Sources `calendar/` under `P:\photos\memorybox\sources` (same root as email/SMS); Archive Health already distinguishes staged vs `calendar_event` counts |
| UX authority | MBUX-001 v0.4 §22.2–22.4; I4 Back/return; previously developed screen set |
| Harness | `prove-p2-i8` exists; **do not add `prove-p2-i8a` until build is authorized** |

**P2-BL-I8-02 root cause (do not fix until authorized):** `search_email_messages` keeps a message if `plan.person_ids` match **or** first-name tokens in `plan.person_names`. A “Peggy” Ask can include mail that is not **Peggy George**.

**Calendar inspect (do not skip at build time):** confirm FlightSim `calendar_event` count vs staged ICS **before** writing a second ingest path.

---

## 9. Surfaces (when built)

| Surface | I8A change |
|---------|------------|
| Ask / Curator | Person lock before counts; commands Add communications / Add email / Add texts / Only * / Show everything; counts **not** gated by Gallery visibility |
| Explore Gallery | Combined time-bucket card; Q3 visual defaults; drill-down stack |
| Timeline | Precision drives aggregation fineness; same state as Gallery |
| Person gallery | Same combined-card rules under Person focus |
| Email/SMS detail | Shared viewer inside the modal stack |
| Calendar detail | Event list + event modal; still `calendar_event` |
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
- Ambiguous Person Ask discloses ambiguity.  
- Calendar in the card is real ingested events, not placeholders.

---

## 11. ACCEPTED gate (FlightSim) — after build only

Pass **all**. Harness ≠ ACCEPTED. Not runnable until build is authorized.

1. Broad **Show me Peggy** does **not** flood Gallery with Email/Text.  
2. **Add communications** adds communication (and calendar, when in-range) **presentation** to the **current** context without resetting Person / query / Timeline / scroll.  
3. A **real** period containing Email + Text + Calendar shows a **combined card** with **correct per-type counts**.  
4. Email channel opens its **list** modal.  
5. Email detail/thread opens **above** the list.  
6. **Back** returns detail → list → **exact** Gallery state.  
7. Same flow works for **Text**.  
8. Same flow works for **Calendar**.  
9. Timeline **narrowing** changes communication/calendar aggregation appropriately (finer groups/items; not one frozen aggregate; not a flood).  
10. Timeline, Gallery, combined-card counts, and drill-down contents remain **synchronized**.  
11. Attachment hover shows the **image** when stored bytes exist.  
12. People rail uses **participants only**.  
13. **P2-BL-I8-02:** “How many times did I send an email to Peggy?” locks **Peggy George** (or discloses ambiguous) **before** count + Gallery; extra non–Peggy-George mail is not included. Counts still work when Gallery presentation is OFF.  
14. Sampling/capping discloses **Showing N of M**.  
15. No invented thread membership.  
16. No Evidence is deleted or reclassified merely for presentation.  
17. Calendar evidence is **real staged/ingested** evidence, not synthetic test rows.  
18. Originals untouched; no Immich dump; Artifact still explicit.  
19. **No I9 / I10 / I11** behavior is pulled into I8A. **No I8.5** face-SoT.

---

## 12. Build (only after final lock + authorization)

Do **not** start until Tom accepts **this revision** and says **“I8A build is authorized.”**

1. FlightSim Calendar inspect: staged ICS vs `calendar_event`; minimum `ingest-calendar` only if needed.  
2. Q3 presentation defaults (Email OFF, SMS OFF) without changing eligibility.  
3. Combined time-bucket card + per-type counts bound to shared Timeline/query/Person/filter state.  
4. Timeline-precision aggregation (behavioral rule in §4.3).  
5. Drill-down modal stack (list → detail → Back ×2).  
6. Shared Email/SMS viewer + image hover + participant People rail.  
7. **P2-BL-I8-02** Person lock before retrieve/count.  
8. `prove-p2-i8a` + FlightSim §11.  
9. **Stop.** Do not start I9 or I8.5 in this increment.

---

## 13. Authorization stop-line

| Step | Status |
|------|--------|
| I8 Richer Email | **ACCEPTED** 2026-08-18 |
| I8A Q1–Q6 | **LOCKED** 2026-08-18 (this founder review) |
| I8A definition | **REVISED** — this document — **awaiting final founder lock** |
| I8A PRD | **REVISED** — [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md) |
| P2-BL-I8-02 | **In I8A** |
| P2-BL-I8A-01 (promo classifier) | **Parked** |
| I8A build | **NOT AUTHORIZED** — no runtime until “I8A build is authorized” after this review |
| I9 Spoken | **NOT STARTED** (next after I8A) |
| I8.5 Face ownership | **LATER** (not next after I8A) |
| I10 / I11 | **NOT STARTED** |

**Stop.** Do not implement I8A until Tom **finally locks this revision** and authorizes build.
