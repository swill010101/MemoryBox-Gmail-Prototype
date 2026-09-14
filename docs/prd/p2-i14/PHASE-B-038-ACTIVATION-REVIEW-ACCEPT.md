# I14 Phase B — unpublished 038 household-email generation: founder visual review accepted

**Date:** 2026-09-14  
**Branch:** `codex/p2-i14-communications`  
**Accepted object:** the current unpublished household-email prepared generation on FlightSim (ledger **038**, replacement load).  
**Not accepted:** Gallery communications exposure, Ask/I11A consumption of prepared text, or any later generation.

This document is acceptance evidence only. It does not activate or publish.

## Disposition

Founder completed the bounded 038 activation-review packet and accepted it.

Reviewed FOCUS messages include required cases `T-2312-M-02` and `T-2345-M-02`, plus representative Peggy messages newly admitted to voice by the glued-Hotmail `Date/From/To/Subject` cut.

Founder finding: cleaned text preserves Peggy’s authored words, removes quoted participant text and glued email-header material, remains understandable in chronological context, and is correctly classified as Peggy authored voice.

**Founder visual review: Accepted.**

Packet (gitignored, never commit): `working/i14-activation-review/` — `INDEX.txt`, `packet-001.txt`, `originals/<Evidence-ref>.txt`. TXT only. 11 threads (max 12). 24 representative other glued-Hotmail Peggy voice FOCUS rows of 42 such messages in the generation. 69 original files (one Evidence-ref at a time, including chronological context). No HTML. No full-corpus dump.

## What this acceptance covers

- Structural replacement load after migration 038 (voice CHECK without requiring recipient identity).
- Household authored-voice rule: authenticated canonical From + `quote_quality=clean` is voice even when To/Cc identity is unverified. Unknown From is not voice. To/Cc never voice.
- Peggy glued-Hotmail cleanup on the two named cases and the sampled other admissions.
- Completeness of the unpublished generation as previously recorded: `91281 = 91247 + 26 + 2 + 6 + 0`, unexplained **0**.

## Loaded voice (replacement generation)

| Person | Census (quote-clean From) | Loaded voice |
| --- | ---: | ---: |
| Tom | 12071 | **12071** |
| Peggy | 1342 | **1368** (+26 glued-Hotmail sequential keep) |
| Sue | 307 | **307** |
| Any other authenticated From | 0 | **0** |

Quote quality: clean **56789**, suspected_contamination **34458**.

## Generation state at acceptance (must still hold before any later activate)

| Check | Result |
| --- | --- |
| Status | `validated`, unpublished, inactive |
| Eligible unpublished generations | **1** |
| Published / active / failed | **0 / 0 / 0** |
| Prior rejected snapshot | deleted; cannot activate |
| Archive baselines | evidence **188656**, sources **27**, RFC ids **287010** |
| Ledger | **001–038**; `/health` pending empty |
| 038 SQL blob | `1efe54148f932dc3a3a49c21273e9b5f43504ac0` |
| Load SHA (corrected loader) | `bf618960fbf3f3e39e49348f3455f1e2e4c23ff7` |
| Packet writer SHA | `57d6759ed4009b6829cc32885571e7ffbd6d0113` |
| Pre-038 backup | `E:\MemoryBox-backups\pre-i14-038-20260914-074522\memorybox.dump` (499252376 bytes; `pg_restore -l` 707) |

## Authorized next from this gate

SQL activation completed 2026-09-14: [PHASE-B-038-ACTIVATION.md](PHASE-B-038-ACTIVATION.md). Gallery and I11A remain separate.
