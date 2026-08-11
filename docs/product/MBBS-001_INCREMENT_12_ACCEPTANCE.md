# MBBS-001 Increment 12 — Minimum Viable Export (EF-16) — Acceptance

**Status:** **READY FOR OWNER ACCEPTANCE** (FlightSim I12-OWNER)  
**Date:** 2026-08-11  
**Definition:** [MBBS-001_INCREMENT_12_DEFINITION.md](MBBS-001_INCREMENT_12_DEFINITION.md) — Final Definition  
**Prove:** `python -m memorybox prove-export` (+ `--flightsim` with `MEMORYBOX_P1_RUNTIME_HOST=1`)

## Harness

Desktop/CI-style prove seeds Story/Journal version history, People relationship supersede history, Guided Capture Response with campaign/question/respondent context + promotion link, MB-managed Artifact bytes, and an Immich-like **externally referenced** evidence row — then builds `memorybox_export_format: 1` folder (+ optional ZIP) and verifies README, retained versions, GC context, SHA-256, and no Immich mirror.

## FlightSim owner gate (I12-OWNER)

1. Ensure Story / Journal / Guided Capture / People / relationship data exists.  
2. Ensure at least one retained version history exists where practical.  
3. Ensure at least one MB-managed original exists.  
4. Set `MEMORYBOX_EXPORT_DIR` to a real writable path (config/env — no hard-coded host path in product).  
5. Open `/export/ui` and start export without SQL.  
6. Open README outside MemoryBox.  
7. Inspect machine-readable tables outside MemoryBox.  
8. Confirm current + retained version history where present.  
9. Confirm Guided Capture response includes prompting question / respondent context.  
10. Verify at least one packaged file against MANIFEST SHA-256.  
11. Confirm MB-managed originals are included.  
12. Confirm external Immich/HVRT media are referenced rather than bulk copied.  
13. Confirm export succeeds without requiring active Immich/HVRT for MB-local knowledge.  
14. Confirm no subscription / vendor portal is required.

## OUT (unchanged)

Full Immich/HVRT mirror · pretty publishing · cloud escrow · multi-user share · import-back (TASK-P1P2-003) · P2 Dashboard · kinship · GC polish · SMS · EVS-140
