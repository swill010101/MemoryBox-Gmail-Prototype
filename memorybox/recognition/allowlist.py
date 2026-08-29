"""Owner allowlist: which People the face-recognition queue may hunt.

One recognition_queue row is Person × video. This module exports one CSV row
per Person, then applies an edited keep-list so opted-out people are dropped
from queued work and are not re-enqueued by Immich sync / archive-pass.

people.attributes_json.face_scan:
  missing / true  → hunt this Person (legacy default)
  false           → do not enqueue; drain skips without opening the video
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from memorybox.db import connection

FACE_SCAN_ATTR = "face_scan"
EXCLUDE_REASON = "owner_face_scan_off"

_FALSE = {"0", "false", "no", "n", "off", ""}
_TRUE = {"1", "true", "yes", "y", "on", "keep"}
_KEEP_FALSE = {"0", "false", "no", "n", "off"}


def _as_attrs(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _truthy_flag(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in _FALSE:
        return False
    if raw in _TRUE:
        return True
    return default


def face_scan_enabled(person_id: str | UUID) -> bool:
    pid = str(person_id or "").strip()
    if not pid:
        return True
    with connection() as conn:
        row = conn.execute(
            "SELECT attributes_json FROM people WHERE id = %s::uuid",
            (pid,),
        ).fetchone()
    if not row:
        return True
    attrs = _as_attrs(row.get("attributes_json"))
    if FACE_SCAN_ATTR not in attrs:
        return True
    return _truthy_flag(attrs.get(FACE_SCAN_ATTR), default=True)


def set_face_scan(person_id: str | UUID, enabled: bool) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE people
            SET attributes_json = COALESCE(attributes_json, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            WHERE id = %s::uuid
            """,
            (json.dumps({FACE_SCAN_ATTR: bool(enabled)}), str(person_id)),
        )


def list_queue_people() -> list[dict[str, Any]]:
    """One row per Person who has any recognition_queue_items row."""
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT p.id::text AS person_id,
                   COALESCE(p.display_name, '') AS display_name,
                   p.status,
                   p.attributes_json,
                   COUNT(*)::int AS total,
                   COUNT(*) FILTER (WHERE q.status = 'queued')::int AS queued,
                   COUNT(*) FILTER (WHERE q.status = 'running')::int AS running,
                   COUNT(*) FILTER (WHERE q.status = 'completed')::int AS completed,
                   COUNT(*) FILTER (WHERE q.status = 'failed')::int AS failed,
                   COUNT(*) FILTER (WHERE q.status = 'excluded')::int AS excluded
            FROM recognition_queue_items q
            JOIN people p ON p.id = q.person_id
            GROUP BY p.id, p.display_name, p.status, p.attributes_json
            ORDER BY LOWER(COALESCE(p.display_name, '')), p.id
            """
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        attrs = _as_attrs(r.get("attributes_json"))
        enabled = True
        if FACE_SCAN_ATTR in attrs:
            enabled = _truthy_flag(attrs.get(FACE_SCAN_ATTR), default=True)
        out.append(
            {
                "person_id": r["person_id"],
                "display_name": r.get("display_name") or "",
                "status": r.get("status") or "",
                "keep": "Y" if enabled else "N",
                "face_scan": "Y" if enabled else "N",
                "queued": int(r["queued"] or 0),
                "running": int(r["running"] or 0),
                "completed": int(r["completed"] or 0),
                "failed": int(r["failed"] or 0),
                "excluded": int(r["excluded"] or 0),
                "total": int(r["total"] or 0),
            }
        )
    return out


def write_people_csv(path: str | Path, rows: list[dict[str, Any]] | None = None) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = rows if rows is not None else list_queue_people()
    fieldnames = [
        "person_id",
        "display_name",
        "keep",
        "queued",
        "running",
        "completed",
        "failed",
        "excluded",
        "total",
        "face_scan",
        "status",
    ]
    with dest.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return dest


def parse_keep_ids(path: str | Path) -> list[str]:
    """Person IDs that should remain searchable.

    Edit style A: delete rows you do not want — remaining person_id values are kept.
    Edit style B: leave every row and set keep=N on people to drop. If any N/no/false
    appears in keep, only Y/yes/true rows are kept.
    """
    src = Path(path)
    text = src.read_text(encoding="utf-8-sig")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError(f"{src}: empty CSV (need a header with person_id)")
    fields = {str(n or "").strip().lower(): str(n or "") for n in reader.fieldnames}
    id_key = fields.get("person_id") or fields.get("id")
    if not id_key:
        raise ValueError(f"{src}: missing person_id column")
    keep_key = fields.get("keep")
    rows: list[dict[str, str]] = []
    saw_keep_no = False
    for raw in reader:
        pid = str(raw.get(id_key) or "").strip()
        if not pid:
            continue
        try:
            pid = str(UUID(pid))
        except (ValueError, TypeError):
            raise ValueError(f"{src}: invalid person_id {pid!r}") from None
        keep_val = str(raw.get(keep_key) or "").strip().lower() if keep_key else "y"
        if keep_key and keep_val in _KEEP_FALSE:
            saw_keep_no = True
        rows.append({"person_id": pid, "keep": keep_val or "y"})
    if not rows:
        raise ValueError(f"{src}: no person_id rows — refusing empty keep-list")
    if keep_key and saw_keep_no:
        kept = [r["person_id"] for r in rows if r["keep"] not in _KEEP_FALSE]
    else:
        kept = [r["person_id"] for r in rows]
    # Preserve file order, unique
    seen: set[str] = set()
    out: list[str] = []
    for pid in kept:
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    if not out:
        raise ValueError(f"{src}: keep-list is empty after applying keep=N rows")
    return out


def apply_keep_ids(
    keep_ids: Iterable[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    keep = [str(UUID(str(p).strip())) for p in keep_ids]
    keep_set = set(keep)
    with connection() as conn:
        queued_people = conn.execute(
            """
            SELECT DISTINCT person_id::text AS person_id
            FROM recognition_queue_items
            """
        ).fetchall()
        queue_ids = {str(r["person_id"]) for r in queued_people}
        drop_ids = sorted(queue_ids - keep_set)

        drop_queued = 0
        if drop_ids:
            row = conn.execute(
                """
                SELECT COUNT(*)::int AS n
                FROM recognition_queue_items
                WHERE person_id = ANY(%s::uuid[])
                  AND status IN ('queued', 'running')
                """,
                (drop_ids,),
            ).fetchone()
            drop_queued = int((row or {}).get("n") or 0)

        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "keep_count": len(keep_set),
                "drop_people": len(drop_ids),
                "queued_or_running_to_exclude": drop_queued,
                "dropped_person_ids": drop_ids,
            }

        if drop_ids:
            conn.execute(
                """
                UPDATE recognition_queue_items
                SET status = 'excluded',
                    reason = %s,
                    finished_at = now(),
                    updated_at = now()
                WHERE person_id = ANY(%s::uuid[])
                  AND status IN ('queued', 'running')
                """,
                (EXCLUDE_REASON, drop_ids),
            )
            conn.execute(
                """
                UPDATE people
                SET attributes_json = COALESCE(attributes_json, '{}'::jsonb) || %s::jsonb,
                    updated_at = now()
                WHERE id = ANY(%s::uuid[])
                """,
                (json.dumps({FACE_SCAN_ATTR: False}), drop_ids),
            )
        conn.execute(
            """
            UPDATE people
            SET attributes_json = COALESCE(attributes_json, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            WHERE id = ANY(%s::uuid[])
            """,
            (json.dumps({FACE_SCAN_ATTR: True}), list(keep_set)),
        )
    return {
        "ok": True,
        "dry_run": False,
        "keep_count": len(keep_set),
        "drop_people": len(drop_ids),
        "queued_or_running_excluded": drop_queued,
        "note": (
            "Completed/failed history kept. Opted-out people will not be "
            "re-queued by archive-pass or Immich sync. Owner Learn turns "
            "face_scan back on for that Person."
        ),
    }


def apply_keep_csv(path: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    keep = parse_keep_ids(path)
    result = apply_keep_ids(keep, dry_run=dry_run)
    result["keep_file"] = str(path)
    result["keep_ids"] = keep
    return result
