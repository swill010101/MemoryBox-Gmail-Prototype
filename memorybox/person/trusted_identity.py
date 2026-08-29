"""Trusted-for-retrieval identity (general — not person-specific).

An email is trusted for Ask/Gallery retrieve only with auditable provenance:
canonical Person-profile contact, owner/operator confirmation, or another
already-approved deterministic trusted source.

Auto-expand, people[] fill, quoted-body corroboration, and nickname pairing
may create candidates. They never grant retrieval trust.
"""
from __future__ import annotations

import json
from typing import Any

from memorybox.db import connection
from memorybox.person.phone_map import normalize_handle

TRUSTED_ACTOR_KEYS = frozenset(
    {
        "owner",
        "operator",
        "owner_confirmed",
    }
)
UNTRUSTED_ACTOR_KEYS = frozenset(
    {
        "comm_identity_expand",
        "sms_auto_map",
    }
)
TRUSTED_PROVENANCE_SOURCES = frozenset(
    {
        "owner",
        "person_profile",
        "owner_confirmed",
        "owner_correction",
        "comm_identity_operator_attested",
        "operator_attest",
        "canonical_profile",
    }
)
UNTRUSTED_PROVENANCE_SOURCES = frozenset(
    {
        "comm_identity_expand",
        "sms_auto_map",
        "corroborated_header_identity",
        "address_centric",
        "confirmed_cache",
        "comm_address_index_resolve",
        "comm_identity_known_address",
        "ensure_confirmed_email_contact",
    }
)


def _as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def classify_contact_trust(row: dict[str, Any]) -> dict[str, Any]:
    """Return retrieval_trust + reason from actor_key / provenance. Fail closed."""
    actor = str(row.get("actor_key") or "").strip()
    prov = _as_dict(row.get("provenance_json"))
    source = str(prov.get("source") or "").strip()
    if prov.get("operator_attested") is True or prov.get("owner_confirmed") is True:
        return {
            "retrieval_trust": "trusted",
            "reason": "owner_or_operator_attested",
            "actor_key": actor,
            "provenance_source": source,
        }
    if source in TRUSTED_PROVENANCE_SOURCES or actor in TRUSTED_ACTOR_KEYS:
        if source in UNTRUSTED_PROVENANCE_SOURCES or actor in UNTRUSTED_ACTOR_KEYS:
            if source in TRUSTED_PROVENANCE_SOURCES:
                return {
                    "retrieval_trust": "trusted",
                    "reason": f"trusted_provenance:{source}",
                    "actor_key": actor,
                    "provenance_source": source,
                }
            return {
                "retrieval_trust": "untrusted",
                "reason": f"auto_expand_actor:{actor or source}",
                "actor_key": actor,
                "provenance_source": source,
            }
        return {
            "retrieval_trust": "trusted",
            "reason": f"canonical_or_owner:{actor or source}",
            "actor_key": actor,
            "provenance_source": source,
        }
    if source in UNTRUSTED_PROVENANCE_SOURCES or actor in UNTRUSTED_ACTOR_KEYS:
        return {
            "retrieval_trust": "untrusted",
            "reason": f"auto_expand:{actor or source}",
            "actor_key": actor,
            "provenance_source": source,
        }
    return {
        "retrieval_trust": "untrusted",
        "reason": "fail_closed_unknown_provenance",
        "actor_key": actor,
        "provenance_source": source,
    }


def _trusted_verdict_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """If any live row is already trusted, return that verdict (do not clobber)."""
    for prior in rows:
        prior_v = classify_contact_trust(dict(prior))
        if prior_v.get("retrieval_trust") == "trusted":
            return prior_v
    return None


def apply_email_contact_trust(
    person_id: str,
    address: str,
    *,
    actor_key: str,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stamp retrieval_trust / status from provenance. Never clobber a trusted row.

    Auto-expand may create a candidate. It must not overwrite owner/operator
    profile provenance on the same address (including a later duplicate row).
    """
    norm = normalize_handle(address)
    verdict = classify_contact_trust(
        {"actor_key": actor_key, "provenance_json": provenance or {}}
    )
    trust = str(verdict.get("retrieval_trust") or "untrusted")
    status = "confirmed" if trust == "trusted" else "candidate"
    if not person_id or not norm:
        return {**verdict, "status": status, "updated": False}
    try:
        with connection() as conn:
            priors = list(
                conn.execute(
                    """
                    SELECT id, actor_key, provenance_json, status
                    FROM person_contact_points
                    WHERE person_id = %s::uuid
                      AND contact_kind = 'email'
                      AND lower(value_text) = %s
                      AND status IN ('confirmed', 'candidate', 'observed')
                    """,
                    (person_id, norm),
                ).fetchall()
            )
        kept = _trusted_verdict_from_rows([dict(r) for r in priors])
        if kept is not None and trust != "trusted":
            return {
                **kept,
                "status": "confirmed",
                "updated": False,
                "address": norm,
                "kept_prior_trust": True,
            }
    except Exception:  # noqa: BLE001
        priors = []
    try:
        with connection() as conn:
            if trust == "trusted":
                conn.execute(
                    """
                    UPDATE person_contact_points
                    SET retrieval_trust = 'trusted',
                        status = 'confirmed',
                        actor_key = %s,
                        provenance_json = %s::jsonb,
                        updated_at = now()
                    WHERE person_id = %s::uuid
                      AND contact_kind = 'email'
                      AND lower(value_text) = %s
                      AND status IN ('confirmed', 'candidate', 'observed')
                    """,
                    (actor_key, json.dumps(provenance or {}), person_id, norm),
                )
            else:
                # Demote status/trust only. Never rewrite owner/operator provenance.
                conn.execute(
                    """
                    UPDATE person_contact_points
                    SET retrieval_trust = 'untrusted',
                        status = CASE
                            WHEN status = 'confirmed' THEN 'candidate'
                            ELSE status
                        END,
                        updated_at = now()
                    WHERE person_id = %s::uuid
                      AND contact_kind = 'email'
                      AND lower(value_text) = %s
                      AND status IN ('confirmed', 'candidate', 'observed')
                    """,
                    (person_id, norm),
                )
    except Exception:  # noqa: BLE001
        try:
            with connection() as conn:
                if trust == "trusted":
                    conn.execute(
                        """
                        UPDATE person_contact_points
                        SET status = %s,
                            actor_key = %s,
                            provenance_json = %s::jsonb,
                            updated_at = now()
                        WHERE person_id = %s::uuid
                          AND contact_kind = 'email'
                          AND lower(value_text) = %s
                        """,
                        (status, actor_key, json.dumps(provenance or {}), person_id, norm),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE person_contact_points
                        SET status = %s,
                            updated_at = now()
                        WHERE person_id = %s::uuid
                          AND contact_kind = 'email'
                          AND lower(value_text) = %s
                        """,
                        (status, person_id, norm),
                    )
        except Exception:  # noqa: BLE001
            return {**verdict, "status": status, "updated": False}
    return {**verdict, "status": status, "updated": True, "address": norm}


# FlightSim address-centric gate (PR #74 result, hostname FlightSim, git e0d8446):
# 700 Person addresses → 42,554 retrieve/Gallery hits. Those keys were
# auto-expand / corroboration, not People-card trust. This module must not
# treat that dump as retrieve keys. Counts are diagnostic, not production caps.
ADDRESS_CENTRIC_FLIGHTSIM_LEGACY = {
    "hostname": "FlightSim",
    "address_count": 700,
    "retrieve_hits": 42_554,
    "gallery_email_n": 42_554,
    "peggo417": "peggo417@hotmail.com",
}


def retrieve_keys_from_contact_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify in-memory contact rows the same way retrieve does (no DB)."""
    trusted: list[str] = []
    untrusted: list[str] = []
    why: list[dict[str, Any]] = []
    for row in rows:
        verdict = classify_contact_trust(row)
        addr = normalize_handle(
            str(row.get("value_text") or row.get("address") or "")
        )
        entry = {
            "address": addr,
            "retrieval_trust": verdict.get("retrieval_trust"),
            "reason": verdict.get("reason"),
            "actor_key": verdict.get("actor_key"),
            "provenance_source": verdict.get("provenance_source"),
        }
        why.append(entry)
        if verdict.get("retrieval_trust") == "trusted" and addr and "@" in addr:
            if addr not in trusted:
                trusted.append(addr)
        elif addr and "@" in addr and addr not in untrusted:
            untrusted.append(addr)
    return {
        "trusted_addresses": trusted,
        "untrusted_addresses": untrusted,
        "rows": why,
        "unsupported_if_used_as_retrieve_keys": [
            a for a in untrusted if a not in trusted
        ],
    }


def trusted_emails_for_people(person_ids: set[str] | list[str]) -> set[str]:
    """Ask/Gallery retrieve keys: emails with retrieval_trust = trusted only."""
    ids = [str(p) for p in person_ids if str(p).strip()]
    if not ids:
        return set()
    out: set[str] = set()
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT value_text, actor_key, provenance_json, status
                FROM person_contact_points
                WHERE contact_kind = 'email'
                  AND person_id::text = ANY(%s)
                  AND status IN ('confirmed', 'candidate', 'observed')
                """,
                (ids,),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return set()
    for r in rows:
        verdict = classify_contact_trust(dict(r))
        if verdict.get("retrieval_trust") != "trusted":
            continue
        n = normalize_handle(str(r.get("value_text") or ""))
        if n and "@" in n:
            out.add(n)
    return out


def reclassify_person_email_trust(person_id: str) -> dict[str, Any]:
    """Demote unsupported auto-confirmed emails; stamp retrieval_trust. Keep rows."""
    pid = str(person_id or "").strip()
    report: dict[str, Any] = {
        "person_id": pid,
        "trusted": [],
        "demoted": [],
        "counts": {
            "confirmed": 0,
            "candidate": 0,
            "observed": 0,
            "trusted_for_retrieval": 0,
        },
    }
    if not pid:
        report["error"] = "missing_person_id"
        return report
    with connection() as conn:
        rows = list(
            conn.execute(
                """
                SELECT id, value_text, status, actor_key, provenance_json
                FROM person_contact_points
                WHERE person_id = %s::uuid
                  AND contact_kind = 'email'
                  AND status IN ('confirmed', 'candidate', 'observed')
                """,
                (pid,),
            ).fetchall()
        )
        trusted_addrs: set[str] = set()
        for r in rows:
            verdict = classify_contact_trust(dict(r))
            addr = normalize_handle(str(r.get("value_text") or ""))
            if verdict.get("retrieval_trust") == "trusted" and addr:
                trusted_addrs.add(addr)
        for r in rows:
            verdict = classify_contact_trust(dict(r))
            trust = str(verdict.get("retrieval_trust") or "untrusted")
            addr = normalize_handle(str(r.get("value_text") or ""))
            entry = {
                "address": addr,
                "reason": verdict.get("reason"),
                "actor_key": verdict.get("actor_key"),
                "provenance_source": verdict.get("provenance_source"),
                "prior_status": r.get("status"),
            }
            if trust == "trusted":
                conn.execute(
                    """
                    UPDATE person_contact_points
                    SET retrieval_trust = 'trusted',
                        status = 'confirmed',
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (r.get("id"),),
                )
                report["trusted"].append(entry)
            else:
                new_status = "candidate" if r.get("status") == "confirmed" else (
                    r.get("status") or "observed"
                )
                if new_status == "confirmed":
                    new_status = "candidate"
                conn.execute(
                    """
                    UPDATE person_contact_points
                    SET retrieval_trust = 'untrusted',
                        status = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (new_status, r.get("id")),
                )
                if addr and addr not in trusted_addrs:
                    conn.execute(
                        """
                        UPDATE communication_identities
                        SET resolution_status = 'observed',
                            updated_at = now()
                        WHERE identity_kind = 'email'
                          AND address_normalized = %s
                          AND resolved_person_id = %s::uuid
                          AND resolution_status = 'confirmed'
                        """,
                        (addr, pid),
                    )
                entry["new_status"] = new_status
                report["demoted"].append(entry)
        for addr in trusted_addrs:
            conn.execute(
                """
                UPDATE communication_identities
                SET resolution_status = 'confirmed',
                    resolved_person_id = %s::uuid,
                    updated_at = now()
                WHERE identity_kind = 'email'
                  AND address_normalized = %s
                """,
                (pid, addr),
            )
        tally = list(
            conn.execute(
                """
                SELECT status, retrieval_trust, count(*)::int AS n
                FROM person_contact_points
                WHERE person_id = %s::uuid AND contact_kind = 'email'
                GROUP BY status, retrieval_trust
                """,
                (pid,),
            ).fetchall()
        )
    for t in tally:
        st = str(t.get("status") or "")
        n = int(t.get("n") or 0)
        if st in report["counts"]:
            report["counts"][st] = int(report["counts"].get(st) or 0) + n
        if str(t.get("retrieval_trust") or "") == "trusted":
            report["counts"]["trusted_for_retrieval"] += n
    return report


def report_person_identity_trust(person_id: str) -> dict[str, Any]:
    """Audit snapshot: trusted identities + status counts (no retrieve)."""
    rec = reclassify_person_email_trust(person_id)
    rec["trusted_addresses"] = sorted(
        {str(x.get("address") or "") for x in rec.get("trusted") or [] if x.get("address")}
    )
    return rec


def report_person_identity_and_retrieve(person_id: str) -> dict[str, Any]:
    """Reclassify, inventory each trusted address, list retrieve-key leakage."""
    rec = report_person_identity_trust(person_id)
    per_addr: list[dict[str, Any]] = []
    try:
        from memorybox.person.comm_address_index import inventory_email_address
    except Exception:  # noqa: BLE001
        inventory_email_address = None  # type: ignore[assignment]
    reasons = {
        str(x.get("address") or ""): x
        for x in (rec.get("trusted") or [])
        if x.get("address")
    }
    for addr in rec.get("trusted_addresses") or []:
        entry: dict[str, Any] = {
            "address": addr,
            "why_trusted": (reasons.get(addr) or {}).get("reason"),
            "actor_key": (reasons.get(addr) or {}).get("actor_key"),
            "provenance_source": (reasons.get(addr) or {}).get("provenance_source"),
            "unique_structured_messages": None,
        }
        if inventory_email_address is not None:
            try:
                inv = inventory_email_address(addr, include_quoted_body=False)
                struct = (inv or {}).get("structured_header") or {}
                entry["unique_structured_messages"] = int(
                    struct.get("occurrence_count") or 0
                )
            except Exception as exc:  # noqa: BLE001
                entry["inventory_error"] = str(exc)
        per_addr.append(entry)
    rec["per_trusted_address"] = per_addr
    try:
        from memorybox.person.comm_identity import expand_emails_for_retrieve

        expanded = expand_emails_for_retrieve({person_id})
        retrieve_addrs = {
            normalize_handle(str(a))
            for a in (expanded.get("addresses") or set())
            if normalize_handle(str(a))
        }
    except Exception as exc:  # noqa: BLE001
        retrieve_addrs = set()
        rec["expand_error"] = str(exc)
        expanded = {}
    trusted_set = set(rec.get("trusted_addresses") or [])
    rec["retrieve_addresses"] = sorted(retrieve_addrs)
    rec["unsupported_retrieve_addresses"] = sorted(retrieve_addrs - trusted_set)
    rec["expansion"] = {
        "trusted_only": (expanded.get("expansion") or {}).get("trusted_only"),
        "cache_hit": (expanded.get("expansion") or {}).get("cache_hit"),
    }
    rec.update(_live_retrieve_and_gallery_scope(person_id, trusted_set))
    return rec


def email_payload_trusted(payload: dict[str, Any], trusted_addrs: set[str]) -> bool:
    """True when structured From/To/CC/BCC intersects trusted retrieve keys."""
    from memorybox.ask.retrieve import _payload_email_addresses

    addrs = _payload_email_addresses(payload if isinstance(payload, dict) else {})
    return bool(addrs & {normalize_handle(a) for a in trusted_addrs if a})


def _live_retrieve_and_gallery_scope(person_id: str, trusted: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "retrieve_hit_count": None,
        "gallery_email_count": None,
        "unique_emails_by_trusted_address": {},
        "unsupported_retrieve_hits": [],
    }
    if not person_id:
        return out
    try:
        from memorybox.ask.retrieve import (
            _payload_email_addresses,
            search_email_messages,
        )
        from memorybox.planner import QueryPlan

        plan = QueryPlan(
            original_ask="tell me about this person",
            effective_ask="tell me about this person",
            is_followup=False,
            want_photo=False,
            want_communication=True,
            want_calendar=False,
            person_names=(),
            person_ids=(person_id,),
            place_names=(),
            time_start=None,
            time_end=None,
            temporal_windows=(),
            notes=("complete_comm_retrieve",),
        )
        hits = search_email_messages(plan, limit=500_000)
        out["retrieve_hit_count"] = len(hits)
        by_addr: dict[str, int] = {a: 0 for a in sorted(trusted)}
        only_via: dict[str, int] = {a: 0 for a in sorted(trusted)}
        shared = 0
        unsupported: list[str] = []
        for h in hits:
            payload = getattr(h, "payload", None) or {}
            if not isinstance(payload, dict):
                payload = {}
            addrs = _payload_email_addresses(payload)
            hit_trusted = addrs & trusted
            if hit_trusted:
                for a in hit_trusted:
                    by_addr[a] = int(by_addr.get(a) or 0) + 1
                if len(hit_trusted) == 1:
                    only = next(iter(hit_trusted))
                    only_via[only] = int(only_via.get(only) or 0) + 1
                else:
                    shared += 1
            else:
                eid = str(getattr(h, "evidence_id", "") or "")
                if eid:
                    unsupported.append(eid)
        out["unique_emails_by_trusted_address"] = by_addr
        out["unique_only_via_trusted_address"] = only_via
        out["shared_across_trusted_addresses"] = shared
        out["unsupported_retrieve_hits"] = unsupported[:48]
        out["unsupported_retrieve_hit_count"] = len(unsupported)
    except Exception as exc:  # noqa: BLE001
        out["retrieve_scope_error"] = str(exc)
    try:
        from memorybox.explore.find import _attach_visible_email

        _items, email_n, match_total = _attach_visible_email(
            [],
            {
                "plan": {
                    "person_ids": [person_id],
                    "person_names": [],
                    "original_ask": "tell me about this person",
                    "effective_ask": "tell me about this person",
                    "gallery_show_email": True,
                },
                "evidence_hits": [],
            },
            ask_text="tell me about this person",
            show_email=True,
        )
        out["gallery_email_count"] = int(email_n or 0)
        out["gallery_match_total"] = int(match_total or 0)
        retrieve_n = out.get("retrieve_hit_count")
        if retrieve_n is not None and int(email_n or 0) and int(retrieve_n) >= 0:
            out["gallery_vs_retrieve"] = {
                "gallery_email_count": int(email_n or 0),
                "retrieve_hit_count": int(retrieve_n),
            }
    except Exception as exc:  # noqa: BLE001
        out["gallery_scope_error"] = str(exc)
    if out.get("unsupported_retrieve_hit_count"):
        rec_ok = False
    else:
        rec_ok = True
    out["retrieve_scope_ok"] = rec_ok and not out.get("unsupported_retrieve_hits")
    return out


def report_named_person_identity_trust(display_name: str) -> dict[str, Any]:
    """Resolve a Person by display name, then report trust + retrieve scope."""
    name = str(display_name or "").strip()
    if not name:
        return {"ok": False, "error": "missing_display_name"}
    try:
        from memorybox.person import resolve_person_by_name

        resolved = resolve_person_by_name(name, create_if_missing=False, confirm=False)
        pid = str(getattr(resolved, "person_id", "") or getattr(resolved, "id", "") or "")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "display_name": name}
    if not pid:
        return {"ok": False, "error": "person_not_found", "display_name": name}
    rec = report_person_identity_and_retrieve(pid)
    trusted_n = len(rec.get("trusted_addresses") or [])
    retrieve_n = rec.get("retrieve_hit_count")
    rec["ok"] = (
        not rec.get("unsupported_retrieve_addresses")
        and not rec.get("unsupported_retrieve_hit_count")
        and trusted_n > 0
        and retrieve_n is not None
        and int(retrieve_n) > 0
    )
    rec["display_name"] = name
    rec["phase1_summary"] = format_phase1_human_report(rec)
    return rec


def format_phase1_human_report(rec: dict[str, Any]) -> str:
    """Short FlightSim paste: trusted + why, counts, unique-only, Gallery."""
    lines = [
        "TRUSTED-IDENTITY PHASE 1 REPORT",
        f"person: {rec.get('display_name') or rec.get('person_id')}",
        f"ok: {rec.get('ok')}",
        f"counts: {json.dumps(rec.get('counts') or {}, default=str)}",
        "trusted identities:",
    ]
    per = rec.get("per_trusted_address") or []
    if not per:
        for addr in rec.get("trusted_addresses") or []:
            per.append({"address": addr})
    only_via = rec.get("unique_only_via_trusted_address") or {}
    by_addr = rec.get("unique_emails_by_trusted_address") or {}
    for row in per:
        addr = str(row.get("address") or "")
        lines.append(
            f"  - {addr} why={row.get('why_trusted') or row.get('reason')} "
            f"actor={row.get('actor_key')} source={row.get('provenance_source')} "
            f"structured={row.get('unique_structured_messages')} "
            f"retrieve_hits={by_addr.get(addr)} unique_only={only_via.get(addr)}"
        )
    lines.extend(
        [
            f"shared_across_trusted: {rec.get('shared_across_trusted_addresses')}",
            f"retrieve_hit_count: {rec.get('retrieve_hit_count')}",
            f"gallery_email_count: {rec.get('gallery_email_count')}",
            f"unsupported_retrieve_addresses: {rec.get('unsupported_retrieve_addresses')}",
            f"unsupported_retrieve_hit_count: {rec.get('unsupported_retrieve_hit_count')}",
        ]
    )
    if rec.get("error"):
        lines.append(f"error: {rec.get('error')}")
    return "\n".join(lines)


def attest_trusted_email(
    person_id: str,
    address: str,
    *,
    actor_key: str = "operator",
) -> dict[str, Any]:
    """Owner/operator confirmation — the only path that grants retrieval trust here."""
    from memorybox.person.comm_identity import ensure_confirmed_email_contact

    norm = normalize_handle(address)
    return ensure_confirmed_email_contact(
        person_id,
        norm,
        provenance={
            "source": "comm_identity_operator_attested",
            "operator_attested": True,
            "normalized": norm,
        },
        note="Owner/operator attested trusted-for-retrieval identity",
    )
