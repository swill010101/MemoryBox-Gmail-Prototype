# MBBS-P2 Increment 8 — Richer Email

**Status:** **DRAFT — awaiting Tom approval** · **NOT BUILD AUTHORIZED** · **no implementation this revision**  
**Date:** 2026-08-18  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) § P2-I8 (Richer Email · A)  
**Thin PRD:** [MBPRD-P2-I8_RICHER_EMAIL.md](MBPRD-P2-I8_RICHER_EMAIL.md)  
**Authority (when locked):** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-COM-02 / P2-COM-03** · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) **CAP-P2-019** · [MBEVS-001 v1.0](MBEVS-001_EVS_CATALOG_v1.0.md) · I1–I7 **ACCEPTED** · I7A **ACCEPTED** · MBQL-001 **ACCEPTED** · I4 **ACCEPTED**  
**Depends:** MBQL-001 **ACCEPTED** (2026-08-18) · existing P1/I3 mbox ingest pattern (`ingest-email` / `comms_email.py`)  
**Does not reopen / does not absorb:** I7 SMS · **P2-BL-I7-01** · I4 Explore redesign / **P2-BL-I4-01** · I5 portrait **P2-BL-I5-01** · I6 kinship · **I8.5** face-evidence · **I9** spoken · **I10** cross-source correlation · **I11** narrative · I13/I14 Settings · multi-user · live Gmail sync / sending mail

**Stop.** This document is for review. **Do not write I8 runtime** until Tom locks Q1–Q6 (or records exceptions) **and** says **approved to build**.

---

## 0. Product intent

> **Staged owner email becomes first-class MemoryBox communication evidence with thread awareness, Person-linked participants, and attachment files stored at ingest — searchable and honest on existing Ask / Explore / Person surfaces. Missing coverage is disclosed. Messages and attachments are never invented.**

I8 is **archive understanding**, not a mail client, not a new family nav item, and not I10/I11.

P1/I3 already ingest mbox **headers + body text** into `evidence_kind=communication`. That is **not** richer email. Today’s DTO has **no attachment files**. I7 accepted SMS **without** attachment bytes (parked **P2-BL-I7-01**). **P2-BL-I8-01 is in-scope here:** email attachment **files go in with the mail**, not as a later surprise.

End-to-end (when built, after authorization):

1. The staged FlightSim mail export is ingested **without modifying originals**.  
2. Each message is communication Evidence with channel `email`.  
3. **Threads** are reconstructable (Message-ID / In-Reply-To / References, plus any thread id the source actually has).  
4. Participants resolve to **canonical MB People** via normalized email identity (same ladder as I7 phones: unique auto-map / ambiguous Review / unmapped retained).  
5. **Attachment bytes** are stored and reachable from the message (open / optional Artifact copy). **Not** auto-promoted to Immich or standalone Explore photo/video cards.  
6. Ask uses **MBQL-001** compile (deterministic first; I7A traces residual model fill). Retrieve, count, Person, date/holiday window, keyword, thread, attachment-aware open, **scope disclosure**.  
7. Explore / Person reuse existing Email/Text cards; dated mail participates in Timeline. I7 SMS default-hide on broad Gallery **does not change**.  
8. Archive Health distinguishes staged vs ingested vs unavailable (unavailable ≠ 0).

Future use I8 must **enable**, not perform: *“Include those Christmas emails in the Alaska trip narrative.”* That is **I10/I11**. I8 must leave timestamp, addresses, thread, body, attachments, and any explicit place/event headers intact.

---

## 1. Why now (sequence lock)

| Order | Artifact | Role |
|-------|----------|------|
| 1–3 | I7 / I7A / MBQL-001 | **ACCEPTED** — SMS pattern, traces, shared compile |
| 4 | **P2-I8** | This definition. Richer email **before** I8.5 |
| 5 | **P2-I8.5** | Face evidence ownership — **after I8**; not this increment |
| 6+ | I9 / I10 / I11 | Speech; cross-source; narrative |

**Build rule:** Definition may be finalized now. **No I8 code** until explicit build authorization.

---

## 2. Proposed locked decisions (Tom to confirm)

| # | Topic | Proposed lock | Notes |
|---|--------|----------------|-------|
| **Q1** | Export path / format | **OPEN until FlightSim `inspect-mbox`** | Same discipline as I7 Q1. Do not invent a convenience corpus. Header/folder/attachment layout must be recorded from the real staged mail. |
| **Q2** | Acceptance people / years | **Selection rules locked; names after Q1 sample** | Prefer Peggy / sister / holiday seasons / owner outbound counts **only if they exist in the real mbox**. Otherwise map real equivalents to EVS intent. Do not invent. |
| **Q3** | Thread model | **Proposed: RFC 5322** | Reconstruct threads from `Message-ID`, `In-Reply-To`, `References`. If the export carries Gmail `X-GM-THRID` (or equivalent), preserve it. **No live Gmail API** in I8. No “Core 4” object. |
| **Q4** | Attachments | **Proposed LOCK (P2-BL-I8-01)** | Ingest **files + metadata at the same time as messages**. Show on the message. Optional “Add to MemoryBox library” → Artifact (I7 SMS pattern). **Do not auto-promote to Immich** or mint Explore photo/video cards from mail attachments. Inline images stay on the message unless the owner copies them. |
| **Q5** | Address → Person | **Proposed: I7 ladder** | Normalize email. Unique confirmed Profile/contact match → auto-map. Ambiguous → Review. No match → unmapped participant (raw address / display name). Never silent duplicate People. Never merge on similar display name alone. |
| **Q6** | How much of P2-COM-02 | **Proposed split** | **I8:** thread, identity, attachments, dates, retrieve/count/keyword, cited extract, **preserve** explicit place/event headers in source metadata. **I10:** infer Place/Event/Trip across mail + SMS + photos/calendar. **I11:** year/trip/person multi-source narrative (EVS-070). “Significant exchanges” as a ranking product is **out** of I8 unless Tom explicitly pulls a thin cited-summary bar (I7 Q6 style). |

**Do not treat this table as locked until Tom says so.**

---

## 3. Scope IN

- Read-only ingest of the **actual** FlightSim staged mail (after Q1 file-open).  
- Expand existing mbox ingest: attachments **in the first I8 ingest**, not a parked byte gap.  
- Communication Evidence + full source-metadata preservation (headers the UI does not show still stored).  
- Thread reconstruction (§2 Q3).  
- Email → Person (§2 Q5).  
- Attachment files reachable from the message; optional Artifact copy; not Immich.  
- Ask via MBQL: email modality, Person, date/holiday windows, keyword, counts (to/from/between), thread open, attachment-aware viewer.  
- Explore / Person Email/Text cards + Timeline for dated mail.  
- Archive Health staged / ingested / unavailable.  
- Source-fidelity check of at least one real message **and one real attachment** against the export.  
- `prove-p2-i8` structural harness **plus** FlightSim owner ACCEPTED (after build).  
- Correlation-**readiness** (metadata preserved). No Alaska inference.

## 4. Scope OUT

| Out | Home |
|-----|------|
| Live IMAP/Gmail sync, sending mail, mail client UX | Never I8 |
| New Email family-nav app | Never |
| SMS / iMessage ingest or **P2-BL-I7-01** | I7 / that backlog item |
| Auto-promote attachments to Immich / Gallery photos | Out (same as I7 Q4) |
| Infer Place / Event / Trip from mail + photos + SMS | **I10** |
| Year / trip / person **multi-source narrative** (EVS-070, 211–213, 235–236) | **I11** |
| Face-evidence ownership / Immich decoupling | **I8.5 after I8** |
| Spoken moments / STT | **I9** |
| I4 Explore chrome redesign / **P2-BL-I4-01** | Closed / polish |
| I5 preferred portrait | **P2-BL-I5-01** |
| Mature Settings / provider catalog | **I13 / I14** |
| Invented messages or silent completeness | Forbidden |
| Multi-user contributed mail | Late / I15 |

---

## 5. EVS coverage (I8 homes)

Canonical homes from MBRM-001A Appendix A.1. Aliases are not separate acceptance.

| EVS | Ask (short) | I8 bar (after Q2 mapping) |
|-----|-------------|---------------------------|
| **EVS-107** | How many times did I email Peggy at her email address? | Outbound (or to-address) count + **scope** |
| **EVS-108** | How many times did my sister respond to any of my emails? | Sister Person + inbound/reply count + scope **or** mapped equivalent |
| **EVS-047** | What did Peggy and I coordinate on around Christmas, in emails and texts? | **I8:** retrieve **email** side in Christmas windows (I4 holiday lock). SMS side already I7 if ingested. **Do not** invent a joint narrative (I11) or photo correlation (I10). Disclose if one channel is missing. |
| **EVS-109** | Summarize emails to sister/Peggy over holiday seasons | Catalog row is mistagged Photos; **Ask text is mail**. I8: holiday-window retrieve + **cited extract**; messages remain reachable. Not Immich. |
| **EVS-070** | Summary through emails, texts, pictures, and videos of my 2024 | **Not an I8 hard gate.** Preserve mail so I11 can cite it. I8 may return **email-only** 2024 retrieve with disclosure. |

**Not I8 ACCEPTED:** I10/I11 multi-source stories; I8.5 face SoT; live Gmail.

---

## 6. Discovery (reuse — do not reinvent)

| Area | Finding |
|------|---------|
| Existing ingest | `memorybox/ingest/comms_email.py` + `ingest-email` — Source + Evidence, originals untouched, hash skip. Parser version `i3-email-1`. |
| DTO gap | `EmailMessageDto` has subject/from/to/cc/bodies/thread headers — **no attachments**. |
| Evidence | `evidence_kind=communication`, `evidence_channel=email` already used. |
| Ask | MBQL + `want_communication` already retrieve PG communication Evidence (email-shaped). |
| Explore | Email/Text cards exist; I7 taught SMS onto the same filter. |
| Identity | Profile `CONTACT_KINDS` includes `email`; I7 ladder is the pattern. |
| Attachments UX | I7 message viewer: open stored file; optional Artifact copy; not Immich. |
| Staged mail | Ops still point SMS/mbox/ICS at `\\media-server\photos\…` until those Sources move ([FLIGHTSIM_IMMICH_CUTOVER.md](../ops/FLIGHTSIM_IMMICH_CUTOVER.md)). **Q1 must open the real path on FlightSim.** |
| Holiday windows | I4 / MBQL Christmas (and other holidays) already compile; I8 retrieve must use those windows, not a new calendar. |

---

## 7. Build plan (only after authorization)

1. `inspect-mbox` (FlightSim): path, byte size, folder/mbox vs Maildir, attachment presence, date span, address sample — **do not commit bodies**.  
2. Extend email parser/DTO/ingest: attachments on disk (or MB blob store already used for SMS files), payload metadata, hash skip, originals untouched.  
3. Thread index from RFC 5322 (+ preserved vendor thread id if present).  
4. Email → Person mapping (I7 ladder).  
5. Ask retrieve/count/keyword/holiday + attachment-aware open; MBQL email phrases; I7A on any residual model fill.  
6. Explore/Person cards show attachment affordance when files exist.  
7. Archive Health staged vs ingested vs unavailable.  
8. `prove-p2-i8` harness + FlightSim §9 owner pass.

---

## 8. Honesty / trust

- staged vs ingested distinguishable  
- unavailable ≠ zero  
- missing mbox ≠ zero messages  
- unsupported date range ≠ zero  
- unmapped participants disclosed  
- attachment listed in source but file missing → disclosed, not invented  
- do not imply completeness beyond ingested source scope  
- P2-COM-03: source, participants, timestamps, thread, import provenance remain reachable behind any cited extract  

---

## 9. ACCEPTED gate (FlightSim, after build is authorized)

Pass **all**. Structural `prove-p2-i8` does **not** equal ACCEPTED.

1. Real staged mail is ingested **without modifying originals**.  
2. At least one real message fidelity-checked: subject, timestamp, from/to, body (or disclosed HTML-only), thread association.  
3. At least one real **attachment file** opens from that message (P2-BL-I8-01).  
4. “How many times did I email **[Q2 Person]**” returns a count **with scope**.  
5. Person filtering works.  
6. Year / holiday-window filtering works (reuse I4 windows).  
7. Keyword filtering works.  
8. Thread open shows related messages, not a flat unrelated dump.  
9. Unique email auto-maps; ambiguous goes to Review; unmapped retained.  
10. Attachments are **not** dumped into Immich as library photos.  
11. Archive Health: staged vs ingested vs unavailable; unavailable ≠ 0.  
12. Broad Explore Gallery SMS hide unchanged.  
13. No I8.5 / I9 / I10 / I11 product in the I8 walk.

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| I7 / I7A / MBQL-001 / I4 | **ACCEPTED** |
| P2-BL-I8-01 (files up front) | **In I8 scope** — not a later parking lot |
| I8 definition | **DRAFT** this revision — Tom review |
| I8 PRD | **DRAFT** — [MBPRD-P2-I8_RICHER_EMAIL.md](MBPRD-P2-I8_RICHER_EMAIL.md) |
| Q1–Q6 | **Awaiting Tom** |
| I8 build | **NOT AUTHORIZED** |
| I8.5 / I9 / I10 / I11 | **NOT STARTED** |

**Stop.** Do not implement I8. Do not start I8.5. Reply with Q1–Q6 locks (or edits) and, separately, **approved to build** when ready.
