# MBC-004 — Plus-address capture, trash-after-verify, retire EVS & subject tags

**Status:** Approved · 2026-08-08  
**ID:** MBC-004  
**Owner:** Tom Will  
**Depends on:** MBC-001, MBC-002  
**Supersedes / retires:** MBC-003 (EVS multi-segment) · inbound `[MB-…]` subject routing · ad-hoc user-initiated MEM

---

## Locked decisions (final)

| Topic | Decision |
|--------|----------|
| Post-verify | **Gmail Trash** (single message) |
| Duplicates in DB | Trash |
| Journal aliases | `+journal`, `+jrn` → JRN (case-insensitive) |
| MEM alias | **`+MEM` only** (case-insensitive) |
| Ad-hoc inbound MEM | **Not allowed** |
| Old subject-only mail | **Unmatched** |
| EVS | **Remove entirely** |
| `segment_index` | **Drop** |
| **Q3 MEM outbound To:** | **Plain `you@gmail.com`** with **Reply-To: `you+MEM@gmail.com`** |
| **Q7 MEM UI:** | **A — keep all four MEM buttons** |

---

## Address table (UI)

```text
you+journal@gmail.com  →  Journal (JRN) — you may compose or reply
you+jrn@gmail.com      →  Journal (JRN) — same
you+MEM@gmail.com      →  Memory bank answers only — reply to Marvin's MEM email
```

(`you` = local-part of configured `gmail.user_email`.)

## MEM model

1. Marvin sends the next bank question to plain `you@gmail.com` with `Reply-To: you+MEM@gmail.com`.  
2. Tom replies (ideally using `you+MEM@` via Reply-To).  
3. Capture binds via Gmail thread → stored `MEM-n` prompt.  
4. Compose to `+MEM` with no matching Marvin thread → **unmatched**.

## Verify-then-trash

1. Process → insert or soft-dedupe.  
2. Verify response row exists for `gmail_message_id` (or duplicate twin verified).  
3. If yes → `messages.trash(id)` for **that** message only.  
4. Poll queries exclude Trash (`-in:trash`) and target plus-alias addresses only.

---

*MBC-003 (EVS) is retired. See `MBC-003_EVS_MULTI_SEGMENT_PRD.md` for historical reference only.*
