"""Owner anchor and shared helpers for Increment 9A profile."""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any
from uuid import UUID

from memorybox.person import get_person

ENV_OWNER_PERSON_ID = "MEMORYBOX_OWNER_PERSON_ID"

ROLE_FATHER_OF = "father_of"
ROLE_MOTHER_OF = "mother_of"
ROLE_PARENT_OF = "parent_of"
ROLE_BIOLOGICAL_PARENT_OF = "biological_parent_of"
ROLE_ADOPTIVE_PARENT_OF = "adoptive_parent_of"
ROLE_STEP_PARENT_OF = "step_parent_of"
ROLE_CHILD_OF = "child_of"
ROLE_SON_OF = "son_of"
ROLE_DAUGHTER_OF = "daughter_of"
ROLE_SPOUSE_OF = "spouse_of"
ROLE_PARTNER_OF = "partner_of"
ROLE_SIBLING_OF = "sibling_of"
ROLE_GRANDPARENT_OF = "grandparent_of"
ROLE_GRANDCHILD_OF = "grandchild_of"
ROLE_UNCLE_OF = "uncle_of"
ROLE_AUNT_OF = "aunt_of"
ROLE_NEPHEW_OF = "nephew_of"
ROLE_NIECE_OF = "niece_of"

ALLOWED_ROLES: frozenset[str] = frozenset(
    {
        ROLE_FATHER_OF,
        ROLE_MOTHER_OF,
        ROLE_PARENT_OF,
        ROLE_BIOLOGICAL_PARENT_OF,
        ROLE_ADOPTIVE_PARENT_OF,
        ROLE_STEP_PARENT_OF,
        ROLE_CHILD_OF,
        ROLE_SON_OF,
        ROLE_DAUGHTER_OF,
        ROLE_SPOUSE_OF,
        ROLE_PARTNER_OF,
        ROLE_SIBLING_OF,
        ROLE_GRANDPARENT_OF,
        ROLE_GRANDCHILD_OF,
        ROLE_UNCLE_OF,
        ROLE_AUNT_OF,
        ROLE_NEPHEW_OF,
        ROLE_NIECE_OF,
    }
)

INVERSE_ROLE: dict[str, str] = {
    ROLE_FATHER_OF: ROLE_CHILD_OF,
    ROLE_MOTHER_OF: ROLE_CHILD_OF,
    ROLE_PARENT_OF: ROLE_CHILD_OF,
    ROLE_BIOLOGICAL_PARENT_OF: ROLE_CHILD_OF,
    ROLE_ADOPTIVE_PARENT_OF: ROLE_CHILD_OF,
    ROLE_STEP_PARENT_OF: ROLE_CHILD_OF,
    ROLE_CHILD_OF: ROLE_PARENT_OF,
    ROLE_SON_OF: ROLE_PARENT_OF,
    ROLE_DAUGHTER_OF: ROLE_PARENT_OF,
    ROLE_SPOUSE_OF: ROLE_SPOUSE_OF,
    ROLE_PARTNER_OF: ROLE_PARTNER_OF,
    ROLE_SIBLING_OF: ROLE_SIBLING_OF,
    ROLE_GRANDPARENT_OF: ROLE_GRANDCHILD_OF,
    ROLE_GRANDCHILD_OF: ROLE_GRANDPARENT_OF,
    ROLE_UNCLE_OF: ROLE_NEPHEW_OF,
    ROLE_AUNT_OF: ROLE_NIECE_OF,
    ROLE_NEPHEW_OF: ROLE_UNCLE_OF,
    ROLE_NIECE_OF: ROLE_AUNT_OF,
}

ASK_ROLE_ALIASES: dict[str, frozenset[str]] = {
    # Gendered asks require gendered SoT roles — do NOT treat generic parent_of
    # as father/mother (that made “my mother” return Eugene after father_of/parent_of).
    "father": frozenset({ROLE_FATHER_OF}),
    "dad": frozenset({ROLE_FATHER_OF}),
    "mother": frozenset({ROLE_MOTHER_OF}),
    "mom": frozenset({ROLE_MOTHER_OF}),
    "parent": frozenset(
        {
            ROLE_PARENT_OF,
            ROLE_FATHER_OF,
            ROLE_MOTHER_OF,
            ROLE_BIOLOGICAL_PARENT_OF,
            ROLE_ADOPTIVE_PARENT_OF,
            ROLE_STEP_PARENT_OF,
        }
    ),
    "son": frozenset({ROLE_SON_OF, ROLE_CHILD_OF}),
    "daughter": frozenset({ROLE_DAUGHTER_OF, ROLE_CHILD_OF}),
    "child": frozenset({ROLE_CHILD_OF, ROLE_SON_OF, ROLE_DAUGHTER_OF}),
    "grandfather": frozenset({ROLE_GRANDPARENT_OF}),
    "grandmother": frozenset({ROLE_GRANDPARENT_OF}),
    "grandparent": frozenset({ROLE_GRANDPARENT_OF}),
    "grandson": frozenset({ROLE_GRANDCHILD_OF}),
    "granddaughter": frozenset({ROLE_GRANDCHILD_OF}),
    "grandchild": frozenset({ROLE_GRANDCHILD_OF}),
    "uncle": frozenset({ROLE_UNCLE_OF}),
    "aunt": frozenset({ROLE_AUNT_OF}),
    "spouse": frozenset({ROLE_SPOUSE_OF, ROLE_PARTNER_OF}),
    "partner": frozenset({ROLE_PARTNER_OF, ROLE_SPOUSE_OF}),
    "sibling": frozenset({ROLE_SIBLING_OF}),
    "brother": frozenset({ROLE_SIBLING_OF}),
    "sister": frozenset({ROLE_SIBLING_OF}),
}

# When father/mother miss but a generic parent exists, disclose (do not invent gender).
GENDERED_PARENT_PHRASES: frozenset[str] = frozenset({"father", "dad", "mother", "mom"})
GENERIC_PARENT_ROLES: frozenset[str] = frozenset(
    {
        ROLE_PARENT_OF,
        ROLE_BIOLOGICAL_PARENT_OF,
        ROLE_ADOPTIVE_PARENT_OF,
        ROLE_STEP_PARENT_OF,
    }
)

FACT_KINDS = frozenset({"birth_date", "death_date", "note", "residence"})
ALIAS_KINDS = frozenset({"nickname", "alternate_name"})
CONTACT_KINDS = frozenset({"email", "phone"})


class ProfileServiceError(Exception):
    pass


class AmbiguousRelationshipError(ProfileServiceError):
    def __init__(self, message: str, *, candidates: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


def iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise ProfileServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProfileServiceError(f"{field} must be a UUID (got {raw!r})") from exc


def parse_date(value: str | date | None, *, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise ProfileServiceError(f"{field} must be YYYY-MM-DD (got {raw!r})") from exc


def ensure_person(person_id: str) -> UUID:
    pid = parse_uuid(person_id, field="person_id")
    view = get_person(str(pid))
    if not view:
        raise ProfileServiceError(f"person not found: {pid}")
    if view.status == "merged_away":
        raise ProfileServiceError(f"person {pid} is merged_away; use survivor")
    return pid


def prov(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return {}


def name_map(conn, ids: list[UUID]) -> dict[str, str | None]:
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT id, display_name FROM people WHERE id = ANY(%s)",
        (ids,),
    ).fetchall()
    return {str(r["id"]): r.get("display_name") for r in rows}


def get_owner_person_id() -> str | None:
    """Canonical P1 owner Person id.

    Prefer env MEMORYBOX_OWNER_PERSON_ID when set (ops override).
    Else durable DB setting set from People UI (“I am this person”).
    Never infer via display_name search.
    """
    raw = (os.environ.get(ENV_OWNER_PERSON_ID) or "").strip()
    if raw:
        try:
            return str(UUID(raw))
        except (ValueError, TypeError, AttributeError):
            return None
    try:
        from memorybox.db import connection

        with connection() as conn:
            row = conn.execute(
                """
                SELECT value_text FROM memorybox_runtime_settings
                WHERE setting_key = 'owner_person_id'
                """
            ).fetchone()
        if not row or not (row.get("value_text") or "").strip():
            return None
        return str(UUID(str(row["value_text"]).strip()))
    except Exception:  # noqa: BLE001 — table may not exist yet / DB down
        return None


def set_owner_person_id(person_id: str, *, actor_key: str = "owner") -> dict[str, Any]:
    """Persist canonical owner from People UI. Env still overrides when set."""
    pid = ensure_person(person_id)
    from memorybox.db import connection

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO memorybox_runtime_settings (setting_key, value_text, actor_key, updated_at)
            VALUES ('owner_person_id', %s, %s, now())
            ON CONFLICT (setting_key) DO UPDATE
            SET value_text = EXCLUDED.value_text,
                actor_key = EXCLUDED.actor_key,
                updated_at = now()
            """,
            (str(pid), actor_key),
        )
    # If env override is active, DB save still succeeds but Ask uses env
    status = owner_config_status()
    status["saved_person_id"] = str(pid)
    status["env_overrides"] = bool((os.environ.get(ENV_OWNER_PERSON_ID) or "").strip())
    return status


def require_owner_person_id() -> str:
    oid = get_owner_person_id()
    if not oid:
        raise ProfileServiceError(
            "MemoryBox does not know who you are yet. "
            "Open People and choose “I am this person” (Tom Will), then ask again. "
            f"(Ops may also set {ENV_OWNER_PERSON_ID}.)"
        )
    view = get_person(oid)
    if not view:
        raise ProfileServiceError(
            f"Configured owner id {oid} does not match an MB Person. "
            "Pick yourself again on People."
        )
    if view.status == "merged_away":
        raise ProfileServiceError(
            f"Owner person {oid} was merged away; merge survivors via People, "
            "then set “I am this person” to the survivor."
        )
    return oid


def owner_config_status() -> dict[str, Any]:
    env_set = bool((os.environ.get(ENV_OWNER_PERSON_ID) or "").strip())
    oid = get_owner_person_id()
    if not oid:
        return {
            "configured": False,
            "owner_person_id": None,
            "env": ENV_OWNER_PERSON_ID,
            "env_overrides": env_set,
            "source": None,
            "display_name": None,
        }
    view = get_person(oid)
    source = "env" if env_set else "database"
    return {
        "configured": bool(view and view.status != "merged_away"),
        "owner_person_id": oid,
        "env": ENV_OWNER_PERSON_ID,
        "env_overrides": env_set,
        "source": source,
        "display_name": view.display_name if view else None,
        "status": view.status if view else "missing",
    }
