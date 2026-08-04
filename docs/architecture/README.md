# Memory Box Architecture

This folder holds **system architecture** ([MBAR-001](MBAR-001%20Memory%20Box%20System%20Architecture.md)) and **Functional Architecture** elaborations (MBX-A-*).

**Governed by:** [Founder's Book (MB-FB-001)](../product/MB-FB-001%20Memory%20Box%20Founders%20Book.md) → [MBPS-001](../product/MBPS-001%20Memory%20Box%20Product%20Specification.md) → ( [MBUX-001](../product/MBUX-001%20Memory%20Box%20User%20Experience%20Specification.md) · [MBKM-001](../product/MBKM-001%20Memory%20Box%20Knowledge%20Model.md) · [MBMS-001](../product/MBMS-001%20Memory%20Box%20Mental%20Model.md) · [MBIA-001](../product/MBIA-001%20Memory%20Box%20Information%20Architecture.md) ) → **[MBAR-001](MBAR-001%20Memory%20Box%20System%20Architecture.md)** → **MBX-A-***.

**Terminology:** [MB-RECONCILE-001 Core Terminology and Principles](../product/MB-RECONCILE-001%20Core%20Terminology%20and%20Principles.md) is binding for shared terms and conflict resolutions. **MBX-A-003** (Canonical Data Model) derives from **MBKM-001 + MB-RECONCILE-001 + MBAR-001 authority/provenance dimensions**.

Product documentation lives in [`docs/product/`](../product/README.md). Project README and operational docs under `docs/` remain project documentation. They point here; they do not duplicate the product constitution.

## System architecture

| Doc | Title | Status |
|-----|--------|--------|
| [MBAR-001](MBAR-001%20Memory%20Box%20System%20Architecture.md) | Memory Box System Architecture (technology-neutral) — Memory Reconstruction, heart pipeline, Understanding + Archive Growth loops | **Governing (system)** — parents MBX-A-* |

## Functional architecture series (elaborations under MBAR-001)

| Doc | Title | Status |
|-----|--------|--------|
| [MBX-A-001](MBX-A-001%20Functional%20Architecture%20Part%201.md) | Functional Architecture Part 1 — Foundational Principles & Query Model | **Governing (functional)** — subordinate to MBAR-001 |
| MBX-A-002 | Part 2 — Functional Components & Layer Responsibilities | Planned |
| MBX-A-003 | Part 3 — Canonical Data Model (personal knowledge graph of a life; RDBMS may store it) — **derive from [MBKM-001](../product/MBKM-001%20Memory%20Box%20Knowledge%20Model.md) + [MB-RECONCILE-001](../product/MB-RECONCILE-001%20Core%20Terminology%20and%20Principles.md) + [MBAR-001](MBAR-001%20Memory%20Box%20System%20Architecture.md)** | Planned |
| MBX-A-004 | Part 4 — Query Planning & Reconstruction Pipeline | Planned |
| MBX-A-005 | Part 5 — Learning Architecture | Planned |
| MBX-A-006 | Part 6 — User Experience (subordinate to [MBUX-001](../product/MBUX-001%20Memory%20Box%20User%20Experience%20Specification.md)) | Planned |

## Reconciliation

| Doc | Title | Status |
|-----|--------|--------|
| [MB-RECONCILE-001](../product/MB-RECONCILE-001%20Core%20Terminology%20and%20Principles.md) | Core Terminology and Principles (FB · MBPS · MBUX · MBKM · MBMS · MBIA) | **Binding** |
| [MBX-A-001-RECONCILE](MBX-A-001-RECONCILE%20Founders%20Book%20and%20MBPS%20vs%20Functional%20Architecture.md) | Founder's Book and MBPS vs Functional Architecture | Report |
| [MBX-A-001-RECONCILE-MBUX](MBX-A-001-RECONCILE-MBUX.md) | MBUX-001 vs Product & Functional Architecture | Report |

## Rule

No implementation shall knowingly violate the Founder's Book, MBPS-001, domain peers (for their domains), MB-RECONCILE-001, **MBAR-001**, or the governing Functional Architecture elaborations. An implementation roadmap is deferred until MBX-A Parts 1–6 are complete; technology selection belongs in MBTS-001 thereafter.
