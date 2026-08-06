# MBC-001 — Marvin Capture v0.1 PRD

**Status:** Approved for PoC implement (Tom-provided brief) · 2026-08-06  
**ID:** MBC-001  
**Owner:** Tom Will (sole user)  
**Host intent:** FlightSim / AI computer · personal daily use

---

## Immutable design principle

**Marvin Capture must never lose information in an attempt to be intelligent.**

The original email, attachments, and reply are the authoritative record. AI may organize, summarize, classify, or suggest metadata later, but it must never replace or discard the original evidence.

Derived fields (extracted reply text, Whisper transcripts, review status) are additive. They sit beside originals; they do not overwrite them.

---

## 1. Problem being solved (and why now)

MemoryBox needs a reliable way for Tom to answer Marvin’s questions by email and have those answers preserved as evidence for later ingestion.

Today there is no closed loop that:

1. Sends a scheduled prompt
2. Receives a natural reply (text, dictate, attachments)
3. Preserves the original message and every attachment
4. Extracts only Tom’s new response
5. Stores the association for future MemoryBox use

**Why now:** Prove the capture loop for Tom’s personal daily use before investing in the full MemoryBox email subsystem, story generation, or ingestion pipeline.

---

## 2. Success criteria

| # | Criterion |
|---|-----------|
| 1 | Marvin successfully sends a scheduled email with a correlatable subject tag |
| 2 | Tom replies naturally (type / dictate / attach) |
| 3 | Marvin retrieves the reply via Gmail API polling |
| 4 | Original email is preserved on disk (raw evidence) |
| 5 | Attachments are preserved exactly as received |
| 6 | Only Tom’s newly written content is extracted into `response_text` |
| 7 | Response is stored in SQLite and linked to the original prompt |
| 8 | Local review page displays Inbox / Reviewed with prompt → reply → attachments → transcript |
| 9 | Voice attachments are queued and transcribed (original audio retained) |
| 10 | Gmail message is labeled `MB/Processed` after successful capture |

---

## 3. Scope

### In

- Outbound scheduled prompts (journal + memory-style questions)
- Inbound Gmail poll + reply association via subject tag / thread
- Raw email + attachment preservation
- Reply-text extraction (non-destructive)
- SQLite storage (`prompt`, `response`, `attachment`)
- Whisper transcription for audio attachments
- Lightweight local review UI (Inbox / Reviewed)
- Configuration: Gmail account, poll interval, SQLite path, attachment folder, Whisper endpoint

### Out

- Multiple users / mailboxes
- marvinbot.net hosting
- Story generation, knowledge graph, AI summarization
- Automatic relationship inference
- MemoryBox ingestion
- Mobile app
- Notifications beyond email

---

## 4. Email workflow

### Outbound

Subject examples:

- `[MB-JRN-20260806]` What happened today?
- `[MB-MEM-000123]` Tell me about your grade-school days.

### Inbound

Tom presses Reply. No special formatting required. May attach images, PDF, DOCX, TXT, m4a, WAV, MP3.

### Processing

1. Poll Gmail
2. Locate original prompt (subject tag and/or thread)
3. Preserve original email + attachments
4. Extract only Tom’s new content
5. Store reply linked to prompt
6. Queue audio for Whisper; store transcript beside original
7. Label message `MB/Processed`

---

## 5. Storage

**SQLite** tables: `prompt`, `response`, `attachment` (plus additive columns for Gmail ids, review state, transcript status — never at the expense of originals).

**Filesystem:** raw `.eml` / MIME dumps and attachment binaries under the configured attachment storage folder (gitignored runtime paths).

---

## 6. Constraints & dependencies

- Gmail API OAuth credentials on Tom’s machine
- Optional Whisper-compatible HTTP endpoint (local or remote)
- Single-user; local review UI bound to localhost by default
- Aligns with MemoryBox Evidence Principles (README): originals unchanged; confidence/inferences labeled later — not in v0.1

---

## 7. Edge cases

| Case | Behavior |
|------|----------|
| Reply has no body, only attachments | Store empty `response_text`; preserve attachments; still process |
| Cannot match prompt | Preserve raw mail under unmatched holding; do not discard; do not mark processed until matched or manually resolved |
| Whisper unavailable | Keep audio; mark transcript `pending`/`error`; retry later |
| Duplicate Gmail message id | Idempotent skip |
| Quoted thread noise | Strip for `response_text` only; raw email remains complete |

---

## 8. Build plan

1. PRD + config schema
2. SQLite + filesystem storage layer
3. Subject tags, reply extraction, attachment writer
4. Gmail send / poll / label (with dry-run / fixtures for tests)
5. Whisper client + transcription worker
6. Review UI
7. Scheduler + CLI runners
8. Tests for extraction, DB, end-to-end fixture mail

---

## 9. Open questions (defaults applied for PoC)

| Question | Default for v0.1 |
|----------|------------------|
| Daily journal send time | 18:00 local |
| Poll interval | 300 seconds |
| Review “accept” meaning | Marks `reviewed=1` only; no MemoryBox ingest |
| Unmatched replies | Hold as raw files + log; operator can inspect |
| Whisper API shape | OpenAI-compatible `/v1/audio/transcriptions` |

---

## 10. Future (explicitly deferred)

EVS / story capture, automatic tagging, Ollama summarization, MemoryBox ingestion, relationship suggestions, weekly interviews, multi-user, public API.
