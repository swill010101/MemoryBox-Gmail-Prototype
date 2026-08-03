# MBX-A-001-RECONCILE-MBUX — MBUX-001 vs Product & Functional Architecture

| Field | Value |
|-------|--------|
| **Doc ID** | MBX-A-001-RECONCILE-MBUX |
| **Related** | [MBUX-001](../product/MBUX-001%20Memory%20Box%20User%20Experience%20Specification.md), [MB-FB-001](../product/MB-FB-001%20Memory%20Box%20Founders%20Book.md), [MBPS-001](../product/MBPS-001%20Memory%20Box%20Product%20Specification.md), [MBX-A-001](MBX-A-001%20Functional%20Architecture%20Part%201.md) |
| **Status** | Report only — no implementation |
| **Purpose** | Place MBUX-001 in the hierarchy and flag Soft conflicts before MBX-A-006 |

## Authority

**Founder's Book → MBPS-001 → MBUX-001 → MBX-A-*** (including planned MBX-A-006).

- MBUX-001 = product **experience constitution** (curator, modes, conversation, never-say, trust presentation).
- MBX-A-006 = functional **UX architecture** (how Ask/clarify/evidence/confidence bind to Reconstruction and Learning). It elaborates MBUX; it does not replace it.
- MBUX does not override Evidence-First mechanics in MBX-A-001.

## Alignment (high)

| Theme | MBUX | Higher / MBX-A | Status |
|-------|------|----------------|--------|
| People are the reason | Design commandments; Ch 9 | Founder's Book; MBPS Person anchor | **Aligned** |
| Curator / family historian | Ch 1 | Founder's philosophy; MBPS design goals | **Aligned** |
| Never invent; evidence before assumption | Ch 18–20, 29–30 | MB-P-001…003; Founder's ethics | **Aligned** |
| Ask when uncertain; invite not instruct | Ch 4, 7, 19 | MB-P-004; MBPS thoughtful questions | **Aligned** |
| Human teaches; archive grows | Ch 6, 16–17, 21 | MB-P-005; Learning hierarchy; MBPS Teach/Learn | **Aligned** |
| Narrative from evidence; evidence available | Ch 18, 20 | Reconstruction; citations | **Aligned** |
| Owner / family control | Ch 24, 28; Family Mode | Founder's trust; MBPS privacy open questions | **Aligned** intent |

## Soft conflicts / naming

| Issue | Resolution |
|-------|------------|
| **Confidence 71%** forbidden in MBUX; MB-P-006 wants explained confidence | UX uses human phrasing (“I think…”, “reasonably confident…”). Engineering may keep ordinal High/Moderate/Low/Unknown + reasons; never show raw percentages as primary UI. |
| **MB-P-008** Facts / Observations / Inferences / Unknowns | Not named in MBUX. Keep as engineering/product label set; present in human language in UI (Part 6 / A-006). |
| **Story vs Narrative** | MBUX uses “story” broadly. Keep MBPS distinction: human **Story** vs AI **Narrative**. Narrative comes first in answer presentation; evidence second (MBUX Ch 20). |
| **Explorer Mode lists Search** | Capability access for power users — not a redefinition of MB as a search engine (MBX-A §12). |
| **Family Mode / stewardship / sharing** | Product-real in MBUX; prototype is single-owner Ask. **Extends** — build only after Share/stewardship architecture exists. |
| **Every interaction enriches the archive** | Stronger than current Ask (learning thin). Aligns with Learning Layer intent; delivery is **Partial** today. |

## Source gaps in MBUX-001 v0.9

- Chapters **2–3 missing** (1 → 4).
- Chapters **31–35** are stubs (visual language, journey maps, delight, accessibility, manifesto).
- Do not treat stubs as complete UX or design-system requirements.

## Implications

| Doc | Implication |
|-----|-------------|
| **MBX-A-002…005** | Still next architecture work; do not skip to UI because MBUX exists. |
| **MBX-A-006** | Bind curator voice, silence-as-feature, never-say list, modes, evidence-after-narrative, confidence phrasing to functional pipelines. |
| **Implementation** | No UI rewrite authorized by canonizing MBUX alone. |

## Bottom line

MBUX-001 v0.9 is **governing product UX** under MBPS. It reinforces Evidence-First and raises the experience bar (curator, modes, enrichment, Family Mode). Functional architecture and the prototype remain incomplete relative to that bar; roadmap stays deferred until MBX-A Parts 1–6 are coherent with product docs.
