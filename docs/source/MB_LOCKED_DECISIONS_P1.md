# MemoryBox P1 locked decisions

**Status:** Locked · **Date:** 2026-08-09 · **Owner:** Tom  
**Source:** Build-Readiness Assessment sign-off

These decisions govern [MBBS-001](../product/MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) and all P1 implementation. Do not reopen without an explicit founder decision record.

**Also governing:** [MB_P1_ENGINEERING_RULES.md](MB_P1_ENGINEERING_RULES.md) (Living Specs, one-increment-at-a-time, provenance, no false memories, etc.)

| ID | Decision | Lock |
|----|----------|------|
| **D1** | Authoritative specification set lives in [`docs/source/`](README.md); obsolete 20-EVS markdown catalog is deprecated | **YES** |
| **D2** | Production application = **new modular monolith**; POC code becomes **adapters/engines**, not the product architecture | **YES** |
| **D3** | Authoritative MemoryBox domain store = **PostgreSQL** from the first production increment | **YES** |
| **D4** | HVRT runs as a **sibling background worker** behind the **Video Intelligence Provider** interface (same logical product; separate process) | **YES** — sibling worker |
| **D5** | P1 EVS gate: communications + Immich photo Ask + Story voice versions + Review teach first; **EVS-014 remains P1** but is **sequenced later within P1** (after Person & Identity) | **YES** |
| **D6** | P1 is **single-owner** (multi-user / family permissions deferred) | **YES** |
| **D7** | **P1 deployment topology + portability:** (1) **FlightSim** is the defined P1 runtime host for the MemoryBox **application** and MemoryBox-owned runtime services — including **PostgreSQL**, **Qdrant**, and local **Ollama**/model service where practical. (2) **media-server** remains the **media host**; Immich, Plex, photos, videos, and related media libraries/storage stay on media-server — MemoryBox accesses them **remotely** via provider interfaces and configured network endpoints; **do not** move or duplicate media libraries onto FlightSim in P1. (3) Development may continue on the **dev box**, but **Increment 3+** must be **deployable to FlightSim without source-code changes**. (4) All host/service locations are **configuration-driven** — do not hard-code FlightSim, media-server, localhost, Windows drive letters, IP addresses, credentials, or development-machine paths into application logic. (5) **Git** = deployable app code only; secrets, runtime data, databases, caches, and machine-specific config excluded from Git | **YES** |

## MBBS-001 v0.2 founder revisions (2026-08-09)

Applied in [MBBS-001](../product/MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md):

1. Journal (EF-12) = **P1** (Increment 5A)  
2. Guided Capture email + in-app (EF-11) = **P1** (Increment 11)  
3. Basic contextual follow-up (EF-02) = **Increment 4** with Ask  
4. Minimum viable Export (EF-16) = **P1** (Increment 12)  
5. Derived-index **rebuildability** = global P1 acceptance criterion  

## MBBS-001 v0.3 — P1 engineering rules (2026-08-09)

Standing process/trust rules approved; see [MB_P1_ENGINEERING_RULES.md](MB_P1_ENGINEERING_RULES.md). Increment 1 accepted under these rules.

## Implications

- MBD-001 “keep existing POC databases” applies to the **demonstrator**, not the production app. Production follows MBAA + D2/D3.  
- Do not push archive takeout/mbox or `hvrt/sample` media via git (see root `.gitignore` and [`../GIT_SYNC.md`](../GIT_SYNC.md)).  
- Build **only** the owner-authorized MBBS increment; demonstrate acceptance; update living specs; then stop.  
- **D7:** Same Git tree: develop on desktop; deploy to **FlightSim** (app + PG + Qdrant + Ollama where practical) by config only from Increment 3 onward. Media libraries stay on **media-server**; Immich/etc. reached via configured provider endpoints — never bake hostnames, IPs, drive letters, or credentials into application logic; never commit secrets or host-local paths as required product defaults.  
