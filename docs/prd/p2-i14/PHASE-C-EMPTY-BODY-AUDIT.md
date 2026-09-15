# I14 empty prepared-body audit (counts only)

**Status:** Read-only. Archive and the active generation were not modified.  
**Date:** 2026-09-15  
**Empty prepared messages:** 8343 of 91247 active-generation messages.  
**Genuine data defects (meaningful original text, empty prepared):** **7076**  
**Correct empty:** 1246  
**Safe / non-displayable:** 21  

John `T-39987` ordinal 2 is **html_only_or_alt_part / defect**: personal, not commercial; `quote_quality=clean`; prepared cleaned text empty; immutable original HTML still has authored content. Current cleaner would recover text from HTML. Loader used empty `body_text` instead of the HTML part. UI must not invent text; it should say prepared text is unavailable and open the original. Voice stays false.

## Categories (mutually exclusive)

| Category | Messages | Threads | Auth From | Unverified From | Personal/retain | Commercial/uncertain | Attachments | Voice flag | Original meaningful | Disposition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| original_genuinely_empty | 54 | 54 | 9 | 45 | 54 | 0 | 0 | 9 | 0 | correct empty |
| attachment_only | 550 | 497 | 257 | 293 | 542 | 8 | 550 | 257 | 0 | correct empty |
| quoted_history_only | 114 | 98 | 39 | 75 | 107 | 7 | 40 | 39 | 114 | correct empty |
| forward_history_only | 384 | 350 | 243 | 141 | 282 | 102 | 132 | 243 | 384 | correct empty |
| commercial_or_automated_shell | 144 | 144 | 69 | 75 | 134 | 10 | 1 | 69 | 144 | correct empty |
| html_only_or_alt_part | 7054 | 6116 | 235 | 6819 | 6486 | 568 | 533 | 235 | 7054 | 7034 defect, 20 safe |
| encoding_or_parser_failure | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | safe |
| cleanup_removed_meaningful | 42 | 39 | 5 | 37 | 28 | 14 | 6 | 2 | 42 | defect |
| other_known | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| unexplained | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |

Private sample index (≤12 threads, including John): `working/i14-empty-body-audit/SAMPLE-INDEX.txt` (gitignored).

## Proposed correction (not authorized)

On disposable PostgreSQL only: when `body_text` is empty, extract authored text from HTML, then run the existing quote cleaner. Expected impact: about **7034** HTML-part recoveries plus **42** Hotmail-block recoveries. Do not load, activate, or publish a replacement generation without founder authorization. Empty stored rows with `voice_corpus=true` must not be treated as authored voice.

## Product display (this change, no prepared rewrite)

Never show a blank body. Attachment-only, quote-only, and unavailable prepared text each have plain-language copy plus **Open the immutable original email**.
