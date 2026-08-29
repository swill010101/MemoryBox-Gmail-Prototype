# MBAS-P2-I11B — Assessment (planning only)

**Status:** Planning · Curator UX **locked v0.3** · **build not authorized**  
**Date:** 2026-08-26  
**PRD:** [MBPRD-P2-I11B_HISTORIAN_LEARNING.md](MBPRD-P2-I11B_HISTORIAN_LEARNING.md) **v0.3**  
**Screen set:** [mockups/i11b/I11B_SCREEN_SET_v0.3.md](mockups/i11b/I11B_SCREEN_SET_v0.3.md)  
**Screen contract:** [MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md](MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md)  
**PNGs (illustrative):** [MBUX-I11B-Curator-Feedback](../source/Screens/MBUX-I11B-Curator-Feedback/README.md)

This increment is **UI + persistence of curator signals**. It must not reopen I11A inference, I11 narrator prompts, or evidence mutation.

---

## Problem now

Ask/Explore already returns a Curator panel plus Gallery. There is no way to say the **whole answer** (prose + media selection) was good or not, and no durable exemplar of an approved narrative. Copy / Save as Story sit on the compact panel (`#mb-explore-curator-actions` in `explore.html`), so long TELL essays compete with Gallery for height.

I11B exists so the family can rate and comment **without** growing the box, and so later historian calls can retrieve preferences/exemplars.

---

## What already exists (do not rebuild)

| Surface | Today |
|---------|--------|
| Compact Curator | `#mb-explore-curator` below Ask, above filters/Gallery. Avatar, title, body, coverage, note, Copy, Save as Story, chips. |
| Shared component | I11 locked one Curator for Explore + Person Explorer. |
| Save as Story | I11: stores a **draft story**; does not become family truth. I11B **moves** the control into the Full Response modal; it does not invent a second save path. |
| Evidence | Gallery + Evidence-behind-this-story footer. No “Full response” overlay. |
| Feedback | None. |

---

## Locked UX (v0.3) — Frozen

Tom locked these on 2026-08-26. They beat v0.2 PNG chrome.

1. Compact Curator is a **stable summary**: about **4–5 lines max**, **fixed bounded height**.
2. Inline **`[more]` only when truncated**. **View full response always**.
3. **👍 / 👎 always** available for Curator output (SHOW, TELL, mixed).
4. **Gallery feedback** only when a Gallery exists. **Narrative feedback / edit / approve** only when a narrative exists.
5. **Copy** and **Save as Story** live only in the Full Response modal.

Resolved from the earlier open list:

| Was open | Resolution |
|----------|------------|
| Same size vs 4–5 lines | **Fixed bound sized for ~4–5 lines.** The box does not grow with narrative length and does not steal Gallery rows. |
| View full always vs `[more]` only | **Both:** `[more]` iff truncated; View full **always**. |
| SHOW vs TELL | Feedback is gated by **what exists**, not by tell/show labels. Gallery comments iff Gallery; narrative comments/edit/approve iff narrative. Gallery-only SHOW still gets thumbs. |

---

## Screen-to-PRD map (v0.3)

| Screen | v0.3 | Do not copy from PNG |
|--------|------|----------------------|
| 01 Compact Curator | Clamp ~4–5 lines; `[more]` iff truncated; View full + thumbs always; no Copy/Save | Always-visible `[more]` |
| 02 Full Response | Overlay; Copy; Save as Story when applicable; thumbs synced | Person Explorer chrome unless locked into v1 |
| 03 Needs work | Columns gated (03-A / 03-B / 03-C) | Always two columns; “Anything else” / consent unless later locked |
| 04 Edit / approve | Narrative exists only | Opening on Gallery-only SHOW |
| 05 Saved | Confirmation; restore Explore | — |

---

## Still Frozen (product rules)

1. **Additional dialogue is overlay**, not an in-place expansion of `#mb-explore-curator`.
2. **One overall rating** (`good` \| `needs_work`) for the whole Curator output.
3. **Feedback never mutates evidence**, relationships, dates, identity, or provenance.
4. **Approved narrative is presentation exemplar**, not historical truth. Original generated text is kept.
5. **I11B v1 = retrieve/context**, not fine-tune/LoRA.
6. **I11A must stay in flight until** compaction quality, Person/Peggy cross-source retrieve, and Ask-relative selection are acceptable. I11B does not block finishing I11A; I11B **build** waits on that gate unless Tom explicitly parallelizes UI-only.

---

## In scope (when authorized)

- Compact Curator: clamp, `[more]` iff truncated, View full always, thumbs always; hide Copy / Save as Story from compact actions.
- Full Response modal: complete narrative when present; Copy; Save as Story; rating sync; Evidence/Details without engineering IDs.
- Needs work form: Narrative and/or Gallery comments per gates.
- Edit / Save as approved when a narrative exists; confirmation.
- Persist feedback + exemplar metadata with a stable `feedback_id`.
- Retrieval hook **stub or thin**: load applicable approved examples/preferences into future narrator/historian context and **trace** that they were supplied. Depth of retrieval ranking can be a later slice if Tom splits v1.

---

## Explicitly out

- Changing I11A Observation IR, extract batching, or llama3.2.
- Teaching the model from thumbs automatically.
- Separate Narrative vs Gallery thumbs.
- New dashboard / side panel / `/narration/ui`.
- Generic MemoryBox-wide model training.
- Unhiding I8A communications in the Gallery as part of this increment.
- Reworking timeline or filter chrome except as needed to not break restore-on-close.

---

## Remaining open (not in the five locks)

1. **Consent checkbox / “Anything else.”** Omit from v1 unless Tom locks them.
2. **Person Explorer.** I11 said one shared Curator. Explore-only first vs both in v1 is still Open. Screen 05 is **confirmation**, not Person Explorer.
3. **Save as Story vs Save as approved.** Two artifacts (I11 draft story vs I11B exemplar). Keep labels distinct. Not reopened; implementers must not collapse them.
4. **FR-13/14 retrieval depth in v1.** Persist + retrieve last-N approved for same person/ask-kind, or persist-only until I11A is stable?
5. **I11A gate.** Do not start I11B UI until Tom says I11A items 1–3 are good enough, or explicitly parallelize UI-only with no learning hook.

---

## Build plan (not authorized)

1. Schema + API for feedback records (no evidence writes).
2. Compact Curator CSS/JS: clamp, `[more]`, View full, rating buttons; move Copy/Save as Story to the modal.
3. Full Response modal + Needs work variants + Edit/approve + saved.
4. Wire rating sync compact ↔ modal.
5. Thin preference retrieval + I7A trace that historian context was attached.
6. Prove: compact height bounded; `[more]` only when truncated; modal restore; feedback persisted; evidence unchanged; Copy/Save absent from compact panel; gated comment/edit paths.

No implementation in this change set.
