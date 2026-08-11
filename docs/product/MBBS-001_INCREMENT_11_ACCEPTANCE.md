# MBBS-001 Increment 11 — Guided Capture — Acceptance

**Status:** **READY FOR OWNER ACCEPTANCE** (synthetic harness runnable; FlightSim I11-OWNER pending Tom)  
**Date:** 2026-08-11  
**Definition:** [MBBS-001_INCREMENT_11_DEFINITION.md](MBBS-001_INCREMENT_11_DEFINITION.md)  
**Prove:** `python -m memorybox prove-guided-capture` (+ `--flightsim` on P1 host)

## Summary

Increment 11 ships **time-driven Guided Capture campaigns**: respondent contact (no auto Person), ordered questions, cadence-driven outbound email (Marvin Gmail lineage adapter), correlated inbound typed/voice responses as **first-class citable testimony**, thin review UI with **credibility**, and Ask cite without Story promotion.

## Criteria

| ID | Result | Notes |
|----|--------|-------|
| I11-A | Harness | Campaign + contact; `people_id` null unless explicitly linked |
| I11-B | Harness | Next question schedules/sends on cadence without prior reply |
| I11-C | Harness | Skip / pause / resume / stop; `outbound_complete` ≠ all answered |
| I11-D | Harness + FS | Typed reply → New response; originals preserved |
| I11-E | Harness + FS | Voice preserve + I5A STT; transcript correctable; audio immutable |
| I11-F | Harness + FS | Review UI + credibility enum + mark reviewed |
| I11-G | Harness | Credibility does not rewrite testimony |
| I11-H | Harness | Ask cites Guided Capture Response without Story |
| I11-I | Harness | Late reply, duplicate, ambiguous quarantine, send/STT fail |
| I11-J | Prior | I1–I10 remains separate |
| I11-K | Docs | OUT list not claimed |
| **I11-OWNER** | **Pending Tom** | Real Gmail loop on FlightSim per definition §13 |

## Surfaces

- UI: `/guided-capture/ui`
- APIs: `/guided-capture/*` (campaigns, tick, poll, responses, credibility, transcript)
- CLI: `prove-guided-capture`
- Migration: `007_guided_capture_i11.sql`
- Email: `MEMORYBOX_GC_EMAIL_PROVIDER=fake|marvin|auto` — live path uses **owner Gmail** (send as owner → Sent; poll owner inbox for replies)

## Email mailbox model (locked)

Outbound questions are sent **through the owner’s configured Gmail account**, so they originate from the owner and appear in **Gmail Sent**. Respondent replies arrive in the **owner’s normal Gmail inbox**; MemoryBox polls, preserves, and correlates them. No separate MemoryBox send mailbox.

## OUT (unchanged)

Multi-user accounts · P2.5 roles · SMS/push · questionnaire CMS · Ask ranking by credibility · collaborative Story · family portal · EVS-140 · kinship · I12 Export · auto-Person from email · in-app self-prompt required for owner gate

## Next

**Stop** — Increment 12 only with new authorization after I11-OWNER acceptance.
