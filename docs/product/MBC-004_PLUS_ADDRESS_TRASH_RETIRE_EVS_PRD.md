# MBC-004 — Plus-address capture, trash-after-verify, retire EVS & subject tags

**Status:** Draft — revised answers in; awaiting final sign-off · 2026-08-08  
**ID:** MBC-004  
**Owner:** Tom Will  
**Depends on:** MBC-001, MBC-002  
**Supersedes / retires:** MBC-003 (EVS multi-segment) · inbound `[MB-…]` subject routing · ad-hoc user-initiated MEM

---

## 1. Problem

1. Inbox clutter after capture.  
2. Leaving mail in Gmail risks re-processing / duplicate journal rows.  
3. Subject tags are easy to misuse; plus-addresses are clearer for **journal**.  
4. EVS is retired.  
5. MEM should not be a free-form drop — only **answer Marvin’s questions**.

## 2. Success criteria

| # | Criterion |
|---|-----------|
| 1 | **Journal inbound:** To: `user+journal@` or `user+jrn@` (case-insensitive) → JRN; no subject-tag required |
| 2 | **MEM inbound:** only replies that bind to an existing Marvin MEM outbound (see §5); alias `user+MEM@` only |
| 3 | No ad-hoc user-initiated MEM (compose-to-+MEM with no matching outbound/thread → unmatched or reject) |
| 4 | After DB verify for that Gmail message id → **Trash that message only** (not whole thread) |
| 5 | Already-in-DB duplicate → trash too |
| 6 | Failures / unmatched → **do not** trash |
| 7 | Mail with only old `[MB-…]` subject and **no** accepted plus-address → **unmatched** (not captured) |
| 8 | EVS fully removed (code, UI, APIs, docs, DB rows); `segment_index` column **dropped** |
| 9 | Keys bar shows address → destination table only (no EVS, no subject-key legend) |
| 10 | Tests cover the above |

## 3. Locked decisions

| Topic | Decision |
|--------|----------|
| Post-verify | **Gmail Trash** (single message) |
| Duplicates in DB | Trash |
| Journal aliases | `+journal`, `+jrn` → JRN (case-insensitive) |
| MEM alias | **`+MEM` only** (case-insensitive; same as `+mem`) |
| `+memorybox` | **Not used** |
| Ad-hoc inbound MEM | **Not allowed** — MEM is outbound-from-Marvin → user answers → return |
| Old subject-only mail | **Unmatched** |
| EVS | **Remove entirely** |
| `segment_index` | **Drop** (migrate schema) |

## 4. Address table (UI)

```text
you+journal@gmail.com  →  Journal (JRN) — you may compose or reply
you+jrn@gmail.com      →  Journal (JRN) — same
you+MEM@gmail.com      →  Memory bank answers only — reply to Marvin’s MEM email
```

(`you` = local-part of configured `gmail.user_email`.)

## 5. MEM model (from answer #1)

**MEM is no longer a random inbound drop.**

1. Marvin (MB) **sends** the next bank question (existing MBC-002 scheduler).  
2. Tom **replies** (ideally To: stays / uses `you+MEM@` if we set outbound `to` that way — see open Q3).  
3. Capture binds the reply to the question via **Gmail thread** (and stored `prompt_id` `MEM-n` from the outbound send).  
4. A brand-new compose to `+MEM` with **no** matching Marvin MEM thread/prompt → **unmatched** (not an ad-hoc MEM row).

Inbound **subject-tag parsing for type** stays retired. Outbound may still use a human-readable subject (question text); correlation is **thread → prompt**, not Tom typing `[MB-MEM-n]`.

## 6. Verify-then-trash

1. Process → insert or soft-dedupe.  
2. Verify: response row(s) exist for `gmail_message_id`.  
3. If yes → `messages.trash(id)` for **that** message only.  
4. If no → leave in Inbox; log.

Poll queries must exclude Trash (`-in:trash`) so trashed mail is not re-ingested.

## 7. Effort (technical)

| Workstream | Invasiveness |
|------------|--------------|
| Plus-alias journal routing + unmatched without alias | Medium |
| MEM: reply/thread-only; reject ad-hoc +MEM | Medium |
| Trash-after-verify | Low–medium |
| EVS rip-out + drop `segment_index` | Medium (schema rebuild) |
| UI keys bar + remove EVS chrome | Low |
| MEM review controls (see clarified Q7) | Depends on your answer |

---

## 8. Clarified question #7 — MEM review UI

This is **not** about email subject keys. It is about the **buttons already on the Marvin Capture page** for the memory bank:

| Control | What it does today |
|--------|---------------------|
| **MEM sends: ON/OFF** | Arms/disarms the scheduler that emails you the next bank question (e.g. every other day at 01:00). |
| **Open questions JSON** | Opens `config/mem_questions.json` so you can edit the question list. |
| **Validate questions** | Checks ids are contiguous `1…N`, texts non-empty, etc. |
| **Extract MEM** | Writes answered questions to `exports/mem_bank/…` (combined + per-question files). |

**Q7 — What should happen to those four controls in MBC-004?**

Pick one (or mix):

- **A. Keep all four** as they are; only remove EVS buttons and change the top keys bar to plus-addresses.  
- **B. Keep sends + extract; drop or hide Open/Validate** (edit JSON by hand only).  
- **C. Change behavior** — describe (e.g. rename labels, move extract elsewhere, require sends ON only when using `+MEM`).  
- **D. Remove MEM UI entirely** for now (scheduler/config only via files/CLI) — not recommended if you still want ON/OFF and Extract.

---

## 9. Still open

### Q3 — Where does Marvin send MEM (and optional journal) mail?

When the bank sends question *n*, should **To:** be:

- **A.** `you+MEM@gmail.com` (recommended — matches inbound alias, keeps primary inbox filterable), or  
- **B.** plain `you@gmail.com` (reply thread still works; plus-address optional on reply)?

(Journal outbound is currently off while MEM bank owns the slot; same question if journal send returns later.)

### Q7 — MEM buttons  
See §8 above (A/B/C/D).

---

## 10. Blockers (updated)

| Blocker | Status |
|---------|--------|
| MEM = outbound→reply only; no ad-hoc | **Resolved** (§5) |
| Single alias `+MEM` | **Resolved** |
| Trash one message; subject-only → unmatched; drop `segment_index`; kill EVS | **Resolved** |
| **Q3 send To: address** | **Open** — needed before wiring MEM outbound `to` |
| **Q7 MEM UI chrome** | **Open** — needed so we don’t remove or keep the wrong buttons |
| Poll must ignore Trash | Implementation constraint (not a product unknown) |
| Schema drop `segment_index` | Requires response-table rebuild migration (doable; test carefully) |

---

## 11. Build plan (after Q3 + Q7)

1. Mark PRD Approved.  
2. Retire MBC-003 / EVS; migrate DB (drop `segment_index`; wipe EVS rows).  
3. Plus-address journal + MEM reply/thread rules; unmatched otherwise.  
4. Verify → trash; tests.  
5. UI: address table; EVS gone; MEM buttons per Q7.  
6. Set `mem_bank.to` per Q3; README update.

---

**No code until you answer Q3 and Q7 (A/B/C/D) and say build.**
