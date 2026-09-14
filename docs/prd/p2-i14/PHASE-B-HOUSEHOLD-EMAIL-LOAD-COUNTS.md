# I14 Phase B — unpublished household-email load (counts only)

**Status:** One unpublished, inactive household-email generation is loaded on FlightSim. Not activated. Not published. Gallery/Ask/I11A remain unauthorized.

**Runtime SHA:** `050e02e96e6813034107270c0e0955a37f1ac577` (tracked-clean on FlightSim).  
**Backup:** `C:\MemoryBox-backups\pre-i14-load-20260913-221915\memorybox.dump` — **433235039** bytes; `pg_restore -l` **707** lines.

Elapsed **1,912,741 ms** (~32 minutes). Insert progress reached 40,800 / 40,996 threads before the final unreported remainder. A prior attempt failed the `https?://` prepared CHECK, was marked `failed` (unpublished), discarded, and retried after URL stripping.

Generation identifier is only in the private operations record (`MemoryBox-backups\pre-i14-load-20260913-221915\private.json`). It is not in Git.

## Completeness

`91281 = 91247 + 26 + 2 + 6 + 0` (check true). Unexplained **0**. Published **0**. Active **0**.

## Actual vs accepted forecast

Structural counts match the accepted pre-load forecast exactly: mbox 91281, assigned 91275, prepared 91247, identity omitted 26, missing-From 2, held 6, threads 40996, max thread size 89.

Class counts that used **in-thread quote prior** (production) vs the accepted census **independent per-message** cleanup:

| Class | Accepted census | Loaded |
| --- | ---: | ---: |
| quote suspected_contamination | 34488 | 34488 |
| commercial retain | 1380 | 1371 |
| commercial suppress | 15376 | 15355 |
| commercial uncertain | 944 | 888 |
| commercial not_commercial | 73547 | 73633 |
| authored-voice Tom / Peggy / Sue | 12071 / 1342 / 307 | 1884 / 1149 / 299 |

Quote-exception **count** matched. Authored-voice **membership** changed because sequential prior changes which authenticated-From messages stay `voice_corpus`. Commercial class shifted slightly for the same reason. The forecast file was not edited after the fact.

## Lineage and prepared

- 035: logical sources 1, extracts 1, memberships 1, canonical records 91247, identity aliases 182494, checkpoint 0
- Prepared: generations 1 (`validated`, unpublished, inactive), threads 40996, messages 91247, participants 294061, attachments 28467
- Participants: authenticated_focal 36841, authenticated_other 60329, unverified 196891 (authenticated total 97170, same as census)

Baseline unchanged: evidence 188656, sources 27, `communication_rfc_ids` 287010. Ledger **001–037**, pending empty. `/health` ok. Historian Capture email ok; `historian_capture_email` Active.

## Review packet (private)

Gitignored TXT tree: `working/i14-household-email-review/` (copy under the backup folder). 12 threads, INDEX + packet-001 + originals by Evidence-ref. Coverage present: Peggy/Sue/Tom From voice, unknown From, commercial retain/suppress/uncertain, attachment, forward, quote cleanup, high quote-risk, multiple participants.

Do not commit bodies or addresses.
