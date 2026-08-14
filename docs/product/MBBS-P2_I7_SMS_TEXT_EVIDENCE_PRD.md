# MBBS — P2-I7 SMS/Text Evidence · Product Request Document

**Status:** **DRAFT for review** · **NO BUILD**  
**Date:** 2026-08-14  
**Owner:** Tom  
**Increment:** P2-I7 (MBRM-001A) — SMS/Text Evidence · A  
**Definition (review this):** [MBBS-P2_INCREMENT_7_DEFINITION.md](MBBS-P2_INCREMENT_7_DEFINITION.md)  
**Depends:** P2-I6 **ACCEPTED**

## Problem

Text messages are staged (Archive Health: CSV under `Sources/sms`) but **ingest is still “Not connected in P1.”** Ask/Explore can talk about SMS as a type; they cannot search a real thread. Email already uses communication Evidence. SMS is the missing first-class channel (MBPS P2-COM-01 · CAP-P2-018).

This matters now because I6 is closed. MBRM-001A’s next increment is SMS, not another Person/kinship slice.

## Success criteria

On FlightSim, after a later authorized build: imported texts for a known Person (propose Peggy) are **shown, counted, and citable** in Ask; dated SMS cards can appear on the existing Explore / Person canvas; Archive Health reports honest ingest; originals are untouched; gaps are disclosed. See definition §8.

## Scope IN

Ingest confirmed export · communication Evidence · phone→Person · Ask EVS-220–223 (and 065/118/224 per Q6) · existing Explore SMS type · Archive Health honesty.

## Scope OUT

Richer email (I8) · live phone sync · SMS app / new nav · I6 reopen · I5 portrait · I8.5 face evidence · trip/year narrative (I11) · inventing messages · Explore redesign.

## Constraints

- Reuse email ingest + `evidence_kind=communication`. Do not invent a second SoT.  
- Canonical MB Person IDs; phone is a mapping.  
- I3 honesty: unavailable ≠ 0.  
- I4 canvas is the UX; do not fork a messaging UI.

## Discovery

See definition §6. Email ingest, phone identity, Ask `want_communication`, Explore `sms`/`text` types, and Archive Health `staged_sms` already exist.

## Open questions

Definition §1 **Q1–Q6**. **Q1 (export path/format) and Q2 (acceptance people/years) block build.**

## Build plan

Definition §7 — **not authorized**.

## Sign-off

**Review only.** Tom: lock Q1–Q2 (and accept or change Q3–Q6), then explicitly authorize build. Until then: **no I7 runtime.**
