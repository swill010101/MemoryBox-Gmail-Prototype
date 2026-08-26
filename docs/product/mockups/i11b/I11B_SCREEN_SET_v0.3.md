# I11B Curator screen set — v0.3 (locked)

**Authority:** `docs/product/MBPRD-P2-I11B_HISTORIAN_LEARNING.md` v0.3  
**Contract:** `docs/product/MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md`  
**PNGs:** `docs/source/Screens/MBUX-I11B-Curator-Feedback/` (v0.2, **illustrative**)

Do not treat a PNG as the spec when it contradicts the five locks. Do not generate replacement PNGs unless Tom supplies them.

**Not authorized to implement until Tom says build.**

## Five locks

1. Compact Curator: **4–5 lines max**, **fixed bounded height**.
2. Inline **`[more]` only when truncated**. **View full response** always.
3. **👍 / 👎 always** on Curator output.
4. **Gallery feedback** only if Gallery exists. **Narrative feedback / edit / approve** only if a narrative exists.
5. **Copy** and **Save as Story** only in the **Full Response** modal.

## Screen inventory

v0.2 filenames live under `docs/source/Screens/MBUX-I11B-Curator-Feedback/`. Short IDs below match the contract.

| ID | v0.2 PNG | v0.3 role | Required variants |
|----|----------|-----------|-------------------|
| 01 | `I11B_Screen_01_Populated_Ask_Curator_Feedback.png` | Compact Curator | **01-A** truncated + `[more]`; **01-B** fits, **no** `[more]`; **01-C** no narrative (SHOW / Gallery-only): thumbs + View full; `[more]` only if the blurb is truncated |
| 02 | `I11B_Screen_02_Full_Response_Modal.png` | Full Response modal | Copy and Save as Story here (when they apply); 👍/👎 synced with compact |
| 03 | `I11B_Screen_03_Needs_Work_Feedback.png` | Needs work overlay | **03-A** narrative + Gallery; **03-B** Gallery only; **03-C** narrative only |
| 04 | `I11B_Screen_04_Edit_Approve_Narrative.png` | Edit & approve | **Only if a narrative exists** (typically TELL). Hidden on Gallery-only SHOW |
| 05 | `I11B_Screen_05_Feedback_Saved.png` | Confirmation | Close returns to compact Curator + Gallery |

Person Explorer is **not** a screen in this set. Whether I11B v1 also lands on Person Explorer remains Open.

## PNG vs lock mismatches (do not implement as drawn)

| PNG | Mismatch | Implement |
|-----|----------|-----------|
| 01 | `[more]` shown on a SHOW-like page | `[more]` **only** when truncated; View full **always** |
| 01 | Compact Copy / Save as Story if present in live UI | Those controls belong on Screen 02 only (v0.2 Screen 01 already omits them — keep that) |
| 03 | Always two comment columns | Gate: Gallery field iff Gallery; Narrative field iff narrative |
| 03 | Optional “Anything else” / consent | Still Open; omit from v1 unless Tom locks them |
| 04 | Looks always-available after rating | Only when a narrative exists |
| 02 | “View in Person Explorer” chrome | Mock-only until Person Explorer is locked into v1 |

## Build order (when Tom authorizes)

1. Compact box + thumbs + View full (01-A / 01-B / 01-C)  
2. Full Response modal (02) with Copy / Save as Story  
3. Needs work overlay (03-A / 03-B / 03-C)  
4. Edit / approve (04) when narrative exists  
5. Saved confirmation (05)
