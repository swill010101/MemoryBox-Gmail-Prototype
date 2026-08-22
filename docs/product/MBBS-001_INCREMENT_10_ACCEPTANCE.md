# MBBS-001 Increment 10 — Cross-provider Person acceptance

**Status:** READY FOR FLIGHTSIM OWNER ACCEPTANCE  
**Date:** 2026-08-11  
**Definition:** [MBBS-001_INCREMENT_10_DEFINITION.md](MBBS-001_INCREMENT_10_DEFINITION.md)

## Harness (desktop / FlightSim)

```powershell
cd C:\memorybox
git pull
python -m memorybox migrate
# Synthetic (no Immich/HVRT required):
python -m memorybox prove-cross-provider-person

# FlightSim final (HVRT worker MUST be running — photo-only invalid):
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_VIDEO_PROVIDER = "hvrt"
$env:MEMORYBOX_VIDEO_WORKER_URL = "http://127.0.0.1:8791"
# After owner teach (below), set:
# $env:MEMORYBOX_I10_OWNER_PERSON_ID = "<people.id with Immich + HVRT mappings>"
python -m memorybox prove-cross-provider-person --flightsim
```

## Owner acceptance gate (I10-OWNER)

**Prerequisite:** Video worker + serve with HVRT (see FlightSim commands in agent reply / ops). One **real family Person** already named in **Immich**, and present in **≥1 real HVRT-processed family video**.

| Step | Do this | Pass when |
|------|---------|-----------|
| 1 | Confirm Immich has a trusted named identity for the Person | Immich People list shows them |
| 2 | Open `/review/ui`, pick that family video, create face candidate, box face | Box confirmed |
| 3 | **Attach to existing MB Person** (picker) if they already exist from Immich/People — **or** Teach by name when Immich bootstrap can seed uniquely. On ambiguity, pick the MB Person — **do not** invent a second Person | Archive Updated; one `people.id` |
| 4 | Ask: `show me <Name>` | Immich **photos** and HVRT **videos** for that Person; provider provenance visible |
| 5 | Library: filter same Person | Same Person X; Immich and/or HVRT cards via same mappings (no new Library UX) |
| 6 | Optional `$env:MEMORYBOX_I10_OWNER_PERSON_ID` to that id; re-run prove `--flightsim` | Owner checks green |

## Success criteria checklist

| ID | Criterion | Who proves |
|----|-----------|------------|
| **I10-A** | Immich trusted + HVRT teach → one `people.id` | Harness ✓ + owner step 3 |
| **I10-B** | Ask photo + video hits | Harness ✓ + owner step 4 |
| **I10-C** | No display-name-only merge; owner map path | Harness ✓ |
| **I10-D** | Ask + Library same Person / mappings | Harness ✓ + owner step 5 |
| **I10-E** | Reprocess reconcile; rebuildable projection | Harness ✓ |
| **I10-F** | Provider unavailable visible | Harness ✓ |
| **I10-G** | Provider UUID ≠ `people.id` | Harness ✓ |
| **I10-H** | I9A relational smoke | Harness ✓ |
| **I10-I** | Prior proves remain runnable | Ops |
| **I10-OWNER** | Real Immich + real HVRT video; worker running; normal UI | Tom |
| **I10-J** | Living specs updated | Docs |
| **I10-K** | Exclusions not claimed | Note |

## Exclusions (not I10)

Kinship inference → TASK-P1P2-002 (P2) · universal lazy-teach · Immich write-back · auto tree · tree viz · multi-user · Guided Capture · Export · Settings/polish · reopening I9A
