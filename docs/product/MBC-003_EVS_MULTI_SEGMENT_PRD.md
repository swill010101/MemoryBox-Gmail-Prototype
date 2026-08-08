# MBC-003 — EVS multi-segment capture

**Status:** Retired · superseded by MBC-004 (2026-08-08)  
**ID:** MBC-003  
**Owner:** Tom Will  
**Depends on:** MBC-001 (Marvin Capture)

---

## Problem

One `[MB-EVS]` email can contain several distinct EVS asks. Marvin previously stored the whole body as a single `response` row. Each delineated piece must be its own EVS in the database and in Extract output.

## Why now

EVS batch extract/remove is live. Soft-wrap collapsing makes blank-line delimiters unreliable; Tom locked a sentence-level `Stop` delimiter that survives wrap→space.

## Success criteria

1. One inbound `[MB-EVS]` mail with N `Stop`-delimited sentences → N `response` rows.
2. Delimiter: **end of sentence/question** (`.?!`) then the word **`Stop`** (any case, optional trailing `.?!`) then the **next sentence**.
3. Trailing `Stop` with no follow-on sentence → ignored (no empty row).
4. No `Stop` → one EVS = full body.
5. Identity: real Gmail `message_id` + `segment_index` `1…N` (export/UI as `01`, `02`, …).
6. Subject headline ignored for EVS semantics; `[MB-EVS]` alone marks the body as EVS payload.
7. No EVS body labels (`EVS-01` etc.) required or parsed.
8. Attachments ignored for EVS (not linked in review). Exception: voice-only empty body → Whisper once, then split; audio not shown as EVS attachments.
9. Mixed typed body + audio → body only; ignore audio.
10. Inbox shows one card per segment; Extract uses `=== EVS n ===` per segment.
11. Raw `.eml` preserved once and shared across segments; Remove-all deletes it once.

## Out of scope

- Blank-line / newline delimiters  
- Splitting JRN or MEM the same way  
- Parsing `EVS-nn` labels in the body  
- Migrating legacy multi-EVS blobs (none expected)

## Delimiter notes

- Mid-sentence “stop” (`don't stop looking`) must not split.  
- ASR may emit `stop`, `Stop.`, `STOP!`, etc. — allow any casing and optional trailing sentence punct after `Stop`.  
- False splits from legitimate `. Stop.` prose are acceptable.

## Schema

- `response.segment_index INTEGER NOT NULL DEFAULT 1`  
- Unique `(gmail_message_id, segment_index)` when `gmail_message_id` is present (replace UNIQUE on `gmail_message_id` alone).

## Immutable principle

Segments are derived. The original email on disk remains authoritative.
