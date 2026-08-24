# P2-I11 — Narrative & Summaries (Ask output mode)

**Status:** Definition **LOCKED** 2026-08-24 (founder narration-prep decisions) · I10C **ACCEPTED** · **synthesis/prep implementation not authorized** until Tom says approved to build **this** contract  
**Assessment:** [MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md) · [evidence prep](MBAS-P2-I11_NARRATIVE_EVIDENCE_PREPARATION.md)  
**PRD:** [MBPRD-P2-I11_NARRATION.md](MBPRD-P2-I11_NARRATION.md)  
**Acceptance:** [MBAT-P2-I11_ACCEPTANCE.md](MBAT-P2-I11_ACCEPTANCE.md) · `python -m memorybox prove-i11` (harness tracks compile/curator contract; tell-LLM prove lands with authorization)  
**MBPS:** P2-NAR-01..03 (not P2-NAR-04 / I12)  
**MBQL:** extend `QueryPlan`; do not fork `act`  
**Does not start:** I13 Save View UI (including disabled Save View) · Curated/Snapshot products · Narration app · Journal redesign · I12 · Face SoT

I10C Journal is **ACCEPTED**. Journal screens stay closed unless a contract defect appears. Do **not** block I11 on unrelated recognition work.

---

## Intent

Narration is an **Ask / Explore output mode**, not a destination. Same Ask behavior in general Explore and Person Explorer. **No `/narration/ui`.**

- **SHOW / FIND** → result set  
- **PLAY** → playable media / moment (existing viewer)  
- **TELL / SUMMARIZE / WHAT DO YOU KNOW / WHAT HAPPENED / WHAT WAS X LIKE** → evidence-backed prose in the **shared** long-form curator  

Natural language selects the semantic family. Do not implement a literal phrase table. Do not overload MBQL `act`.

---

## Pipeline (locked)

Deterministic: people, places, events/trips, time, communication identities, retrieve, eligibility, user filters, evidence scope, provenance, coverage/gaps/conflicts, trust, visibility.

Then **Narrative Evidence Preparation** → normalized pack (smallest complete representation for **this** Ask).

Then **LLM synthesis** for `tell` only. I7A traces the request/response and orchestrator/pack state. The model does not clean the archive or elect Spam/Trash.

Gallery hide ≠ pack exclude. Curator for `tell` is from the pack, not `visible_items`.

---

## Evidence scope follows the Ask

Necessary and relevant to **this** question — not “everything in the date range.”

| Ask | Pack |
|---|---|
| Peggy and I discussed at Christmas 2017 | Peggy + owner + Christmas 2017 + communications; calendar only if it involves them or the thread/place/topic |
| Write a narrative about my 2017 | Owner + 2017, broad modalities; still rank, do not dump every row to the model |
| Tell me about Peggy's 2017 | Peggy + 2017 across supported evidence |
| Summarize our Alaska trip | Alaska trip evidence, including hidden comms when relevant — not unrelated same-year items |

Spam/Trash: excluded from Ask/Narration **before** the model. Originals may remain in the import. No “send spam and tell the model to ignore it.”

Email: authored-message units; strip repeated quotes when prior messages exist independently; conservative if uncertain. SMS: same Communication Evidence shape; group-thread metadata; participant filter for Peggy/Tom-specific Asks. Calendar: contextual units; scheduled ≠ occurred without corroboration.

Volume: retrieve → organize → dedupe → significance → compact units with provenance. Hierarchical summaries, if any, are traced and not authoritative evidence.

---

## I11 vs I13

| Increment | Owns |
|---|---|
| **I11** | `output_mode`; Narrative Evidence Preparation; tell LLM; shared long-form curator (Explore + Person Explorer); Copy; Save as Story; emit persistable Saved View JSON |
| **I13** | **Save View** / reopen / manage **Saved Views**; Curated Collections; Snapshot/frozen views |

I11 does **not** ship Save View UI. Do not add a disabled Save View control.

User-facing later: action **Save View**, object **Saved View** (live/recompute). Do not use **Living Album** as the family name. Keep Saved View ≠ Curated Collection ≠ Snapshot.

---

## Copy / Save as Story / Saved View JSON

- **Copy:** clipboard of current narrative text. No object, no Ask mutation.  
- **Save as Story:** working draft + proposed text + people/place/time + supporting evidence; `composed_by_model`; Story editor; Ask-current only on owner Save Story.  
- Persistable JSON: `schema_version`, `original_ask`, `output_mode`, `plan`, `presentation`. Store original wording **and** normalized plan (e.g. “Dad when he was young”). I13 persists and reopens.

---

## Presentation

Grow the existing curator: readable width, multiple paragraphs, vertical expansion, optional collapse, evidence access, Copy, Save as Story. Gallery/timeline remain for drill-down.

---

A prior tree may contain compile/curator/Copy/Save-as-Story scaffolding and a **deterministic stitch**. That stitch is **not** the authorized synthesizer. Do not implement prep/LLM until explicit build authorization on this definition.

---

**LOCKED 2026-08-24.** Synthesis/prep **not** build-authorized until Tom says so.
