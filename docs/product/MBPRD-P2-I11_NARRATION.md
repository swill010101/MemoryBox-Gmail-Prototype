# MBPRD-P2-I11 — Narrative & Summaries (Ask output mode)

**Status:** PRD **LOCKED** · **BUILD AUTHORIZED** 2026-08-24 (Tom: “i11 next”)  
**Definition:** [MBBS-P2_INCREMENT_11_DEFINITION.md](MBBS-P2_INCREMENT_11_DEFINITION.md)  
**Assessment:** [MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md)  
**Acceptance:** [MBAT-P2-I11_ACCEPTANCE.md](MBAT-P2-I11_ACCEPTANCE.md) · `python -m memorybox prove-i11`  
**Depends:** I10C Journal **ACCEPTED** 2026-08-24 · I10A Stories · I10A.2 · I10B · MBQL-001 · I10 pack  
**Does not start:** `/narration/ui` · Journal redesign · I13 Save View UI · I12 · Face SoT · guided-capture campaigns

Founder lock: Narration is Ask / Explore **output**, not a new app.

---

## Frozen

1. Keep MBQL `act` as find / refine / navigate / clarify. Add sibling `output_mode`: `show` | `play` | `tell`.
2. SHOW / FIND → result set. PLAY → existing playable moment. TELL / SUMMARIZE / WHAT DO YOU KNOW → evidence-backed synthesis in the **existing curator**.
3. `Show me Peggy` stays `show`, not an essay.
4. `tell` retrieves the full supported pack. Gallery hide ≠ retrieve exclude. Curator for `tell` uses orchestrator prose from the pack, not visible tiles only.
5. Generated prose is **not** family truth. **Copy** = clipboard only. **Save as Story** = `POST /story/drafts` then `/story/ui?id=&edit=1`. Working draft may be model-proposed; **Save Story** (Ask-current) remains owner confirmation. Never auto-`save_story`.
6. No Save View chrome in I11. Freeze persistable JSON (`schema_version`, `original_ask`, `output_mode`, `plan`, `presentation`) for I13.
7. v1 synthesizer is **deterministic stitch** from statements / coverage / excerpts. Do not send every Ask to a model.
8. Person Explorer does not grow a second narration screen. Explore curator is the I11 surface.

---

## Success

`Tell me about…` compiles `tell` and can cite Journal / Story / hidden comms. `Show me…` stays counts. Copy creates no rows. Save as Story opens a working draft. `prove-i11` green. No `/narration/` route.

---

**LOCKED and BUILD AUTHORIZED 2026-08-24.**
