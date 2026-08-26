# MBPRD-P2-I11B — Historian Learning Layer & Curator Response Feedback

**Status:** Planning / pre-build · UX rules **locked 2026-08-26** · **not build-authorized**  
**Date:** 2026-08-26  
**Revision:** **v0.3** (UX locks). v0.2 Word file remains the historical master for purpose/data/learning; **v0.3 markdown wins** on Curator box behavior.  
**Increment:** P2-I11B (after I11A stabilization items 1–3; before I12)  
**Assessment:** [MBAS-P2-I11B_ASSESSMENT.md](MBAS-P2-I11B_ASSESSMENT.md)  
**Screen set:** [mockups/i11b/I11B_SCREEN_SET_v0.3.md](mockups/i11b/I11B_SCREEN_SET_v0.3.md)  
**Screen contract:** [MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md](MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md)  
**Definition (planning):** [MBBS-P2_INCREMENT_11B_DEFINITION.md](MBBS-P2_INCREMENT_11B_DEFINITION.md)  
**Founder binary (v0.2):** [docs/source/prd/MBPRD-P2-I11B_Historian_Learning_Layer_v0.2.docx](../source/prd/MBPRD-P2-I11B_Historian_Learning_Layer_v0.2.docx)  
**Screens (v0.2 pixels; contract supersedes on conflict):** [docs/source/Screens/MBUX-I11B-Curator-Feedback/](../source/Screens/MBUX-I11B-Curator-Feedback/README.md)

**Does not start:** I12 · model fine-tuning / LoRA · `/narration/ui` · unhide I8A gallery comms · changing historical evidence · I11A extract/compaction work

---

## Locked UX (v0.3)

The compact Curator box is a **stable response summary surface**. Additional dialogue is overlay. These five locks are Frozen:

1. **Bounded compact panel.** About **4–5 lines max**, **fixed height**. The box does not grow with narrative length and does not steal Gallery rows.
2. **Openers.** Inline **`[more]` only when truncated**. **View full response** is **always** available.
3. **Overall rating.** 👍 Good / 👎 Needs work is **always** available whenever there is Curator output.
4. **Targeted comments are gated.** Gallery feedback only when a Gallery exists. Narrative feedback, edit, and approve **only when a narrative exists**.
5. **Compact actions.** Copy and Save as Story live **only** in the Full Response modal — not on the compact box.

---

## 1. Purpose

I11B adds the Historian Learning Layer to the existing Ask/Explore experience. The Curator response is the **complete answer**: narrative (when present), Gallery (when present), and evidence/support presentation. The owner can rate that full answer, give targeted comments that apply, and optionally edit/save an approved narrative **without changing historical evidence**.

I11B v1 is a **preference-learning and exemplar-capture** layer, not model fine-tuning.

---

## 2. Compact Curator box

Location unchanged: immediately below the Ask bar, immediately above Gallery filters/results. Existing visual language. No dashboard or side panel.

- Fixed bounded height sized for ~4–5 lines of summary text (title + clamped body + rating row).
- Truncate at a natural boundary. Show inline `[more]` **only** when the compact text is truncated.
- **View full response** always present (short SHOW summaries and long TELL essays).
- 👍 / 👎 always present for Curator output (SHOW counts, TELL essay, mixed).
- Do not show Copy or Save as Story on this panel.

---

## 3. Full Response modal

Opened from `[more]` (when shown) or **View full response**.

- Overlay; Gallery and timeline stay populated behind it.
- Scrollable full narrative when a narrative exists; otherwise Evidence/Details as applicable.
- Copy and Save as Story here only, and only when they apply (a copyable response / I11 story draft).
- Overall Good / Needs work synchronized with the compact panel.
- Close restores Ask, Gallery, filters, and timeline position.

---

## 4. Feedback model

- Overall rating: `good` | `needs_work` for the **Curator output as a whole**.
- Needs work:
  - **Gallery** comment field **if** the current result has a Gallery.
  - **Narrative** comment field **if** the current result has a narrative.
  - Omit the unused field; do not show an empty Narrative box on a Gallery-only SHOW.
- Comment not required to save a rating.
- v1: no separate thumbs for Narrative vs Gallery.

---

## 5. Edit / approve narrative

- Only when a **narrative exists**.
- Only from the Full Response flow.
- Editor seeded with the generated narrative.
- Save as approved creates a presentation exemplar linked to the Ask/response and semantic pack.
- Trust note: editing does not change evidence.
- Keep the original generated narrative.

---

## 6. Functional requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Existing panel below Ask, above Gallery. |
| FR-2 | Fixed bounded height; about 4–5 lines of summary. |
| FR-3 | `[more]` only when truncated. |
| FR-4 | `[more]` and View full response open Full Response without changing Explore state. |
| FR-5 | View full response always available. |
| FR-6 | 👍 / 👎 always available for Curator output; sync compact ↔ modal. |
| FR-7 | Copy and Save as Story only in the Full Response modal. |
| FR-8 | Full Response: complete scrollable narrative when present; evidence access without model IDs. |
| FR-9 | Needs work: Gallery comments iff Gallery exists; Narrative comments iff narrative exists. |
| FR-10 | Edit / Save as approved iff narrative exists. |
| FR-11 | Persist original response, approved response, feedback, model/prompt versions, semantic-pack reference, Gallery asset IDs/order, timestamps. |
| FR-12 | Feedback never changes source evidence, relationships, dates, identity, provenance, or other historical facts. |
| FR-13 | Applicable approved examples/preferences retrievable for future historian/narrator calls. |
| FR-14 | Trace whether historian rubric, preferences, or approved examples were supplied to a future model call. |

---

## 7. Data to capture

`feedback_id`, ask/session/response/trace IDs, `ask_text`, `overall_rating`, `narrative_feedback` (null if no narrative), `gallery_feedback` (null if no Gallery), `generated_narrative` (null if none), `approved_narrative`, gallery asset IDs/order, semantic-pack ref/fingerprint, model/provider/version, historian_rubric_version, preference_context_version, timestamps.

---

## 8. Learning rules

- MemoryBox-level historian behavior and family-specific preference memory stay separate layers.
- Thumbs are weak signals; written feedback is stronger; curator-approved narrative is the strongest narrative exemplar.
- Gallery feedback is a **presentation-selection** preference, not evidence.
- I11B v1 uses feedback through **retrieval/context**, not automatic weight updates.
- Future fine-tuning/LoRA only after semantic inputs are trustworthy and privacy/consent rules exist.

---

## 9. Trust and privacy

Feedback and approved narratives are not historical evidence. Preferences may affect selection, emphasis, ordering, tone, and representative media **only within validated evidence**. Family-specific learning stays private to the archive unless the owner explicitly chooses otherwise. Generic MemoryBox model training is **out of scope** for I11B.

---

## 10. Acceptance

- Compact panel stays a fixed summary strip; Gallery is not crowded out.
- Long answers truncate; `[more]` appears only then; View full response always.
- 👍 / 👎 always on Curator output.
- Gallery comment path only with a Gallery; narrative comment/edit/approve only with a narrative.
- Copy / Save as Story absent from compact panel; present in modal when applicable.
- Closing the modal restores Explore context.
- Approved narrative saved when used; original generated response preserved.
- Feedback cannot mutate evidence or provenance.

---

## 11. Roadmap

P2-I11B **build** begins after I11A stabilization: (1) communication compaction/extraction quality, (2) Peggy/Person cross-source retrieval, (3) Ask-relative selection/correlation quality. Then I12. Spec work (this v0.3) may land now.
