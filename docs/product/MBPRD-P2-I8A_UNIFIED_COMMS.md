# MBPRD-P2-I8A — Unified Communications Gallery & Timeline Precision

**Status:** **REVISED** · Q1–Q6 **LOCKED** (founder 2026-08-18) · **not BUILD AUTHORIZED** · awaiting **final founder lock** of the increment definition  
**Date:** 2026-08-18  
**Increment definition:** [MBBS-P2_INCREMENT_8A_DEFINITION.md](MBBS-P2_INCREMENT_8A_DEFINITION.md)  
**Depends:** I8 **ACCEPTED** · I7 **ACCEPTED** · I4 **ACCEPTED** · MBQL-001 **ACCEPTED** · existing ICS ingest path  
**Does not start:** I8A runtime until “I8A build is authorized” · I9 spoken product inside I8A · I8.5 face SoT · I10 · I11 · live Gmail · Calendar product redesign

This PRD tracks the **revised definition**. No code until Tom finally locks that sheet **and** says **“I8A build is authorized.”**

---

## 1. Problem being solved (and why it matters now)

I7 and I8 put SMS and email into Evidence. I4 put photos/video on a Timeline/Gallery. High-volume dated mail, texts, and calendar still either **flood** the Gallery or stay in a **too-narrow** shared-viewer story.

Tom accepted I8 (2026-08-18) and, in founder review the same day, required I8A to include:

- unified **high-volume Gallery** combined cards;  
- **Timeline-precision** aggregation;  
- **Calendar in the same time-bucket card** (still calendar evidence);  
- Email **and** SMS **visually OFF** on a broad Gallery, without losing eligibility;  
- the shared viewer / Person-lock work already scoped.

It matters **now** because both comms channels exist and the owner already uses Show me + Explore. Spoken (I9) is next. Face-SoT is later.

---

## 2. Success criteria

After final lock + build authorization + FlightSim definition §11 (all items).

---

## 3. Scope

**IN / OUT:** definition §§4–5.

**IN:** combined time-bucket card (Email · Text · Calendar counts); Timeline-precision aggregation; one shared state; drill-down modal stack; Q3 visual defaults; shared Email/SMS viewer; **P2-BL-I8-02**; minimum ICS ingest if FlightSim has no `calendar_event` rows.

**OUT:** Evidence deletion; AI promo classifier (**P2-BL-I8A-01**); invented threads; Calendar-as-comms; I9/I8.5/I10/I11; runtime before authorization.

---

## 4. Constraints, dependencies, edge cases

Definition §6. Calendar inspect before any ingest code. Combined card is presentation only.

---

## 5. Build plan

Definition §12 — **not authorized**.

---

## 6. Q1–Q6

**LOCKED** in the increment definition §2 (founder 2026-08-18). Short form:

1. I8 → I8A → I9. Face-ownership later.  
2. No delete / no silent suppress; no new AI promo classifier; combined cards + Timeline + caps.  
3. Broad Gallery: Email OFF, SMS OFF visually; eligibility unchanged; explicit Add/Only/Show everything.  
4. No invented threads; detail inside drill-down.  
5. Calendar IN the combined card; minimum ICS ingest if needed.  
6. Revise definition first; no runtime until “I8A build is authorized” after final lock.

---

## 7. Decision status

PRD **REVISED**. Definition **REVISED**. Q1–Q6 **LOCKED**. Build **not authorized**. Awaiting **final founder lock** of the definition, then explicit build authorization.
