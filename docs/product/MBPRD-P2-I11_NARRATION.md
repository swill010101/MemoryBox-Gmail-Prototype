# MBPRD-P2-I11 — Narrative & Summaries (Ask output mode)

**Status:** PRD **LOCKED** 2026-08-24 (founder narration-prep decisions) · I10C **ACCEPTED** · **do not implement** prep/LLM until explicit build authorization  
**Definition:** [MBBS-P2_INCREMENT_11_DEFINITION.md](MBBS-P2_INCREMENT_11_DEFINITION.md)  
**Assessment:** [MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md) · [evidence prep](MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md)  
**Acceptance:** [MBAT-P2-I11_ACCEPTANCE.md](MBAT-P2-I11_ACCEPTANCE.md)  
**Depends:** I10C Journal **ACCEPTED** · I10A · I10A.2 · I10B · MBQL-001 · I10 pack · I7A traces  
**Does not start:** `/narration/ui` · Journal redesign · I13 Save View UI · I12 · Face SoT · guided-capture campaigns

Narration is Ask / Explore **output**, not a new app. Same Tell experience in Person Explorer.

---

## Frozen (founder 2026-08-24)

1. Sibling `output_mode` on `QueryPlan`: `show` | `play` | `tell`. Do not overload `act`. Semantic family from natural language, not a phrase table.
2. Pipeline: deterministic retrieve/eligibility → **Narrative Evidence Preparation** → LLM synthesis for `tell` only. Model does not clean the archive or judge Spam/Trash.
3. Evidence scope follows **this Ask** (narrow vs broad). Not “all data in the window.”
4. Spam/Trash excluded from Ask/Narration before the model. Originals may remain. No model-side “ignore spam.”
5. Email: authored-message representation; drop repeated quotes when independent messages exist; conservative if uncertain; provenance to original. Participant filter for “Peggy and I”; keep `group_thread` metadata.
6. SMS: same Communication Evidence abstraction as Email.
7. Calendar: normalized contextual units; query-dependent selection; scheduled ≠ occurred without corroboration.
8. Photos / video moments / Journal / Stories / Artifacts: human-relevant content + provenance, not provider dumps or obsolete versions.
9. Volume: staged reduction; provenance retained; intermediate summaries not authoritative.
10. Gallery visibility does not constrain the pack. Curator from pack, not `visible_items`.
11. Shared long-form curator: Explore + Person Explorer. Copy. Save as Story (working draft, `composed_by_model`, owner Save Story). No auto Story truth.
12. I11 emits Saved View JSON (`schema_version`, `original_ask`, `output_mode`, `plan`, `presentation`). I13 owns Save View UI. No disabled Save View control. Names: **Save View** / **Saved View**. Not Living Album. Saved View ≠ Curated Collection ≠ Snapshot.
13. Do not block on Face-SoT. Disclose missing coverage. Journal is a first-class pack source (I10C ACCEPTED).

**Supersedes:** “v1 synthesizer = deterministic stitch / no tell model.”

---

## Success (when authorized and built)

`Tell me about…` / discussion / year / trip Asks produce pack-grounded, I7A-traced prose. `Show me Peggy` stays a result set. Hidden comms can inform tell. Copy creates nothing. Save as Story is a working draft. Person Explorer Tell matches Explore. `prove-i11` covers the contract. No `/narration/` route.

---

**LOCKED 2026-08-24.** Not authorized to implement prep/LLM until Tom approves this PRD to build.
