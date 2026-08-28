"""Archive-wide address-centric communication identity ledger.

Address is the stable identity. Display names (Peg Legg, Peggy George) are
observations. Person resolution attaches confirmed contacts after corroboration;
discovery does not require the Person to already hold the email.
"""
from __future__ import annotations

import json
import re
from typing import Any

from memorybox.db import connection
from memorybox.person.phone_map import normalize_handle

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_QUOTED_HDR_RE = re.compile(
    r"(?im)^(from|to|cc|bcc)\s*:\s*(.+)$",
)
_MAX_EVIDENCE_SAMPLE = 48


def _norm_display(raw: str | None) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip().lower())


def _header_records(payload: dict[str, Any]) -> list[dict[str, str]]:
    from memorybox.person.comm_identity import _header_records as _hr

    return _hr(payload)


def _quoted_body_address_displays(body: str, address: str) -> list[dict[str, str]]:
    """Lower-confidence: RFC-looking From/To/Cc/Bcc lines inside body text."""
    addr = normalize_handle(address)
    if not addr or "@" not in addr or not body:
        return []
    out: list[dict[str, str]] = []
    for m in _QUOTED_HDR_RE.finditer(body or ""):
        field = m.group(1).lower()
        value = m.group(2) or ""
        if addr not in value.lower():
            continue
        dn = ""
        angle = re.search(
            rf"([^<>]*?)\s*<\s*{re.escape(addr)}\s*>",
            value,
            flags=re.I,
        )
        if angle:
            dn = angle.group(1).strip().strip('"')
        out.append({"header_field": f"quoted_{field}", "display_name": dn, "raw": value[:240]})
    return out


def inventory_email_address(
    address: str,
    *,
    limit_scan: int = 100_000,
    include_quoted_body: bool = True,
) -> dict[str, Any]:
    """Report distinct display names for one address across the archive.

    Separates structured From/To/CC participant headers from quoted-body headers.
    """
    addr = normalize_handle(address)
    if not addr or "@" not in addr:
        return {"ok": False, "error": "invalid_address", "address": addr}

    like = f"%{addr}%"
    header_names: dict[str, dict[str, Any]] = {}
    quoted_names: dict[str, dict[str, Any]] = {}
    header_evidence: list[str] = []
    quoted_evidence: list[str] = []
    header_fields_seen: set[str] = set()
    rows_scanned = 0
    header_hits = 0
    quoted_hits = 0

    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT id, payload_json
                FROM evidence
                WHERE evidence_kind = 'communication'
                  AND lower(coalesce(payload_json->>'evidence_channel', 'email'))
                      NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs')
                  AND (
                    lower(coalesce(payload_json->>'from', '')) LIKE %s
                    OR lower(coalesce((payload_json->'to')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'cc')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'bcc')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'people')::text, '')) LIKE %s
                    OR lower(coalesce(payload_json->>'body_text', '')) LIKE %s
                    OR EXISTS (
                      SELECT 1 FROM jsonb_array_elements(
                        coalesce(payload_json->'from_parsed','[]'::jsonb)
                        || coalesce(payload_json->'to_parsed','[]'::jsonb)
                        || coalesce(payload_json->'cc_parsed','[]'::jsonb)
                        || coalesce(payload_json->'bcc_parsed','[]'::jsonb)
                      ) e
                      WHERE lower(coalesce(e->>'normalized', e->>'address', '')) = %s
                    )
                  )
                LIMIT %s
                """,
                (like, like, like, like, like, like, addr, limit_scan),
            ).fetchall()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "address": addr}

    for r in rows:
        rows_scanned += 1
        eid = str(r.get("id") or "")
        raw = r.get("payload_json")
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        structured_hit = False
        for rec in _header_records(payload):
            if rec.get("address") != addr:
                continue
            structured_hit = True
            header_hits += 1
            header_fields_seen.add(rec.get("header_field") or "")
            dn = _norm_display(rec.get("display_name"))
            key = dn or "(empty_display_name)"
            slot = header_names.setdefault(
                key,
                {"display_name": rec.get("display_name") or "", "count": 0, "header_fields": set()},
            )
            slot["count"] += 1
            slot["header_fields"].add(rec.get("header_field") or "")
            if eid and eid not in header_evidence and len(header_evidence) < _MAX_EVIDENCE_SAMPLE:
                header_evidence.append(eid)
        if include_quoted_body:
            body = str(payload.get("body_text") or "")
            for q in _quoted_body_address_displays(body, addr):
                # Skip if same message already counted this display in structured headers
                # — still count as quoted observation for the report.
                quoted_hits += 1
                dn = _norm_display(q.get("display_name"))
                key = dn or "(empty_display_name)"
                slot = quoted_names.setdefault(
                    key,
                    {
                        "display_name": q.get("display_name") or "",
                        "count": 0,
                        "header_fields": set(),
                    },
                )
                slot["count"] += 1
                slot["header_fields"].add(q.get("header_field") or "")
                if eid and eid not in quoted_evidence and len(quoted_evidence) < _MAX_EVIDENCE_SAMPLE:
                    quoted_evidence.append(eid)
        _ = structured_hit

    def _freeze(d: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for key, slot in d.items():
            out.append(
                {
                    "normalized_display": key,
                    "display_name": slot.get("display_name") or "",
                    "count": int(slot.get("count") or 0),
                    "header_fields": sorted(slot.get("header_fields") or []),
                }
            )
        out.sort(key=lambda x: (-int(x["count"]), x["normalized_display"]))
        return out

    header_list = _freeze(header_names)
    quoted_list = _freeze(quoted_names)
    has_peggy_george_header = any(
        x["normalized_display"] == "peggy george" for x in header_list
    )
    has_peg_legg_header = any(x["normalized_display"] == "peg legg" for x in header_list)
    has_peggy_george_quoted = any(
        x["normalized_display"] == "peggy george" for x in quoted_list
    )
    has_peg_legg_quoted = any(x["normalized_display"] == "peg legg" for x in quoted_list)

    return {
        "ok": True,
        "address": addr,
        "rows_scanned": rows_scanned,
        "structured_header": {
            "occurrence_count": header_hits,
            "distinct_display_names": header_list,
            "header_fields_seen": sorted(header_fields_seen),
            "evidence_ids_sample": header_evidence,
            "has_peggy_george": has_peggy_george_header,
            "has_peg_legg": has_peg_legg_header,
        },
        "quoted_body_headers_only": {
            "occurrence_count": quoted_hits,
            "distinct_display_names": quoted_list,
            "evidence_ids_sample": quoted_evidence,
            "has_peggy_george": has_peggy_george_quoted,
            "has_peg_legg": has_peg_legg_quoted,
            "note": (
                "Lower confidence — From/To/Cc/Bcc lines embedded in body_text "
                "(quoted/forwarded). Do not establish identity alone."
            ),
        },
    }


def upsert_communication_identity_from_inventory(
    inventory: dict[str, Any],
    *,
    resolved_person_id: str | None = None,
    resolution_status: str | None = None,
) -> dict[str, Any]:
    """Persist inventory into communication_identities (idempotent upsert)."""
    if not inventory.get("ok"):
        return {"upserted": False, "reason": "inventory_not_ok"}
    addr = normalize_handle(str(inventory.get("address") or ""))
    if not addr:
        return {"upserted": False, "reason": "invalid_address"}

    observed: dict[str, Any] = {}
    for src_key, conf_key in (
        ("structured_header", "header_count"),
        ("quoted_body_headers_only", "quoted_body_count"),
    ):
        block = inventory.get(src_key) or {}
        for row in block.get("distinct_display_names") or []:
            nd = str(row.get("normalized_display") or "")
            if not nd:
                continue
            slot = observed.setdefault(
                nd,
                {
                    "display_name": row.get("display_name") or "",
                    "header_count": 0,
                    "quoted_body_count": 0,
                    "header_fields": [],
                },
            )
            slot[conf_key] = int(row.get("count") or 0)
            fields = list(slot.get("header_fields") or [])
            for f in row.get("header_fields") or []:
                if f not in fields:
                    fields.append(f)
            slot["header_fields"] = fields

    header_n = int((inventory.get("structured_header") or {}).get("occurrence_count") or 0)
    quoted_n = int(
        (inventory.get("quoted_body_headers_only") or {}).get("occurrence_count") or 0
    )
    evidence = list(
        (inventory.get("structured_header") or {}).get("evidence_ids_sample") or []
    )[:_MAX_EVIDENCE_SAMPLE]
    status = resolution_status or (
        "confirmed"
        if resolved_person_id
        else ("observed" if header_n else "observed")
    )
    prov = {
        "source": "comm_address_index",
        "inventory_rows_scanned": inventory.get("rows_scanned"),
        "has_peggy_george_header": (inventory.get("structured_header") or {}).get(
            "has_peggy_george"
        ),
        "has_peg_legg_header": (inventory.get("structured_header") or {}).get(
            "has_peg_legg"
        ),
    }

    try:
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO communication_identities (
                    address_normalized, identity_kind, observed_display_names,
                    evidence_ids_sample, header_occurrence_count,
                    quoted_body_occurrence_count, resolved_person_id,
                    resolution_status, provenance_json, updated_at
                ) VALUES (
                    %s, 'email', %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::jsonb, now()
                )
                ON CONFLICT (identity_kind, address_normalized) DO UPDATE SET
                    observed_display_names = EXCLUDED.observed_display_names,
                    evidence_ids_sample = EXCLUDED.evidence_ids_sample,
                    header_occurrence_count = EXCLUDED.header_occurrence_count,
                    quoted_body_occurrence_count = EXCLUDED.quoted_body_occurrence_count,
                    resolved_person_id = COALESCE(
                        EXCLUDED.resolved_person_id,
                        communication_identities.resolved_person_id
                    ),
                    resolution_status = CASE
                        WHEN EXCLUDED.resolved_person_id IS NOT NULL THEN EXCLUDED.resolution_status
                        ELSE communication_identities.resolution_status
                    END,
                    provenance_json = EXCLUDED.provenance_json,
                    updated_at = now()
                """,
                (
                    addr,
                    json.dumps(observed),
                    json.dumps(evidence),
                    header_n,
                    quoted_n,
                    resolved_person_id,
                    status,
                    json.dumps(prov),
                ),
            )
    except Exception as exc:  # noqa: BLE001
        return {"upserted": False, "error": str(exc), "address": addr}
    return {
        "upserted": True,
        "address": addr,
        "observed_display_names": observed,
        "header_occurrence_count": header_n,
        "quoted_body_occurrence_count": quoted_n,
        "resolved_person_id": resolved_person_id,
        "resolution_status": status,
    }


def find_addresses_for_person_forms(
    known_forms: list[str],
    *,
    limit_scan: int = 50_000,
) -> list[dict[str, Any]]:
    """Address-first discovery: scan headers for addresses whose display matches Person forms.

    Does not require the Person to already have an email contact.
    """
    from memorybox.person.comm_identity import (
        _display_matches_person,
        _nickname_tokens_for_person,
    )

    forms = [f for f in (known_forms or []) if f]
    if not forms:
        return []
    multi = [f for f in forms if " " in f.strip()]
    prefilter = multi or forms
    nicks = sorted(_nickname_tokens_for_person(forms))
    patterns = list(dict.fromkeys(
        [f"%{f}%" for f in prefilter] + [f"%{n} %" for n in nicks] + [f"{n} %" for n in nicks]
    ))
    candidates: dict[str, dict[str, Any]] = {}
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT id, payload_json
                FROM evidence
                WHERE evidence_kind = 'communication'
                  AND lower(coalesce(payload_json->>'evidence_channel', 'email'))
                      NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs')
                  AND (
                    lower(coalesce(payload_json->>'from', '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'to')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'cc')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'bcc')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'people')::text, '')) LIKE ANY(%s)
                    OR EXISTS (
                      SELECT 1 FROM jsonb_array_elements(
                        coalesce(payload_json->'from_parsed','[]'::jsonb)
                        || coalesce(payload_json->'to_parsed','[]'::jsonb)
                        || coalesce(payload_json->'cc_parsed','[]'::jsonb)
                        || coalesce(payload_json->'bcc_parsed','[]'::jsonb)
                      ) e
                      WHERE lower(coalesce(e->>'display_name', '')) LIKE ANY(%s)
                    )
                  )
                LIMIT %s
                """,
                (
                    patterns,
                    patterns,
                    patterns,
                    patterns,
                    patterns,
                    patterns,
                    limit_scan,
                ),
            ).fetchall()
    except Exception:  # noqa: BLE001
        rows = []

    for r in rows:
        raw = r.get("payload_json")
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        eid = str(r.get("id") or "")
        for rec in _header_records(payload):
            strength = _display_matches_person(rec.get("display_name") or "", forms)
            if not strength:
                continue
            addr = rec.get("address") or ""
            if not addr or "@" not in addr:
                continue
            slot = candidates.setdefault(
                addr,
                {
                    "address": addr,
                    "display_names": {},
                    "match_strengths": {},
                    "evidence_ids": [],
                    "header_fields": set(),
                    "occurrences": 0,
                },
            )
            slot["occurrences"] += 1
            dn = rec.get("display_name") or ""
            if dn:
                slot["display_names"][dn] = int(slot["display_names"].get(dn) or 0) + 1
                slot["match_strengths"][dn] = strength
            slot["header_fields"].add(rec.get("header_field") or "")
            if eid and eid not in slot["evidence_ids"]:
                slot["evidence_ids"].append(eid)

    out = []
    for addr, slot in candidates.items():
        out.append(
            {
                "address": addr,
                "display_names": slot["display_names"],
                "match_strengths": slot["match_strengths"],
                "evidence_ids": slot["evidence_ids"][:24],
                "header_fields": sorted(slot["header_fields"]),
                "occurrences": slot["occurrences"],
                "match_strength": (
                    "full"
                    if "full" in slot["match_strengths"].values()
                    or "alias_full" in slot["match_strengths"].values()
                    else next(iter(slot["match_strengths"].values()), None)
                ),
            }
        )
    out.sort(key=lambda c: (-int(c["occurrences"]), c["address"]))
    return out


def resolve_and_attach_addresses_for_person(
    person_id: str,
    *,
    persist: bool = True,
    backfill: bool = True,
    inventory_attached: bool = True,
) -> dict[str, Any]:
    """Three-step identity pipeline for one Person (Ask/Gallery).

    1. DISCOVER — find archive addresses whose structured display names match
       this Person's forms; upsert ``communication_identities`` as observed
       (no Person email contact required).
    2. RESOLVE — corroborate each identity → Person; write contacts + ledger.
    3. RETRIEVE prep — backfill ``person_ids`` so all mail for those addresses
       is Person evidence (including Peg Legg–labeled messages).
    """
    from memorybox.person.comm_identity import (
        backfill_email_person_ids,
        corroborate_email_candidate,
        ensure_confirmed_email_contact,
        person_identity_snapshot,
        _seed_header_display_aliases,
    )

    snap = person_identity_snapshot(person_id)
    forms = list(snap.get("known_name_forms") or [])
    report: dict[str, Any] = {
        "person_id": person_id,
        "display_name": snap.get("display_name"),
        "known_name_forms": forms,
        "pipeline": ["discover", "resolve", "retrieve_prep"],
        "discovered": [],
        "candidates": [],
        "accepted": [],
        "rejected": [],
        "inventories": [],
    }
    if not forms:
        report["reason"] = "no_known_name_forms"
        return report

    # --- 1. DISCOVER (archive → identities; person not yet required on ledger) ---
    cands = find_addresses_for_person_forms(forms)
    for cand in cands:
        addr = str(cand.get("address") or "")
        inv = inventory_email_address(addr, include_quoted_body=True)
        ledger = upsert_communication_identity_from_inventory(
            inv, resolution_status="observed"
        )
        report["discovered"].append(
            {"address": addr, "candidate": cand, "ledger": ledger}
        )
        if inventory_attached:
            report["inventories"].append(
                {
                    "address": addr,
                    "structured_has_peggy_george": (inv.get("structured_header") or {}).get(
                        "has_peggy_george"
                    ),
                    "structured_has_peg_legg": (inv.get("structured_header") or {}).get(
                        "has_peg_legg"
                    ),
                    "quoted_has_peggy_george": (inv.get("quoted_body_headers_only") or {}).get(
                        "has_peggy_george"
                    ),
                    "quoted_has_peg_legg": (inv.get("quoted_body_headers_only") or {}).get(
                        "has_peg_legg"
                    ),
                    "structured_names": (inv.get("structured_header") or {}).get(
                        "distinct_display_names"
                    ),
                }
            )

        # --- 2. RESOLVE (identity → Person) ---
        decision = corroborate_email_candidate(person_id, cand, known_forms=forms)
        entry = {"candidate": cand, "decision": decision, "inventory": inv}
        report["candidates"].append(entry)

        if decision.get("accepted") and decision.get("reason") != "already_confirmed_for_person":
            if persist:
                ensure_confirmed_email_contact(
                    person_id,
                    addr,
                    provenance={
                        "source": "comm_address_index_resolve",
                        "reason": decision.get("reason"),
                        "corroboration": decision.get("corroboration"),
                        "matched_display_name": decision.get("matched_display_name"),
                        "match_strength": decision.get("match_strength"),
                        "address_centric": True,
                        "pipeline": "discover_then_resolve",
                    },
                    note="Resolved via archive-first communication identity",
                )
                _seed_header_display_aliases(
                    person_id,
                    list((cand.get("display_names") or {}).keys()),
                    known_forms=forms,
                    address=addr,
                )
                upsert_communication_identity_from_inventory(
                    inv,
                    resolved_person_id=person_id,
                    resolution_status="confirmed",
                )
                # --- 3. RETRIEVE prep (all messages for this address) ---
                if backfill:
                    entry["backfill"] = backfill_email_person_ids(person_id, {addr})
            report["accepted"].append(entry)
        elif decision.get("reason") == "already_confirmed_for_person":
            upsert_communication_identity_from_inventory(
                inv,
                resolved_person_id=person_id,
                resolution_status="confirmed",
            )
            if backfill:
                entry["backfill"] = backfill_email_person_ids(person_id, {addr})
            report["accepted"].append(entry)
        else:
            report["rejected"].append(entry)

    return report
