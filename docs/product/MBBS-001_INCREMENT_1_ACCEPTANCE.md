# MBBS-001 Increment 1 — Acceptance report

**Date:** 2026-08-09  
**Status:** **ACCEPTED** (criteria + synthetic persistence)  
**Charter:** [MBBS-001 v0.3](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) Increment 1  
**Full report:** [MBBS-001_INCREMENT_1_COMPLETION_REPORT.md](MBBS-001_INCREMENT_1_COMPLETION_REPORT.md)  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 1  
**Checkpoint:** git tag `increment-1-accepted`

---

## Acceptance criteria (Increment 1)

| Criterion | Result | Evidence |
|-----------|--------|----------|
| App boots | **PASS** | `python -m memorybox serve` → `GET /health` (`ok: true`) |
| Migrates empty PG | **PASS** | `python -m memorybox migrate` applied `001_domain_v0.sql` |
| Health OK | **PASS** | `/health` → `"ok": true`, pending `[]`, domain tables complete |
| No provider schemas as domain tables | **PASS** | `provider_schema_leaks: []`; only MemoryBox domain tables |
| Synthetic graph persists + retrieves | **PASS** | Seed Grandpa fixture → restart PostgreSQL + bounce serve → `prove-synthetic` ok |

### Health snapshot (excerpt)

```json
{
  "ok": true,
  "service": "memorybox",
  "increment": 1,
  "database": { "status": "ok", "database": "memorybox" },
  "migrations": {
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

---

## What was delivered

| Artifact | Purpose |
|----------|---------|
| [`memorybox/`](../../memorybox/) | Modular monolith package root |
| [`memorybox/app.py`](../../memorybox/app.py) | FastAPI `/` + `/health` |
| [`memorybox/config.py`](../../memorybox/config.py) | `MEMORYBOX_DATABASE_URL` / host / port |
| [`memorybox/db.py`](../../memorybox/db.py) | psycopg connection helpers |
| [`memorybox/migrate.py`](../../memorybox/migrate.py) | Ordered SQL migrations + `schema_migrations` |
| [`memorybox/migrations/001_domain_v0.sql`](../../memorybox/migrations/001_domain_v0.sql) | Domain v0 (MBDM-aligned, minimal) |
| [`memorybox/__main__.py`](../../memorybox/__main__.py) | CLI: `migrate` \| `health` \| `seed-synthetic` \| `prove-synthetic` \| `serve` |
| [`memorybox/synthetic_i1.py`](../../memorybox/synthetic_i1.py) | Idempotent Grandpa photo graph fixture + join prove |
| [`docker-compose.yml`](../../docker-compose.yml) | Optional Postgres 16 (Docker Hub was flaky; used local PG 17) |
| [`config/memorybox_app.env.example`](../../config/memorybox_app.env.example) | Env template |

Default URL: `postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox`  
Default API port: **8790**

---

## Runtime notes

- Local **PostgreSQL 17** Windows service `postgresql-x64-17` on `:5432` (winget install eventually completed enough to run).  
- Superuser used for bootstrap: `postgres` / `postgres` (installer default). App role/db: `memorybox` / `memorybox`.  
- Docker Hub pull of `postgres:16-alpine` still failed earlier (CloudFront EOF); not required once local PG was available.  
- An elevated `postgresql-17.10-2-windows-x64` installer process may still be lingering — safe to end via Task Manager if present.

---

## Deviations / unresolved decisions

| Item | Notes |
|------|--------|
| Package name `memorybox/` | Chosen per MBBS preference |
| `media_refs` + `assertion_evidence` | Thin supporting tables for provider IDs and assertion↔evidence links |
| Place / Event / Artifact tables | Not in Inc 1 MBBS list — deferred |
| Postgres 17 vs Compose 16 | Either acceptable for Inc 1; documented |

---

## Synthetic persistence proof (acceptance gate)

Commands:

```powershell
$env:MEMORYBOX_DATABASE_URL = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
python -m memorybox seed-synthetic
python -m memorybox prove-synthetic
# Restart PostgreSQL (elevated): Restart-Service postgresql-x64-17
# Bounce MemoryBox serve process
python -m memorybox prove-synthetic   # must remain ok: true
```

Graph: Person **Grandpa** ← Assertion ← Evidence (face) ← MediaRef `grandpa_christmas.jpg` ← Source **test photo import**; Story linked to Grandpa + evidence via `relationships` + `narrator_person_id`.

**Result after PostgreSQL service restart + serve bounce:** `prove-synthetic` → `"ok": true` (2026-08-09).

---

## Stop for review

**Increment 1: ACCEPTED** (including synthetic persistence).  
Owner authorized Increment 2 after this gate.
