# MemoryBox application package (MBBS-001)

Production modular monolith. Increment 1: PostgreSQL domain v0 + health + migrations.

## Prerequisites

- Docker Desktop (for local Postgres via Compose), or any PostgreSQL 16+ reachable via `MEMORYBOX_DATABASE_URL`
- Python 3.11+ (3.14 OK)

## Quick start (Increment 1)

```powershell
cd C:\memorybox
docker compose up -d db
pip install -r memorybox\requirements.txt
python -m memorybox migrate
python -m memorybox health
python -m memorybox serve
# http://127.0.0.1:8790/health
```

## Acceptance (Increment 1)

See [docs/product/MBBS-001_INCREMENT_1_ACCEPTANCE.md](../docs/product/MBBS-001_INCREMENT_1_ACCEPTANCE.md).

## Rules

- Domain tables are MemoryBox-owned (MBDM). Provider systems (Immich, HVRT) map through `provider_identities` / `media_refs` only.
- Derived indexes are not introduced in Increment 1; when added later they must be rebuildable.
