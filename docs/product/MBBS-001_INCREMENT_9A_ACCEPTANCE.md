# MBBS-001 Increment 9A — Person Profile acceptance

**Status:** READY FOR FLIGHTSIM OWNER ACCEPTANCE  
**Date:** 2026-08-11  
**Definition:** [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md)

## Harness (already green on FlightSim)

```powershell
cd C:\memorybox
git pull
python -m memorybox migrate
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
# harness uses a temporary synthetic owner; still set real owner for Ask path below
python -m memorybox prove-person-profile --flightsim
```

## Owner acceptance gate (I9A-OWNER) — what Tom proves by hand

Prerequisite: `$env:MEMORYBOX_OWNER_PERSON_ID` = canonical **Tom Will** `people.id` (I6-merge duplicate Toms first if needed), then restart `python -m memorybox serve`.

| Step | Do this | Pass when |
|------|---------|-----------|
| 1 | Open `/people/ui` | Unified name list loads (MB + Immich, each name once); no UUID paste required |
| 2 | Open **Eugene Will** profile | Identity / names / facts / contacts / relationships / life events / photo links show as distinct sections |
| 3 | Save Eugene **birth date** `06-11-1927` (or calendar / `06111927`) | Fact shows as **06-11-1927** on profile |
| 4 | Assert **Eugene is the father of** owner (Tom) | Relationship appears; inverse wording also shown |
| 5 | Record **Eugene & Anne** marriage `09-25-1947` | Shared life event on both; one date |
| 6 | Ask: **Who is my father?** | Answer names Eugene (domain resolve — not a string hack) |
| 7 | Ask: **When was my father born?** | **06-11-1927** / 1927-06-11 birth fact |
| 8 | Ask: **Show me pictures of my father.** | Resolves to Eugene, then existing photo path (empty OK if no Immich map) |
| 9 | Optional: add/correct email or **10-digit** phone on profile contact cards | Contact appears; tap card to change |

## Success criteria checklist (from definition §5)

| ID | Criterion | Who proves |
|----|-----------|------------|
| **I9A-A** | Layered model (not flat Person god-row) | Harness ✓ |
| **I9A-B** | `MEMORYBOX_OWNER_PERSON_ID`; never infer “me” via display_name | Harness ✓ + FS env |
| **I9A-C** | Eugene birthdate with provenance | Harness ✓ + **owner step 3** |
| **I9A-D** | Eugene `father_of` owner; inverse child | Harness ✓ + **owner step 4** |
| **I9A-E** | Inverse from same SoT (no dual editable inverse rows) | Harness ✓ |
| **I9A-F** | Multi-qualified parents; ambiguity disclosed | Harness ✓ |
| **I9A-G** | Shared Eugene↔Anne marriage/anniversary | Harness ✓ + **owner step 5** |
| **I9A-H** | Ask “Who is my father?” → Eugene | **Owner step 6** |
| **I9A-I** | Ask “When was my father born?” | **Owner step 7** |
| **I9A-J** | Ask “Show me pictures of my father.” | **Owner step 8** |
| **I9A-K** | Correction uncle→father; prior provenance kept | Harness ✓ |
| **I9A-L** | Aliases + contacts with provenance; ≠ provider identity | Harness ✓ + optional step 9 |
| **I9A-M** | `/people/ui` Profile surface coherent | **Owner steps 1–2** |
| **I9A-N** | Missing/ambiguous disclosed | Harness ✓ |
| **I9A-O** | I6 mappings unchanged by profile writes | Harness ✓ |
| **I9A-P** | Prior proves still runnable | `prove-artifact` ✓ |
| **I9A-OWNER** | Full FS path above without SQL/dev help | **Tom** |
| **I9A-Q** | Living specs updated | Docs |
| **I9A-R** | Out of scope not claimed | Note |

## Explicitly OUT (do not block acceptance)

EVS-014 · genealogy tree viz · auto-inferred family · Immich write-back · multi-user · Places/Event platform · universal lazy-teach · polish / “less clunky” chrome
