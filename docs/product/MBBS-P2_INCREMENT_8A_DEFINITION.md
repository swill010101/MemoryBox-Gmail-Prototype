# MBBS-P2 Increment 8A — Unified Communications

**Status:** **Definition written** · Q1–Q6 **OPEN** (proposed defaults below) · **not BUILD AUTHORIZED** · **no I8A runtime**  
**Date:** 2026-08-18  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) — after **P2-I8 ACCEPTED**, **before P2-I8.5**  
**Thin PRD:** [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md)  
**Authority:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-COM-01 / P2-COM-02 / P2-COM-03** · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) **CAP-P2-018 / CAP-P2-019** (display/retrieve maturation, not new ingest) · I7 SMS **ACCEPTED** · I8 Richer Email **ACCEPTED** 2026-08-18  
**Depends:** P2-I8 **ACCEPTED** (2026-08-18) · I7 **ACCEPTED** · MBQL-001 **ACCEPTED** · I4 **ACCEPTED**  
**Does not reopen / does not absorb:** I7/I8 evidence ingest or parsers · **P2-BL-I7-01** SMS attachment bytes · live Gmail / sending mail · new family-nav app · **I8.5** face-evidence · **I9** spoken · **I10** correlation · **I11** narrative · I13/I14 Settings · multi-user · **P2-BL-I4-01** general Explore chrome (unless a comms-card defect)

**I8 follow-up in this increment (proposed):** **P2-BL-I8-02** — Ask email counts lock canonical Person (Peggy George) before retrieve. Does not reopen I8.

**Build rule:** This document is the increment definition. Do **not** implement I8A, add `prove-p2-i8a`, or change Ask/Explore runtime until Tom (1) locks Q1–Q6 and (2) says **“I8A build is authorized.”** Do not start I8.5, I9, I10, or I11 as part of this increment.

---

## 0. Product intent

> **Email and SMS already exist as honest communication Evidence. I8A makes them feel like one communications product on Ask / Explore / Person — shared viewer, hover, people rail, gallery density, and Person-locked counts — without changing ingest, inventing threads, or narrating across sources.**

I8 shipped archive understanding (mbox → Evidence, MIME files, RFC/vendor threads, identity ladder, Ask retrieve). I7 shipped SMS retrieve with a different Gallery default (texts hidden until Add texts). FlightSim I8 owner pass (2026-08-18) accepted the evidence/Ask contract and **parked aesthetic and unified-comms UX** here, plus **P2-BL-I8-02**.

I8A is **UX maturation on existing comms Evidence**, not a mail client, not a messenger, and not I10/I11.

End-to-end (when built, **after** authorization):

1. Opening an email or a text uses the **same structured communications viewer** (channel disclosed).  
2. Hover on a comms card shows that structured view; hover on an image attachment shows the **image**, not only the filename.  
3. People on a message come from **participants** (I7/I8 identity), never the subject line.  
4. Gallery/Email-Text density is usable on a ~90k email + ~90k SMS archive (caps, year-fair samples, honest “Showing N of M”). Newsletter/promo **noise** is handled per Q2 — not by deleting Evidence.  
5. SMS default-hide vs email default-visible is **one explicit rule** (Q3), not two accidental products.  
6. Quoted `On … wrote:` history stays **display of one MIME body**. RFC/vendor thread membership stays I8 honesty (no invented members).  
7. **P2-BL-I8-02:** Ask “how many times did I send an email to Peggy?” locks **Peggy George** (or discloses ambiguous) **before** count + Gallery.  
8. No new ingest; originals untouched; no Immich auto-promote; explicit Artifact copy only.

---

## 1. Why now (sequence lock)

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15 |
| 2 | **P2-I8** Richer Email | **ACCEPTED** 2026-08-18 (FlightSim §9) |
| 3 | **P2-I8A** Unified Communications | **This increment** — UX + Person-lock after both channels exist |
| 4 | **P2-I8.5** Face Evidence Ownership | **After I8A** unless Tom reorders in Q1 |
| 5+ | I9 / I10 / I11 | Speech; correlate; narrate — **not I8A** |

I8A sits **between I8 and I8.5** so family comms are livable before face-SoT. If Tom wants I8.5 next instead, Q1 must say so — I8A must not silently delay Face Evidence.

---

## 2. Decisions for Tom (Q1–Q6) — OPEN

Do not treat these as locked until Tom answers. If Tom says **“as drafted,”** use the Default column.

| # | Topic | Default if Tom says “as drafted” | Alternative |
|---|--------|----------------------------------|-------------|
| **Q1** | Sequence vs I8.5 | **I8 ACCEPTED → I8A → I8.5** | Skip or slim I8A; I8.5 next |
| **Q2** | Gallery noise (newsletters, promo) | **Disclose + density/caps** in I8A; do **not** delete mail. Optional later filter (labels / “primary” / owner-only) as **P2-BL-I8A-01** if not in this build | I8A includes a real promo/newsletter hide (Gmail labels / heuristics — must stay honest) |
| **Q3** | SMS vs email Gallery default | **Keep I7 hide-SMS / I8 show-email**, but one Email/Text filter and one viewer | One default for all comms (both visible, or both behind Add communications) |
| **Q4** | Thread presentation | **Quoted turns in the body** + optional list of **RFC/vendor siblings already in the result set**. Do not fetch-invent a Gmail app thread | Full thread pane that walks `X-GM-THRID` / RFC graph as a separate object |
| **Q5** | Calendar in this canvas | **Out.** Calendar stays calendar cards | Include ICS events in the same comms viewer (not recommended for I8A) |
| **Q6** | Build gate | Definition may be read now. **No I8A runtime** until Q1–Q6 locked **and** explicit “I8A build is authorized” | Authorize a **thin** slice only (viewer+hover+people rail+**P2-BL-I8-02**) and park density/noise |

### Additional rules (proposed; lock with Qs)

1. Do not reopen I7 or I8 parsers / ingest jobs except for display fields already stored.  
2. Do not invent RFC thread membership. Quoted history ≠ thread reconstruction.  
3. Do not auto-Artifact / auto-Immich.  
4. Do not start I8.5 / I9 / I10 / I11.  
5. **P2-BL-I4-01** (Explore chrome) stays parked unless a defect is comms-card-specific.  
6. **P2-BL-I7-01** (SMS attachment bytes) stays its own item; I8A may **display** bytes when present.  
7. **P2-BL-I8-02** is **in I8A** unless Tom parks it. Ambiguous first-name Ask is lock-or-clarify, not a silent union of every matching display name.  
8. Any model-assisted person disambiguation uses **I7A traces**. Deterministic Person lock first (MBQL + existing People index).

---

## 3. EVS (I8A is retrieve/display, not narrative)

| EVS | Ask (short) | I8A bar |
|-----|-------------|--------|
| **EVS-047** | Peggy + Christmas in emails **and** texts | Same Email/Text surface + shared viewer; **no** joint story. SMS still I7 evidence; email still I8 evidence. Person lock per **P2-BL-I8-02**. |
| **EVS-107 / 108** | Counts by Person / sister | **P2-BL-I8-02:** first-name “Peggy” must lock **Peggy George** (or disclose ambiguous) **before** count + Gallery. Viewer must open the cited message. Scope discloses which Person. |
| **EVS-109** | Holiday-season email extract | Unchanged retrieve; I8A makes the opened message readable (quoted turns). |
| **EVS-070** | 2024 across mail, texts, pictures, video | **Not an I8A gate.** Density/caps must not pretend the gallery is a year narrative (I11). |

---

## 4. Scope IN (proposed)

- Shared Explore / Person **communications viewer** (email + SMS/MMS/iMessage).  
- Hover: structured comms; image-attachment preview from stored bytes.  
- People rail: participants only (no `Re:` / `Fwd:` / subject-as-person).  
- Gallery density for mixed Show-me + Email/Text (caps, year-fair, scope text).  
- One Email/Text filter behavior documented under Q3.  
- Honest notes when HTML-only, incomplete thread, truncated sample, missing attachment bytes.  
- Thin CSS/layout for comms cards/viewer (**comms-specific** aesthetic; not a full Explore redesign).  
- **P2-BL-I8-02:** Ask email (and SMS, same rule) counts resolve **canonical Person first** (Peggy → Peggy George when unique / owner-preferred; otherwise clarify). Count + Gallery must not include other Peggys by first-name substring.  
- After authorization only: `prove-p2-i8a` structural harness + FlightSim owner pass.

## 5. Scope OUT

| Out | Home |
|-----|------|
| Re-ingest mbox / SMS CSV; change spam-trash skip rules | I8 / I7 (done) |
| SMS attachment **bytes** ingest | **P2-BL-I7-01** |
| Newsletter deletion or silent drop from Evidence | Forbidden; Q2 filter is display-only if in |
| Live Gmail, send, IMAP | Never |
| New Email family-nav app | Never |
| Joint email+SMS **narrative** | **I11** |
| “Alaska trip” correlation across mail + texts + photos | **I10** |
| Face evidence / Immich decoupling | **I8.5** |
| Spoken / STT | **I9** |
| Calendar-as-comms (unless Q5 yes) | I3 ICS / later |
| General Explore mockup pixel polish | **P2-BL-I4-01** |
| I8A code / `prove-p2-i8a` before build authorization | Forbidden |

---

## 6. Constraints / edge cases (proposed)

- **No new ingest.** I8A reads stored communication Evidence and existing attachment bytes.  
- **Quoted history ≠ thread.** `On … wrote:` splits are display of one MIME body. RFC / `X-GM-THRID` membership is I8 honesty only.  
- **HTML-only:** disclose; do not invent a plain-text body.  
- **Missing SMS attachment bytes:** disclose; do not fetch from Immich; **P2-BL-I7-01** remains the ingest home.  
- **Newsletter hide (if Q2):** view filter only; Evidence rows stay; Archive Health counts do not drop.  
- **Caps:** “Showing N of M” required when sampling ~90k mail or ~90k SMS. Unavailable ≠ 0.  
- **People:** I7/I8 identity ladder only. Never merge on display name. Never treat `Re:` / `Fwd:` / subject as a Person.  
- **P2-BL-I8-02:** If several People share “Peggy,” Ask must **clarify** or lock the owner-preferred Person. Do not substring-match every Peggy in From/To/Cc display names. Disclose scope (which Person, which addresses).  
- **MBQL:** I8A does not invent a third planner. Email/SMS Ask still compiles on MBQL-001.  
- **I10/I11:** opening mail next to a photo is not correlation or narrative.

---

## 7. FlightSim I8 leftovers that I8A owns

From I8 owner pass 2026-08-18 (Tom: I8 accepted; aesthetics + Person-lock → I8A):

| Leftover | I8A bar |
|----------|---------|
| Structured email vs quoted blob | Shared comms viewer; quoted turns readable |
| Hover 📎 shows filename | Hover shows **image** when bytes exist |
| Hover on email card | Same structured view as zoom (compact) |
| Gallery noise (All Mail + photos) | Density/caps + Q2 noise policy |
| Email/Text vs SMS hide mismatch | Q3 one rule |
| Subject in People rail | Participants only (partially fixed in I8; I8A verifies) |
| **P2-BL-I8-02** Ask first-name Peggy count | Lock **Peggy George** (or disclose ambiguous) before count + Gallery; no extra non–Peggy-George mail |

---

## 8. Discovery (reuse — do not rebuild)

| Area | Finding |
|------|---------|
| Email viewer | `memorybox/explore/email_attach.py` · `explore.js` quoted turns · `/explore/api/email/{id}` |
| SMS viewer | same Email/Text cards; `gallery_default_hidden` |
| Attachments | `/explore/api/email-attachment` · `/explore/api/sms-attachment` |
| Ask retrieve | `search_email_messages` / `search_sms_messages` in `memorybox/ask/retrieve.py` |
| Explore attach | `memorybox/explore/find.py` `_attach_visible_email` / hidden SMS caps |
| Identity ingest | I7 ladder `resolve_handles` (phone + email) — **already stored**; I8A must not re-ingest |
| MBQL | shared compile; I8A does not add a private comms language |
| Harness | `prove-p2-i8` exists; **`prove-p2-i8a` must not be added until build is authorized** |

**P2-BL-I8-02 root cause (do not fix until authorized):** `search_email_messages` keeps a message if `plan.person_ids` match **or** `_sms_name_match` on first-name tokens in `plan.person_names`. A first-name “Peggy” Ask can therefore include mail that is not **Peggy George**. Count + Gallery still “work.” I8A must lock canonical Person (or clarify) **before** that retrieve.

---

## 9. Surfaces (when built)

| Surface | I8A change |
|---------|------------|
| Ask / Curator | Person lock before email/SMS count; shared open-into-viewer; scope text |
| Explore Email/Text | Shared viewer, hover, density/caps, Q3 filter |
| Person gallery | Same viewer + Person-scoped comms; no subject-as-person |
| Archive Health | Unchanged counts; view filters do not delete Evidence |
| Settings / family nav | None |

---

## 10. Honesty / trust

- Channel always visible (email vs sms/imessage/mms).  
- Truncation disclosed.  
- Quoted history ≠ RFC thread.  
- Missing attachment bytes disclosed.  
- Unavailable ≠ 0.  
- Promo hide (if Q2) is a **view filter**, not deletion.  
- Ambiguous Person Ask discloses that it is ambiguous; it does not silently over-count.

---

## 11. ACCEPTED gate (FlightSim) — after build only

Pass **all**. Harness ≠ ACCEPTED. This gate is **not** runnable until build is authorized.

1. Open one **email** and one **SMS** in the same viewer pattern (channel disclosed).  
2. Hover image attachment shows the picture when bytes exist.  
3. Hover/zoom on email is structured turns, not one undifferentiated blob.  
4. People rail has no `Re:` subject-as-person.  
5. Show me **[Person]** + Email/Text is usable (not empty, not 90k unsorted cards).  
6. SMS hide rule matches Q3; Add texts (or successor) still works.  
7. Q2 noise policy visible and honest.  
8. No I8.5 / I9 / I10 / I11 in the I8A walk.  
9. Originals untouched; no Immich dump; Artifact still explicit.  
10. **P2-BL-I8-02:** “How many times did I send an email to Peggy?” locks **Peggy George** (or discloses ambiguous) **before** count + Gallery; extra non–Peggy-George mail is not included.

---

## 12. Build (only after authorization)

Do **not** start this list until Tom locks Q1–Q6 **and** authorizes build.

1. Lock Q1–Q6 in this table.  
2. Shared viewer component for email + SMS; fetch full body on open.  
3. Hover image + structured compact turns.  
4. People rail from parsed participants.  
5. Gallery density + Q3 filter semantics.  
6. **P2-BL-I8-02:** Ask person-lock before email/SMS count retrieve.  
7. `prove-p2-i8a` + FlightSim §11.  
8. **Stop.** Do not start I8.5 unless Q1 skipped I8A.

---

## 13. Authorization stop-line

| Step | Status |
|------|--------|
| I8 Richer Email | **ACCEPTED** 2026-08-18 |
| I8A definition | **WRITTEN** — this document; awaiting Tom lock |
| I8A PRD | **WRITTEN** — [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md) |
| Q1–Q6 | **OPEN** (proposed defaults in §2) |
| P2-BL-I8-02 (Ask Person lock) | **In I8A (proposed)** |
| I8A build | **NOT AUTHORIZED** — no runtime, no harness, no FlightSim I8A deploy |
| I8.5 / I9 / I10 / I11 | **NOT STARTED** |

**Stop.** Do not implement I8A until Tom locks Q1–Q6 and authorizes build. Do not start I8.5 in this increment.
