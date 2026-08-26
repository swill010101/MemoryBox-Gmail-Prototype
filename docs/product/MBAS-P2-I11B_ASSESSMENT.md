# MBAS-P2-I11B — Assessment (planning only)

**Status:** Planning · **not locked** · **no build**  
**Date:** 2026-08-26  
**Inputs:** founder PRD v0.2 · five screens · Tom: keep existing curator box, **same size**, open additional dialogue, accept feedback  
**PRD:** [MBPRD-P2-I11B_HISTORIAN_LEARNING.md](MBPRD-P2-I11B_HISTORIAN_LEARNING.md)  
**Screens:** [MBUX-I11B-Curator-Feedback](../source/Screens/MBUX-I11B-Curator-Feedback/README.md)

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
| Save as Story | I11: stores a **draft story**; does not become family truth. I11B **moves** the control into the modal; it does not invent a second save path. |
| Evidence | Gallery + Evidence-behind-this-story footer. No “Full response” overlay. |
| Feedback | None. |

---

## Screen-to-PRD map

| Screen | Matches PRD | Deltas to lock |
|--------|-------------|----------------|
| 01 Compact Curator | Existing layout + `[more]` + Good / Needs work + View full response; Copy/Save gone | Always-visible **View full response** vs FR-3 (`[more]` only when truncated). Recommend both: `[more]` when truncated; **View full response** always available so Gallery-only/short answers can still be rated in the modal. |
| 02 Full response | Overlay, Narrative tab, thumbs, Close | Tabs **Evidence** / **Details** are not in FR-7 wording. Keep; do not leak model IDs. Thumbnails + “View all (N)” must not replace the live Gallery behind the modal. |
| 03 Needs work | Narrative + Gallery fields, 500 caps | Screen adds **Anything else** (optional) and **Allow MemoryBox to use my feedback** (checked). Not in FR-8. Recommend capture both: `other_feedback`, `consent_improve_answers`. |
| 04 Edit / approve | Seeded editor, 2000 cap, “does not change any evidence”, Save as approved | Toolbar (bold/lists/link) is presentation-only. Do not treat formatted HTML as evidence. |
| 05 Saved | Lightweight thank-you | Privacy bullets; Close. No new product surface. |

---

## Frozen if Tom signs off (proposed)

1. **Same Curator footprint.** Do not grow the panel with narrative length. Do not steal Gallery rows. Tom’s “same size” wins over PRD “increase modestly for 4–5 lines” unless he reopens it. Compact body uses CSS line-clamp / existing height; overflow is `[more]`.
2. **Additional dialogue is overlay**, not an in-place expansion of `#mb-explore-curator`.
3. **One overall rating** (`good` \| `needs_work`) for the whole response (narrative + Gallery).
4. **Feedback never mutates evidence**, relationships, dates, identity, or provenance.
5. **Approved narrative is presentation exemplar**, not historical truth. Original generated text is kept.
6. **I11B v1 = retrieve/context**, not fine-tune/LoRA.
7. **I11A must stay in flight until** compaction quality, Person/Peggy cross-source retrieve, and Ask-relative selection are acceptable. I11B does not block finishing I11A; I11B **build** waits on that gate.

---

## In scope (when authorized)

- Compact Curator: truncate + `[more]`; Good / Needs work; hide Copy / Save as Story from compact actions.
- Full Response modal: complete narrative; Copy; Save as Story; rating sync; Evidence/Details without engineering IDs.
- Needs work form: Narrative + Gallery comments; optional extra + consent if locked.
- Edit / Save as approved; confirmation.
- Persist feedback + exemplar metadata (FR-10) with a stable `feedback_id`.
- Retrieval hook **stub or thin**: load applicable approved examples/preferences into future narrator/historian context (FR-12) and **trace** that they were supplied (FR-13). Depth of retrieval ranking can be a later slice if Tom splits v1.

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

## Risks and open questions for Tom

1. **Same size vs 4–5 lines.** Screen 01 shows a slightly taller copy block than today’s one-paragraph curator. Confirm: clamp to **today’s pixel height**, or allow the mock’s ~4 lines?
2. **View full response always vs `[more]` only when truncated.** Recommend always + `[more]` when truncated.
3. **Consent checkbox default on.** Confirm opt-in is required to use text for future answers; rating-only still stored either way?
4. **SHOW vs TELL.** “show me tom will” mock is a **show** result (counts, not I11A essay). Feedback must work when there is **no** TELL narrative — Gallery-only comments still valid; Edit/approve disabled or N/A.
5. **Person Explorer.** I11 said one shared Curator. Does I11B land on Explore Ask only first, then Person Explorer, or both in v1?
6. **Save as Story vs Save as approved.** Two different artifacts (I11 story draft vs I11B exemplar). Keep labels distinct so “approved” is not mistaken for family truth.
7. **FR-12/13 depth in v1.** Persist + retrieve last-N approved for same person/ask-kind, or persist-only until I11A is stable?
8. **I11A gate.** Do not start I11B UI until Tom says I11A items 1–3 are good enough, or explicitly parallelize UI-only with no learning hook.

---

## Build plan (not authorized)

1. Schema + API for feedback records (no evidence writes).
2. Compact Curator CSS/JS: clamp, `[more]`, rating buttons; move Copy/Save as Story.
3. Full Response modal + Needs work + Edit/approve + saved.
4. Wire rating sync compact ↔ modal.
5. Thin preference retrieval + I7A trace that historian context was attached.
6. Prove: compact height bounded; modal restore; feedback persisted; evidence unchanged; Copy/Save absent from compact panel.

No implementation in this change set.
