# I14 Phase B — prepared-email loader (build and rehearsal)

**Status:** Directionally accepted (2026-09-13) plus pre-load validation. **Not** a production load.  
**Schema:** 036 remains the prepared tables. **037** (repo only) widens `display_id` / `evidence_ref` CHECKs. FlightSim still empty; 037 not applied.

## Founder decisions (locked)

1. Survivor = earliest UTC instant, then `evidence_id`.
2. Similar text with a different full content hash **and** a different RFC stays two prepared messages.
3. Quoted/forwarded overlap is prepared-text cleanup, not evidence merge.
4. The 99-message `M-NN` cap is removed from the design (migration 037). Live max thread size is 89; **40996** threads still require `T-[0-9]{4,}` because 036 allowed only four thread digits.

## Completeness (live)

`eligible/mbox universe 91281 = prepared 91247 + identity omitted 26 + excluded-in-stream 2 + held 6 + unexplained 0`.

Evidence originals are never updated. Identity extras keep survivor lineage.

## Tests

```
python -m unittest tests.test_i14_consolidation tests.test_i14_prepared_loader tests.test_i14_duplicate_audit tests.test_i14_prepared_text tests.test_p2_i14_037_schema tests.test_i14_preload_census
```

## Review

Counts-only: [PHASE-B-PRELOAD-VALIDATION.md](PHASE-B-PRELOAD-VALIDATION.md) and JSON beside it. No HTML dump. No corpus TXT.

Production unpublished load remains a separate founder authorization. Apply **037** on FlightSim before that load.
