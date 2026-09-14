# I14 Phase B — replacement unpublished household-email load

**Status:** Replacement generation is loaded on FlightSim. **Not activated. Not published.** Gallery/Ask/I11A remain unauthorized.

**Code SHA:** `bf618960fbf3f3e39e49348f3455f1e2e4c23ff7`  
**038 SQL blob:** `1efe54148f932dc3a3a49c21273e9b5f43504ac0` (`038_p2_i14_voice_without_recipient_identity.sql`)

**Backup (pre-038 + pre-replace):** `E:\MemoryBox-backups\pre-i14-038-20260914-074522\memorybox.dump` — **499252376** bytes; `pg_restore -l` **707** lines. Rejected-generation id is only in that folder’s `private.json`.

Elapsed **1,954,017 ms** (~32.6 minutes) for the replacement load (includes preflight census).

## Generation state

| Check | Result |
| --- | --- |
| Published | **0** |
| Active | **0** |
| Failed leftover | **0** |
| Eligible unpublished (`validated`, inactive) | **1** (replacement only) |
| Prior unpublished snapshot | **deleted**; cannot activate |
| Activation called | false |

## Completeness (unchanged structurally)

`91281 = 91247 + 26 + 2 + 6 + 0`. Unexplained **0**. One evidence id appears in at most one prepared message. Identity-omit count **26** with lineage aliases **182494**.

Baseline unchanged: evidence **188656**, sources **27**, RFC ids **287010**.

Ledger **001–038**, pending empty (desktop migrate). CHECK `comms_prepared_messages_voice_corpus_ck`: voice requires `quote_quality=clean` and `authorship=authenticated_focal` (identity may be uncertain).

## Voice: rejected snapshot vs replacement

Census (accepted, independent quote-clean From): Tom **12071**, Peggy **1342**, Sue **307**.

| Person | Rejected loaded voice | Replacement voice |
| --- | ---: | ---: |
| Tom | 1884 | **12071** |
| Peggy | 1149 | **1368** |
| Sue | 299 | **307** |
| Any other authenticated From | 0 | **0** |

Tom and Sue now match census. Peggy is **+26** vs census because glued Hotmail `Date/From/To/Subject` headers are now cut, so more Peggy From messages stay `quote_quality=clean` under sequential compact. Quote exceptions **34458** (was 34488).

Household rule: authenticated From + clean quote is voice even when To/Cc are unverified. Unknown From is not voice. To/Cc never voice.

## Two Peggy sentence-loss cases

Both were false “new sentence” hits: a quoted Tom line glued onto concatenated Hotmail headers. Independent cleanup left that glue in prepared text; sequential prior stripped the Tom fragment and still marked trusted voice.

**Disposition (both): preserve.** Header block is cut. Peggy’s authored sentences remain. Tom quote and `Date:` glue are gone. `quote_quality=clean`, `voice_corpus=true`. Same evidence ids; display refs still `T-2312-M-02` and `T-2345-M-02`.

Regression: unit tests plus disposable Postgres `test_glued_hotmail_peggy_reply_keeps_authored_sentence_on_disposable_postgres`. Leftover glue without separable authored text is quote-risk / non-voice.

## Review

Private 12-thread TXT: `working/i14-household-email-review-038/` (gitignored). No HTML. No full corpus.

## Not this gate

No activate, no publish, no Gallery, no I11A.
