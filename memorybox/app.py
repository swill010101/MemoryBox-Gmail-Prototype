"""FastAPI entry for MemoryBox monolith (Increment 1: health + migrate status)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from memorybox import __version__
from memorybox import migrate as migrate_mod
from memorybox.config import settings
from memorybox.db import ping

# Domain tables created by 001_domain_v0.sql — listed for health/inventory (no provider schemas).
DOMAIN_V0_TABLES = (
    "sources",
    "media_objects",
    "media_refs",
    "evidence",
    "people",
    "provider_identities",
    "assertions",
    "assertion_evidence",
    "relationships",
    "stories",
    "story_versions",
    "journal_entries",
    "jobs",
    "processing_states",
)

app = FastAPI(
    title="MemoryBox",
    version=__version__,
    description="MemoryBox modular monolith (MBBS-001). Increment 1: skeleton + domain v0.",
)


@app.get("/health")
def health() -> dict[str, Any]:
    db: dict[str, Any]
    try:
        db = {"status": "ok", **ping()}
    except Exception as exc:  # noqa: BLE001 — surface connection errors in health
        db = {"status": "error", "error": str(exc)}

    migrations: dict[str, Any]
    try:
        applied = migrate_mod.applied_versions()
        pending = migrate_mod.pending()
        migrations = {
            "status": "ok",
            "applied": [
                {
                    "version": r["version"],
                    "filename": r["filename"],
                    "applied_at": r["applied_at"].isoformat()
                    if hasattr(r["applied_at"], "isoformat")
                    else str(r["applied_at"]),
                }
                for r in applied
            ],
            "pending": pending,
        }
    except Exception as exc:  # noqa: BLE001
        migrations = {"status": "error", "error": str(exc)}

    tables_ok = False
    missing: list[str] = []
    if db.get("status") == "ok":
        try:
            from memorybox.db import connection

            with connection() as conn:
                rows = conn.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """
                ).fetchall()
            present = {r["table_name"] for r in rows}
            missing = [t for t in DOMAIN_V0_TABLES if t not in present]
            # Guard: Immich/HVRT must not appear as domain tables
            provider_leaks = sorted(
                n
                for n in present
                if n.startswith("immich") or n.startswith("hvrt_") or n == "face_appearances"
            )
            tables_ok = not missing and not provider_leaks
            table_info = {
                "domain_v0_complete": not missing,
                "missing": missing,
                "provider_schema_leaks": provider_leaks,
            }
        except Exception as exc:  # noqa: BLE001
            table_info = {"error": str(exc)}
            provider_leaks = []
    else:
        table_info = {"skipped": True}
        provider_leaks = []

    ok = (
        db.get("status") == "ok"
        and migrations.get("status") == "ok"
        and not migrations.get("pending")
        and tables_ok
    )
    return {
        "ok": ok,
        "service": "memorybox",
        "increment": 1,
        "version": __version__,
        "database": db,
        "migrations": migrations,
        "domain_tables": table_info,
        "host": settings.host,
        "port": settings.port,
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "memorybox",
        "increment": 1,
        "version": __version__,
        "health": "/health",
    }
