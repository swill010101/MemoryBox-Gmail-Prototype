# MBPRD-P2-I8 — Richer Email

**Status:** **DRAFT — awaiting Tom approval** · definition **not locked** · **NOT BUILD AUTHORIZED**  
**Date:** 2026-08-18  
**Increment definition:** [MBBS-P2_INCREMENT_8_DEFINITION.md](MBBS-P2_INCREMENT_8_DEFINITION.md)  
**Depends:** I7 / I7A / MBQL-001 / I4 **ACCEPTED**  
**Does not start:** I8.5 face SoT · I9 spoken · I10 correlation · I11 narrative · Settings · multi-user · live Gmail

No build until Tom approves the definition (Q1–Q6) and separately authorizes implementation.

---

## 1. Problem being solved (and why it matters now)

P1/I3 mbox ingest stores **headers and body text**. It does not store **attachment files**, does not treat **threads** as a product, and does not finish **email → Person** the way I7 finished phone → Person.

I7 taught the communication Evidence path on SMS — and accepted **without** attachment bytes (**P2-BL-I7-01**). Tom already parked **P2-BL-I8-01:** I8 must take **email attachment files up front**. Waiting would repeat the SMS gap.

MBQL-001 is ACCEPTED, so “how many times did I email Peggy” / holiday windows can compile on one contract. I7A can trace any residual model fill. I8 should reuse those, not invent a third planner.

**What I8 is not:** a mail app, live sync, I10 “Alaska from mail+photos”, I11 year-in-review narrative, or I8.5 face ownership.

---

## 2. Success criteria (how we’ll know it works)

After an authorized build + FlightSim owner pass (definition §9):

1. Real staged mail ingested; originals untouched.  
2. Thread-aware retrieve and counts with **scope disclosure**.  
3. Participants mapped without silent People merges.  
4. At least one real attachment **file** opens from a message.  
5. Holiday/year Ask uses existing I4/MBQL windows.  
6. Cited extract allowed; underlying messages remain reachable.  
7. Attachments not auto-promoted to Immich.  
8. `prove-p2-i8` is harness only.

---

## 3. Scope

**IN / OUT:** definition §§3–4.

**P2-BL-I8-01** is **in** I8 (files at ingest). It is not a follow-up increment.

---

## 4. Constraints, dependencies, edge cases

- Same evidence model as email-today + I7 SMS (`communication`).  
- Originals untouched; hash skip.  
- Unavailable ≠ 0.  
- MBQL deterministic first; I7A on residual fill.  
- I7 Gallery SMS hide unchanged.  
- Q1 must `inspect-mbox` on FlightSim before parser lock (path may still be `\\media-server\photos\…`).  
- HTML-only bodies: preserve HTML; disclose if plain text is empty.  
- Duplicate Message-IDs / broken threads: disclose; do not invent a thread.

---

## 5. Build plan (not authorized)

See definition §7. Sequence: Tom locks Qs → **approved to build** → inspect-mbox → implement → FlightSim §9.

---

## 6. Open questions for Tom

Same Q1–Q6 as the definition. Short form:

1. Where is the real mail export, and what format is it?  
2. Which people/years/holidays exist for the EVS walk?  
3. Confirm RFC 5322 threads (no live Gmail API)?  
4. Confirm attachment **files** at ingest, not Immich auto-promote?  
5. Confirm I7 identity ladder for email addresses?  
6. Confirm I8 vs I10 vs I11 split (retrieve/preserve vs infer vs narrate)?

---

## 7. Decision status

PRD **DRAFT**. Definition **DRAFT**. **No build.** Waiting on Tom approval.
