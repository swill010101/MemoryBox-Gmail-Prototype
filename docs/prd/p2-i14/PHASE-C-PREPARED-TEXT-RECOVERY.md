# I14 prepared-text recovery (review, not authorized to load)

**Status:** Implemented and proven on disposable PostgreSQL plus a read-only production census. **Not accepted for replacement generation, migrate, load, or activate.** Phase C Gallery remains in review.  
**Date:** 2026-09-15  
**Active generation:** unchanged. Archive evidence: unchanged. Ledger on FlightSim: **001–038**.

## Source-selection rule

1. Keep meaningful plain `body_text` / `body`.
2. If that field is absent or not meaningful, recover from `body_html` via `html_to_plain`.
3. If HTML is also empty, try alternate MIME parts (`body_parts` / `parts` / `mime_parts`).
4. Do not replace valid plain text because HTML exists.
5. Do not synthesize, summarize, or infer. Immutable evidence is never rewritten.
6. Run the existing quote/forward cleaner (`prepare_message_text`) on the selected source.

New unpublished loads use `algo_version=i14-prepared-email-v2`. Voice is authenticated From + `quote_quality=clean` + **nonblank** prepared text.

## Empty-message dispositions

Every message ends in one of: `authored_prepared`, `correctly_empty`, `attachment_only`, `prepared_text_unavailable`, `defect_unexplained`. Gallery must not show a silent blank body (Phase C notices already cover unavailable / attachment-only).

## Proposed activation invariant (do not apply on FlightSim)

File: [039_p2_i14_voice_requires_prepared_text.PROPOSED.sql](039_p2_i14_voice_requires_prepared_text.PROPOSED.sql)

`comms_prepared_assert_generation_ready` refuses `voice_corpus` with blank/whitespace `cleaned_authored_text` (`voice_requires_nonblank_prepared_text`). No table CHECK, so the currently active flawed generation is not rewritten and would not fail a row constraint. **Do not copy this file into `memorybox/migrations/` until founder authorization.** Applying it would only block *future* activations of a generation that still has blank+voice rows.

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
| Prepared text unavailable — open original | **265** |
| Defect / unexplained | **42** |
| `voice_corpus=true` with blank prepared text after recovery | **0** |

Voice by authenticated From Person (stored → rehearsal): Tom **12,071 → 11,552**; Peggy **1,368 → 1,345**; Sue **307 → 210**. Blank stored voice rows are no longer counted as voice.

Commercial class (stored → rehearsal): not_commercial 73,636 → 70,220; retain_life_evidence 1,371 → 1,558; suppress_default 15,352 → 18,702; uncertain 888 → 767.

Quote quality: clean 56,789 → 56,361; suspected_contamination 34,458 → 34,886.

**Unexplained (classifier leftover from sequential census): 42.** These match the empty-body **cleanup_removed_meaningful** bucket exactly (42). They are remaining defects, not an unknown category. Hotmail-glue **recoveries** on this pass: **0**. After relabeling those 42 as remaining defects, **unexplained = 0** as a “we don’t know” bucket.

Reconcile vs empty-body baseline (8,343 empty / 1,246 correct empty / 21 safe / 7,076 defects):

- HTML recoveries **7,014** vs **7,034** html-only defects (20 html-only remain unauthored after sequential compact; overlap with safe/nondisplayable).
- Remaining defects **42** = prior Hotmail-block cleanup failures (not recovered).
- Attachment-only rehearsal **586** vs baseline **550** (rehearsal classifies some empty+attachment rows that sequential compact still blanks).
- Correctly empty rehearsal **1,662** includes quote/forward/commercial-empty plus genuine empties (baseline split 1,246 correct + 21 safe + quote/forward/commercial shells).

**John `T-39987` ordinal 2** (Evidence-ref `5941e1bb-5354-4bba-9bac-fb1f0a9fd963`): original `html_only`; stored prepared empty; fallback `html_to_plain` + `prepare_message_text` (method `on_wrote`) yields authored text, no tags/scripts/URLs. Immutable original unchanged. Packet slot overwritten to ordinal 2.

Do not treat 7,014 HTML recoveries as sufficient for production load while **42** Hotmail leftovers and **265** unavailable remain. Replacement generation still requires founder authorization.

```powershell
python -m unittest tests.test_i14_html_source tests.test_i14_empty_body tests.test_i14_prepared_text tests.test_i14_prepared_loader.PreparedLoaderPg.test_html_only_body_recovers_authored_text_on_disposable_postgres tests.test_i14_prepared_loader.PreparedLoaderPg.test_proposed_039_blocks_blank_voice_without_rewriting_rows -v
```

Read-only census (never writes):

```powershell
$env:MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB = "1"
$env:MEMORYBOX_I14_AUDIT_ALLOW_FLIGHTSIM = "1"
python -m memorybox i14-prepared-text-recovery-census
```

Counts: `working/i14-prepared-text-recovery/COUNTS.json` (gitignored).  
Founder packet (≤12 threads, private bodies): `working/i14-prepared-text-recovery/FOUNDER-PACKET.txt` (gitignored).

## Stop conditions still in force

Do not modify the active generation, migrate, load a replacement, activate, begin I11A, or add normalized SMS/calendar.

Do not optimize the ~20–25 s Sue Will Ask delay in this recovery work. That is an open Phase C acceptance item after recovery: [PHASE-C-PERFORMANCE-DEFECT.md](PHASE-C-PERFORMANCE-DEFECT.md).
