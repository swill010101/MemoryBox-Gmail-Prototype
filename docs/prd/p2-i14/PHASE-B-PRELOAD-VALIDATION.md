# I14 Phase B — pre-load validation (counts only)

**Status:** Validation complete. **Production load not performed.**  
**Date:** 2026-09-13  
**Branch:** `codex/p2-i14-communications`  
**Live census:** read-only FlightSim Postgres; rollback; no 035/036/037 row inserts; prepared tables remain empty.

Founder decisions accepted: earliest-UTC then `evidence_id` survivor; different hash **and** different RFC stay two messages; quoted/forward overlap is prepared-text cleanup; the 99-message cap is not an unexplored production limit.

## Thread cap

Live household-email reconstruction:

| Metric | Count |
| --- | --- |
| Threads | 40996 |
| Threads with more than 99 messages | **0** |
| Maximum thread size | **89** |

036 still locked `display_id` to exactly four digits (`T-NNNN`) and `evidence_ref` to `M-NN`. This corpus has **40996** threads, so `T-40996` would fail 036 even though no thread exceeds 99 messages.

**Disposition:** additive migration `037_p2_i14_prepared_evidence_ref_scale.sql` widens both CHECKs to `T-[0-9]{4,}-M-[0-9]{2,}`. `T-0001` and `T-0001-M-01` keep their meaning. The loader no longer aborts at 99. **037 is in the repo and proven on disposable Postgres. It is not applied on FlightSim in this gate.** Apply 037 before any production unpublished load.

## Six held rows

All six mbox rows outside the assigned extract now have a reason. Unexplained hold = 0.

| Reason | Sources | Rows |
| --- | --- | --- |
| `held_testish_landing_uri` | 1 | 1 |
| `held_tiny_below_assign_threshold` | 1 | 5 |

Assigned household email remains the single large mbox (91275 rows).

## RFC fanout (household email)

The earlier corpus-wide 13 RFC-own token groups are **entirely** in the assigned household-email extract: 13 groups inside assigned email, 0 mixed, 0 outside. SQL extras for those groups = 13.

The loader identity rule unions **content_hash and RFC-own**. That omits **26** assigned rows (all with survivor lineage). Completeness uses the loader omit count, not the SQL-only RFC extra count.

## Completeness

`91281 = 91247 + 26 + 2 + 6 + 0`

- eligible assigned: 91275 = 91247 prepared + 26 identity omitted + 2 missing From
- held 6 accounted by reason
- unexplained **0**

Evidence is not deleted or updated. Omitted duplicates retain `duplicate_of` survivor lineage (26/26).

## Forecast (live counts)

See [PHASE-B-PRELOAD-VALIDATION.json](PHASE-B-PRELOAD-VALIDATION.json). Voice-by-Person is authenticated From with clean quote, not the census’s arbitrary focal Person (`voice_corpus_messages_focal` is 0 because the census focal is the first `people.display_name`, not a production focal choice).

Quote/commercial counts used independent per-message cleanup (hard deadline). Production load still uses in-thread quote prior; those class counts may shift slightly.

## Duplicate audit

Keyset batches, 30s statement timeout, 600s census deadline (audit finished in 49.9s). Progress on stderr. Failure path is `{ok:false,error}` without a partial `ok:true` report.

## Not this gate

No unpublished generation, no activate/publish, no Gallery, no I11A. Do not `python -m memorybox migrate` on FlightSim until founder authorizes 037 apply and/or production load.
