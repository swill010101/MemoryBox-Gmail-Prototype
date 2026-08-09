# MemoryBox P1 Engineering Rules

**Status:** Governing for all P1 increments · **Approved:** 2026-08-09 · **Owner:** Tom  
**ID:** MB-P1-RULES  
**Applies with:** [MB_LOCKED_DECISIONS_P1.md](MB_LOCKED_DECISIONS_P1.md) · [MBBS-001](../product/MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md)

These rules govern **every** P1 increment. They do not replace MBPS / MBEVS / MBUX / MBDM / MBEF / MBAA; they constrain how we implement and how we keep those documents truthful.

**Conflict rule:** If a requested change conflicts with a locked decision (**D1–D7**) or a higher-authority controlled specification, **stop and flag** for owner resolution. Do not silently supersede a controlled specification in code.

---

## Living Specification Rule

During P1 development, approved product decisions discovered through implementation and user evaluation **must be propagated to all affected controlled specifications before the affected increment is accepted**.

- No end-of-P1 documentation cleanup.  
- Controlled specifications must describe the product we are **actually building** throughout P1.  
- Implementation must not silently become the new specification.  
- If using the application teaches that a specification is wrong: **change the specification deliberately** (Working Software Gets a Vote — Not the Final Vote).

---

## Process rules

| Rule | Requirement |
|------|-------------|
| **One Increment at a Time** | Build only the authorized MBBS increment. Do not start the next because it is convenient. |
| **Acceptance Before Advancement** | An increment is complete only when its MBBS acceptance criteria are **demonstrated**, not merely when code compiles or unit tests pass. |
| **Change-Impact Check** | Before a material change, identify impact on **EVS → UX → Domain → Experience Flow → Architecture → Build Spec**. Update every affected authoritative document in that increment. |
| **No Silent Architecture Changes** | Architectural changes may be **recommended**, but must not be made solely to solve an implementation problem. Conflicts return to the owner. |
| **Stop on Expensive Ambiguity** | Ordinary implementation choices are fine. If a choice materially affects Domain Model, data ownership, architecture, security/privacy, provider independence, or would be expensive to reverse — **stop and ask**. |
| **Decision / Deviation Log** | Each increment records: decisions discovered, specs changed, intentional deviations, accepted tech debt, unresolved questions, and why. See [MBBS_DECISION_LOG.md](../product/MBBS_DECISION_LOG.md). |
| **Keep Runnable** | Keep the application runnable throughout P1. |

---

## Architecture and code rules

| Rule | Requirement |
|------|-------------|
| **Prototype Code Must Earn Its Way In** | POC code is not automatically production. Reuse only when it fits approved architecture; otherwise refactor, wrap, or replace. |
| **No Premature Generalization** | Build what the current increment requires under the approved architecture. No elaborate frameworks for hypothetical futures. |
| **No Shortcuts That Create Future Migration Debt** | Thin P1 is fine. Temporary designs that contradict MBDM/MBAA and knowingly need replacement are **not** — especially IDs, provenance, provider boundaries, PostgreSQL, and relationships. |
| **Test the User Outcome** | Unit/integration tests matter; acceptance asks whether the user can complete the EVS / Experience Flow. |
| **Don't Optimize Before Measuring** | Measure before caching, denormalization, concurrency, or architectural complexity. |
| **Host-portable configuration (D7)** | **FlightSim** = P1 host for MemoryBox app + owned services (PostgreSQL, Qdrant, Ollama where practical). **media-server** = media host (Immich, Plex, photo/video libraries) — access remotely via providers; do not move/duplicate media libs to FlightSim in P1. Dev box OK for development; **Inc 3+ deployable to FlightSim with zero source changes**. Never hard-code FlightSim, media-server, localhost, drive letters, IPs, credentials, or machine paths in application logic — env/config only. Git = app code; exclude secrets/runtime data/DBs/caches/machine config. |

---

## Trust, evidence, and providers

| Rule | Requirement |
|------|-------------|
| **Originals and Provenance Are Sacred** | Never destructively alter original evidence. Derived OCR, STT, embeddings, thumbnails, AI descriptions, identity matches, etc. remain distinguishable and traceable to source. |
| **Derived Data Must Be Rebuildable** | Qdrant/vector indexes, FTS, embeddings, thumbnails, and similar indexes must not become hidden sources of truth. Rebuild from authoritative MemoryBox data + preserved/referenced sources. |
| **No False Memories** | When evidence is insufficient: uncertainty, missing evidence, or ask the owner — never invent family facts to make the experience look better. |
| **Human Teaching Is Durable Knowledge** | Corrections, merges, rejects, and owner annotations must survive provider reprocessing. Immich/HVRT/other AI reruns must not silently overwrite owner teaching. |
| **Provider Failure Must Be Visible** | Do not map “Immich unavailable” to “no photos found.” Same for HVRT, LLMs, OCR, email, etc. |

---

## Change-impact checklist (use every material change)

1. **EVS (MBEVS-001)** — Does a user outcome / scenario change?  
2. **UX (MBUX-001)** — Do shells, patterns, or interaction contracts change?  
3. **Domain (MBDM-001)** — Do entities, authority, provenance, or identity semantics change?  
4. **Experience Flow (MBEF-001)** — Do flow steps or completion conditions change?  
5. **Architecture (MBAA-001)** — Do modules, providers, storage, or job boundaries change?  
6. **Build Spec (MBBS-001)** — Do increments, acceptance, or sequencing change?  
7. **Locked decisions** — Any conflict with **D1–D7**? If yes → **stop**.

Propagate updates to every checked box **before** marking the increment accepted.

---

## Relationship to product authority

These rules sit **beside** the product stack for P1 execution:

`MBPS → MBEVS → MBUX → MBDM → MBEF → MBAA → MBBS`  
plus **this document** and **locked decisions** as process/architecture constraints.
