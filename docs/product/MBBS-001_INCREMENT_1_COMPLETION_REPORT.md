# MBBS-001 Increment 1 — Completion Report

**Document:** Increment 1 completion report  
**Charter:** [MBBS-001 v0.3](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md)  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 1  
**Report date:** 2026-08-09  
**Verdict:** **COMPLETE — ALL INCREMENT 1 ACCEPTANCE CRITERIA MET** (incl. synthetic persistence)

**Authorization:** Build Increment 1 only → synthetic gate → **Increment 1 accepted**; Increment 2 authorized 2026-08-09.  
**Checkpoint:** git tag `increment-1-accepted`

---

## 1. Increment objective (charter)

| Charter item | Required | Result |
|--------------|----------|--------|
| Objective | Production app package with migrations for core MBDM concepts (minimal physical schema) | **MET** — package `memorybox/`, migration `001_domain_v0.sql` |
| Modules | App entry, config, DB migrations, health | **MET** — `app.py`, `config.py`, `migrate.py`, `db.py`, `__main__.py` |
| Domain v0 entities | Source, MediaObject/MediaRef, Evidence, Person, ProviderIdentity, Assertion, Relationship, Story, StoryVersion, JournalEntry, Job, ProcessingState | **MET** — see §3 table inventory |
| Dependencies | Increment 0; D2 modular monolith; D3 PostgreSQL | **MET** |
| Flows / EVSs | None user-facing | **MET** — no Ask/UX flows claimed |

---

## 2. Increment 1 acceptance criteria (MBBS §5 Inc 1)

These are the **explicit** Increment 1 acceptance lines in MBBS-001.

| # | Criterion | Status | Demonstration |
|---|-----------|--------|---------------|
| **I1-A** | **App boots** | **PASS** | HTTP `GET /` and `GET /health` on `:8791` returned MemoryBox service/increment payloads with health `ok: true`. A later `serve --port 8791` attempt exited with WinError 10048 (port already bound); CLI `python -m memorybox health` remains the durable proof. Port 8790 often held by Marvin Capture — not a product failure. |
| **I1-B** | **Migrates empty PG** | **PASS** | Initial run applied `001_domain_v0.sql` to database `memorybox`. Re-run 2026-08-09: `{"applied":[]}` (idempotent); `schema_migrations` shows version `001` applied at `2026-08-09 06:52:40.782001-05`. |
| **I1-C** | **Health OK** | **PASS** | `python -m memorybox health` → `"ok": true`, DB status ok, migrations pending `[]`, `domain_v0_complete: true`. Same payload via HTTP `/health` on 8791. |
| **I1-D** | **No provider schemas as domain tables** | **PASS** | Health reports `provider_schema_leaks: []`. `\dt` shows only MemoryBox domain + `schema_migrations`. No Immich/HVRT native tables. Provider IDs only via `provider_identities` / `media_refs` mapping tables. |
| **I1-E** | **Synthetic graph persists across restart** | **PASS** | `seed-synthetic` → elevated `Restart-Service postgresql-x64-17` → serve bounce → `prove-synthetic` `"ok": true` (Grandpa ↔ photo ↔ evidence ↔ assertion ↔ story). |

### 2.1 Health evidence (CLI, re-verified)

```json
{
  "ok": true,
  "service": "memorybox",
  "increment": 1,
  "version": "0.1.0",
  "database": { "status": "ok", "ok": true, "database": "memorybox" },
  "migrations": {
    "status": "ok",
    "applied": [{ "version": "001", "filename": "001_domain_v0.sql" }],
    "pending": []
  },
  "domain_tables": {
    "domain_v0_complete": true,
    "missing": [],
    "provider_schema_leaks": []
  }
}
```

### 2.2 Commands used

```powershell
cd C:\memorybox
$env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
python -m memorybox migrate
python -m memorybox health
python -m memorybox serve --port 8791
# GET http://127.0.0.1:8791/health
```

---

## 3. Domain v0 inventory vs MBBS list

| MBBS domain concept | Physical table(s) | Present |
|---------------------|-------------------|---------|
| Source | `sources` | Yes |
| MediaObject | `media_objects` | Yes |
| MediaRef | `media_refs` | Yes |
| Evidence | `evidence` | Yes |
| Person | `people` | Yes |
| ProviderIdentity | `provider_identities` | Yes |
| Assertion | `assertions` (+ `assertion_evidence` link) | Yes |
| Relationship | `relationships` | Yes |
| Story | `stories` | Yes |
| StoryVersion | `story_versions` | Yes |
| JournalEntry | `journal_entries` | Yes |
| Job | `jobs` | Yes |
| ProcessingState | `processing_states` | Yes |
| *(platform)* | `schema_migrations` | Yes |

**PostgreSQL:** Local service `postgresql-x64-17` on `127.0.0.1:5432`, database/role `memorybox` (D3 satisfied).

---

## 4. Global P1 cross-cutting criteria (MBBS §6) — applicability to Increment 1

Increment 1 has no Ask/ingest/UI. Criteria are scored **PASS**, **N/A (deferred — not in scope)**, or **PASS by design**.

| # | Global criterion | I1 result | Notes |
|---|------------------|-----------|-------|
| 1 | Evidence First | **N/A** | No answers yet; Evidence table exists for later increments |
| 2 | Create No False Memories | **N/A** | No synthesis yet |
| 3 | Originals sacred | **N/A** | No ingest yet; schema supports referenced vs memorybox_managed originals |
| 4 | Owner authority / durable human teaching | **PASS by design** | `assertions.authority`, `status`, `provider_identities` separate from provider reprocessing |
| 5 | Provider replaceability | **PASS** | No Immich/HVRT tables as domain; mappings only |
| 6 | Provider failure visible | **N/A** | No providers wired (Increment 2+) |
| 7 | Local-first | **PASS** | Local PostgreSQL + local API process |
| 8 | Jobs async / visible | **PASS by design** | `jobs` + `processing_states` tables; no workers yet |
| 9 | Derived-index rebuildability | **N/A** | No FTS/Qdrant/derived indexes in I1 |
| 10 | Ownership / MV export | **N/A** | Increment 12 |
| 11 | Living specs before acceptance | **PASS** | Rules, decision log, hierarchy updated before treating I1 complete under v0.3 |
| 12 | Keep runnable | **PASS** | Health and serve demonstrated after I1 |

---

## 5. Standing engineering rules (spot-check for I1)

| Rule | I1 result |
|------|-----------|
| One increment at a time | **PASS** — only I1 built |
| Acceptance before advancement | **PASS** — criteria demonstrated; I2 not started |
| Living specifications / no silent supersede | **PASS** |
| Change-impact check recorded | **PASS** — decision log |
| No silent architecture changes | **PASS** — monolith+PG per D2/D3 |
| POC must earn its way in | **PASS** — no POC schema promoted |
| No premature generalization | **PASS** — thin migrate/health only |
| No migration-debt shortcuts (IDs/provenance/PG/providers) | **PASS** — UUID PKs; provider IDs in mapping tables only |
| Originals / provenance / rebuildable / no false memories | **N/A or by-design** as in §4 |
| Decision/deviation log | **PASS** |
| Stop on expensive ambiguity | **PASS** — no unresolved architecture forks left open in I1 scope |

---

## 6. Deliverables

| Path | Role |
|------|------|
| `memorybox/` | Monolith package |
| `memorybox/migrations/001_domain_v0.sql` | Domain v0 |
| `memorybox/app.py` | `/`, `/health` |
| `memorybox/__main__.py` | `migrate` \| `health` \| `serve` |
| `docker-compose.yml` | Optional Postgres 16 (local PG 17 used for demo) |
| `config/memorybox_app.env.example` | Env template |
| `docs/product/MBBS_DECISION_LOG.md` | I1 decisions/deviations |
| `docs/source/MB_P1_ENGINEERING_RULES.md` | Standing P1 rules |

---

## 7. Deviations (intentional, accepted for I1)

| Deviation | Justification |
|-----------|----------------|
| `assertion_evidence` link table | Needed for Evidence↔Assertion without JSON-only provenance |
| Serve demo on **8791** | **8790** held by Marvin Capture |
| Postgres **17** local vs Compose **16** | Same D3 requirement; Docker Hub pull failed earlier |

No deviation contradicts MBDM/MBAA locked architecture for Increment 1 scope.

---

## 8. Unresolved items (not I1 blockers)

| Item | Owner action when ready |
|------|-------------------------|
| Canonical port vs Marvin | Choose default before multi-service demos |
| Founder's Book DOCX not in `docs/source` | Provide file when available |
| Lingering elevated Postgres installer process (if still present) | End via Task Manager / Admin if desired |

---

## 9. Final statement

**Increment 1 is accepted.** Every MBBS Increment 1 acceptance criterion (**I1-A through I1-D**) plus synthetic persistence (**I1-E**) has been demonstrated.

**Checkpoint:** `increment-1-accepted`. Increment 2 authorized by owner after this gate.
