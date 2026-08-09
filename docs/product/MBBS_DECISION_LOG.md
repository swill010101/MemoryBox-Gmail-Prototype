# MBBS Decision / Deviation Log

**Status:** Living · **Owner:** Tom  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md)

Record one section per increment. Do not wait until end of P1.

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
