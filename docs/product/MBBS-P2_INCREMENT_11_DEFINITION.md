# P2-I11 — Narrative & Summaries (Ask output mode)

**Status:** Definition **LOCKED** 2026-08-24 · **BUILD AUTHORIZED** 2026-08-24 (Tom: “i11 next”)  
**Assessment:** [MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md](MBAS-P2-I11_NARRATION_LIVING_VIEW_ASSESSMENT.md)  
**PRD:** [MBPRD-P2-I11_NARRATION.md](MBPRD-P2-I11_NARRATION.md)  
**Acceptance:** [MBAT-P2-I11_ACCEPTANCE.md](MBAT-P2-I11_ACCEPTANCE.md) · `python -m memorybox prove-i11`  
**MBPS:** P2-NAR-01..03 (not P2-NAR-04 / I12)  
**MBQL:** extend `QueryPlan`; do not fork  
**Does not start:** I13 Save View UI · Curated/Snapshot products · Narration app · Journal redesign · I12

I10C Journal is **ACCEPTED**. Journal screens stay closed unless a contract defect appears.

---

## Intent

Narration is an **Ask / Explore output mode**, not a destination.

- **SHOW / FIND** → evidence/result set  
- **PLAY** → playable media / moment (existing viewer)  
- **TELL / SUMMARIZE / WHAT DO YOU KNOW** → evidence-backed synthesis in the **existing curator**

Gallery visibility must not limit `tell` evidence. Generated prose is **not** family truth. **Copy** creates nothing. **Save as Story** uses the existing Story editor. **Save View** (Living View) is Ask + normalized state, recomputed later — **I13**.

**No new Narration screen required.**

---

## Frozen product decisions (founder 2026-08-24)

See assessment § product decisions 1–12. Pixels and Explore I4 interaction reference still win over a new app.

Open questions (defaults for this build): Copy + Save as Story only; no Save View control. Synthesizer = deterministic stitch. Person Explorer does not fork a narration screen. I10C wait is cleared.

---

## Split vs I13

| Increment | Owns |
|---|---|
| **I11** | Compile `output_mode`; `tell` synthesizer; curator long-form; Copy; Save as Story; freeze persistable Ask JSON |
| **I13** | Named Save View reopen; Curated Collection; Snapshot; Living Album naming if kept |

---

**LOCKED and BUILD AUTHORIZED 2026-08-24.**
