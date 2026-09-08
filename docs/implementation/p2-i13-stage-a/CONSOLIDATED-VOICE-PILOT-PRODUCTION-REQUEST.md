# Consolidated production request — bounded voice pilot (STOP)

**Date:** 2026-09-08  
**Branch:** `codex/p2-i13-stage-a`  
**Purpose:** Single founder decision immediately before any real bounded voice-learning/recognition run

---

## Request

Tom: confirm **Outcome W — waive additional voice pilot execution** for the five-category I13 matrix.

| Option | Meaning |
|---|---|
| **W — Waive (recommended)** | Accept that the canonical eight assignments and six **current** stopped voice pilots already satisfy Eugene training, Eugene held-out, Tom training, off-camera Tom held-out, and uncertain/no-match evidence. **Do not** register or execute another voice pilot for this matrix. |
| **R — Re-run (reject)** | Explicitly authorize re-execution of a prior admission — **not recommended**; violates evidence-preservation locks unless a new reviewed plan addresses a documented regression. |
| **N — New pilot** | Authorize a **new** bounded plan only if inspection shows a **missing category** — inspection reports **none missing** ([VOICE-ASSIGNMENT-COVERAGE.md](VOICE-ASSIGNMENT-COVERAGE.md)). |

---

## Evidence summary (read-only)

- **Eight assignments** mapped — no training/held-out ID conflicts
- **Five categories** — all satisfied with **current** stopped admissions
- **No additional annotation** required for the matrix
- **Gate 3** transcription admission `458d1a76…` complete (do not retry)
- **Overlap pilot** `339b3a14…` complete (do not retry)
- **Gate 4** archive plan preview passed; register/unlock/start **not** authorized

---

## If Outcome W is confirmed

Record in `FOUNDER-AUTHORIZATION.md`:

```text
Tom-waived-additional-voice-pilot-matrix-run-2026-09-08
```

No FlightSim processing commands. Next I13 work remains:

1. Face/voice corroboration (separate PRD), **or**
2. Gate 4 Outcome C+ with fresh sign-off, **or**
3. Full I13 acceptance review

---

## If Outcome N is ever required later

Minimum package before `-Execute`:

1. Fresh backup on FlightSim (operator procedure)
2. `prepare-*-voice-pilot.py` check-only + `-WritePlan`
3. `deploy-*-voice-pilot.ps1` check-only
4. Explicit approval reference string from Tom
5. Single `-Execute`; then `stop` and drains off

---

## Sign-off

| Field | Value |
|---|---|
| Outcome (W / R / N) | _pending Tom reply_ |
| Reference string | _pending_ |
| Signed | |
| Date | |

**Agent stops here** until Tom records Outcome **W**, **R**, or **N**.
