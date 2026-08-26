# MBSC-P2-I11B — Curator screen contract (v0.3)

**Status:** Planning · UX **locked** 2026-08-26 · pixels from v0.2 mocks are **illustrative**  
**Authority on conflict:** this contract + [MBPRD-P2-I11B v0.3](MBPRD-P2-I11B_HISTORIAN_LEARNING.md) beat the PNG.

**Screen set (variants):** [mockups/i11b/I11B_SCREEN_SET_v0.3.md](mockups/i11b/I11B_SCREEN_SET_v0.3.md)

v0.2 mockups remain in [MBUX-I11B-Curator-Feedback](../source/Screens/MBUX-I11B-Curator-Feedback/README.md) until founder drops replacement PNGs. Implementers follow the **required** column, not leftover mock chrome.

---

## Compact Curator (was Screen 01)

Keep `#mb-explore-curator` where it is. Fixed height. ~4–5 lines of summary (title + clamped body). Rating row inside that bound.

| Control | Required |
|---------|----------|
| Summary text | Clamped. Truncate at a natural boundary. |
| `[more]` | **Only** when text is truncated. Inline after visible text. Opens Full Response. |
| View full response | **Always.** Opens Full Response. |
| 👍 Good / 👎 Needs work | **Always** when Curator output exists. |
| Copy | **Absent** |
| Save as Story | **Absent** |
| Chips / avatar | Existing; do not grow the box. |

**Variants (replace a single Screen 01 PNG):**

| ID | When | Compact chrome |
|----|------|----------------|
| 01-A | Long TELL, truncated | `[more]` + View full response + thumbs |
| 01-B | Short summary, not truncated | **No** `[more]`; View full response + thumbs |
| 01-C | SHOW / Gallery-only, no narrative | No `[more]` unless counts/blurb truncated; View full response + thumbs; **no** edit/approve later |

v0.2 Screen 01 shows `[more]` and View full response together on a SHOW-like page. That is valid **only** if the blurb is truncated. If it fits, drop `[more]`.

---

## Full Response (was Screen 02)

Overlay. Does not change Gallery/timeline behind it.

| Control | Required |
|---------|----------|
| Close / X | Restore exact Explore state |
| Narrative tab | **Only if** a narrative exists; otherwise land on Evidence |
| Evidence / Details | No model IDs, no prompt dumps |
| 👍 / 👎 | Synced with compact rating |
| Copy | Here when there is copyable Curator text |
| Save as Story | Here when I11 story-draft applies (TELL), not on Gallery-only SHOW unless product already allows it |
| Edit / improve narrative | **Only if** a narrative exists |

v0.2 Screen 02 always shows a full biographical essay. For 01-C, Full Response is evidence/details + rating, not an empty Narrative editor.

---

## Needs work (was Screen 03)

Opened from 👎. Optional comments. Rating can save with empty fields.

| Field | Required |
|-------|----------|
| Narrative box | **Iff** a narrative exists |
| Gallery box | **Iff** a Gallery exists |
| Anything else / consent | Still **Open** (not in the five locks). Do not block v0.3 UX; omit from v1 unless Tom locks them. |

**Variants:**

| ID | When | Fields |
|----|------|--------|
| 03-A | TELL + Gallery | Narrative + Gallery |
| 03-B | Gallery only | Gallery only |
| 03-C | Narrative, empty Gallery | Narrative only |

v0.2 Screen 03 always shows both columns. That mock is 03-A only.

---

## Edit / approve (was Screen 04)

**Only if a narrative exists.** Seeded with generated text. “Editing does not change evidence.” Save as approved. Do not open this from 01-C.

---

## Feedback saved (was Screen 05)

Unchanged intent. Close returns to compact Curator + Gallery. This screen is **not** Person Explorer.

---

## Do not build from pixels

Until new PNGs exist, treat v0.2 images as mood/layout only. Do not copy: always-on `[more]`, always-on dual Needs-work columns, Edit on Gallery-only SHOW, Copy/Save as Story on the compact bar (already absent in Screen 01 — keep it that way).
