# I14 Phase B — prepared-email loader (build and rehearsal)

**Status:** One unpublished household-email generation is loaded on FlightSim (`validated`, not active, not published). Founder visual review **accepted** 2026-09-14. Activation/Gallery/I11A remain separate execute gates. See [PHASE-B-038-ACTIVATION-REVIEW-ACCEPT.md](PHASE-B-038-ACTIVATION-REVIEW-ACCEPT.md) and [PHASE-B-038-ACTIVATION-PLAN.md](PHASE-B-038-ACTIVATION-PLAN.md).

Voice is household-wide: any authenticated canonical From Person may qualify. `IdentityLedger.focal_person_id` does not gate another Person’s authored voice.

## Production load (unpublished, inactive)

Requires FlightSim ledger **001–038**, pending empty, and either empty 035/prepared tables or one unpublished `validated` snapshot with:

```
MEMORYBOX_I14_REPLACE_UNPUBLISHED=1
MEMORYBOX_I14_REPLACE_CONFIRM=replace-unpublished-voice-038-v1
```

```
MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM=1
MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB=1
MEMORYBOX_I14_LOAD_CONFIRM=household-email-unpublished-v1
MEMORYBOX_I14_CENSUS_ALLOW_FLIGHTSIM=1
MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB=1
```

```powershell
C:\MemoryBox\.venv\Scripts\python.exe -m memorybox i14-prepared-load
```

Never calls `comms_prepared_activate_generation`. Failure marks the generation `failed` (unpublished, inactive) when batches were persisted.

Private review (gitignored): `MEMORYBOX_I14_REVIEW_EMIT_PRIVATE=1` and `MEMORYBOX_I14_REVIEW_OUT`.

Activation-review packet (gitignored, max 12 threads, TXT only): `python -m memorybox i14-activation-review` with the same private-emit flags plus `MEMORYBOX_I14_VOICE_DELTA_ALLOW_FLIGHTSIM=1`. Output: `working/i14-activation-review/` (`INDEX.txt`, `packet-001.txt`, `originals/<Evidence-ref>.txt`). Do not activate from the packet.

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
python -m unittest tests.test_i14_consolidation tests.test_i14_prepared_loader tests.test_i14_duplicate_audit tests.test_i14_prepared_text tests.test_p2_i14_037_schema tests.test_i14_preload_census tests.test_i14_prepared_load_prod
```

## Review

Counts-only: [PHASE-B-PRELOAD-VALIDATION.md](PHASE-B-PRELOAD-VALIDATION.md) and JSON beside it. No HTML dump. No corpus TXT. Private 12-thread packets are gitignored (`working/i14-household-email-review-038/`, `working/i14-activation-review/`).
