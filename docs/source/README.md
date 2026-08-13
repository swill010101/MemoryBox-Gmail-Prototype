# Controlled MemoryBox specifications (P2)

**Status:** P2 locked sources · MBCAP-001 v0.2 + MBUX-001 v0.4 full baseline ingested 2026-08-13  
**Rule:** On conflict with supporting or historical docs, **flag** — do not silently reinterpret.  
**DOCX / PDF masters win** over markdown extracts.

## Authority order (P2 iteration)

1. [MBPS-002](MBPS-002_MemoryBox_Product_Specification_P2_Iteration_v0.1.docx) — P2 Product Specification (WHAT)  
2. [MBEVS-001 v1.0](MBEVS-001_EVS_Catalog_v1.0.docx) — Experience Validation Scenario Catalog  
3. Supporting specs (as updated for P2):  
   - [MBUX-001 v0.4](MBUX-001_MemoryBox_UX_Foundation_and_Design_Principles_v0.4.docx) — UX foundation (governing interaction / visual rules)  
   - [MBCAP-001 v0.2](MBCAP-001_MemoryBox_Capability_Catalog_P2_v0.2.docx) — reusable capabilities (EVS → Capability → Increment)  
4. Execution sequencing: [MBRM-001A](../product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) · Increment definitions under `docs/product/MBBS-P2_INCREMENT_*.md`  
   (Prior shell-first draft: [MBRM-001](../product/MBRM-001_P2_ROADMAP.md))

## Readable markdown extracts (not substitutes for masters)

- [MBPS-002 extract](../product/MBPS-002_P2_PRODUCT_SPECIFICATION.md)
- [MBEVS-001 v1.0 extract](../product/MBEVS-001_EVS_CATALOG_v1.0.md)
- [MBUX-001 v0.4 extract](../product/MBUX-001_v0.4.md) — **full baseline** (includes approved §22 exploration patterns)
- [MBCAP-001 v0.2 extract](../product/MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md)
- Planning delta: [MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md](../product/MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md)
- Historical: [MBUX-001 v0.4 I4 addendum](../product/MBUX-001_v0.4_I4_MIXED_MEDIA_EXPLORATION_ADDENDUM.md) — absorbed into full MBUX-001 v0.4; kept for I4 history

## Build / authorization gate

Roadmap defines sequence. **No increment build** until owner approves the roadmap and then approves that increment’s definition document. Docs ingest ≠ feature authorization.
