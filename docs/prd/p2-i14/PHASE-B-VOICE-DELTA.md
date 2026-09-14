# I14 Phase B — authored-voice delta (unpublished generation)

**Status:** Read-only investigation complete. Production rows were not updated. Not activated. Not published. Gallery/I11A remain unauthorized.

**Code SHA:** recorded at commit time in git. Runtime on FlightSim remains the unpublished generation created before this investigation.

## Safety (FlightSim, SELECT only)

| Check | Result |
| --- | --- |
| Successful unpublished generations | **1** (`validated`, unpublished, inactive) |
| Failed generations | **0** (first URL-CHECK attempt discarded; cannot activate) |
| Published generations | **0** |
| Active generations | **0** |
| Archive evidence / sources / RFC ids | **188656 / 27 / 287010** (unchanged) |
| Completeness | `91281 = 91247 + 26 + 2 + 6 + 0`; unexplained **0** |

## Why Tom dropped 12,071 → 1,884

Accepted census labeled authored voice as **authenticated From + `quote_quality=clean`** (`authenticated_from_clean_quote_by_person_label`). That count is still sitting on the loaded rows:

| Person | Census (quote-clean From) | Loaded `voice_corpus` | Gap |
| --- | ---: | ---: | ---: |
| Tom | 12071 | 1884 | 10187 |
| Peggy | 1342 | 1149 | 193 |
| Sue | 307 | 299 | 8 |

Loaded `voice_corpus` also required `identity_quality=resolved`. Unverified To/Cc set `ambiguous_participant`, which stored `identity_quality=uncertain` and **blocked From voice**. Every census-not-loaded row for these three people is in that bucket.

### Exclusive reasons (census quote-clean From, not loaded voice)

| Reason | Tom | Peggy | Sue |
| --- | ---: | ---: | ---: |
| identity / unverified recipient (`identity_quality=uncertain`) | 10187 | 193 | 8 |
| quote contamination | 0 | 0 | 0 |
| cleaned empty/trivial (exclusive) | 0 | 0 | 0 |
| From-participant mismatch | 0 | 0 | 0 |
| commercial suppression (exclusive) | 0 | 0 | 0 |
| forward/history (exclusive) | 0 | 0 | 0 |
| sequential prior removed new authored | 0 | 0 | 0 |

### Overlap flags on the same identity-uncertain, quote-clean, not-voice rows

These did **not** cause the voice drop (quote is already clean). They describe the same messages:

| Flag | Tom | Peggy | Sue |
| --- | ---: | ---: | ---: |
| cleaned empty or &lt;20 chars | 679 | 25 | 2 |
| commercial `suppress_default` | 1132 | 12 | 0 |
| forward_status not none | 2439 | 9 | 3 |

Tom From messages that are **not** census voice candidates are quote-contaminated (21726 = 19743 uncertain + 1983 resolved). Quote-exception corpus total remains **34488**.

## Sequential prior is not the Tom reduction

A full-thread recompact (40,996 threads, ~955s, read-only) compared independent per-message cleanup to in-thread prior:

- Tom: **0** messages lost newly authored sentences and also lost voice.
- Sue: **0**.
- Peggy: **2** messages lost a new sentence **and still remained voice** (not the census gap).
- Stored `voice_corpus` matched sequential recompute (**0** mismatches).

Unique new lines after a prior blob still survive `_remove_prior_blob` in unit tests. Tom’s drop is not “this looks like earlier text.”

## Rule correction (not applied to FlightSim)

Loader voice is now **authenticated From + clean quote**. `identity_quality` may stay `uncertain` when To/Cc are unverified. Migration **038** replaces the 036 CHECK that forbade `voice_corpus` unless identity was resolved.

Proven on disposable Postgres (`test_household_voice_is_authenticated_from_not_focal_person`). **038 is not applied on FlightSim. Production prepared rows were not updated.**

## Retain or replace

**Replace before activation.** Keep the unpublished generation as a structural snapshot if useful; do **not** activate or publish it. Voice membership does not match the accepted census. After founder authorization: apply 038 on FlightSim, reload the unpublished generation, then re-prove counts (expect Tom/Peggy/Sue voice 12071/1342/307 if quote membership is unchanged).

## Private review packet

Gitignored: `working/i14-voice-delta-review/` (INDEX, packet-001, originals by Evidence-ref). At most 12 Tom examples: retained voice, identity-uncertain rejects, quote-contamination rejects. No HTML, no full corpus.

## Not this gate

No activate, no publish, no Gallery, no I11A, no production reload.
