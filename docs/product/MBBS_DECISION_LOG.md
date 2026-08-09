# MBBS Decision / Deviation Log

**Status:** Living · **Owner:** Tom  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md)

Record one section per increment. Do not wait until end of P1.

---

## Increment 4 — Ask + Query Planner + basic contextual follow-up

**Date:** 2026-08-09  
**Authorization:** Build Increment 4 only (locked definition); corrective reopen for planner/context + exploratory multimodal  
**Acceptance:** [MBBS-001_INCREMENT_4_ACCEPTANCE.md](MBBS-001_INCREMENT_4_ACCEPTANCE.md) · [MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md](MBBS-001_INCREMENT_4_CORRECTIVE_ACCEPTANCE.md) — **ACCEPTED** (corrective + owner manual validation)  
**Next increment:** [MBBS-001_INCREMENT_5_DEFINITION.md](MBBS-001_INCREMENT_5_DEFINITION.md) — **REVIEW ONLY**; build requires explicit authorization  
**Post-acceptance policy:** Further Ask-language edge cases → defects/EVS refinements in future increments unless fundamental trust/architecture failure. **No I4 polish.**

### Corrective decisions (same day, post manual test)

| Decision | Rationale |
|----------|-----------|
| Reopen I4 for planner/context only | Manual defects A–H; not a new increment |
| Typed slots + supersede + reference resolution + ambiguity | Prevent person→place contamination and silent wrong retrieval |
| `i4_context_semantics_AH` regression | Catch failure pattern + unseen variation without demo hardcoding |
| In-package Immich HTTP client | FlightSim had no `application/api`; earn-in under `memorybox/providers/photo/` |
| Immich env URL hardening | Mangled `IMMICH_BASE_URL=` pastes caused urllib scheme errors on FlightSim |
| Exploratory / know-about = always multimodal (I4 modalities) | “Know about / tell me about / what do I have about” explores subject across Immich stills + email/calendar — not comms-only and not photo-fallback; explicit narrowing still wins |
| `i4_exploratory_multimodal` regression | Photo-only / evidence-only / both / neither / narrowed communication with unseen subjects |

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| Template/structured answers from Evidence + provider hits (no free-form invention) | Evidence First / No False Memories; LLM optional via LlmProvider only |
| In-memory `ContextStore` protocol | I4 session; clean contract for later persistence |
| `MEMORYBOX_PHOTO_PROVIDER=unavailable` + harness `UnavailablePhotoProvider` for I4-G | Deliberate degradation without taking family Immich offline |
| `MEMORYBOX_P1_RUNTIME_HOST=1` required with `--flightsim` | Prevents desktop from claiming P1-runtime final acceptance |
| Proper-noun lexical constraints on Evidence retrieval | Stops weak keyword/semantic hits from “answering” nonsense asks |
| Thin static Ask shell | Locked: functional only, no polish |
| **Intent-oriented visual semantics** | Broad “show me / pictures / images” → `visual_scope=broad` (stills+video intent); “photos” may narrow to stills; “videos” → video only; “show me” ≠ media type. I4 executes available stills only; **no HVRT/video build**. Contract fields enable later video without NL/architecture change |

### Change-impact check

| Layer | Impact? |
|-------|---------|
| EVS | 005/006 exercised (shaped asks) |
| UX | Thin Ask shell + breadcrumb / clear-change |
| Domain | Session context contract only (no new SoT tables) |
| Experience Flow | EF-01, EF-02 basic, EF-04 thin |
| Architecture | Planner + orchestrator + providers |
| Build Spec | Inc 4 **accepted** on FlightSim |
| Locked decisions | D2/D3/D6/D7 aligned |
| In-package Immich HTTP client | FlightSim had no `application/api`; earn-in under `memorybox/providers/photo/` |
| Immich env URL hardening | Mangled `IMMICH_BASE_URL=` pastes caused urllib scheme errors on FlightSim |

### Specs changed

| Spec | Change |
|------|--------|
| I4 definition | Status → built / awaiting FlightSim final; **§0.1 intent-oriented visual semantics locked** |
| This log | Inc 4 section + visual semantic rule |
| MBBS-001 | Inc 4 status |
| Ops | FlightSim I4 acceptance runbook |
| Planner | `visual_scope` / want_still / want_video contract |

### Intentional tech debt

| Item | Why acceptable |
|------|----------------|
| Process-session context only | Locked for I4; protocol ready for persistence |
| Heuristic planner (regex) v0 | Sufficient for EF-02 basic; not multi-agent |
| POC Immich client earn-in behind PhotoProvider | Matches Inc 2 pattern |

---

## Increment 3 — Email + Calendar → Evidence + derived Qdrant

**Date:** 2026-08-09  
**Authorization:** Build Increment 3 only (final scope: email + calendar; SMS deferred)  
**Acceptance:** [MBBS-001_INCREMENT_3_ACCEPTANCE.md](MBBS-001_INCREMENT_3_ACCEPTANCE.md) — **ACCEPTED**  
**Next increment:** Not started (requires explicit authorization)

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| `evidence_kind=communication` for email; `calendar_event` for calendar | Owner lock — event-oriented kind ≠ communication |
| No `communications` table | Locked; Source + Evidence + payload contracts |
| SMS deferred with Inc 9 / later comms anchor | Final I3 scope |
| Qdrant `:memory:` allowed for desktop prove via config | D7 — network URL on P1 runtime host |
| Fake token-hash embeddings when Ollama unset | Deterministic I3-D retrieval without requiring live LLM |
| Real smoke optional via `MEMORYBOX_SMOKE_*_URI` | Where practical; none available on this host at acceptance |
| `MEMORYBOX_ALLOW_DEV_DEFAULTS` for desktop only | FlightSim must set explicit URLs |

### Change-impact check

| Layer | Impact? |
|-------|---------|
| EVS | No Ask yet |
| UX | No |
| Domain | Email/calendar Evidence payload conventions |
| Experience Flow | EF-05/14 thin |
| Architecture | Ingest + derived Qdrant; D7 |
| Build Spec | Inc 3 accepted; SMS deferred noted |
| Locked decisions | D2/D3/D7 aligned |

### Specs changed

| Spec | Change |
|------|--------|
| I3 definition | Final email+calendar scope |
| MBBS-001 | Inc 3 accepted; SMS deferred |
| This log | Inc 3 section |

---

## Cross-cutting — Media-Server Sources checkpoint (2026-08-09)

**Authorization:** Establish `\\media-server\photos\MemoryBox\Sources`; copy/verify email/calendar/SMS; FlightSim path config; small ingest; originals unchanged  
**Status:** **PASSED** — [MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md](MBBS-001_MEDIA_SERVER_SOURCES_CHECKPOINT.md)

| Item | Outcome |
|------|---------|
| Sources tree | email / calendar(+ics) / sms + MANIFEST |
| Copy verify | SHA256 match for mbox, calendar zip, SMS CSV |
| Archive mbox after robocopy | UNCHANGED |
| Ingest from Sources | email+calendar limit 5 ok; files unchanged |
| SMS | Staged only — ingest still deferred |
| Next | Increment 4 **not** authorized |

---

## Cross-cutting — FlightSim I1–I3 deployment checkpoint (2026-08-09)

**Authorization:** Deploy accepted I1–I3 to P1 runtime host; real-data smoke; no Increment 4  
**Status:** **PASSED** — [MBBS-001_FLIGHTSIM_I1_I3_CHECKPOINT.md](MBBS-001_FLIGHTSIM_I1_I3_CHECKPOINT.md)

| Item | Outcome |
|------|---------|
| Host | FlightSim (`tomwi`); Docker PG + Qdrant; Ollama local |
| Synthetic proves | PASS |
| Real email + calendar smoke | PASS (5+5 Evidence rows; IDs only in report) |
| Qdrant | Derived; network URL; rebuild/retrieval PASS |
| Next | Increment 4 **not** authorized |

---

## Cross-cutting — D7 P1 deployment (2026-08-09; updated same day)

**Authorization:** Owner lock (not tied to a single increment build)  
**Status:** **LOCKED** as [D7](../source/MB_LOCKED_DECISIONS_P1.md)

| Decision | Detail |
|----------|--------|
| P1 runtime host | **FlightSim** — MemoryBox **application** + MemoryBox-owned services |
| MB-owned on FlightSim | PostgreSQL, Qdrant, local Ollama/model service **where practical** |
| Media host | **media-server** — Immich, Plex, photos, videos, related media storage/libraries |
| Media access | Remote via **provider interfaces** + configured network endpoints |
| P1 non-goal | Do **not** move or duplicate media libraries onto FlightSim |
| Development | May continue on **dev box**; **Increment 3+** must deploy to FlightSim **without source-code changes** |
| Config rule | No hard-coded FlightSim, media-server, localhost, drive letters, IPs, credentials, or dev-machine paths in application logic |
| Git | Deployable app code only; exclude secrets, runtime data, DBs, caches, machine-specific config |

**Specs updated:** Locked decisions, P1 engineering rules, MBBS §2.2 / non-goals, I3 definition §0/§8.  
**Code debt noted:** Inc 1/2 localhost **dev defaults** remain; must not be required for FlightSim — clear for I3-G.  
**Increment 3:** Still **awaiting authorization** after definition review.  

---

## Increment 2 — Provider interfaces + first adapters

**Date:** 2026-08-09  
**Authorization:** Contingent on I1 synthetic gate (owner authorized I2 after Grandpa fixture passed)  
**Acceptance:** [MBBS-001_INCREMENT_2_ACCEPTANCE.md](MBBS-001_INCREMENT_2_ACCEPTANCE.md) — **ACCEPTED**  
**Next increment:** Increment 3 authorized and accepted (2026-08-09)

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| Providers live under `memorybox/providers/` | Matches monolith package; Inc 1 package root |
| Photo/LLM/Email protocols + frozen DTOs | Prevent Immich/Ollama shapes leaking into domain |
| `PhotoPersonRef.external_id` only — no `person_id` field | Hardens “never Immich UUID as Person PK” |
| Immich/Ollama adapters import POC clients via path earn-in | Reuse without promoting POC as architecture |
| Mbox reader reimplemented in-package (no SQLite write) | Email-read → DTO only; ingest dual-write deferred to Inc 3 |
| Offline Fake photo/LLM for `prove-providers` | Acceptance without requiring live Immich/Ollama |

### Change-impact check (this increment)

| Layer | Impact? |
|-------|---------|
| EVS | No |
| UX | No |
| Domain | Mapping pattern exercised via `provider_identities` only |
| Experience Flow | No |
| Architecture | Provider adapter layer realized per MBAA/MBBS |
| Build Spec | Yes — Inc 2 status |
| Locked decisions | Aligns with D2 POC-as-adapter |

---

## Increment 1 — Monolith + PostgreSQL domain v0

**Date:** 2026-08-09  
**Authorization:** Build Increment 1 only (MBBS-001 v0.2 charter)  
**Acceptance:** [MBBS-001_INCREMENT_1_ACCEPTANCE.md](MBBS-001_INCREMENT_1_ACCEPTANCE.md) — **ACCEPTED** (incl. synthetic persistence after PG restart)  
**Checkpoint tag:** `increment-1-accepted`  
**Next increment:** Increment 2 authorized after synthetic gate (2026-08-09)

### Decisions discovered during build

| Decision | Rationale |
|----------|-----------|
| Package root = `memorybox/` | Matches MBBS preference for production package name |
| SQL file migrations + `schema_migrations` table | Thin, explicit, no premature migration framework |
| Default DB URL `postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox` | Local single-owner P1; credentials via env |
| Default API port **8790** (demo used **8791** when Marvin held 8790) | Avoid silent collision; document port conflict |
| Local PostgreSQL 17 Windows service used when Docker Hub pull failed | Still PostgreSQL authoritative store (D3); Compose remains optional path |
| Bootstrap superuser password for local install was installer default `postgres`/`postgres` | Dev-only; not for production secrets |
| Synthetic I1 fixture (Grandpa / christmas.jpg) with stable UUIDs + `seed-synthetic` / `prove-synthetic` | Prove domain FKs survive PG restart without real archive ingest |

### Specifications changed this increment

| Spec | Change |
|------|--------|
| [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) | **Added** — founder P1 standing rules (Living Spec, process, trust) |
| [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) | **v0.3** — embed standing rules; Inc 1 complete; keep runnable |
| [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md) | Pointer to engineering rules |
| [DOCUMENT_HIERARCHY.md](../DOCUMENT_HIERARCHY.md) | Index rules + decision log |
| MBPS / MBEVS / MBUX / MBDM / MBEF / MBAA DOCX | **No product content change** — rules reinforce existing Evidence First, provenance, provider, rebuildability positions (change-impact: process layer only) |

### Intentional deviations

| Item | Notes |
|------|--------|
| `media_refs`, `assertion_evidence` tables | Supporting physical tables not named as top-level MBBS list items; align with MediaRef + Evidence↔Assertion without provider schemas |
| Place / Event / Artifact tables absent | Per MBBS Inc 1 scope list — deferred |

### Technical debt accepted

| Debt | Why acceptable in Inc 1 |
|------|-------------------------|
| No auth on `/health` | Single-owner local; auth later |
| Docker Compose path unproven on this machine (Hub EOF) | Local PG 17 demonstrated acceptance |
| Possible lingering elevated Postgres installer process | Ops hygiene; does not affect schema |

### Unresolved questions

| Question | Impact if deferred |
|----------|--------------------|
| Canonical app listen port vs Marvin (8790) | Low — env-configurable; resolve before multi-service demos |
| When to check in Founder's Book DOCX | Docs completeness; extract remains interim |

### Change-impact check (this increment)

| Layer | Impact? |
|-------|---------|
| EVS | No |
| UX | No |
| Domain | Physical schema v0 introduced under MBDM concepts — documented in migration; conceptual MBDM DOCX unchanged |
| Experience Flow | No |
| Architecture | Monolith + PG path realized per MBAA/D2/D3 |
| Build Spec | Yes — rules + Inc 1 status |
| Locked decisions | No conflict |

### Rules compliance (Inc 1)

| Rule | Status |
|------|--------|
| One increment at a time | Met — only Inc 1 |
| Acceptance before advancement | Met — health/migrate demonstrated |
| Living specs / no silent supersede | Met — rules written into controlled docs this increment |
| No provider schemas as domain | Met |
| No false memories / teaching / provider failure UX | N/A this increment (no Ask yet) — schema supports future provenance |
| Rebuildable derived data | N/A — no derived indexes yet |
| Keep runnable | Met — `python -m memorybox serve` |
| POC earn its way in | Met — no POC code promoted as domain model |
| No migration-debt shortcuts on IDs/provenance/PG | Met — UUID domain PKs; provider IDs only in mapping tables |
