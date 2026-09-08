# Eugene affected-only reprocessing proposal

**Status:** design only — not an admission, not authorized to run  
**Purpose:** lifecycle proof after T1 retirement stale cascade  
**Processing authorized:** false

## Preconditions

1. T1 retirement is complete; admission `1039c733-2149-40b2-b027-97058e032af3` is stopped and stale.
2. Tom, N1, and Eugene Patio admissions remain stopped and current.
3. Read-only inspector output from FlightSim is recorded below or attached before founder review.
4. Learn, recognition/speech drains, archive processing, and legacy processing remain locked.

## Inspector gate

FlightSim read-only inspection completed **2026-09-08** from `C:\MemoryBox` using tool release `p2-i13-voice-pilot-6d56da5`. Pinned evidence: [eugene-reprocessing-candidates-proof.json](eugene-reprocessing-candidates-proof.json).

| Field | Value |
|---|---|
| `fresh_reference_count` | **0** |
| Selected fresh reference `annotation_id` | **none — blocked** |
| Inspector run date | 2026-09-08 |

### Why every current Eugene assignment is ineligible

| Annotation | Key / note | Block |
|---|---|---|
| `6b41bd21…` | T3-patio | Used as training in Patio pilots |
| `5651a4bd…` | U1-clear | Prior pilot held-out; source `vid-c57dbd21f993f6d1` excluded |
| `d5a3d050…` | T1 | Retired |
| `b4e5fd32…` | E3-patio-held-out | Prior pilot held-out |
| `f47ee4ec…` | H1 | Prior pilot held-out; source excluded |
| `bbceb696…` | No pilot key yet | **No prior pilot use**, but same excluded 1532 source — inspector marks ineligible |

**Conclusion:** affected-only reprocessing proposal remains **blocked** until Tom saves one new clear Eugene assignment.

### Owner action required before this proposal can advance

1. In MemoryBox Review/Explore, select a **clear Eugene passage** on a source **other than** `vid-c57dbd21f993f6d1` (`20111105_1532.MP4`).
2. Prefer a distinct interval on an already-reviewed clean source, for example:
   - `vid-da41273dbd9ac4bb` (`20111105_1530.MP4`) — new span, not T1
   - `vid-8163a680131fd30a` (`Grandpa sessions 003.MP4`) — new span, not T3/E3 intervals
   - Another manifest source only after listening confirms clean single-speaker Eugene audio
3. Assign **Eugene Will** and save. Do not mark Unknown. Do not reuse retired T1, H1, U1-clear, N1, or Q1 intervals.
4. Rerun the inspector on FlightSim. Proceed only when `fresh_reference_count` is **1** (select exactly one eligible row).

### If count becomes positive

Select exactly one row with `eligible_fresh_reference: true`. Pin that annotation as the sole new training reference. Define fresh held-out spans that were not used as training in any prior pilot. Do not silently convert prior held-out evidence into training.

## Proposed bounded scope (template)

Fill only after inspector selection is pinned.

| Role | Key | Annotation ID | Source | Interval | Expected |
|---|---|---|---|---|---|
| Training | `R1-fresh` | _TBD_ | _TBD_ | _TBD_ | Eugene Will reference only |
| Held-out | `H-new-1` | _TBD_ | _TBD_ | _TBD_ | Eugene match |
| Held-out | `H-new-2` | _TBD_ | _TBD_ | _TBD_ | Eugene match or agreed control |
| Held-out | `T2-negative` | `5e106e50-76ce-4fb2-8f62-0083119154cc` | `vid-da41273dbd9ac4bb` | 00:37.12–00:42.40 | Tom no-match control |

Budget mirrors existing voice pilots: one training span, up to three held-out spans, one attempt per span, no automatic retries, unchanged legacy queue/transcript counts.

## What reprocessing must prove

- Retirement stale cascade already verified for T1.
- A separately approved affected-only reprocessing run exercises lifecycle controls without invalidating current Tom, N1, or Patio evidence.
- No archive acceptance, generalized accuracy, overlap/poor-audio acceptance, or Learn unlock is implied.

## Backup and rollback (required before any run)

1. Create a fresh hash-verified PostgreSQL backup on FlightSim C: before registration, same pattern as Tom/N1/Patio pilots.
2. Record backup path and SHA-256 in a separate readiness note.
3. Rollback is logical: preserve all run records and stale markers; do not delete results or restore the database without a separate founder decision.
4. If preparation fails before registration, production remains unchanged.
5. After registration, stop the admission in `finally`; no automatic retry.

## Explicit prohibitions

- Do not reuse retired T1 (`d5a3d050-76d6-446e-91d4-ff89986856cb`).
- Do not use Eugene evidence from `vid-c57dbd21f993f6d1`.
- Do not restart stopped admissions or rerun completed pilots.
- Do not invoke Learn, drains, archive processing, or bare `python` on FlightSim helpers.

## Next step after inspector JSON

**Current state (2026-09-08):** `fresh_reference_count = 0`. Tom must save one new clear Eugene assignment, rerun the inspector, then return here to finalize spans and `eugene-affected-reprocessing-proposal.json` for consolidated founder authorization. No run is authorized yet.
