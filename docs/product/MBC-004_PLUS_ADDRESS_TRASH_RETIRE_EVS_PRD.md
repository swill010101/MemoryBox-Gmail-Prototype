# MBC-004 — Plus-address capture, trash-after-verify, retire EVS & subject tags

**Status:** Draft — awaiting Tom sign-off · 2026-08-08  
**ID:** MBC-004  
**Owner:** Tom Will  
**Depends on:** MBC-001, MBC-002  
**Supersedes / retires:** MBC-003 (EVS multi-segment) · subject-tag routing (`[MB-…]`)

---

## 1. Problem

1. Personal Inbox clutter: capture mail sits in `swill01@gmail.com` after processing.  
2. If Gmail keeps the message, a later poll/re-process risk can recreate journal rows.  
3. Subject tags (`[MB-JRN]`, `[MB-EVS]`, …) are easy to forget and duplicate routing logic; plus-addresses are memorable and filterable.  
4. EVS batch UI/code is no longer needed.

## 2. Why now

Option A (plus-address) is the chosen tidy path. Trash-after-verify keeps Gmail clean once MemoryBox/Marvin has the row. Retiring EVS + subject parsing simplifies the product surface.

## 3. Success criteria

| # | Criterion |
|---|-----------|
| 1 | Inbound routing uses **To:** plus-local-part only (case-insensitive); **no** subject-tag parse for type |
| 2 | Accepted aliases (local-part after `+`, case-insensitive): `journal`, `jrn` → **JRN**; `mem`, `memorybox` → **MEM** |
| 3 | After successful DB write (row exists for that Gmail message id), message is moved to **Gmail Trash** |
| 4 | `duplicate_skipped` (body already in DB): still trash — already verified present |
| 5 | Failures / unmatched: **do not** trash |
| 6 | All EVS code, UI, APIs, docs, and any EVS DB rows removed |
| 7 | Review header shows **plus-addresses → destination** (not `[MB-…]` subject keys) |
| 8 | Raw `.eml` on disk remains authoritative; trash only affects Gmail copy |
| 9 | Tests cover alias routing, trash-on-success, no-trash-on-failure, EVS gone |

## 4. Scope

### In

- Config list of plus aliases → prompt type (`journal`/`jrn` → JRN, `mem`/`memorybox` → MEM)  
- Poll query aimed at those To: addresses (and/or still-labeled backlog during transition)  
- Resolve type from To: header (Delivered-To / To / X-Original-To as available)  
- `trash_message` via Gmail API after verify  
- Remove EVS: package code, static UI (Extract/Remove EVS), APIs, MBC-003 docs pointers, `split_evs_segments`, segment-only-EVS paths, format/delete EVS helpers, tests  
- Startup or one-shot: `DELETE` EVS responses/prompts/attachments if any  
- UI keys bar: only the four address patterns and where they go  
- Stop using `parse_subject_tag` for **inbound** classification  

### Out

- Second Google account / Workspace domain  
- Permanent `messages.delete` (use Trash only)  
- Re-introducing EVS  
- Changing MEM bank schedule / questions JSON format  
- Auto-creating Gmail filters (Tom may still add Skip Inbox filters manually)

## 5. Locked decisions (from Tom)

| Topic | Decision |
|--------|----------|
| Post-verify action | **Trash** (not archive) |
| Duplicates already in DB | Verify presence → **trash** |
| Aliases | `swill01+journal`, `+jrn`, `+mem`, `+memorybox` (case-insensitive) |
| Subject-tag inbound routing | **Removed** |
| EVS | **Fully removed** |

## 6. Proposed routing table (UI copy)

```text
swill01+journal@gmail.com   →  Journal (JRN)
swill01+jrn@gmail.com       →  Journal (JRN)
swill01+mem@gmail.com       →  Memory (MEM)
swill01+memorybox@gmail.com →  Memory (MEM)
```

(Base local-part from config `gmail.user_email`, not hard-coded `swill01`, so renames stay config-driven.)

## 7. Verify-then-trash algorithm

1. Process message → attempt insert / soft-dedupe.  
2. **Verify:** `SELECT 1 FROM response WHERE gmail_message_id = ?` (any segment_index).  
3. If verified → `users.messages.trash(id)` + keep `MB/Processed` optional (Trash wins for inbox tidy).  
4. If not verified → leave in Inbox; log error.  
5. Never trash Marvin’s unmatched hold files’ Gmail source without a DB row.

## 8. Effort (technical)

| Workstream | Invasiveness |
|------------|--------------|
| Plus-alias parse + poll query | Medium — replaces subject routing core |
| Trash-after-verify | Low–medium — Gmail client + success path |
| EVS deletion (code/UI/tests/docs/DB wipe) | Medium — wide but mechanical |
| MEM bank correlation without `[MB-MEM-n]` subject | **Open — see questions** (may be medium–high) |
| UI keys bar | Low |

---

## 9. Questions for Tom (blockers until answered)

### Q1 — MEM bank replies without subject tags (**blocker**)

Outbound MEM today uses subject `[MB-MEM-n] …` and inbound matches that tag to `prompt_id = MEM-n`.

If inbound **ignores subject entirely**, how should a reply bind to question *n*?

Pick one:

- **A.** Bind by **Gmail thread_id** only (reply on Marvin’s outbound thread → that question). New compose to `+mem` with no thread = ad-hoc `MEM` only.  
- **B.** Keep **outbound** subjects for humans, but inbound still allowed to read `[MB-MEM-n]` **only for bank id** (exception to “no subject processing”).  
- **C.** Something else (describe).

### Q2 — Ad-hoc MEM vs bank MEM

Both `+mem` and `+memorybox` → same MEM bucket? Or one alias = bank-only and one = ad-hoc?

### Q3 — Journal outbound / daily journal

When Marvin sends a journal prompt (if ever re-enabled), send **to** `user+journal@…`? Same for MEM bank `mem_bank.to`?

### Q4 — Trash scope

Trash **only** the processed inbound message id, not the whole thread (recommended). Confirm.

### Q5 — Transition

Mail still arriving with only `[MB-JRN]` subject and **no** plus-address: drop as unmatched, or short compatibility window?

### Q6 — `segment_index` column

EVS introduced `segment_index`. After EVS removal: keep column (always `1` for JRN/MEM) or migrate it away? (Keep is simpler.)

### Q7 — UI “Extract MEM” / MEM sends

Unchanged aside from keys bar + EVS chrome removal — confirm.

---

## 10. Blockers summary

| Blocker | Why |
|---------|-----|
| **MEM↔question correlation** | Must choose Q1 A/B/C before removing subject parsing |
| **Gmail Trash vs re-poll** | Trash removes from Inbox/All-Mail active lists; messages can exist in Trash briefly — poll must not re-ingest Trash (query `in:inbox` / `-in:trash`) |
| **OAuth** | Already `gmail.modify` — sufficient for trash |
| **False confidence** | Delete/trash is irreversible for casual recovery after 30 days — verify gate is mandatory (locked) |

---

## 11. Build plan (after sign-off)

1. Lock Q1–Q7.  
2. PRD status → Approved; mark MBC-003 retired.  
3. Remove EVS (code, UI, tests, docs); wipe EVS DB rows on startup.  
4. Plus-alias routing + poll; strip inbound subject-tag classification.  
5. Verify-then-trash; tests.  
6. UI keys bar = address table only.  
7. Update README / MBC-001 pointers.

---

## 12. Explicit non-goals this slice

- Permanent Gmail delete API  
- Multi-account OAuth  
- Rebuilding EVS later under a new id without a new PRD  
