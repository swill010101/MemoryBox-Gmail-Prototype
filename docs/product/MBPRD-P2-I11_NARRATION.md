# MBPRD-P2-I11 — Narrative & Summaries (Ask output mode)

**Status:** PRD **LOCKED** 2026-08-24 · I10C **ACCEPTED** · **BUILD AUTHORIZED** 2026-08-24  
**Definition:** [MBBS-P2_INCREMENT_11_DEFINITION.md](MBBS-P2_INCREMENT_11_DEFINITION.md)  
**Assessment:** [MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md) · [evidence prep](MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md)  
**Acceptance:** [MBAT-P2-I11_ACCEPTANCE.md](MBAT-P2-I11_ACCEPTANCE.md)  
**Depends:** I10C Journal **ACCEPTED** · I10A · I10A.2 · I10B · MBQL-001 · I10 pack · I7A  
**Does not start:** `/narration/ui` · Journal redesign · I13 Save View UI · I12 retrieval · Face SoT · persisted authored-body as a gate

Narration is Ask **output**, not a new app. One shared long-form curator for Explore and Person Explorer. I11 prepares a **question-specific evidence pack**; it does not dump chunks into the model.

---

## Frozen (final 2026-08-24)

1. `output_mode` sibling on `QueryPlan`: `show` | `play` | `tell`. Natural-language semantic family. No phrase table. No overload of `act`.
2. Pipeline: deterministic retrieve/eligibility → Narrative Evidence Preparation → optional hierarchical derived summaries → LLM `tell` synthesis via provider-neutral `LlmProvider`. I7A traces provider, model, prepared context, response, errors. **No product-hard-coded host/model name. No product-level token cap as the semantic boundary.**
3. Pack schema: `schema_version`, `ask`, `scope`, `units[]`, `derived_summaries`, `coverage`, `volume`, `evidence_used`. Unit kinds: communication, media_observation, travel, calendar, journal, story, artifact, place_event, spoken_moment. Reserved: `external_historical` (I12; never family evidence).
4. **Claim-specific trust:** a source supports only the claim it can establish. Presence (identity + reliable place/time) ≠ photographer, purpose, motive, emotion, companions, causation, significance.
5. Media observation: human-relevant observations. Filename / folder / camera owner / archive owner are not photographer or purpose.
6. Trip Asks correlate travel confirmations, calendar, GPS/media, comms, Journal/Stories, places — then synthesize. Original itinerary/hotel/rental **email stays a communication unit**. When extraction is reliable, **also** emit a derived `travel` unit (flight/lodging/car/reservation + confirmation ref) with provenance to that email. **Never replace** the original with the derived record. Corroboration raises confidence; one strong source can suffice.
7. SMS timestamp is **not** location. Location `basis`: authored text | shared-location payload | attachment EXIF | corroborated other source.
8. Email authored body: **derive at pack time**, conservative. Do not persist authored-body as an I11 gate. Raw Email remains SoT. Spam/Trash out before the model.
9. Email + SMS → one communication shape. Narrow Peggy-and-I Asks: their authored units; group-thread metadata; no unrelated calendar dump.
10. Broad “my 2017”: owner + year + all relevant family evidence; still prepare/rank. Hierarchical volume management **IN**. Not first-N as the primary solution. Intermediate summaries are derived, traced, regenerable, not family truth. Disclose truncation.
11. Calendar: structured context; scheduled ≠ occurred without corroboration.
12. Substantial narration ends with **Family evidence used** counts of **normalized units supplied**, not raw hits or quoted copies. I12 later adds a separate external list.
13. Gallery hide ≠ pack exclude. Curator from pack. Shared curator **component** (do not merely unhide Person card).
14. Model unavailable: **fail closed** for prose. Evidence + coverage remain. No stitch that looks like the narrative.
15. Copy = clipboard. Save as Story = working draft + `composed_by_model`; owner Save Story for durability.
16. Saved View JSON: `schema_version`, `original_ask`, `output_mode`, `plan`, `presentation`. Essay is not the view. Relative language uses the **general semantic resolver**: store Person, resolved `age_band`, interpretation/version — not a `when_he_was_young` field and **not** a hard-coded `young = 10–25`. Birth fact (or other sufficient age/date evidence) converts the band to dates; if insufficient, **ask rather than guess**.
17. I13 owns Save View UI. No disabled Save View. Names: Save View / Saved View. Not Living Album.
18. Do not implement I12 in I11. Do not block on Face-SoT. Disclose missing coverage.

**Supersedes:** deterministic stitch as synthesizer; first-N as primary volume strategy; stitch fallback when the model is down; persist-authored-email as I11 gate.

---

## Success (when authorized and built)

Acceptance C-01–C-25 including dual travel units and “when Dad was young” generic constraints. No `/narration/` route.

---

**LOCKED 2026-08-24. BUILD AUTHORIZED 2026-08-24.**
