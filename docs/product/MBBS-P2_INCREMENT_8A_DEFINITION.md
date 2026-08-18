# MBBS-P2 Increment 8A — Unified Communications

**Status:** **DRAFT definition** · **not BUILD AUTHORIZED** · Q1–Q6 **OPEN** (Tom)  
**Date:** 2026-08-18  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) — after **P2-I8 ACCEPTED**, **before P2-I8.5**  
**Thin PRD:** [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md)  
**Authority:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-COM-01 / P2-COM-02 / P2-COM-03** · I7 SMS **ACCEPTED** · I8 Richer Email **ACCEPTED** 2026-08-18  
**Depends:** P2-I8 **ACCEPTED** (2026-08-18) · I7 **ACCEPTED** · MBQL-001 **ACCEPTED** · I4 **ACCEPTED**  
**Does not reopen / does not absorb:** I7/I8 evidence ingest or parsers · **P2-BL-I7-01** SMS attachment bytes · live Gmail / sending mail · new family-nav app · **I8.5** face-evidence · **I9** spoken · **I10** correlation · **I11** narrative · I13/I14 Settings · multi-user · **P2-BL-I4-01** general Explore chrome (unless a comms-card defect)

I8A is **definition only** until Tom locks Q1–Q6 and authorizes build. Do not start I8.5, I9, I10, or I11 as part of this increment.

---

## 0. Product intent

> **Email and SMS already exist as honest communication Evidence. I8A makes them feel like one communications product on Ask / Explore / Person — shared viewer, hover, people rail, and gallery density — without changing ingest, inventing threads, or narrating across sources.**

I8 shipped archive understanding (mbox → Evidence, MIME files, RFC/vendor threads, identity ladder, Ask retrieve). I7 shipped SMS retrieve with a different Gallery default (texts hidden until Add texts). FlightSim I8 owner pass (2026-08-18) accepted the evidence/Ask contract and **parked aesthetic and unified-comms UX** here.

I8A is **UX maturation on existing comms Evidence**, not a mail client, not a messenger, and not I10/I11.

End-to-end (when built, after authorization):

1. Opening an email or a text uses the **same structured communications viewer** (channel disclosed).  
2. Hover on a comms card shows that structured view; hover on an image attachment shows the **image**, not only the filename.  
3. People on a message come from **participants** (I7/I8 identity), never the subject line.  
4. Gallery/Email-Text density is usable on a ~90k email + ~90k SMS archive (caps, year-fair samples, honest “Showing N of M”). Newsletter/promo **noise** is handled per Q2 — not by deleting Evidence.  
5. SMS default-hide vs email default-visible is **one explicit rule** (Q3), not two accidental products.  
6. Quoted `On … wrote:` history stays **display of one MIME body**. RFC/vendor thread membership stays I8 honesty (no invented members).  
7. No new ingest; originals untouched; no Immich auto-promote; explicit Artifact copy only.

---

## 1. Why now (sequence lock)

| Order | Artifact | Role |
|-------|----------|------|
| 1 | **P2-I7** SMS/Text | **ACCEPTED** 2026-08-15 |
| 2 | **P2-I8** Richer Email | **ACCEPTED** 2026-08-18 (FlightSim §9) |
| 3 | **P2-I8A** Unified Communications | **This increment** — UX after both channels exist |
| 4 | **P2-I8.5** Face Evidence Ownership | **After I8A** unless Tom reorders in Q1 |
| 5+ | I9 / I10 / I11 | Speech; correlate; narrate — **not I8A** |

I8A sits **between I8 and I8.5** so family comms are livable before face-SoT. If Tom wants I8.5 next instead, Q1 must say so — I8A must not silently delay Face Evidence.

---

## 2. Decisions for Tom (Q1–Q6) — OPEN

Do not treat these as locked until Tom answers.

| # | Topic | Default if Tom says “as drafted” | Alternative |
|---|--------|----------------------------------|-------------|
| **Q1** | Sequence vs I8.5 | **I8 ACCEPTED → I8A → I8.5** | Skip or slim I8A; I8.5 next |
| **Q2** | Gallery noise (newsletters, promo) | **Disclose + density/caps** in I8A; do **not** delete mail. Optional later filter (labels / “primary” / owner-only) as **P2-BL-I8A-01** if not in this build | I8A includes a real promo/newsletter hide (Gmail labels / heuristics — must stay honest) |
| **Q3** | SMS vs email Gallery default | **Keep I7 hide-SMS / I8 show-email**, but one Email/Text filter and one viewer | One default for all comms (both visible, or both behind Add communications) |
| **Q4** | Thread presentation | **Quoted turns in the body** + optional list of **RFC/vendor siblings already in the result set**. Do not fetch-invent a Gmail app thread | Full thread pane that walks `X-GM-THRID` / RFC graph as a separate object |
| **Q5** | Calendar in this canvas | **Out.** Calendar stays calendar cards | Include ICS events in the same comms viewer (not recommended for I8A) |
| **Q6** | Build gate | Definition may be read now. **No I8A runtime** until Q1–Q6 locked **and** explicit “I8A build is authorized” | Authorize a **thin** slice only (viewer+hover+people rail) and park density/noise |

### Additional rules (proposed; lock with Qs)

1. Do not reopen I7 or I8 parsers / ingest jobs except for display fields already stored.  
2. Do not invent RFC thread membership. Quoted history ≠ thread reconstruction.  
3. Do not auto-Artifact / auto-Immich.  
4. Do not start I8.5 / I9 / I10 / I11.  
5. **P2-BL-I4-01** (Explore chrome) stays parked unless a defect is comms-card-specific.  
6. **P2-BL-I7-01** (SMS attachment bytes) stays its own item; I8A may **display** bytes when present.

---

## 3. EVS (I8A is retrieve/display, not narrative)

| EVS | Ask (short) | I8A bar |
|-----|-------------|--------|
| **EVS-047** | Peggy + Christmas in emails **and** texts | Same Email/Text surface + shared viewer; **no** joint story. SMS still I7 evidence; email still I8 evidence. |
| **EVS-107 / 108** | Counts by Person / sister | Unchanged I8 retrieve; I8A does not change counts. Viewer must open the cited message. |
| **EVS-109** | Holiday-season email extract | Unchanged retrieve; I8A makes the opened message readable (quoted turns). |
| **EVS-070** | 2024 across mail, texts, pictures, video | **Not an I8A gate.** Density/caps must not pretend the gallery is a year narrative (I11). |

---

## 4. Scope IN (proposed)

- Shared Explore / Person **communications viewer** (email + SMS/MMS/iMessage).  
- Hover: structured comms; image-attachment preview from stored bytes.  
- People rail: participants only (no `Re:` subject-as-person).  
- Gallery density for mixed Show-me + Email/Text (caps, year-fair, scope text).  
- One Email/Text filter behavior documented under Q3.  
- Honest notes when HTML-only, incomplete thread, truncated sample, missing attachment bytes.  
- `prove-p2-i8a` harness + FlightSim owner pass.  
- Thin CSS/layout for comms cards/viewer (**comms-specific** aesthetic; not a full Explore redesign).

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

---

## 6. Constraints / edge cases (proposed)

- **No new ingest.** I8A reads stored communication Evidence and existing attachment bytes.  
- **Quoted history ≠ thread.** `On … wrote:` splits are display of one MIME body. RFC / `X-GM-THRID` membership is I8 honesty only.  
- **HTML-only:** disclose; do not invent a plain-text body.  
- **Missing SMS attachment bytes:** disclose; do not fetch from Immich; **P2-BL-I7-01** remains the ingest home.  
- **Newsletter hide (if Q2):** view filter only; Evidence rows stay; Archive Health counts do not drop.  
- **Caps:** “Showing N of M” required when sampling ~90k mail or ~90k SMS. Unavailable ≠ 0.  
- **People:** I7/I8 identity ladder only. Never merge on display name. Never treat `Re:` / `Fwd:` / subject as a Person.  
- **MBQL:** I8A does not invent a third planner. Email/SMS Ask still compiles on MBQL-001.  
- **I10/I11:** opening mail next to a photo is not correlation or narrative.

---

## 7. FlightSim I8 leftovers that I8A owns

From I8 owner pass 2026-08-18 (Tom: I8 accepted; aesthetics → I8A):

| Leftover | I8A bar |
|----------|---------|
| Structured email vs quoted blob | Shared comms viewer; quoted turns readable |
| Hover 📎 shows filename | Hover shows **image** when bytes exist |
| Hover on email card | Same structured view as zoom (compact) |
| Gallery noise (All Mail + photos) | Density/caps + Q2 noise policy |
| Email/Text vs SMS hide mismatch | Q3 one rule |
| Subject in People rail | Participants only (partially fixed in I8; I8A verifies) |

---

## 8. Discovery (reuse — do not rebuild)

| Area | Finding |
|------|---------|
| Email viewer | `explore.js` quoted turns + `/explore/api/email/{id}` |
| SMS viewer | same Email/Text cards; `gallery_default_hidden` |
| Attachments | `/explore/api/email-attachment` · `/explore/api/sms-attachment` |
| Ask | `search_email_messages` / `search_sms_messages` · MBQL |
| Identity | I7 ladder (phone + email) |
| Density | `_attach_visible_email` / `_attach_hidden_sms` caps |

---

## 9. Build (only after authorization)

1. Lock Q1–Q6 in this table.  
2. Shared viewer component for email + SMS; fetch full body on open.  
3. Hover image + structured compact turns.  
4. People rail from parsed participants.  
5. Gallery density + Q3 filter semantics.  
6. `prove-p2-i8a` + FlightSim §9.  
7. **Stop.** Do not start I8.5 unless Q1 skipped I8A.

---

## 10. Honesty / trust

- Channel always visible (email vs sms/imessage/mms).  
- Truncation disclosed.  
- Quoted history ≠ RFC thread.  
- Missing attachment bytes disclosed.  
- Unavailable ≠ 0.  
- Promo hide (if Q2) is a **view filter**, not deletion.

---

## 11. ACCEPTED gate (FlightSim) — after build

Pass **all**. Harness ≠ ACCEPTED.

1. Open one **email** and one **SMS** in the same viewer pattern (channel disclosed).  
2. Hover image attachment shows the picture when bytes exist.  
3. Hover/zoom on email is structured turns, not one undifferentiated blob.  
4. People rail has no `Re:` subject-as-person.  
5. Show me **[Person]** + Email/Text is usable (not empty, not 90k unsorted cards).  
6. SMS hide rule matches Q3; Add texts (or successor) still works.  
7. Q2 noise policy visible and honest.  
8. No I8.5 / I9 / I10 / I11 in the I8A walk.  
9. Originals untouched; no Immich dump; Artifact still explicit.

---

## 12. Authorization stop-line

| Step | Status |
|------|--------|
| I8 Richer Email | **ACCEPTED** 2026-08-18 |
| I8A definition | **DRAFT** — this document |
| I8A PRD | **DRAFT** — [MBPRD-P2-I8A_UNIFIED_COMMS.md](MBPRD-P2-I8A_UNIFIED_COMMS.md) |
| Q1–Q6 | **OPEN** |
| I8A build | **NOT AUTHORIZED** |
| I8.5 / I9 / I10 / I11 | **NOT STARTED** |

**Stop.** Do not implement I8A until Tom locks Q1–Q6 and authorizes build. Do not start I8.5 in this increment.
