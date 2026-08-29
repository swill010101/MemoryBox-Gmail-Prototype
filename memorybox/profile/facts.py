"""Person aliases, facts, and contact points (Increment 9A)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
import re
from datetime import date
from typing import Any
from uuid import uuid4

from memorybox.db import connection
from memorybox.profile.owner import (
    ALIAS_KINDS,
    CONTACT_KINDS,
    FACT_KINDS,
    ProfileServiceError,
    ensure_person,
    iso,
    parse_date,
    parse_uuid,
    prov,
)

DATE_PRECISIONS = frozenset({"day", "month", "year", "unknown"})
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def format_life_date(value_date: Any, precision: str | None = "day") -> str:
    """Format a stored DATE without implying more precision than recorded."""
    raw = (iso(value_date) or "").strip()
    if not raw:
        return ""
    prec = (precision or "day").strip().lower()
    year = raw[:4]
    if prec == "year":
        return year
    month_i = int(raw[5:7]) if len(raw) >= 7 and raw[5:7].isdigit() else 0
    month = _MONTHS[month_i - 1] if 1 <= month_i <= 12 else ""
    if prec == "month":
        return f"{month} {year}".strip()
    if prec == "unknown":
        return ""
    day_i = int(raw[8:10]) if len(raw) >= 10 and raw[8:10].isdigit() else 0
    if month and day_i:
        return f"{month} {day_i}, {year}"
    return raw[:10]


def _normalize_fact_date(
    value_date: str | date | None, precision: str, *, field: str
) -> date:
    prec = (precision or "day").strip().lower()
    if prec not in DATE_PRECISIONS or prec == "unknown":
        raise ProfileServiceError(f"{field} date_precision must be day, month, or year")
    raw = "" if value_date is None else str(value_date).strip()
    if prec == "year":
        m = re.match(r"^(\d{4})", raw)
        if not m:
            raise ProfileServiceError(f"{field} year precision requires YYYY")
        return date(int(m.group(1)), 1, 1)
    if prec == "month":
        m = re.match(r"^(\d{4})-(\d{2})", raw)
        if not m:
            raise ProfileServiceError(f"{field} month precision requires YYYY-MM")
        return date(int(m.group(1)), int(m.group(2)), 1)
    got = parse_date(raw, field=field)
    if got is None:
        raise ProfileServiceError(f"{field} requires a calendar date")
    return got


@dataclass
class AliasView:
    id: str
    person_id: str
    alias_kind: str
    alias_text: str
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactView:
    id: str
    person_id: str
    fact_kind: str
    value_text: str | None
    value_date: str | None
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None
    date_precision: str = "day"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["display_date"] = format_life_date(self.value_date, self.date_precision)
        return d


@dataclass
class ContactView:
    id: str
    person_id: str
    contact_kind: str
    value_text: str
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _alias_view(row: dict[str, Any]) -> AliasView:
    return AliasView(
        id=str(row["id"]),
        person_id=str(row["person_id"]),
        alias_kind=row["alias_kind"],
        alias_text=row["alias_text"],
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
    )


def _fact_view(row: dict[str, Any]) -> FactView:
    return FactView(
        id=str(row["id"]),
        person_id=str(row["person_id"]),
        fact_kind=row["fact_kind"],
        value_text=row.get("value_text"),
        value_date=iso(row.get("value_date")),
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
        date_precision=str(row.get("date_precision") or "day"),
    )


def _contact_view(row: dict[str, Any]) -> ContactView:
    return ContactView(
        id=str(row["id"]),
        person_id=str(row["person_id"]),
        contact_kind=row["contact_kind"],
        value_text=row["value_text"],
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
    )


def add_alias(
    person_id: str,
    *,
    alias_kind: str,
    alias_text: str,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> AliasView:
    pid = ensure_person(person_id)
    kind = (alias_kind or "").strip().lower()
    if kind not in ALIAS_KINDS:
        raise ProfileServiceError(f"alias_kind must be one of {sorted(ALIAS_KINDS)}")
    text = (alias_text or "").strip()
    if len(text) < 1:
        raise ProfileServiceError("alias_text required")
    aid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO person_aliases (
                id, person_id, alias_kind, alias_text, status, actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (aid, pid, kind, text, actor_key, note, json.dumps(provenance or {"source": "owner"})),
        )
        row = conn.execute("SELECT * FROM person_aliases WHERE id = %s", (aid,)).fetchone()
    return _alias_view(row)


def list_aliases(person_id: str, *, include_withdrawn: bool = False) -> list[AliasView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        if include_withdrawn:
            rows = conn.execute(
                "SELECT * FROM person_aliases WHERE person_id = %s ORDER BY created_at ASC",
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM person_aliases
                WHERE person_id = %s AND status = 'confirmed'
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
    return [_alias_view(r) for r in rows]


def add_fact(
    person_id: str,
    *,
    fact_kind: str,
    value_date: str | date | None = None,
    value_text: str | None = None,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
    supersede_current: bool = True,
    date_precision: str | None = None,
) -> FactView:
    pid = ensure_person(person_id)
    kind = (fact_kind or "").strip().lower()
    if kind not in FACT_KINDS:
        raise ProfileServiceError(f"fact_kind must be one of {sorted(FACT_KINDS)}")
    prec = (date_precision or ("unknown" if kind == "note" else "day")).strip().lower()
    if prec not in DATE_PRECISIONS:
        raise ProfileServiceError("date_precision must be day, month, year, or unknown")
    vd = None
    vt = (value_text or "").strip() or None
    if kind in ("birth_date", "death_date"):
        vd = _normalize_fact_date(value_date, prec, field=kind)
        vt = vt or format_life_date(vd, prec)
    elif kind == "note" and not vt:
        raise ProfileServiceError("note requires value_text")
    else:
        prec = "unknown"
    if supersede_current and kind in ("birth_date", "death_date"):
        current = get_current_fact(str(pid), kind)
        if (
            current
            and current.value_date == iso(vd)
            and (current.date_precision or "day") == prec
            and (note or None) == (current.note or None)
        ):
            return current
    fid = uuid4()
    try:
        with connection() as conn:
            # Insert first. person_facts.superseded_by_id FKs to person_facts(id),
            # so pointing the old row at fid before the new row exists is a 500.
            has_prec = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'person_facts'
                  AND column_name = 'date_precision'
                """
            ).fetchone()
            if has_prec:
                conn.execute(
                    """
                    INSERT INTO person_facts (
                        id, person_id, fact_kind, value_text, value_date,
                        status, actor_key, note, provenance_json, date_precision
                    ) VALUES (%s, %s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb, %s)
                    """,
                    (
                        fid,
                        pid,
                        kind,
                        vt,
                        vd,
                        actor_key,
                        note,
                        json.dumps(provenance or {"source": "owner"}),
                        prec,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO person_facts (
                        id, person_id, fact_kind, value_text, value_date,
                        status, actor_key, note, provenance_json
                    ) VALUES (%s, %s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
                    """,
                    (
                        fid,
                        pid,
                        kind,
                        vt,
                        vd,
                        actor_key,
                        note,
                        json.dumps(provenance or {"source": "owner"}),
                    ),
                )
            if supersede_current and kind in ("birth_date", "death_date"):
                conn.execute(
                    """
                    UPDATE person_facts
                    SET status = 'superseded', superseded_by_id = %s, updated_at = now()
                    WHERE person_id = %s AND fact_kind = %s AND status = 'confirmed'
                      AND id <> %s
                    """,
                    (fid, pid, kind, fid),
                )
            row = conn.execute("SELECT * FROM person_facts WHERE id = %s", (fid,)).fetchone()
        return _fact_view(row)
    except ProfileServiceError:
        raise
    except Exception as exc:
        raise ProfileServiceError(f"could not save {kind}: {exc}") from exc


def list_facts(person_id: str, *, include_withdrawn: bool = False) -> list[FactView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        if include_withdrawn:
            rows = conn.execute(
                "SELECT * FROM person_facts WHERE person_id = %s ORDER BY created_at ASC",
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM person_facts
                WHERE person_id = %s AND status = 'confirmed'
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
    return [_fact_view(r) for r in rows]


def get_current_fact(person_id: str, fact_kind: str) -> FactView | None:
    kind = (fact_kind or "").strip().lower()
    for f in list_facts(person_id):
        if f.fact_kind == kind:
            return f
    return None


def add_contact(
    person_id: str,
    *,
    contact_kind: str,
    value_text: str,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> ContactView:
    pid = ensure_person(person_id)
    kind = (contact_kind or "").strip().lower()
    if kind not in CONTACT_KINDS:
        raise ProfileServiceError(f"contact_kind must be one of {sorted(CONTACT_KINDS)}")
    text = (value_text or "").strip()
    if len(text) < 2:
        raise ProfileServiceError("value_text required")
    cid = uuid4()
    prov_json = json.dumps(provenance or {"source": "owner"})
    trust = (
        "trusted"
        if (actor_key or "owner") in {"owner", "operator", "owner_confirmed"}
        else "untrusted"
    )
    with connection() as conn:
        try:
            conn.execute(
                """
                INSERT INTO person_contact_points (
                    id, person_id, contact_kind, value_text, status,
                    actor_key, note, provenance_json, retrieval_trust
                ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb, %s)
                """,
                (cid, pid, kind, text, actor_key, note, prov_json, trust),
            )
        except Exception:  # noqa: BLE001
            conn.execute(
                """
                INSERT INTO person_contact_points (
                    id, person_id, contact_kind, value_text, status,
                    actor_key, note, provenance_json
                ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
                """,
                (cid, pid, kind, text, actor_key, note, prov_json),
            )
        row = conn.execute("SELECT * FROM person_contact_points WHERE id = %s", (cid,)).fetchone()
    return _contact_view(row)


def supersede_contact(
    contact_id: str,
    *,
    value_text: str,
    actor_key: str = "owner",
    note: str | None = None,
) -> ContactView:
    old_id = parse_uuid(contact_id, field="contact_id")
    text = (value_text or "").strip()
    if len(text) < 2:
        raise ProfileServiceError("value_text required")
    new_id = uuid4()
    with connection() as conn:
        old = conn.execute(
            "SELECT * FROM person_contact_points WHERE id = %s", (old_id,)
        ).fetchone()
        if not old:
            raise ProfileServiceError(f"contact not found: {old_id}")
        if old["status"] != "confirmed":
            raise ProfileServiceError("only confirmed contacts can be superseded")
        conn.execute(
            """
            UPDATE person_contact_points
            SET status = 'superseded', superseded_by_id = %s, updated_at = now()
            WHERE id = %s
            """,
            (new_id, old_id),
        )
        conn.execute(
            """
            INSERT INTO person_contact_points (
                id, person_id, contact_kind, value_text, status,
                actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (
                new_id,
                old["person_id"],
                old["contact_kind"],
                text,
                actor_key,
                note,
                json.dumps(
                    {
                        "source": "owner_correction",
                        "supersedes": str(old_id),
                        "prior_value": old["value_text"],
                    }
                ),
            ),
        )
        row = conn.execute(
            "SELECT * FROM person_contact_points WHERE id = %s", (new_id,)
        ).fetchone()
    return _contact_view(row)


def list_contacts(person_id: str, *, include_withdrawn: bool = False) -> list[ContactView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        if include_withdrawn:
            rows = conn.execute(
                """
                SELECT * FROM person_contact_points WHERE person_id = %s
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM person_contact_points
                WHERE person_id = %s
                  AND status IN ('confirmed', 'candidate', 'observed')
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
    return [_contact_view(r) for r in rows]
