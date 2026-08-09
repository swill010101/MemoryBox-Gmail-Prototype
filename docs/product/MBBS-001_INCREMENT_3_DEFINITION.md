# MBBS-001 Increment 3 — Definition

**Status:** **ACCEPTED** (built under authorization) · **Date:** 2026-08-09  
**Acceptance report:** [MBBS-001_INCREMENT_3_ACCEPTANCE.md](MBBS-001_INCREMENT_3_ACCEPTANCE.md)  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 3  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md) (**D7**)  
**Depends on:** Increment 1 (accepted) · Increment 2 (accepted)  
**Authorization:** **Build Increment 3 only** — then stop. Do not begin Increment 4.

---

## 0. Final locked scope decisions

| Topic | Decision |
|-------|----------|
| Channels in I3 | **Email + Calendar** |
| SMS | **Deferred** to a later communications increment (see §4.1) |
| Email domain | `Source` + `Evidence` with `evidence_kind = communication` |
| Calendar domain | `Source` + `Evidence` with **event-oriented** `evidence_kind` (not `communication`) — use `calendar_event` |
| Communications table | **Do not add** unless an existing locked domain decision requires it (none does) |
| Architecture pattern | external source → provider/import → Source → Evidence → PostgreSQL → derived Qdrant |
| Acceptance corpus | Synthetic fixtures for **both** email and calendar; **plus** small real-data smoke where practical |
| Real family content | **Never** commit to Git or reproduce in acceptance reports |
| PostgreSQL | **Authoritative** |
| Qdrant | **Derived**; rebuildable from PG Evidence + preserved/referenced sources |
| P1 hosts | **FlightSim** = MemoryBox app + MB-owned services (PG, Qdrant, Ollama where practical); **media-server** = Immich/Plex/media libraries (remote providers only) |
| Config | All host-specific values externalized; no hard-coded FlightSim, media-server, localhost, IPs, drive letters, credentials, or machine paths in application logic |
| Deploy | Dev desktop OK; **same source** deploys to FlightSim via **configuration only** |
| Out of I3 | Ask, UX, SMS, photo ingest, Story, Journal, Increment 4 |

---

## 1. Problem / why now

Ask (Increment 4) needs authoritative **email and calendar** Evidence in PostgreSQL with a rebuildable derived index. SMS stays deferred so I3 can ship email+calendar cleanly.

---

## 2. Objective

Ingest **email** (mbox) and **calendar** (ICS) into MemoryBox **Source → Evidence**, with stable payload contracts and untouched originals. Index into **Qdrant** as derived data with demonstrated rebuild from PostgreSQL. Remain host-portable per **D7**.

---

## 3. Success criteria (acceptance)

| ID | Criterion | Demonstration |
|----|-----------|---------------|
| **I3-A** | Email → Source + Evidence (`communication`) | Synthetic mbox ingest + payload contract; optional real mbox smoke via config (opaque metrics only) |
| **I3-A2** | Calendar → Source + Evidence (`calendar_event`) | Synthetic ICS ingest + payload contract; optional real ICS smoke via config (opaque metrics only) |
| **I3-B** | Originals untouched | Sources reference originals; files not rewritten |
| **I3-C** | No POC SQLite product dual-write | PostgreSQL only |
| **I3-D** | Qdrant rebuildable from PG | Clear collection → rebuild from PG Evidence → expected Evidence IDs present + fixed retrieval test passes |
| **I3-E** | Provider/source failure visible | Missing path / Qdrant down → error job state, not silent empty success |
| **I3-F** | Keep runnable | health / prior proves still pass |
| **I3-G** | Deployment portability | Same code → FlightSim by config only; no forbidden hard-coding in application logic |

---

## 4. Scope

### In

- Email ingest via `EmailReadProvider` → Source + Evidence (`communication`) + §5.1 payload  
- Calendar ingest via Calendar provider/import → Source + Evidence (`calendar_event`) + §5.2 payload  
- Jobs / processing_states  
- Idempotent re-runs (content/event hash)  
- Embeddings → Qdrant (derived); rebuild from PG Evidence  
- Config-driven endpoints/paths/collection names  
- Acceptance report (no real family content)

### Out

Ask/UX/SMS/photo ingest/Story/Journal/Inc 4; communications table; SQLite product store; media-lib move to FlightSim; hard-coded hosts.

### 4.1 Deferred — must not be dropped

| Capability | Plan anchor |
|------------|-------------|
| **SMS / iMessage → Source + Evidence** | Later **communications** increment (or Increment 9 import jobs). POC: `scripts/import_messages.py`. **Do not remove from P1 plan.** |

---

## 5. Domain mapping

| Channel | Source | Evidence |
|---------|--------|----------|
| Email | `sources` (`mbox_import`) | `evidence_kind = communication` |
| Calendar | `sources` (`ics_import`) | `evidence_kind = calendar_event` |

No separate `communications` table.

### 5.1 Email Evidence payload (minimum)

`message_id`, `subject`, `from`, `to`, `cc`, `bcc` (where available), `sent_at`, `body_text` (normalized full usable text), `source_locator`, `provenance`, `content_hash`; recommended `evidence_channel: "email"`.

### 5.2 Calendar Evidence payload (minimum, where available)

`event_uid`, `title`/`summary`, `start`, `end`, `timezone`, `location`, `description`, `organizer`, `attendees`, `recurrence`, `source_locator`, `provenance`, `content_hash` (event hash); recommended `evidence_channel: "calendar"`.

---

## 6–12. Modules, flows, config, build plan

Same architectural pattern for both channels; modules under `memorybox/ingest/` + calendar provider; EF-05/EF-14 thin; D7 host roles unchanged (FlightSim vs media-server); build email → calendar → Qdrant rebuild → proves → acceptance report → **stop**.

**Authorization gate:** Building under explicit *Build Increment 3 only*.
