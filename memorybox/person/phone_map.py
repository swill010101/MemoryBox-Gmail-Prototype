"""Normalize phone / Apple-handle identities and map to canonical MB People."""
from __future__ import annotations

import re
from typing import Any

from memorybox.db import connection


def normalize_handle(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if "@" in text:
        return text.lower()
    digits = re.sub(r"\D", "", text)
    if not digits:
        return text.lower()
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return "+1" + digits
    if text.startswith("+"):
        return "+" + digits
    return digits


def _index_confirmed_handles(conn: Any | None = None) -> dict[str, list[str]]:
    """normalized handle -> list of person_id (confirmed contacts + phone identities)."""
    out: dict[str, list[str]] = {}

    def _run(c: Any) -> None:
        try:
            rows = c.execute(
                """
                SELECT person_id, value_text
                FROM person_contact_points
                WHERE contact_kind IN ('phone', 'email')
                  AND status = 'confirmed'
                """
            ).fetchall()
        except Exception:  # noqa: BLE001
            rows = []
        for r in rows:
            key = normalize_handle(str(r.get("value_text") or ""))
            if not key:
                continue
            pid = str(r["person_id"])
            out.setdefault(key, [])
            if pid not in out[key]:
                out[key].append(pid)
        try:
            ids = c.execute(
                """
                SELECT person_id, external_id
                FROM provider_identities
                WHERE lower(identity_kind) IN ('phone', 'handle', 'apple_id', 'email')
                """
            ).fetchall()
        except Exception:  # noqa: BLE001
            ids = []
        for r in ids:
            key = normalize_handle(str(r.get("external_id") or ""))
            if not key:
                continue
            pid = str(r["person_id"])
            out.setdefault(key, [])
            if pid not in out[key]:
                out[key].append(pid)

    if conn is not None:
        _run(conn)
        return out
    with connection() as c:
        _run(c)
    return out


def resolve_handles(
    handles: list[str],
    *,
    index: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Map handles to people. Unique confirmed → auto; ambiguous → review; else unmapped."""
    index = index if index is not None else _index_confirmed_handles()
    mapped: list[dict[str, str]] = []
    ambiguous: list[dict[str, Any]] = []
    unmapped: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in handles:
        norm = normalize_handle(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        hits = list(index.get(norm) or [])
        if len(norm) == 12 and norm.startswith("+1"):
            extra = index.get(norm[2:]) or []
            for pid in extra:
                if pid not in hits:
                    hits.append(pid)
        if len(hits) == 1:
            mapped.append(
                {
                    "handle": raw,
                    "normalized": norm,
                    "person_id": hits[0],
                    "status": "auto_mapped",
                }
            )
        elif len(hits) > 1:
            ambiguous.append(
                {
                    "handle": raw,
                    "normalized": norm,
                    "person_ids": hits,
                    "status": "review",
                }
            )
        else:
            unmapped.append(
                {
                    "handle": raw,
                    "normalized": norm,
                    "status": "unmapped",
                }
            )
    return {"mapped": mapped, "ambiguous": ambiguous, "unmapped": unmapped}
