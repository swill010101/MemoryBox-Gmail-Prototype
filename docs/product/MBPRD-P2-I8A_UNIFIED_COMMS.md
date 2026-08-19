# MBPRD-P2-I8A — Unified Communications Gallery & Timeline Precision

**Status:** **LOCKED** · **ACCEPTED** 2026-08-19 (Tom: owner-pass complete; “i8a is accepted”)  
**Date:** 2026-08-18 (locked) · 2026-08-19 (accepted)  
**Increment definition:** [MBBS-P2_INCREMENT_8A_DEFINITION.md](MBBS-P2_INCREMENT_8A_DEFINITION.md)  
**Visual baseline:** [`docs/source/mockups/i8A/`](../source/mockups/i8A/)  
**Depends:** I8 **ACCEPTED** · I7 **ACCEPTED** · I4 **ACCEPTED** · MBQL-001 **ACCEPTED** · existing ICS ingest path  
**Does not start:** I9 spoken product · I8.5 face SoT · I10 · I11 **narrative generation** · live Gmail / send · Calendar product redesign · Reply/Reply all/Forward

This PRD tracks the **locked definition**. Runtime follows MBBS-P2 I8A.

---

## 1. Problem being solved (and why it matters now)

I7 and I8 put SMS and email into Evidence. I4 put photos/video on a Timeline/Gallery. High-volume dated mail, texts, and calendar still either **flood** the Gallery or stay in a **too-narrow** shared-viewer story.

Tom accepted I8 (2026-08-18), then accepted the committed I8A screens 00–11 and locked conflict resolutions the same day. I8A must include:

- unified **high-volume Gallery** combined **day** cards (E/T/C when mixed presentation is on);  
- **density-aware** aggregation (Timeline precision **and** evidence density — not scale-equals-bucket);  
- **Calendar as its own filter dimension**, also eligible for the combined day card;  
- Communications filter = Email + Text; **Attachments only** as a first-class mode on stored bytes;  
- Email **and** SMS **visually OFF** on a broad Gallery, without losing eligibility; Memory chip may hide comms after an explicit SMS Ask;  
- drill-down: rollover → Open Day → channel tabs → list → detail;  
- shared viewer **without** mail-client send controls;  
- **P2-BL-I8-02** Person resolution (behavioral).

It matters **now** because both comms channels exist and the owner already uses Show me + Explore. Spoken (I9) is next. Face-SoT is later. I11 still owns narrative generation; I8A only keeps the combined card reusable as Supporting Evidence.

---

## 2. Success criteria

FlightSim owner pass 2026-08-19 — **met**. Increment **ACCEPTED**.

---

## 3. Scope

**IN / OUT:** definition §§4–5.

**IN:** combined day card; Communications + Calendar filters; Attachments only (stored evidence); density-aware aggregation; one shared Ask/Explore state; drill-down stack (§4.5); Q3 visual defaults + Memory presentation command; shared viewer without send; **P2-BL-I8-02**; minimum ICS ingest if FlightSim has no `calendar_event` rows; combined-card reuse for later Supporting Evidence.

**OUT:** Evidence deletion; AI promo classifier (**P2-BL-I8A-01**); invented threads; Calendar-as-comms; I9/I8.5/I10/I11 generation; Reply/Forward; **P2-BL-I7-01** byte ingest.

---

## 4. Constraints, dependencies, edge cases

Definition §6. Calendar inspect before any ingest code. Combined card is presentation only. Screen 11 send buttons superseded.

---

## 5. Build plan

Definition §12 — **not authorized**.

---

## 6. Q1–Q6 and visual locks

**LOCKED** in the increment definition §2 and §2.1. Short form:

1. I8 → I8A → I9. Face-ownership later.  
2. No delete / no silent suppress; no new AI promo classifier; combined cards + density-aware aggregation + caps.  
3. Broad Gallery: Email/SMS/Calendar OFF visually; eligibility unchanged; explicit Ask sets initial presentation; later chips/filters may change presentation.  
4. No invented threads; detail inside drill-down.  
5. Calendar IN as its own filter; also on the combined day card; minimum ICS ingest if needed.  
6. Revise definition first; no runtime until “I8A build is authorized” after final lock.

Visual authority: definition §0.1.

---

## 7. Decision status

PRD **LOCKED**. Definition **LOCKED**. Build **shipped**. Increment **ACCEPTED** 2026-08-19. **P2-BL-I8-02 absorbed.** Do not reopen I8A. Next is **I9** (not authorized).
