# MBC-002 — MEM Question Bank (Marvin Capture)

**Status:** Approved for implement (Tom answers 2026-08-07)  
**Parent:** MBC-001 Marvin Capture  
**Owner:** Tom Will

## Purpose

Run a sequenced life-interview: 300+ questions from JSON, one new question per weekday at 01:00 local, replies captured as MEM with full Q&A + attachments reconstructible.

## Decisions (locked)

| Topic | Decision |
|-------|----------|
| Source | `config/mem_questions.json` — ids `1…N` in order |
| Cadence | Mon–Fri **01:00** local — email waiting when Tom wakes |
| Advance | Send **next unsent** each scheduled day |
| Unanswered | Still advance next day; **resend** unanswered question **7 days** after last send |
| Subject | `[MB-MEM-n] <question text>` (bare id). Tokenless `[MB-MEM]` = ad-hoc only |
| Answered | Any captured reply for that `MEM-n` |
| Voice-only | Whisper transcript → `response_text`; original audio kept |
| Journal | Ad-hoc only while bank enabled (`daily_journal.enabled: false`) |
| Complete | When all N answered → one email “Interview complete…” (email only) |
| Export | Combined `.txt` **and** per-question files in a folder; attachments named with question # + received date |
| Resume | Continue at next unsent; stop when complete |

## Immutable principle

Originals never discarded. Derived text (extraction, Whisper) is additive.

## Out of scope

MemoryBox ingest, AI summarization, multi-user, changing question order mid-bank (edit JSON + restart cursor carefully).
