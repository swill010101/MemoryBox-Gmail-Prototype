"""Structured PersonContext for I11A inference input."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from memorybox.ask.i11a import resolve_request_context

_REL_LABELS = frozenset(
    {
        "spouse",
        "partner",
        "sibling",
        "brother",
        "sister",
        "child",
        "son",
        "daughter",
        "parent",
        "father",
        "mother",
        "family",
        "friend",
        "colleague",
        "uncle",
        "aunt",
        "niece",
        "nephew",
        "grandparent",
        "grandchild",
    }
)


def _parse_day(raw: Any) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()[:10]
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _age_on(birth: date, at: date) -> int | None:
    if at < birth:
        return None
    years = at.year - birth.year
    if (at.month, at.day) < (birth.month, birth.day):
        years -= 1
    return years


def _window_span(plan: Any) -> tuple[date | None, date | None]:
    windows = list(getattr(plan, "temporal_windows", ()) or ())
    if windows:
        start = _parse_day(windows[0][0] if windows[0] else None)
        end_raw = windows[0][1] if len(windows[0]) > 1 else windows[0][0]
        return start, _parse_day(end_raw)
    return (
        _parse_day(getattr(plan, "time_start", None)),
        _parse_day(getattr(plan, "time_end", None)),
    )


def _period_as_of(plan: Any) -> date | None:
    """Age against the resolved episode/trip period, not year-end filler dates."""
    notes = " ".join(getattr(plan, "notes", ()) or ())
    start, end = _window_span(plan)
    if "trip_window_resolved" in notes and start:
        return start
    if start and end:
        span = (end - start).days
        if span <= 90:
            return start
        # Unresolved calendar year (or similar): omit age rather than Dec 31.
        if span >= 300:
            return None
        return start
    return start


def _dedupe_relationship_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("from_person_id") or ""),
            str(row.get("to_person_id") or ""),
            str(row.get("role_kind") or "").lower(),
            str(row.get("authority") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _person_card(person_id: str, *, at: date | None) -> dict[str, Any] | None:
    try:
        from memorybox.person import get_person
        from memorybox.profile.facts import get_current_fact, list_aliases, list_contacts
        from memorybox.profile.relationships import (
            list_relationship_assertions,
            project_derived_edges,
        )
    except Exception:  # noqa: BLE001
        return None
    view = get_person(person_id)
    if not view:
        return None
    birth = get_current_fact(person_id, "birth_date")
    death = get_current_fact(person_id, "death_date")
    birth_day = _parse_day(getattr(birth, "value_date", None) if birth else None)
    death_day = _parse_day(getattr(death, "value_date", None) if death else None)
    age = _age_on(birth_day, at) if birth_day and at else None
    aliases = []
    try:
        aliases = [a.to_dict() if hasattr(a, "to_dict") else dict(a) for a in list_aliases(person_id)]
    except Exception:  # noqa: BLE001
        aliases = []
    contacts = []
    try:
        contacts = [c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in list_contacts(person_id)]
    except Exception:  # noqa: BLE001
        contacts = []
    # Merge archive-wide communication_identities (address ledger) onto the card
    # so Gallery/Ask see observed display names (Peg Legg / Peggy George), not
    # only person_contact_points rows.
    comm_ids: list[dict[str, Any]] = []
    seen_addrs: set[str] = set()
    try:
        from memorybox.db import connection
        from memorybox.person.phone_map import normalize_handle

        with connection() as conn:
            rows = conn.execute(
                """
                SELECT address_normalized, observed_display_names,
                       header_occurrence_count, quoted_body_occurrence_count,
                       resolution_status, resolved_person_id
                FROM communication_identities
                WHERE identity_kind = 'email'
                  AND resolved_person_id::text = %s
                """,
                (str(person_id),),
            ).fetchall()
            for r in rows:
                addr = normalize_handle(str(r.get("address_normalized") or ""))
                if not addr:
                    continue
                seen_addrs.add(addr)
                obs = r.get("observed_display_names") or {}
                if isinstance(obs, str):
                    try:
                        obs = json.loads(obs)
                    except Exception:  # noqa: BLE001
                        obs = {}
                comm_ids.append(
                    {
                        "contact_kind": "email",
                        "value_text": addr,
                        "status": str(r.get("resolution_status") or "observed"),
                        "source": "communication_identities",
                        "observed_display_names": obs,
                        "header_occurrence_count": int(r.get("header_occurrence_count") or 0),
                        "quoted_body_occurrence_count": int(
                            r.get("quoted_body_occurrence_count") or 0
                        ),
                    }
                )
    except Exception:  # noqa: BLE001
        pass
    for c in contacts:
        addr = str(c.get("value_text") or "")
        try:
            from memorybox.person.phone_map import normalize_handle

            n = normalize_handle(addr)
        except Exception:  # noqa: BLE001
            n = addr.strip().lower()
        if n and n not in seen_addrs:
            row = dict(c)
            row.setdefault("source", "person_contact_points")
            comm_ids.append(row)
            seen_addrs.add(n)
        elif n and n in seen_addrs:
            # Prefer ledger row; mark contact confirmed on matching ledger entry
            for row in comm_ids:
                if str(row.get("value_text") or "").lower() == n:
                    row["person_contact_status"] = c.get("status")
                    row["person_contact_id"] = c.get("id")
                    break
    trusted_addrs: set[str] = set()
    try:
        from memorybox.person.trusted_identity import trusted_emails_for_people

        trusted_addrs = trusted_emails_for_people({str(person_id)})
    except Exception:  # noqa: BLE001
        trusted_addrs = set()
    if trusted_addrs:
        filtered: list[dict[str, Any]] = []
        for row in comm_ids:
            kind = str(row.get("contact_kind") or "")
            val = str(row.get("value_text") or "")
            try:
                from memorybox.person.phone_map import normalize_handle

                n = normalize_handle(val)
            except Exception:  # noqa: BLE001
                n = val.strip().lower()
            if kind == "email" or "@" in n:
                if n in trusted_addrs:
                    filtered.append(row)
            else:
                filtered.append(row)
        comm_ids = filtered
    elif comm_ids:
        comm_ids = [
            row
            for row in comm_ids
            if str(row.get("contact_kind") or "") != "email"
            and "@" not in str(row.get("value_text") or "")
        ]
    if not comm_ids:
        comm_ids = [
            c
            for c in contacts
            if str(c.get("contact_kind") or "") != "email"
            or (
                str(c.get("value_text") or "").strip().lower() in trusted_addrs
            )
        ]
    known: list[dict[str, Any]] = []
    allowed: set[str] = set()
    try:
        for a in list_relationship_assertions(person_id):
            d = a.to_dict() if hasattr(a, "to_dict") else dict(a)
            role = str(d.get("role_kind") or "")
            known.append(
                {
                    "from_person_id": d.get("from_person_id"),
                    "to_person_id": d.get("to_person_id"),
                    "role_kind": role,
                    "status": d.get("status"),
                    "authority": "confirmed",
                }
            )
            allowed.add(role.lower())
            for tok in role.lower().replace("_of", "").split("_"):
                if tok:
                    allowed.add(tok)
    except Exception:  # noqa: BLE001
        pass
    inferred: list[dict[str, Any]] = []
    try:
        for e in project_derived_edges(person_id):
            d = e.to_dict() if hasattr(e, "to_dict") else dict(e)
            if d.get("is_inverse_projection") or d.get("inferred"):
                inferred.append(
                    {
                        "from_person_id": d.get("from_person_id"),
                        "to_person_id": d.get("to_person_id"),
                        "role_kind": d.get("role_kind"),
                        "authority": "inferred",
                        "provenance": d.get("provenance"),
                    }
                )
                rk = str(d.get("role_kind") or "").lower()
                allowed.add(rk)
                for tok in rk.replace("_of", "").split("_"):
                    if tok:
                        allowed.add(tok)
    except Exception:  # noqa: BLE001
        pass
    known = _dedupe_relationship_rows(known)
    inferred = _dedupe_relationship_rows(inferred)
    return {
        "person_id": person_id,
        "display_name": view.display_name,
        "birth_date": birth_day.isoformat() if birth_day else None,
        "death_date": death_day.isoformat() if death_day else None,
        "age_at_period": age,
        "aliases": aliases,
        "communication_identities": comm_ids,
        "known_relationships": known,
        "inferred_relationships": inferred,
        "allowed_relationship_labels": sorted(_REL_LABELS & allowed) or sorted(allowed),
    }


def build_person_context(plan: Any) -> dict[str, Any]:
    req = resolve_request_context(plan)
    at = _period_as_of(plan)
    requestor_card = (
        _person_card(req["requestor_person_id"], at=at) if req.get("requestor_person_id") else None
    )
    focals = []
    for pid in req.get("focal_subject_person_ids") or []:
        card = _person_card(pid, at=at)
        if card:
            focals.append(card)
    allowed: set[str] = set()
    for card in ([requestor_card] if requestor_card else []) + focals:
        for lab in card.get("allowed_relationship_labels") or []:
            allowed.add(str(lab).lower())
    return {
        "requestor": requestor_card,
        "focal_subjects": focals,
        "request_context": req,
        "allowed_relationship_labels": sorted(allowed),
        "as_of": at.isoformat() if at else None,
    }


def slim_person_context_for_model(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """Compact PersonContext for the inference payload (full ctx stays in the pack)."""

    def _card(card: dict[str, Any] | None) -> dict[str, Any] | None:
        if not card:
            return None
        known = []
        for row in _dedupe_relationship_rows(card.get("known_relationships") or [])[:24]:
            known.append(
                {
                    "from_person_id": row.get("from_person_id"),
                    "to_person_id": row.get("to_person_id"),
                    "role_kind": row.get("role_kind"),
                }
            )
        return {
            "person_id": card.get("person_id"),
            "display_name": card.get("display_name"),
            "age_at_period": card.get("age_at_period"),
            "known_relationships": known,
            "allowed_relationship_labels": card.get("allowed_relationship_labels") or [],
        }

    ctx = ctx or {}
    return {
        "requestor": _card(ctx.get("requestor") if isinstance(ctx.get("requestor"), dict) else None),
        "focal_subjects": [
            c
            for c in (_card(x) for x in (ctx.get("focal_subjects") or []) if isinstance(x, dict))
            if c
        ],
        "allowed_relationship_labels": ctx.get("allowed_relationship_labels") or [],
        "as_of": ctx.get("as_of"),
    }


def allowed_relationship_labels(person_context: dict[str, Any] | None) -> set[str]:
    raw = (person_context or {}).get("allowed_relationship_labels") or []
    return {str(x).lower() for x in raw if str(x).strip()}
