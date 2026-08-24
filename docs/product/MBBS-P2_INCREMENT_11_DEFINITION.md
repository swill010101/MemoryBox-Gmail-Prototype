# P2-I11 — Narrative & Summaries (Ask output mode)

**Status:** Definition **LOCKED** 2026-08-24 (final evidence-prep decisions) · I10C **ACCEPTED** · **not authorized to build** until Tom reviews and approves  
**Assessment:** [MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md) · [evidence prep](MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md)  
**PRD:** [MBPRD-P2-I11_NARRATION.md](MBPRD-P2-I11_NARRATION.md)  
**Acceptance:** [MBAT-P2-I11_ACCEPTANCE.md](MBAT-P2-I11_ACCEPTANCE.md)  
**MBPS:** P2-NAR-01..03 (not P2-NAR-04 / I12)  
**Does not start:** I13 Save View UI · Narration app · Journal redesign · I12 · Face SoT · prep/LLM code

I10C is **ACCEPTED**. Do not block I11 on unrelated recognition.

---

## Intent

Ask/Explore **output mode**, not a destination. One shared Narrative/Curator component (Explore + Person Explorer). **No `/narration/ui`.**

SHOW/FIND → `show`. PLAY → `play`. TELL/SUMMARIZE/WHAT DO YOU KNOW/WHAT HAPPENED/WHAT WAS X LIKE → `tell`. Natural language, not a phrase table. Do not overload `act`.

I11 prepares a **grounded, Ask-specific evidence pack**. It must not become retrieve-chunks-and-call-the-model.

---

## Pipeline

Retrieve/eligibility (Spam/Trash out) → Narrative Evidence Preparation (units + claims + provenance) → hierarchical derived summaries when volume requires (not family truth; I7A) → provider-neutral LLM for `tell` only.

Model down: fail closed for prose; keep evidence/coverage; say narration unavailable. **No stitch fallback that looks like the essay.**

---

## Trust (claim-specific)

A source supports only the claim it can establish. Presence ≠ photographer, purpose, emotion, companions, causation. Media: no filename/folder/camera-owner-as-photographer. SMS time ≠ location. Calendar scheduled ≠ occurred.

Travel Asks correlate independent sources (itinerary, lodging, calendar, GPS/media, comms, Journal/Stories) before synthesis. Corroboration increases confidence; one strong source can suffice.

---

## Pack (see evidence-prep assessment)

`schema_version`, `ask`, `scope`, `units[]`, `derived_summaries`, `coverage`, `volume`, `evidence_used`.

Kinds: communication, media_observation, travel, calendar, journal, story, artifact, place_event, spoken_moment. Reserved `external_historical` for I12.

Authored email: derive at pack time; do not persist as an I11 gate. Email+SMS share communication shape. Hierarchical volume **IN**. Evidence-used footer counts **included units**.

Relative Asks: general semantic constraints on `QueryPlan` (e.g. age band), not phrase-specific fields.

---

## I11 vs I13

I11: output_mode, prep, tell LLM, shared curator, Copy, Save as Story, emit Saved View JSON.  
I13: Save View UI / Saved Views / Curated / Snapshot.  
No disabled Save View. Not Living Album.

---

**LOCKED 2026-08-24.** Do not implement until explicit build authorization.
