# MBPRD-P2-I10 — Cross-Source Correlation

**Status:** **LOCKED** · **BUILD AUTHORIZED** 2026-08-20 (Tom: “I10 is approved to build”)  
**Increment definition:** [MBBS-P2_INCREMENT_10_DEFINITION.md](MBBS-P2_INCREMENT_10_DEFINITION.md)  
**Depends:** I1–I8A **ACCEPTED** · I9 Spoken Moments on this tree · MBQL-001 **ACCEPTED**  
**Does not start:** I11 narrative generation · I12 external history · I8.5 face SoT · Place GIS · OCR engines · Paprika

This PRD is the discover pass for I10. Runtime follows the increment definition.

---

## 1. Problem being solved (and why it matters now)

Photos, video moments, spoken passages, email, SMS, calendar, Stories, Journal, and Artifacts can each retrieve. An Ask such as “everything about Grandpa’s military service” still fails as a **family question** if MemoryBox answers from one modality, hides the rest, or invents a paragraph.

It matters **now** because I9 just made speech a source, I8/I8A made communications real, and GRAPH-02/03 are the next locked P2 expansion. Tom authorized continuing P2 from increment 9 onward.

## 2. Success criteria

1. Everything-about compiles to a cross-source plan (not video-only, not email-only).
2. The result is a **cited pack** with per-source counts and **missing** sources disclosed.
3. Owner reject of a correlation link survives re-index of the same evidence.
4. Conflicting dates for one event are both shown.
5. Curator text is not stored as Evidence. No I11 story is auto-saved.
6. `python -m memorybox prove-p2-i10` passes on the harness.

FlightSim owner ACCEPTED is a later pass on a real Person + theme.

## 3. Scope

**IN / OUT:** definition §§3–4.

## 4. Constraints, dependencies, edge cases

- I8A Q3 hide-comms stays for ordinary Show-me. Everything-about is explicit all-source presentation.
- Person ambiguity still uses I8A lock/clarify before counting.
- Theme keywords must not substring-union unrelated People.
- Candidate ≠ confirmed. System may propose; owner decides.
- Do not cartesian people × archive.

## 5. Build plan

1. Places + correlatable events + correlation_links migration.
2. Compile everything-about / theme slot; skip I9 spoken-narrowing when cross-source.
3. Pack + coverage + reject filter + date-conflict disclosure.
4. Confirm/reject API; Explore coverage strip.
5. Prove harness; FlightSim notes.

## 6. Open questions

None blocking. Paprika, OCR, GIS, and narrative save stay parked.

## 7. Decision status

PRD locked. Tom 2026-08-20: **“I10 is approved to build.”** Runtime is this increment.
