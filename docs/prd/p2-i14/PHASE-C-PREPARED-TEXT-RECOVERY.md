# I14 prepared-text recovery (review, not authorized to load)

**Status:** Founder recovery packet accepted. Replacement unpublished load is separately authorized: [PHASE-C-REPLACEMENT-GENERATION.md](PHASE-C-REPLACEMENT-GENERATION.md). **Do not activate.** Phase C Gallery remains in review.  
**Date:** 2026-09-15  
**Active generation:** unchanged until a later activation authorization. Ledger after this work: **001–039**.

## Mixed Gallery SMS (Phase C)

Email and SMS are independent members of the mixed Communications category.

- I14 person Find retrieves and counts SMS even when `gallery_show_sms` is false (Email off is not a hydrate step).
- A partial orchestrator SMS sample no longer blocks the Ask-window retrieve.
- Mixed All defaults both Email and SMS on (`gallery_mixed_comms`) without selecting the Communications pill.
- Email off leaves SMS; SMS off leaves Email. Curator, pills, cards, and buckets use the same include flags.
- Single-year Asks band the timeline to **Jan 1–Dec 31** of that year (no 2016-12→2018-01 pad).
- A new typed Ask mints a new session, aborts prepared fetches, and applies `keepPresentation: false` (Person, date, paging, filter, timeline, and background token reset).

Disposable proof: `tests.test_i14_gallery_prepared.ExploreFind.test_dated_person_ask_hydrates_sms_from_existing_path` and `test_partial_orchestrator_sms_does_not_block_mixed_retrieve`.

Live proof is FlightSim-only (desktop Postgres has no `comms_prepared_*`). After recycle:

1. Hard refresh Explore (`explore.js?v=i14-c6`).
2. Ask **Show me Sue Will in 2017**. Mixed All: 328 SMS + 10 email threads; timeline 2017-01-01→2017-12-31.
3. Communications: Email off → 328 SMS, email counts/cards gone; SMS off → email intact.
4. New Ask **Show me Tom Will SMS** (not a follow-up): unbounded Tom SMS **3,717**, no 2024 range.

## Source-selection rule

1. Keep meaningful plain `body_text` / `body`.
2. If that field is absent or not meaningful, recover from `body_html` via `html_to_plain`.
3. If HTML is also empty, try alternate MIME parts (`body_parts` / `parts` / `mime_parts`).
4. Do not replace valid plain text because HTML exists.
5. Do not synthesize, summarize, or infer. Immutable evidence is never rewritten.
6. Run the existing quote/forward cleaner (`prepare_message_text`) on the selected source.

New unpublished loads use `algo_version=i14-prepared-email-v2`. Voice is authenticated From + `quote_quality=clean` + **nonblank** prepared text.

## Empty-message dispositions

Every message ends in one of: `authored_prepared`, `correctly_empty`, `attachment_only`, `prepared_text_unavailable`. There is no `defect_unexplained` leftover.

If original source text was meaningful and cleaned text is not, the message is **`prepared_text_unavailable`**: lineage and ordinal stay, `voice_corpus=false`, Gallery notice plus **Open the immutable original**. No fabricated body.

The previous **42** `cleanup_removed_meaningful` Hotmail leftovers are this class (empty-body audit: 42 messages / 39 threads / 5 authenticated From / **2** stored `voice_corpus=true`). They are not silently dropped.

## Proposed activation invariant (do not apply)

File: [039_p2_i14_voice_requires_prepared_text.PROPOSED.sql](039_p2_i14_voice_requires_prepared_text.PROPOSED.sql)

Function-only replacement of `comms_prepared_assert_generation_ready`. Candidate generation cannot activate with blank/whitespace `voice_corpus=true` (`voice_requires_nonblank_prepared_text`). No `ALTER TABLE`, no row `UPDATE`, no CHECK on existing messages. Activate still flips `comms_prepared_active_generations` only after assert succeeds; failure leaves the current active generation unchanged.

**Do not copy this file into `memorybox/migrations/` until founder authorization.**

## Exact read-only census (active generation, no writes)

Processed **91,247** messages. Lineage totals unchanged: **40,996** threads, **91,247** messages, **294,061** participants, **28,467** attachments.

| Result | Count |
|--------|------:|
| Recovered from HTML (stored empty → authored prepared) | **7,014** |
| Recovered from alternate MIME parts | **0** |
| Hotmail-glue recoveries (empty → authored, glued headers) | **0** |
| Authored text prepared successfully | **88,692** |
| Correctly empty | **1,662** |
| Attachment-only | **586** |
| Prepared text unavailable — open original | **265 + 42 = 307** after this disposition (prior split: 265 unavailable + 42 unexplained) |
| Unexplained defects | **0** |
| `voice_corpus=true` with blank prepared text after recovery | **0** |

Re-run `i14-prepared-text-recovery-census` on FlightSim after this SHA so `dispositions.prepared_text_unavailable` absorbs the 42 and `unexplained` prints 0. Desktop default Postgres is not the corpus.

### Voice forecast (stored → rehearsal)

| Person | Stored voice | Rehearsal voice | Net |
|--------|-------------:|----------------:|----:|
| Tom | 12,071 | 11,552 | **−519** |
| Peggy | 1,368 | 1,345 | **−23** |
| Sue | 307 | 210 | **−97** |

Voice does **not** use commercial class. `commercial_suppression` as a voice-drop reason is **0**.

Net reduction is stored `voice_corpus=true` rows that must not remain voice because prepared text is blank or quote-unclean after recovery — not because HTML recovery invented authors.

Household empty-body audit of **stored blank + voice=true** (these never were trustworthy authored voice):

| Reason (empty-body category) | Blank+voice rows |
|---|---:|
| blank prepared / genuinely empty | 9 |
| correctly empty — quoted history only | 39 |
| correctly empty — forward history only | 243 |
| attachment-only | 257 |
| commercial/automated shell (still blank prepared; not a commercial *voice* rule) | 69 |
| prepared text unavailable (cleanup_removed_meaningful / Hotmail) | 2 |
| html_only (stored empty; most recover and **keep** voice if From is authenticated and quote-clean) | 235 |
| **Household blank+voice** | **854** |

Named-person net drop **519+23+97 = 639**. The gap versus 854 is recovered HTML that stays voice (justified) plus any From labels other than Tom/Peggy/Sue. Sue’s **−97** is the largest relative cut: stored Sue voice included blank/quote-contaminated rows the new nonblank rule drops; Hotmail unique-inside-block leftovers stay in thread as unavailable, not as voice.

Per-person mutually exclusive drop buckets (`blank_prepared_text`, `correctly_empty`, `attachment_only`, `prepared_text_unavailable`, `quote_contamination`, `commercial_suppression=0`, `identity_authorship_change`, `other`) are written by the census as `voice_drop_by_person`. Private Sue retained/removed samples (Evidence-ref + ordinal, bodies not in git): `working/i14-prepared-text-recovery/FOUNDER-PACKET.txt` after the FlightSim census.

### Commercial reclassification

| Class | Stored | Rehearsal | Δ |
|---|---:|---:|---:|
| not_commercial | 73,636 | 70,220 | **−3,416** |
| retain_life_evidence | 1,371 | 1,558 | **+187** |
| suppress_default | 15,352 | 18,702 | **+3,350** |
| uncertain | 888 | 767 | **−121** |

Identity: **3,416 = 3,350 + 187 − 121**. Recovered HTML bodies are fed to `classify_commercial`. Empty stored rows were often default `not_commercial`; marketing HTML becomes `suppress_default`. Personal/life HTML is counted in `html_personal_not_suppressed` (packet slot `personal_html`). HTML is not a suppress signal by itself.

Quote quality: clean 56,789 → 56,361; suspected_contamination 34,458 → 34,886.

**John `T-39987` ordinal 2** (Evidence-ref `5941e1bb-5354-4bba-9bac-fb1f0a9fd963`): original `html_only`; stored prepared empty; fallback recovers authored text. Immutable original unchanged.

Replacement generation is **not** ready to load until founder authorizes a new generation after reviewing the FlightSim census packet.

```powershell
python -m unittest tests.test_i14_html_source tests.test_i14_empty_body tests.test_i14_prepared_text tests.test_i14_gallery_prepared tests.test_i14_prepared_loader.PreparedLoaderPg.test_html_only_body_recovers_authored_text_on_disposable_postgres tests.test_i14_prepared_loader.PreparedLoaderPg.test_proposed_039_blocks_blank_voice_without_rewriting_rows -v
```

Read-only census (never writes):

```powershell
$env:MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_AUDIT_ALLOW_FLIGHTSIM = "1"
python -m memorybox i14-prepared-text-recovery-census
```

Counts: `working/i14-prepared-text-recovery/COUNTS.json` (gitignored).  
Founder packet (private bodies, Sue voice samples, personal HTML): `working/i14-prepared-text-recovery/FOUNDER-PACKET.txt` (gitignored).

## Stop conditions still in force

Do not modify the active generation, migrate, load a replacement, activate, begin I11A, or add normalized SMS/calendar.

Do not optimize the ~20–25 s Sue Will Ask delay in this recovery work. That is an open Phase C acceptance item after recovery: [PHASE-C-PERFORMANCE-DEFECT.md](PHASE-C-PERFORMANCE-DEFECT.md).
