# MBBS-001 Increment 12 — Minimum Viable Export (EF-16) — Acceptance

**Status:** **ACCEPTED** (FlightSim owner 2026-08-11)  
**Date:** 2026-08-11 (accepted)  
**Definition:** [MBBS-001_INCREMENT_12_DEFINITION.md](MBBS-001_INCREMENT_12_DEFINITION.md) — Final Definition  
**Prove:** `python -m memorybox prove-export` (+ `--flightsim` with `MEMORYBOX_P1_RUNTIME_HOST=1`)

## Harness

Desktop/CI-style prove seeds Story/Journal version history, People relationship supersede history, Guided Capture Response with campaign/question/respondent context + promotion link, MB-managed Artifact bytes, and an Immich-like **externally referenced** evidence row — then builds `memorybox_export_format: 1` folder (+ optional ZIP) and verifies README, retained versions, GC context, SHA-256, and no Immich mirror.

## FlightSim owner gate (I12-OWNER) — PASSED

Owner ran export from `/export/ui` to a local folder; package produced with real archive counts. Default destination corrected to **`C:\memorybox_exports`** when unset / when configured drive is missing (was incorrectly suggested as `D:\`).

## OUT (unchanged)

Full Immich/HVRT mirror · pretty publishing · cloud escrow · multi-user share · import-back (TASK-P1P2-003) · P2 Dashboard · kinship · GC polish · SMS · EVS-140

**Next (done):** [MBBS-001_INCREMENT_12A_ACCEPTANCE.md](MBBS-001_INCREMENT_12A_ACCEPTANCE.md) — thin Status — **ACCEPTED**; [P1 closeout](MBBS-001_P1_CLOSEOUT.md)
