# MBBS — P2-I7 SMS/Text Evidence · Product Request Document

**Status:** **BUILD AUTHORIZED** (2026-08-14 — Tom: “approved to build”) · **not ACCEPTED**  
**Date:** 2026-08-14 (build)  
**Owner:** Tom  
**Increment:** P2-I7 (MBRM-001A) — SMS/Text Evidence · A  
**Definition (lock this):** [MBBS-P2_INCREMENT_7_DEFINITION.md](MBBS-P2_INCREMENT_7_DEFINITION.md)  
**Depends:** P2-I6 **ACCEPTED** · I1–I6 ACCEPTED

## Problem

Text messages are staged on media-server (`Sources\sms\Messages - 1085 chat sessions.csv`, checkpoint 2026-08-09) but ingest is still deferred. Ask/Explore can name SMS as a type; they cannot search a real thread. Email already uses communication Evidence. SMS/iMessage is the missing first-class channel (MBPS P2-COM-01 · CAP-P2-018).

This matters now because I6 is closed. I7 must ingest **and keep** enough source metadata that later “Alaska texts in the Alaska trip” work does not re-import the export — without doing that correlation in I7.

## Success criteria

Definition §8 (24 FlightSim gates): real ingest, source-fidelity check, Person/date/keyword retrieve, outbound + bidirectional counts with scope, identity mapping without silent merge, group threads preserved when present, attachments linked not promoted, correlation metadata preserved, honesty in Archive Health, existing Ask/Explore/Person surfaces only.

## Scope IN / OUT

IN/OUT as definition §§3–4. Explicitly **not** I8 richer email, I9 spoken, I10 correlation, I11 narrative, I13/I14 Settings, multi-user, or I4 Explore redesign.

## Constraints

- Parser is header-driven (this cloud revision did not open the real CSV bytes). FlightSim `inspect-sms` records real headers.  
- One communication Evidence model; preserve unused columns in source_metadata.  
- Canonical MB Person IDs; phone/handle is mapping only.  
- Unavailable ≠ 0.  
- No new messaging product.  
- Default Gallery hides SMS/Text on broad memory asks; “Add texts” / “Only texts” / explicit text asks override. Visibility ≠ exclusion. Query language = **MBQL-001 after I7 ACCEPTED**, not this increment.

## Discovery

Definition §§1.1 and 6. Documented path from Sources checkpoint; **row-level format still uninspected** from this environment.

## Q1–Q6

| # | Status |
|---|--------|
| Q1 | Path documented; **bytes not opened here** — `inspect-sms` on FlightSim |
| Q2 | Real-corpus rules locked; names after sample |
| Q3–Q6 | **LOCKED** (definition §1) |

## Build plan

Definition §7 — **authorized and implemented** this revision (`ingest-sms`, Ask/Explore/Archive Health, `prove-p2-i7`).

## Sign-off

Tom authorized build 2026-08-14 (“approved to build”). ACCEPTED still requires definition §8 on FlightSim against the real staged export.
