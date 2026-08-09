# MemoryBox Document Hierarchy

**Status:** Index · **Updated:** 2026-08-09  
**Purpose:** One-page map of what each document class is for — and what it is not.

MemoryBox documentation is layered. Lower layers do not replace upper ones. Implementation must not knowingly violate governing product constitution.

```text
Controlled product / architecture (docs/source)
  MBPS-001, MBEVS-001 v0.8, MBUX-001 v0.2, MBDM-001, MBEF-001, MBAA-001
  MB_LOCKED_DECISIONS_P1
Build execution
  MBBS-001 Build Specification
Philosophy / supporting
  Founder's Book (extract until DOCX checked in)
  MBX-A-* Functional Architecture
Commercial thesis
  MBBC Business Case (docs/mbbc)
Experience validation (program)
  MBVP-001, MBD-001 Demonstrator PRD
Capability / feature PRDs
  MBC-*, HVRT PRDs, parked evals
Operational / runbooks
  docs/*.md import & run notes
```

## Layer map

| Layer | Document | Location | Answers | Does not |
|-------|----------|----------|---------|----------|
| **Controlled specs** | MBPS / MBEVS v0.8 / MBUX v0.2 / MBDM / MBEF / MBAA | [`source/`](source/README.md) | What to build and how it is structured | Implementation tasks |
| **P1 decisions** | [MB_LOCKED_DECISIONS_P1](source/MB_LOCKED_DECISIONS_P1.md) | `docs/source/` | Locked **D1–D7** | Open debate |
| **P1 engineering rules** | [MB_P1_ENGINEERING_RULES](source/MB_P1_ENGINEERING_RULES.md) | `docs/source/` | Living specs, increment discipline, trust | Product EVS content |
| **Build spec** | [MBBS-001](product/MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) | `docs/product/` | Increments, acceptance, reuse | Product philosophy rewrite |
| **Decision log** | [MBBS_DECISION_LOG](product/MBBS_DECISION_LOG.md) | `docs/product/` | Per-increment decisions/deviations | Spec authority |
| Philosophy | Founder's Book v0.91 | `architecture/_tmp_extract/founders.txt` (extract) | Why MemoryBox exists | Pricing, architecture detail |
| Functional architecture | [MBX-A-001](architecture/MBX-A-001%20Functional%20Architecture%20Part%201.md) (+ planned 002–006) | `docs/architecture/` | Query model, evidence rules | Business model |
| Gap report | [MBX-A-001-GAP](architecture/MBX-A-001-GAP%20Gap%20Analysis%20vs%20Codebase%20and%20PRDs.md) | `docs/architecture/` | Gaps vs codebase/PRDs | Roadmap commitment |
| Business case | [MBBC Full v0.1](mbbc/MBBC_Full_V0.1.docx) + [mbbc README](mbbc/README.md) | `docs/mbbc/` | Why a company | Validated forecasts |
| EVS catalog | **[MBEVS-001 v0.8 XLSX](source/MBEVS-001_EVS_Catalog_v0.8.xlsx)** | `docs/source/` | Concrete experiences | Implementation design |
| ~~EVS markdown subset~~ | ~~[deprecated](mbbc/MBEVS-001_EVS_CATALOG.md)~~ | `docs/mbbc/` | Historical only | **Do not use** |
| Validation program | [MBVP-001](mbbc/MBVP-001_VALIDATION_PROGRAM.md) | `docs/mbbc/` | Proof gates → pilots | Feature backlog |
| Demonstrator | [MBD-001](product/MBD-001_MEMORYBOX_DEMONSTRATOR_PRD.md) | `docs/product/` | Near-term demo | Production architecture |
| Feature PRDs | e.g. [MBC-001](product/MBC-001_MARVIN_CAPTURE_PRD.md), HVRT docs | `docs/product/`, `hvrt/docs/` | Scoped builds | Company thesis |
| Ops | Import/run/sync docs | `docs/*.md` | How to run and ingest | Product constitution |

## Framing note (keep both)

- **Family Memory Platform** — commercial category (MBBC).
- **Trusted family historian** — product feel (Founder's Book / MBPS).

## Reading order

1. [source/README.md](source/README.md) + locked decisions  
2. MBPS-001 → MBAA-001 (as needed)  
3. [MBBS-001](product/MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md)  
4. MBEVS-001 v0.8 for acceptance scenarios  
