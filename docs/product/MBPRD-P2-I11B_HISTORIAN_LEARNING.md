# MBPRD-P2-I11B — Historian Learning Layer & Curator Response Feedback

**Status:** Planning / pre-build · **not locked** · **not build-authorized**  
**Date:** 2026-08-26  
**Revision:** v0.2 (founder Word spec) transcribed for the repo  
**Increment:** P2-I11B (after I11A stabilization items 1–3; before I12)  
**Assessment:** [MBAS-P2-I11B_ASSESSMENT.md](MBAS-P2-I11B_ASSESSMENT.md)  
**Definition (planning):** [MBBS-P2_INCREMENT_11B_DEFINITION.md](MBBS-P2_INCREMENT_11B_DEFINITION.md)  
**Founder binary:** [docs/source/prd/MBPRD-P2-I11B_Historian_Learning_Layer_v0.2.docx](../source/prd/MBPRD-P2-I11B_Historian_Learning_Layer_v0.2.docx)  
**Screens:** [docs/source/Screens/MBUX-I11B-Curator-Feedback/](../source/Screens/MBUX-I11B-Curator-Feedback/README.md)

**Does not start:** I12 · model fine-tuning / LoRA · `/narration/ui` · unhide I8A gallery comms · changing historical evidence · I11A extract/compaction work

Source: founder MBPRD v0.2 (2026-08-26). v0.2 corrects Curator UX to the real Ask/Explore screen.

---

## 1. Purpose

I11B adds the Historian Learning Layer to the existing Ask/Explore experience. The Curator response is the **complete answer**: narrative, Gallery, and evidence/support presentation. The owner can rate that full answer, give targeted Narrative and Gallery feedback, and optionally edit/save an approved narrative **without changing historical evidence**.

I11B v1 is a **preference-learning and exemplar-capture** layer, not model fine-tuning. Collect high-quality curator signals now so MemoryBox can improve future responses and later build a trustworthy training corpus.

---

## 2. Curator box (compact panel)

The Curator box is the response panel immediately below the Ask bar and immediately above Gallery filters/results.

Use the **existing** Curator panel location and visual language. Do not add a dashboard or side panel.

- Bound the panel: long-form reading belongs in the Full Response modal. Do not let the box grow with narrative length. Do not shrink the Gallery to make room for a long answer.
- If narrative exceeds the compact allowance, truncate at a natural boundary and show `[more]`.
- `[more]` / **View full response** opens the Full Response modal.
- Keep overall **Good** / **Needs work** in the compact box.
- Move **Copy** and **Save as Story** out of the compact box into the Full Response modal.

**Tom constraint (2026-08-26, planning):** keep the existing curator box and **keep it the same size**; additional dialogue and feedback open from that footprint. See assessment — this overrides a modest height increase unless Tom reopens it.

---

## 3. Full Response modal

Opened from `[more]` / View full response.

- Overlay the current Ask/Explore screen; Gallery and timeline stay populated behind it.
- Narrative fully scrollable.
- Copy and Save as Story live here.
- Evidence/details access without exposing internal model IDs or engineering terms.
- Overall Good / Needs work here too, **synchronized** with the compact-panel rating.
- Close returns to the exact Ask, Gallery, filters, and timeline position.

---

## 4. Feedback model

The user evaluates the **whole** Curator response, not only the prose.

- Overall rating: `good` | `needs_work`.
- Needs work reveals optional **Narrative** and **Gallery** text areas.
- Comment is not required to save a rating.
- v1: no separate thumbs for Narrative vs Gallery.

---

## 5. Edit / approve narrative

Available only from the Full Response feedback flow.

- Editor seeded with the generated narrative.
- Save creates a curator-approved narrative version linked to the Ask/response and semantic evidence pack.
- Trust note: editing the narrative does not change underlying evidence.
- Preserve the original generated narrative.
- Approved narrative is a **presentation exemplar**, not authoritative historical evidence.

---

## 6. Functional requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Render the Curator response in the existing panel below Ask and above Gallery. |
| FR-2 | Compact narrative allowance (PRD: ~4–5 lines; Tom: same box size as today). |
| FR-3 | Show `[more]` only when the response exceeds the compact allowance. |
| FR-4 | `[more]` opens Full Response without changing Explore state. |
| FR-5 | Overall Good / Needs work in the compact Curator box. |
| FR-6 | Copy and Save as Story only in the Full Response modal. |
| FR-7 | Full Response: complete scrollable narrative and evidence access. |
| FR-8 | Needs work reveals optional Narrative and Gallery feedback fields. |
| FR-9 | Optional narrative edit and Save as approved. |
| FR-10 | Persist original response, approved response, feedback, model/prompt versions, semantic-pack reference, Gallery asset IDs/order, timestamps. |
| FR-11 | Feedback never changes source evidence, relationships, dates, identity, provenance, or other historical facts. |
| FR-12 | Applicable approved examples/preferences retrievable for future historian/narrator calls. |
| FR-13 | Trace whether historian rubric, preferences, or approved examples were supplied to a future model call. |

---

## 7. Data to capture

`feedback_id`, ask/session/response/trace IDs, `ask_text`, `overall_rating`, `narrative_feedback`, `gallery_feedback`, `generated_narrative`, `approved_narrative`, gallery asset IDs/order, semantic-pack ref/fingerprint, model/provider/version, historian_rubric_version, preference_context_version, timestamps.

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

## 10. Acceptance (from founder PRD)

- With a populated Gallery, the Curator panel stays above the Gallery and does not crowd it out.
- Compact answers stay in the bounded panel; longer answers use `[more]`.
- Copy / Save as Story absent from compact panel; present in modal.
- Good / Needs work from compact panel or modal.
- Needs work supports separate optional Narrative and Gallery comments.
- Closing the modal restores Explore context.
- Approved narrative saved; original generated response preserved.
- Feedback cannot mutate evidence or provenance.
- A future similar Ask can retrieve applicable examples/preferences without hard-coding Ask type.

---

## 11. Roadmap

P2-I11B begins after I11A stabilization: (1) communication compaction/extraction quality, (2) Peggy/Person cross-source retrieval, (3) Ask-relative selection/correlation quality. Then I12.
