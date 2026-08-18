# MBPRD-P2-I8 — Richer Email

**Status:** **LOCKED** · **BUILD AUTHORIZED** 2026-08-18 · **not yet ACCEPTED** (FlightSim definition §9)  
**Date:** 2026-08-18  
**Increment definition:** [MBBS-P2_INCREMENT_8_DEFINITION.md](MBBS-P2_INCREMENT_8_DEFINITION.md)  
**Depends:** I7 / I7A / MBQL-001 / I4 **ACCEPTED**  
**Does not start:** I8.5 face SoT · I9 spoken · I10 correlation · I11 narrative · Settings · multi-user · live Gmail

---

## 1. Problem being solved (and why it matters now)

P1/I3 mbox ingest stored **headers and body text**. It did not store **attachment files**, did not treat **threads** honestly as a product, and did not finish **email → Person** the way I7 finished phone → Person.

**P2-BL-I8-01** is in this increment: email attachment **files go in with the mail**.

---

## 2. Success criteria

After this build + FlightSim owner pass (definition §9, including the three extra checks):

1. Real staged mail ingested; originals untouched. Inspected **before** parser assumptions (`inspect-mbox`).  
2. Thread-aware retrieve and counts with **scope disclosure**; incomplete threads honest.  
3. Participants mapped without silent People merges (I7 ladder).  
4. Attachment **files** open from a message; MIME fidelity preserved; not auto-Artifact / not Immich.  
5. Holiday/year Ask uses existing I4/MBQL windows.  
6. Cited extract allowed; underlying messages remain reachable.  
7. Default Gallery: emails visible; SMS hide unchanged.  
8. `prove-p2-i8` is harness only.

---

## 3. Scope

**IN / OUT:** definition §§3–4. **P2-BL-I8-01** is in.

---

## 4. Constraints, dependencies, edge cases

- Same evidence model (`communication` / channel `email`).  
- Originals untouched; hash skip; I3 rows upgrade to `i8-email-1` on re-ingest.  
- Unavailable ≠ 0.  
- MBQL deterministic first; I7A on residual fill.  
- Q1: `inspect-mbox` on `P:\photos\memorybox\sources\email\all mail including spam and trash-002.mbox`.  
- Spam/Trash: Gmail Takeout labels (`X-Gmail-Labels` / `X-GM-LABELS`), **not** the Takeout filename. Default ingest **skips** Spam/Junk and Trash/Bin/Deleted; originals untouched. Pass `--include-spam-trash` to ingest those too. `inspect-mbox` counts labels and does not skip.  
- HTML-only bodies: preserve HTML; disclose empty plain text.  
- Duplicate Message-IDs / broken threads: disclose; do not invent a thread.  
- Inline/CID vs ordinary attachments distinguished.

---

## 5. Build plan

Definition §7 — **authorized and implementing** this revision (`inspect-mbox`, richer `ingest-email`, Ask/Explore/Archive Health, `prove-p2-i8`).

---

## 6. Q1–Q6

Locked in the increment definition §2 (Tom 2026-08-18). Short form:

1. Inspect the real staged source; do not fabricate a corpus.  
2. Map real people/dates/keywords/threads to EVS intent.  
3. RFC threads + preserve vendor ids; no invented membership.  
4. Attachment bytes+metadata with the message; explicit Artifact only.  
5. I7 identity ladder; never merge on display name alone.  
6. I8 = evidence + correlation readiness; I10 = correlate; I11 = synthesize.

---

## 7. Decision status

PRD **LOCKED**. Definition **LOCKED**. Build **AUTHORIZED**. ACCEPTED waits on FlightSim §9 (including attachment/MIME fidelity, incomplete-thread honesty, and MBQL/default-Gallery checks).
