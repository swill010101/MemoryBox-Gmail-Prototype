# MBBS — P2-I6 Relationship Graph, Relationship UX & Derived Kinship · PRD

**Status:** **ACCEPTED** (Tom 2026-08-14 — “i6 passes”)  
**Date:** 2026-08-14  
**Owner:** Tom  
**Increment:** P2-I6 (MBRM-001A) — Kinship Inference · A (+ Relationship UX)  
**Branch:** `cursor/p2-i6-relationship-kinship-3061` (from I5 ACCEPTED)  
**Depends:** P2-I5 ACCEPTED  
**Acceptance record:** [MBBS-P2_INCREMENT_6_DEFINITION.md](MBBS-P2_INCREMENT_6_DEFINITION.md)

## Problem

Relationships are stored as thin SoT edges with inverse projection only. Users teach family via admin redirect; no Direct vs Derived UX; Ask cannot answer cousins / how-related / grandchildren composition (EVS-204–210).

## Success criteria

Per I6 directive §12 (modal CRUD, reciprocal consistency, derived + path explain, Ask EVS-204–210 relationship portion, no family tree, I5 intact).

## Scope IN

- Relationships **modal** over Person Explorer (dark I5 language)
- Direct groups: Parents / Siblings / Spouse·Partner / Children
- Add / Edit / Change Person / Remove / View History
- Reciprocal via existing one-edge SoT + inverse projection (extend labels)
- Multi-hop kinship derivation + explainable paths
- Ask integration for EVS-204–210 as far as media/identity allow

## Scope OUT

- Graphical family tree
- New nav / Relationship Health / Export Relationships / Review Possible Matches
- Persisting derived kinship as editable SoT
- New face recognition (EVS-209 uses existing recognized People only)
- I5 reopen / Immich portrait P2-BL-I5-01

## Constraints

- Canonical MB Person IDs only
- Owner-entered = high authority with provenance/history
- Derived ≠ asserted; correction fixes underlying direct edges then recomputes
- Neutral reciprocal when gender unsafe to invent

## Discovery (pre-build)

| Area | Finding |
|------|---------|
| SoT | `person_relationship_assertions` (005) — reuse |
| Inverse | `project_derived_edges` — keep; do not dual-store reciprocal |
| I5 UI | Family drawer + admin redirect — replace write path with modal |
| Ask | Direct roles only — extend kinship intents |
| Blockers | **None** |

## Build plan

1. `profile/kinship.py` — graph + paths  
2. GET relationships bundle API + history  
3. Relationships modal (Direct / Extended tabs)  
4. Ask EVS-204–210  
5. `prove-p2-i6` acceptance  

## Sign-off

Tom: I6 directive + “if no questions or blockers you are approved to build” (2026-08-14).  
**Increment:** **ACCEPTED** (2026-08-14 — Tom: “i6 passes”). EVS-209 kinship-in-photo = backlog **P2-BL-I6-01** (not a reopen). Next: I7 SMS definition (no build until authorized).
