# I14 Phase B — Person Pilot 2 representative packet (Sue)

**Date:** 2026-09-13  
**Status:** **Accepted** 2026-09-13 (12 / 12 packet threads). See [PHASE-B-PILOT-2-SUE-PACKET-ACCEPT.md](PHASE-B-PILOT-2-SUE-PACKET-ACCEPT.md).  
**Private folder (gitignored):** `working/i14-thread-review-pilot-2/`  
**Counts:** `docs/prd/p2-i14/PHASE-B-STEP-2-SUE-PREVIEW-COUNTS.json`

## Timestamp rule

Authoritative time is payload `sent_at` parsed to a UTC instant. Display uses America/Chicago. Tie-break is `evidence_id`. Lexicographic ISO-string sort is not used (it mis-orders mixed offsets).

## Sue corpus (counts only, 2,332 messages / 1,590 threads)

| Measure | Count |
| --- | ---: |
| Threads that lexicographic ISO sort would mis-order | 47 |
| Display order mismatches after UTC sort | 0 |
| Reply-header remnants in cleaned authored text | 0 |
| Forward bodies omitted as duplicates of a thread message | 28 / 26 threads |
| Forwarded messages with tracking URLs in the immutable original | 249 |
| Forwarded commercial (retain/suppress/uncertain) | 361 |
| commercial_suppress | 430 messages / 331 threads |
| commercial_retain (strong trip/life facts) | 74 / 64 threads |
| commercial_uncertain | 53 / 49 threads |

Original-plus-forward duplication is detected by normalized ≥80-character overlap between a forward block and an earlier message in the same canonical thread. Short human replies are not collapsed.

## Packet

12 threads, 22 originals, **44,520** bytes. Same one-file contract. Production I14 writes: false.
