# Eugene affected-only reprocessing proposal

**Status:** design only — not an admission, not authorized to run  
**Purpose:** lifecycle proof after T1 retirement stale cascade  
**Processing authorized:** false  
**Machine-readable plan:** [eugene-affected-reprocessing-proposal.json](eugene-affected-reprocessing-proposal.json)

## Preconditions

1. T1 retirement is complete; admission `1039c733-2149-40b2-b027-97058e032af3` is stopped and stale.
2. Tom, N1, and Eugene Patio admissions remain stopped and current.
3. Browser proxy for `vid-34df63e61b949890` published 2026-09-08 after staged playable-copy validation.
4. Learn, recognition/speech drains, archive processing, and legacy processing remain locked.

## Inspector gate (2026-09-08, second run)

FlightSim read-only inspection after two new Eugene assignments on `grandpa sessions 2 002.MP4`. Pinned evidence: [eugene-reprocessing-candidates-proof.json](eugene-reprocessing-candidates-proof.json).

| Field | Value |
|---|---|
| `fresh_reference_count` | **2** |
| Training reference | `3eb88a19-7249-4ce6-b976-e3066daf205a` |
| Held-out Eugene (same source) | `5d87a6ac-d512-4504-857e-ec8589e8bd78` |
| Transcript version | `aa9d7675-5f50-4685-ba25-3d462f2abf6d` |

Inspector selected **one** fresh training reference (shorter early clear span). The second fresh assignment is held-out only.

## Proposed bounded scope

| Role | Key | Annotation | Source | Interval | Words | Expected |
|---|---|---|---|---|---|---|
| Training | `R1-gs2-fresh` | `3eb88a19…` | `vid-34df63e61b949890` | 00:26.30–00:34.78 | 24 | Eugene reference |
| Held-out | `H1-gs2-held-out` | `5d87a6ac…` | `vid-34df63e61b949890` | 01:26.42–01:45.44 | 65 | Eugene match |
| Held-out | `T2-as-Eugene-negative` | `5e106e50…` | `vid-da41273dbd9ac4bb` | 00:37.12–00:42.40 | 14 | Tom no-match |
| Held-out | `N1-TV-announcer-unknown` | `74cc9646…` | `vid-c015e0fe07414fcc` | 00:00.00–00:06.74 | 31 | Unknown no-match |

Budget: one training span, three held-out spans, ~39.52 seconds selected audio, one attempt per span, no automatic retries. Same four-span voice-pilot shape as the completed Eugene Patio pilot.

## What this run must prove

- Exercises lifecycle/reprocessing controls on a **fresh** Eugene reference after T1 retirement.
- Does not invalidate current Tom, N1, or Eugene Patio stopped/current results.
- Does not establish archive acceptance, overlap/poor-audio acceptance, face/voice corroboration, or generalized accuracy.

## Backup and rollback (required before any run)

1. Create a fresh hash-verified PostgreSQL backup on FlightSim C: before registration (same pattern as Tom/N1/Patio pilots).
2. Record backup path and SHA-256 in a separate readiness note before asking for run authorization.
3. Run read-only preflight rechecking all four annotation IDs, source hashes, and unchanged legacy queue/transcript counts.
4. Rollback is logical: preserve all run records; do not delete results or restore the database without a separate founder decision.
5. After registration, stop the admission in `finally`; no automatic retry.

## Explicit prohibitions

- Do not reuse retired T1 or repurpose prior pilot held-out spans as training.
- Do not use Eugene evidence from `vid-c57dbd21f993f6d1`.
- Do not restart stopped admissions or rerun completed pilots.
- Do not invoke Learn, drains, archive processing, or bare `python` for I13 pilot helpers.

## Current state

Design-only proposal is **ready for founder review**. No admission, backup, deployment helper, or processing run is authorized by this document alone. Next: founder consolidated authorization, then prepare FlightSim readiness package mirroring Patio/Tom/N1 deploy helpers.
