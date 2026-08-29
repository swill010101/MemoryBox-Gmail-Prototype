"""Bootstrap default owner + current person for serve / video_worker.

FlightSim testing aid (2026-08-13): on process start, ensure MB Person
"Tom Will" exists, set owner_person_id and current_person_id to that Person.

Owner and interactive user remain distinct roles later; for now both point
at Tom Will so Ask relativity and People “I am this person” work without a
manual People step.

Disable with MEMORYBOX_BOOTSTRAP_OWNER=0.
Override name with MEMORYBOX_BOOTSTRAP_OWNER_NAME (default Tom Will).
"""
from __future__ import annotations

import os
from typing import Any

from memorybox.profile.owner import (
    ENV_OWNER_PERSON_ID,
    ProfileServiceError,
    set_owner_person_id,
)

ENV_BOOTSTRAP = "MEMORYBOX_BOOTSTRAP_OWNER"
ENV_BOOTSTRAP_NAME = "MEMORYBOX_BOOTSTRAP_OWNER_NAME"
DEFAULT_OWNER_NAME = "Tom Will"
SETTING_CURRENT_PERSON = "current_person_id"


def _env_truthy(name: str, default: str = "1") -> bool:
    raw = (os.environ.get(name) if name in os.environ else default) or default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def get_current_person_id() -> str | None:
    """Session/current Person id (testing bootstrap; user role later)."""
    try:
        from memorybox.db import connection
        from uuid import UUID

        with connection() as conn:
            row = conn.execute(
                """
                SELECT value_text FROM memorybox_runtime_settings
                WHERE setting_key = %s
                """,
                (SETTING_CURRENT_PERSON,),
            ).fetchone()
        if not row or not (row.get("value_text") or "").strip():
            return None
        return str(UUID(str(row["value_text"]).strip()))
    except Exception:  # noqa: BLE001
        return None


def set_current_person_id(person_id: str, *, actor_key: str = "owner") -> str:
    from uuid import UUID

    from memorybox.db import connection
    from memorybox.profile.owner import ensure_person

    pid = ensure_person(person_id)
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO memorybox_runtime_settings (setting_key, value_text, actor_key, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (setting_key) DO UPDATE
            SET value_text = EXCLUDED.value_text,
                actor_key = EXCLUDED.actor_key,
                updated_at = now()
            """,
            (SETTING_CURRENT_PERSON, str(pid), actor_key),
        )
    return str(UUID(str(pid)))


def ensure_default_owner_session(
    *,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Resolve Tom Will (or override name), set owner + current person.

    Safe to call repeatedly. No-ops when MEMORYBOX_BOOTSTRAP_OWNER=0.
    Does not raise on soft failures (DB down) — returns ok=False detail.
    """
    if not _env_truthy(ENV_BOOTSTRAP, "1"):
        return {"ok": True, "skipped": True, "reason": f"{ENV_BOOTSTRAP}=0"}

    name = (display_name or os.environ.get(ENV_BOOTSTRAP_NAME) or DEFAULT_OWNER_NAME).strip()
    if len(name) < 2:
        return {"ok": False, "error": "bootstrap owner name too short"}

    try:
        from memorybox.person import resolve_person_by_name

        resolved = resolve_person_by_name(name, create_if_missing=True, confirm=True)
        pid = resolved.person_id
        owner_status = set_owner_person_id(pid, actor_key="bootstrap")
        current_id = set_current_person_id(pid, actor_key="bootstrap")

        # Process-local env so Ask relativity sees owner even if DB lag/cache;
        # only set when ops did not already pin MEMORYBOX_OWNER_PERSON_ID.
        if not (os.environ.get(ENV_OWNER_PERSON_ID) or "").strip():
            os.environ[ENV_OWNER_PERSON_ID] = pid

        return {
            "ok": True,
            "skipped": False,
            "display_name": resolved.display_name,
            "person_id": pid,
            "person_created": bool(resolved.created),
            "owner_person_id": owner_status.get("owner_person_id") or pid,
            "current_person_id": current_id,
            "owner_source": owner_status.get("source"),
        }
    except (ProfileServiceError, Exception) as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "display_name": name}
