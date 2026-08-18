# MBBS-P2 Increment 8 — Richer Email

**Status:** **ACCEPTED** (2026-08-18 — Tom: FlightSim §9 “All pass….. accepted”)  
**Date:** 2026-08-18 (build) · 2026-08-18 (accepted)  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) § P2-I8 (Richer Email · A)  
**Thin PRD:** [MBPRD-P2-I8_RICHER_EMAIL.md](MBPRD-P2-I8_RICHER_EMAIL.md)  
**Authority:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-COM-02 / P2-COM-03** · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) **CAP-P2-019** · [MBEVS-001 v1.0](MBEVS-001_EVS_CATALOG_v1.0.md) · I1–I7 **ACCEPTED** · I7A **ACCEPTED** · MBQL-001 **ACCEPTED** · I4 **ACCEPTED**  
**Depends:** MBQL-001 **ACCEPTED** (2026-08-18) · existing P1/I3 mbox ingest pattern (`ingest-email` / `comms_email.py`)  
**Does not reopen / does not absorb:** I7 SMS · **P2-BL-I7-01** · I4 Explore redesign / **P2-BL-I4-01** · I5 portrait **P2-BL-I5-01** · I6 kinship · **I8A** unified comms UX · **I8.5** face-evidence · **I9** spoken · **I10** cross-source correlation · **I11** narrative · I13/I14 Settings · multi-user · live Gmail sync / sending mail

P2-I8 is **ACCEPTED**. Unified Communications Gallery & Timeline Precision is **[P2-I8A](MBBS-P2_INCREMENT_8A_DEFINITION.md)** (revised; not build-authorized). Do not reopen I8 for chrome. Near-term after I8A is **I9**. Face-SoT is later.

## What shipped (ACCEPTED)

- `inspect-mbox` on `P:\photos\memorybox\sources\email\all mail including spam and trash-002.mbox` (~19.7 GB, 93,885 messages)
- `ingest-email` `i8-email-1`: 91,275 inserted; Spam 240 / Trash 2,363 skipped; 28,464 attachment files; originals untouched; NUL bytes stripped
- RFC + Gmail `X-GM-THRID` threads; incomplete/unthreaded honest
- I7 identity ladder on email; MIME attachments with the message; not Immich; explicit Artifact only
- Ask: person / holiday window / keyword / count+scope; Explore Email/Text; SMS hide unchanged
- Owner pass: Show me email; Christmas window; Sue Will mail with photos; §9 all pass
- Follow-up (did not fail I8): Ask “how many times did I send an email to Peggy?” returned a count and Gallery showed mail, but **Peggy was not locked to Peggy George first**, so extra non–Peggy-George messages were included. Parked **P2-BL-I8-02** for the next increment (I8A).

## Carry-forward (not ACCEPTED blockers)

| ID | Item | Notes |
|----|------|-------|
| **P2-I8A** | Unified Communications Gallery & Timeline Precision | Definition revised (screens 00–11 accepted). Combined day cards + density-aware aggregation + Calendar filter + viewer + **P2-BL-I8-02**. **Not BUILD AUTHORIZED.** |
| **P2-BL-I8-01** | Attachment files up front | **Absorbed in I8** (shipped). |
| **P2-BL-I8-02** | Ask email count must lock canonical Person first | Owner 2026-08-18: “how many times did I send an email to Peggy?” counted and showed mail **without resolving Peggy George first**, so extra mail that is not Peggy George was included. Count path still worked. **Do not reopen I8.** Next increment: **I8A**. |

---

## 0. Product intent

> **Staged owner email becomes first-class MemoryBox communication evidence with thread awareness, Person-linked participants, and attachment files stored at ingest — searchable and honest on existing Ask / Explore / Person surfaces. Missing coverage is disclosed. Messages and attachments are never invented.**

I8 is **archive understanding**, not a mail client, not a new family nav item, and not I10/I11.

P1/I3 already ingest mbox **headers + body text** into `evidence_kind=communication`. That is **not** richer email. Parser version **`i8-email-1`** stores MIME parts (bytes + metadata) with the message.

End-to-end:

1. The staged FlightSim mail export is ingested **without modifying originals**.  
2. Each message is communication Evidence with channel `email`.  
3. **Threads** use RFC `Message-ID` / `In-Reply-To` / `References`, plus preserved vendor ids (`X-GM-THRID` when present). Membership is **not invented**; valid mail may remain **unthreaded**. Incomplete threading is represented honestly.  
4. Participants resolve via the **I7 identity ladder** on normalized email (never display name alone). Raw source address and display name are preserved.  
5. **Attachment bytes** ingest with the message (filename, MIME type, size, hash, disposition/inline, Content-ID, source relationship, provenance). Inline/CID ≠ ordinary attachments. **No** automatic Immich or standalone Gallery promotion. **Explicit Artifact copy only.** Email attachment evidence is **not** automatically an Artifact.  
6. Ask uses **MBQL-001** (deterministic first; I7A traces residual model fill). Default Gallery semantics: emails stay visible; I7 SMS default-hide is unchanged.  
7. Archive Health distinguishes staged vs ingested vs unavailable (unavailable ≠ 0).  
8. I8 is **correlation-ready**; I10 correlates; I11 narrates.

---

## 1. Why now (sequence lock)

| Order | Artifact | Role |
|-------|----------|------|
| 1–3 | I7 / I7A / MBQL-001 | **ACCEPTED** |
| 4 | **P2-I8** | **ACCEPTED** 2026-08-18 |
| 4a | **P2-I8A** Unified Communications Gallery & Timeline Precision | After I8; **before I9** |
| 5 | **P2-I9** | Spoken — **after I8A**; not I8 |
| later | **P2-I8.5** | Face evidence ownership — **later**, not next after I8A |

---

## 2. Locked decisions (Tom 2026-08-18)

| # | Topic | Lock |
|---|--------|------|
| **Q1** | Export path / format | **Inspect the actual FlightSim staged email source first.** Do not assume format or fabricate a convenience corpus. Cloud/harness uses `inspect-mbox` (headers/counts/attachment presence; **no bodies in the report**). In-repo fixture is **not** the acceptance corpus. |
| **Q2** | Acceptance people / years | **Use real people / date ranges / keywords / threads from that source**, mapped to EVS intent (Peggy / sister / holidays if present; otherwise real equivalents). Harness fixture is EVS-intent stand-in only. |
| **Q3** | Thread model | **RFC message relationships** (`Message-ID`, `In-Reply-To`, `References`). **Preserve vendor thread IDs when present.** Do not invent thread membership when evidence is insufficient; valid email may remain unthreaded. Incomplete threading must be represented honestly rather than guessed. |
| **Q4** | Attachments | **In I8 scope.** Bytes + metadata ingested **with the message**. Preserve filename, MIME type, size, hash, disposition/inline state, Content-ID where available, source relationship, provenance. Distinguish inline/CID from ordinary attachments. **No** automatic Immich / standalone Gallery promotion. **Explicit Artifact copy only.** Email attachment evidence is **not** automatically an Artifact. |
| **Q5** | Address → Person | **I7 identity ladder.** Unique confirmed match → canonical Person; ambiguous → Review; unmatched retained. Preserve raw source address/display name. **Never merge on display name alone.** |
| **Q6** | P2-COM-02 split | **Locked.** I8 provides rich email evidence and **correlation readiness**. **I10** performs cross-source correlation. **I11** performs richer narrative/synthesis. |

Additional rules (locked): preserve sufficient original MIME/header provenance for source fidelity; use MBQL shared state and default Gallery semantics; use I7A tracing for any model-assisted interpretation; **do not implement I8.5, I9, I10, or I11**.

---

## 3. Scope IN

- Read-only ingest of the **actual** FlightSim staged mail (after Q1 `inspect-mbox`).  
- Expand mbox ingest: attachments **in the first I8 ingest**.  
- Communication Evidence + MIME/header provenance.  
- Thread reconstruction (§2 Q3) with honest incomplete/unthreaded states.  
- Email → Person (§2 Q5).  
- Attachment files reachable from the message; optional Artifact copy; not Immich.  
- Ask via MBQL: email modality, Person, date/holiday windows, keyword, counts, thread open, attachment-aware viewer, **scope disclosure**.  
- Explore / Person Email/Text cards + Timeline for dated mail. Emails **visible** on default mixed Gallery; SMS hide unchanged.  
- Archive Health staged / ingested / unavailable.  
- `prove-p2-i8` structural harness **plus** FlightSim owner ACCEPTED (after this build).  
- Correlation-**readiness**. No Alaska inference / year narrative.

## 4. Scope OUT

| Out | Home |
|-----|------|
| Live IMAP/Gmail sync, sending mail, mail client UX | Never I8 |
| New Email family-nav app | Never |
| SMS / iMessage ingest or **P2-BL-I7-01** | I7 / that backlog item |
| Auto-promote attachments to Immich / Gallery photos | Out |
| Infer Place / Event / Trip from mail + photos + SMS | **I10** |
| Year / trip / person **multi-source narrative** | **I11** |
| Face-evidence ownership / Immich decoupling | **I8.5 later** (after I8A and after recognition/correction/merge/relearn are solid; I9 is next after I8A) |
| Spoken moments / STT | **I9** |
| I4 Explore chrome redesign / **P2-BL-I4-01** | Closed / polish |
| Invented messages or guessed threads | Forbidden |

---

## 5. EVS coverage (I8 homes)

| EVS | Ask (short) | I8 bar |
|-----|-------------|--------|
| **EVS-107** | How many times did I email Peggy at her email address? | Outbound count + **scope** (map real Person from Q1 inspect) |
| **EVS-108** | How many times did my sister respond to any of my emails? | Sister Person or **mapped equivalent** + inbound/reply count + scope |
| **EVS-047** | What did Peggy and I coordinate on around Christmas, in emails and texts? | **I8:** retrieve **email** side in Christmas windows. SMS side is I7. No joint narrative. |
| **EVS-109** | Summarize emails to sister/Peggy over holiday seasons | Holiday-window retrieve + **cited extract**; messages remain reachable. |
| **EVS-070** | Summary through emails, texts, pictures, and videos of my 2024 | **Not an I8 hard gate.** Email-only retrieve with disclosure. I11 narrates later. |

---

## 6. Discovery (reuse)

| Area | Finding |
|------|---------|
| Ingest | `ingest-email` / `inspect-mbox` / `comms_email.py` · parser `i8-email-1` |
| Attachments | `put_media_object` (origin `email_ingest`) · `/explore/api/email-attachment` |
| Identity | `phone_map.resolve_handles` (email contacts + `identity_kind=email`) |
| Ask | `search_email_messages` · MBQL `EMAIL_RE` · I7A residual traces unchanged |
| Explore | Email/Text cards; SMS `gallery_default_hidden` only for SMS |
| Staged mail | `P:\photos\memorybox\sources\email\all mail including spam and trash-002.mbox` |

**Spam / Trash (not a Gmail search filter).** The Takeout file is an All Mail dump; the words in the filename do not change ingest. Each message still carries `X-Gmail-Labels` / `X-GM-LABELS`. Tokens `Spam`/`Junk` skip as spam; `Trash`/`Bin`/`Deleted` skip as trash. Inbox (and other labels) ingest even when the file is named “including spam and trash.”

- Inventory (counts labels, does not skip): `python -m memorybox inspect-mbox`
- Ingest kept mail only (default): `python -m memorybox ingest-email`
- Include Spam + Trash Evidence: `python -m memorybox ingest-email --include-spam-trash`

`--limit N` on ingest is kept messages after that skip. Originals stay read-only.

---

## 7. Build (this revision)

1. `inspect-mbox` (FlightSim): path, byte size, mbox vs Maildir, attachment presence, date span, address sample — **do not commit bodies**.  
2. Parser/DTO/ingest: MIME parts, RFC/vendor threads, identity, originals untouched, hash skip + `i8-email-1` upgrade of prior I3 rows.  
3. Ask retrieve/count/keyword/holiday + attachment-aware open.  
4. Explore/Person attachment affordance; explicit Artifact copy.  
5. Archive Health honesty.  
6. `prove-p2-i8` harness + FlightSim §9 owner pass.

---

## 8. Honesty / trust

- staged vs ingested distinguishable  
- unavailable ≠ zero  
- missing mbox ≠ zero messages  
- unmapped participants disclosed  
- attachment listed but bytes missing → disclosed  
- incomplete thread → `thread_completeness=incomplete`, not guessed members  
- P2-COM-03: source, participants, timestamps, thread, MIME provenance remain reachable  

---

## 9. ACCEPTED gate (FlightSim)

Pass **all**. Structural `prove-p2-i8` does **not** equal ACCEPTED.

1. Real staged mail is ingested **without modifying originals**.  
2. At least one real message fidelity-checked: subject, timestamp, from/to, body (or disclosed HTML-only), thread association.  
3. At least one real **attachment file** opens from that message.  
4. “How many times did I email **[Q2 Person]**” returns a count **with scope**. *(Owner 2026-08-18: first-name “Peggy” counted without locking **Peggy George** — **P2-BL-I8-02**, next increment; did not fail I8.)*  
5. Person filtering works.  
6. Year / holiday-window filtering works (reuse I4 windows).  
7. Keyword filtering works.  
8. Thread open shows related messages, not a flat unrelated dump. Unthreaded mail is not forced into a thread.  
9. Unique email auto-maps; ambiguous goes to Review; unmapped retained.  
10. Attachments are **not** dumped into Immich as library photos and are **not** automatic Artifacts.  
11. Archive Health: staged vs ingested vs unavailable; unavailable ≠ 0.  
12. Broad Explore Gallery SMS hide unchanged; emails remain visible on Email/Text and default mixed Gallery.  
13. No I8.5 / I9 / I10 / I11 product in the I8 walk.  

**Additional harness/owner checks (required):**

14. **Attachment / MIME fidelity** — filename, MIME type, size, hash, disposition/inline, Content-ID (when present), inline vs ordinary attachment.  
15. **Incomplete-thread honesty** — missing parents / insufficient RFC or vendor evidence stay unthreaded or `incomplete`; no subject-line invention.  
16. **MBQL email / default-Gallery behavior** — email asks compile on MBQL shared state; emails are not hidden by the SMS `gallery_default_hidden` rule.

---

## 10. Authorization stop-line

| Step | Status |
|------|--------|
| I7 / I7A / MBQL-001 / I4 | **ACCEPTED** |
| P2-BL-I8-01 (files up front) | **Absorbed in I8 ACCEPTED** |
| I8 definition | **LOCKED** 2026-08-18 |
| I8 PRD | **LOCKED** — [MBPRD-P2-I8_RICHER_EMAIL.md](MBPRD-P2-I8_RICHER_EMAIL.md) |
| Q1–Q6 | **LOCKED** (this table §2) |
| I8 build | **AUTHORIZED** — shipped |
| I8 ACCEPTED | **ACCEPTED** 2026-08-18 |
| P2-BL-I8-02 (Ask Person lock on email count) | **Parked for I8A** — first-name Peggy vs Peggy George |
| I8A Unified Communications Gallery & Timeline Precision | **REVISED, not BUILD AUTHORIZED** — [MBBS-P2_INCREMENT_8A_DEFINITION.md](MBBS-P2_INCREMENT_8A_DEFINITION.md) |
| I9 Spoken | **NOT STARTED** (next after I8A) |
| I8.5 / I10 / I11 | **NOT STARTED** (I8.5 later) |

**Stop.** Do not reopen I8 for chrome. I8A is next (awaiting final founder lock). Do not start I8A runtime, I9, I8.5, I10, or I11 until authorized.
