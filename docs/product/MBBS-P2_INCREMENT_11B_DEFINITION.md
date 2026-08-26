# P2-I11B — Historian Learning Layer & Curator Response Feedback

**Status:** Planning **only** · Curator UX **locked v0.3** · definition otherwise **not locked** · **BUILD NOT AUTHORIZED**  
**Date:** 2026-08-26  
**PRD:** [MBPRD-P2-I11B_HISTORIAN_LEARNING.md](MBPRD-P2-I11B_HISTORIAN_LEARNING.md) **v0.3**  
**Assessment:** [MBAS-P2-I11B_ASSESSMENT.md](MBAS-P2-I11B_ASSESSMENT.md)  
**Screen set:** [mockups/i11b/I11B_SCREEN_SET_v0.3.md](mockups/i11b/I11B_SCREEN_SET_v0.3.md)  
**Screen contract:** [MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md](MBSC-P2-I11B_CURATOR_SCREEN_CONTRACT.md)  
**PNGs (illustrative):** [docs/source/Screens/MBUX-I11B-Curator-Feedback/](../source/Screens/MBUX-I11B-Curator-Feedback/README.md)

**Depends:** I11 Ask/Explore Curator (Copy, Save as Story, tell/show) · I11A inference pack identity for feedback persistence · I11A stabilization items 1–3 before **build**

**Does not start:** I12 · fine-tuning · evidence mutation · I11A extract work · `/narration/ui`

---

## Intent

Keep the **existing** Curator box on Ask/Explore as a **fixed** ~4–5 line summary. Open additional dialogue (Full Response / Needs work / Edit) as overlays. Rate the whole Curator output. Comment on Gallery only when Gallery exists; comment/edit/approve narrative only when a narrative exists. Copy and Save as Story live in the Full Response modal. Store signals as learning exemplars, not as historical facts.

---

## Gate

Do not implement until Tom **explicitly authorizes build**. UX height, `[more]`/View full, SHOW-vs-TELL gating, thumbs, and Copy/Save placement are **locked** in v0.3. Remaining open: consent / “anything else”, Person Explorer in v1, retrieval-hook depth, I11A items 1–3.
