# I14 Phase B — prepared-email loader (build and rehearsal)

**Status:** Built and proven on **disposable PostgreSQL** only. **Not** a production load.  
**Date:** 2026-09-13  
**Branch:** `codex/p2-i14-communications`  
**Schema:** migration **036** (FlightSim empty apply accepted). This document does not authorize writing 035/036 rows on FlightSim.

## Separation of authorizations

| Stage | This build | Needs later founder go-ahead |
| --- | --- | --- |
| Loader build / disposable rehearsal | **Yes** | — |
| Production load as unpublished | No | Yes |
| Generation activation / publication | No | Yes (never called here) |
| Gallery integration | No | Yes |
| I11A narrative / Words of a Life | No | Yes |

## Product intent (locked)

One **household-email** prepared generation. Each eligible communication is stored once. People (Peggy, Sue, others) attach through `comms_prepared_participants`. Evidence originals are never updated. Unknown From/To/Cc stay unverified with `person_id` NULL. Voice corpus is authenticated **From** only.

## Deterministic consolidation rule (`i14-household-email-consolidate-v1`)

Do **not** merge, delete, or suppress `evidence` because text is similar.

| Class | How it is recognized | Prepared-layer action |
| --- | --- | --- |
| Exact duplicate evidence | Same complete `content_hash` inside one `source_id` | Display earliest UTC (`sent_at`, then `evidence_id`); extras omitted; evidence rows unchanged |
| Same communication, multiple extracts | Same hash across sources **or** same RFC-own token on ≥2 evidence rows | Same survivor rule; extras counted `duplicate_omitted`; lineage is the displayed `evidence_id` + 035 `canonical_record_id` |
| Quoted / forwarded overlap | Different hash and RFC; body overlap only | **Not a duplicate.** Both rows can become prepared messages. Forward body may be omitted from *prepared text* when already represented (`forward_omitted`) |
| Genuinely separate similar messages | Different hash and RFC | Always two prepared messages |

Unexplained loss (`eligible − displayed − duplicates − excluded`) must be **0**.

## Audit

`memorybox/ops/i14_duplicate_audit.py` remains counts-only, TEMP + rollback, keyset batches, statement timeout + run deadline. It refuses FlightSim hosts and dbname `memorybox`. Bodies are never read, so quoted/forwarded overlap is **not** inferred on a live corpus; that class is proven in unit/loader tests.

## Loader

`memorybox/ops/i14_prepared_loader.py`

- Refuses FlightSim DSN and dbname `memorybox`.
- Writes only on the connection it is given (tests: disposable DB).
- Inserts one unpublished, inactive `validated` generation.
- Requires 035 `canonical_record_id` on every prepared message.
- Rolls back the whole generation on failure (`run_load`).
- Idempotent on the same displayed checksum.
- Never calls `comms_prepared_activate_generation`.

## Tests

```
python -m unittest tests.test_i14_consolidation tests.test_i14_prepared_loader tests.test_i14_duplicate_audit tests.test_i14_prepared_text
```

## Founder review

**Read:** this file and [PHASE-B-PREPARED-LOAD-FORECAST.json](PHASE-B-PREPARED-LOAD-FORECAST.json).  
No HTML dump. No corpus TXT. Synthetic rehearsal used `example.test` addresses only.

**Judgment needed (product, not mechanics):**

1. Accept survivor = earliest UTC instant, then `evidence_id`, for identity-key duplicates?
2. Accept that similar bodies with different hash **and** RFC stay two messages?
3. Accept that production quoted/forward overlap is handled at prepared-text time, not by the identity audit?
4. Note schema cap: `evidence_ref` allows at most **99** messages per thread (`M-NN`). Long threads above that must be a later schema/split decision.

Do not treat this commit as permission to load FlightSim.
