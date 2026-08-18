# MBPRD-P2-I8A — Unified Communications

**Status:** **DRAFT** · **not BUILD AUTHORIZED** · Q1–Q6 **OPEN**  
**Date:** 2026-08-18  
**Increment definition:** [MBBS-P2_INCREMENT_8A_DEFINITION.md](MBBS-P2_INCREMENT_8A_DEFINITION.md)  
**Depends:** I8 **ACCEPTED** 2026-08-18 · I7 **ACCEPTED** · MBQL-001 **ACCEPTED** · I4 **ACCEPTED**  
**Does not start:** I8.5 face SoT · I9 spoken · I10 correlation · I11 narrative · Settings · multi-user · live Gmail · I7/I8 re-ingest

---

## 1. Problem being solved (and why it matters now)

I7 and I8 put SMS and email into Evidence. They do not yet feel like **one** communications product: different Gallery defaults, a flat quoted-email blob, filename-only attachment hover, subject leaking into People, and All Mail noise next to family photos.

Tom accepted I8 (2026-08-18) with those aesthetics **parked in I8A**.

---

## 2. Success criteria

After build authorization + FlightSim definition §11:

1. Email and SMS open in a shared structured viewer (channel disclosed).  
2. Hover matches zoom for comms; image attachments preview as images when bytes exist.  
3. People = participants, not subject.  
4. Person + Email/Text is usable at archive scale (caps + “Showing N of M”).  
5. SMS/email visibility follows locked Q3.  
6. Noise policy follows locked Q2 (view filter, not deletion).  
7. `prove-p2-i8a` is harness only.

---

## 3. Scope

**IN / OUT:** definition §§4–5.

**IN (proposed):** shared communications viewer; hover that matches zoom; image-attachment preview from stored bytes; participant-only people rail; gallery density/caps; Q2/Q3 display rules; `prove-p2-i8a` after authorization.

**OUT:** re-ingest; SMS attachment **bytes** (**P2-BL-I7-01**); deleting Evidence for newsletters; live Gmail; new nav app; I8.5–I11; **P2-BL-I4-01** general Explore chrome.

---

## 4. Constraints, dependencies, edge cases

- Same evidence model (`communication`; channel `email` vs `sms` / `imessage` / `mms`).  
- Originals untouched; no parser rewrite; no Immich auto-promote.  
- Quoted `On … wrote:` ≠ RFC thread membership.  
- HTML-only: disclose; do not invent plain text.  
- Missing attachment bytes: disclose.  
- Do not merge People on display name or subject.  
- Promo/newsletter hide (if Q2) is a **view filter**, not deletion.  
- I10/I11 remain later. EVS-047 in I8A is **open both channels**, not a joint summary.

---

## 5. Build plan

Definition §9 — **not authorized** until Q-lock + “I8A build is authorized”.

---

## 6. Q1–Q6

Open in the increment definition §2. Short form:

1. I8A before I8.5, or slim/skip?  
2. Newsletter noise: density only, or a display filter?  
3. Keep hide-SMS / show-email, or one comms default?  
4. Quoted turns + in-result siblings, or a full thread object?  
5. Calendar in this canvas? (default no)  
6. Full I8A vs thin viewer-only first slice?

---

## 7. Decision status

PRD **DRAFT**. Definition **DRAFT**. Q1–Q6 **OPEN**. Build **not authorized**. ACCEPTED waits on build + FlightSim definition §11.
