"""Reusable Person communication-identity expansion (email/phone).

Discovers and corroborates participant identities from communication headers
(From/To/CC), persists trusted contacts with provenance, and supports
Person-scoped retrieval closure. Not Peggy-specific.

Rules:
- Prefer header/participant identity over body-name mentions.
- Fail closed on ambiguity (do not silently attach).
- Bounded deterministic expansion loops (no infinite rescans).
- Once persisted, Ask/Gallery reuse confirmed contacts without rediscovery.
"""
from __future__ import annotations

import json
import re
from typing import Any

from memorybox.db import connection
from memorybox.person.phone_map import normalize_handle

_MAX_EXPAND_ROUNDS = 3
_MIN_PAIR_OCCURRENCES = 1  # unique full-name Person + unique unclaimed address is enough
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# First-token nicknames for header discovery (Peg Legg ↔ Peggy George).
_FIRST_NAME_NICKNAMES: dict[str, frozenset[str]] = {
    "peggy": frozenset({"peg", "peggy"}),
    "peg": frozenset({"peg", "peggy"}),
    "margaret": frozenset({"margaret", "meg", "maggie", "peg", "peggy"}),
    "william": frozenset({"william", "will", "bill", "billy"}),
    "will": frozenset({"william", "will", "bill", "billy"}),
    "robert": frozenset({"robert", "rob", "bob", "bobby"}),
    "richard": frozenset({"richard", "rick", "dick"}),
    "rick": frozenset({"richard", "rick"}),
    "james": frozenset({"james", "jim", "jimmy"}),
    "thomas": frozenset({"thomas", "tom", "tommy"}),
    "tom": frozenset({"thomas", "tom", "tommy"}),
    "elizabeth": frozenset({"elizabeth", "liz", "beth", "betty"}),
    "jennifer": frozenset({"jennifer", "jen", "jenny"}),
    "michael": frozenset({"michael", "mike"}),
    "andrew": frozenset({"andrew", "andy", "drew"}),
    "daniel": frozenset({"daniel", "dan", "danny"}),
    "dan": frozenset({"daniel", "dan", "danny"}),
}


def _nickname_tokens_for_person(forms: list[str]) -> set[str]:
    out: set[str] = set()
    for form in forms:
        toks = _name_tokens(form)
        if not toks:
            continue
        first = toks[0]
        out.add(first)
        out |= set(_FIRST_NAME_NICKNAMES.get(first) or ())
    return {t for t in out if len(t) >= 2}


def _norm_name(raw: str | None) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip().lower())


def _name_tokens(raw: str | None) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9']{2,}", _norm_name(raw)) if t]


def person_identity_snapshot(person_id: str) -> dict[str, Any]:
    """Names, aliases, phones, emails, provider mappings for one Person."""
    from memorybox.person import get_person
    from memorybox.profile.facts import list_aliases, list_contacts

    view = get_person(person_id)
    aliases = []
    contacts = []
    provider_ids: list[dict[str, Any]] = []
    try:
        aliases = [a.to_dict() for a in list_aliases(person_id)]
    except Exception:  # noqa: BLE001
        aliases = []
    try:
        contacts = [c.to_dict() for c in list_contacts(person_id)]
    except Exception:  # noqa: BLE001
        contacts = []
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT provider_key, identity_kind, external_id, attributes_json
                FROM provider_identities
                WHERE person_id = %s
                """,
                (person_id,),
            ).fetchall()
            for r in rows:
                provider_ids.append(
                    {
                        "provider_key": r.get("provider_key"),
                        "identity_kind": r.get("identity_kind"),
                        "external_id": r.get("external_id"),
                        "attributes": r.get("attributes_json") or {},
                    }
                )
    except Exception:  # noqa: BLE001
        provider_ids = []

    from memorybox.person.trusted_identity import classify_contact_trust

    emails = []
    for c in contacts:
        if str(c.get("contact_kind") or "").lower() != "email":
            continue
        verdict = classify_contact_trust(
            {
                "actor_key": c.get("actor_key"),
                "provenance_json": c.get("provenance") or c.get("provenance_json") or {},
            }
        )
        if verdict.get("retrieval_trust") == "trusted":
            emails.append(c)
    phones = [
        c
        for c in contacts
        if str(c.get("contact_kind") or "").lower() == "phone"
        and str(c.get("status") or "") == "confirmed"
    ]
    return {
        "person_id": person_id,
        "display_name": getattr(view, "display_name", None) if view else None,
        "aliases": aliases,
        "phones": phones,
        "emails": emails,
        "provider_identities": provider_ids,
        "known_name_forms": _known_name_forms(
            getattr(view, "display_name", None) if view else None, aliases
        ),
    }


def _known_name_forms(display_name: str | None, aliases: list[dict[str, Any]]) -> list[str]:
    forms: list[str] = []
    seen: set[str] = set()
    for raw in [display_name] + [a.get("alias_text") for a in aliases]:
        n = _norm_name(str(raw or ""))
        if not n or n in seen:
            continue
        seen.add(n)
        forms.append(n)
    return forms


def _people_sharing_first_name(first: str) -> list[str]:
    first = (first or "").strip().lower()
    if len(first) < 2:
        return []
    nicks = sorted(_FIRST_NAME_NICKNAMES.get(first) or {first})
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT id, display_name FROM people
                WHERE status IN ('confirmed', 'unresolved')
                  AND lower(split_part(display_name, ' ', 1)) = ANY(%s)
                """,
                (nicks,),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    return [str(r["id"]) for r in rows]


def _address_claimed_by(addr: str) -> list[str]:
    norm = normalize_handle(addr)
    if not norm or "@" not in norm:
        return []
    out: list[str] = []
    try:
        with connection() as conn:
            from memorybox.person.trusted_identity import classify_contact_trust

            rows = conn.execute(
                """
                SELECT person_id, value_text, actor_key, provenance_json, status
                FROM person_contact_points
                WHERE contact_kind = 'email'
                  AND status IN ('confirmed', 'candidate', 'observed')
                """
            ).fetchall()
            for r in rows:
                if normalize_handle(str(r.get("value_text") or "")) != norm:
                    continue
                verdict = classify_contact_trust(dict(r))
                if verdict.get("retrieval_trust") != "trusted":
                    continue
                pid = str(r["person_id"])
                if pid not in out:
                    out.append(pid)
            # Provider email rows are not trusted-for-retrieval (same as
            # phone_map). They must not claim Person ownership.
    except Exception:  # noqa: BLE001
        return out
    return out


def _revoke_confirmed_email_contact(person_id: str, address: str) -> dict[str, Any]:
    """Drop a confirmed email contact (operator reclaim / merge cleanup)."""
    norm = normalize_handle(address)
    pid = str(person_id or "").strip()
    if not norm or "@" not in norm or not pid:
        return {"revoked": False, "reason": "invalid"}
    try:
        with connection() as conn:
            conn.execute(
                """
                DELETE FROM person_contact_points
                WHERE person_id = %s::uuid
                  AND contact_kind = 'email'
                  AND status = 'confirmed'
                  AND lower(value_text) = %s
                """,
                (pid, norm),
            )
            # Clear stale ledger resolution pointing at the revoked Person.
            conn.execute(
                """
                UPDATE communication_identities
                SET resolved_person_id = NULL,
                    resolution_status = 'observed',
                    updated_at = now()
                WHERE identity_kind = 'email'
                  AND address_normalized = %s
                  AND resolved_person_id = %s::uuid
                """,
                (norm, pid),
            )
        return {"revoked": True, "person_id": pid, "address": norm}
    except Exception as exc:  # noqa: BLE001
        return {"revoked": False, "error": str(exc), "person_id": pid, "address": norm}


def _header_records(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Extract participant records from From/To/CC/BCC (never body text)."""
    out: list[dict[str, str]] = []
    parsed_addrs_by_field: dict[str, set[str]] = {
        "from": set(),
        "to": set(),
        "cc": set(),
        "bcc": set(),
    }
    for field in ("from_parsed", "to_parsed", "cc_parsed", "bcc_parsed"):
        base = field.replace("_parsed", "")
        for rec in payload.get(field) or []:
            if not isinstance(rec, dict):
                continue
            addr = normalize_handle(
                str(rec.get("normalized") or rec.get("address") or "")
            )
            if not addr or "@" not in addr:
                continue
            parsed_addrs_by_field[base].add(addr)
            out.append(
                {
                    "address": addr,
                    "display_name": str(rec.get("display_name") or "").strip(),
                    "header_field": base,
                }
            )
    # Fallback: parse raw From/To/CC/BCC only for addresses missing from *_parsed.
    for field, raw in (
        ("from", payload.get("from") or payload.get("from_raw")),
        ("to", payload.get("to")),
        ("cc", payload.get("cc")),
        ("bcc", payload.get("bcc")),
    ):
        texts: list[str] = []
        if isinstance(raw, (list, tuple)):
            texts = [str(x) for x in raw]
        elif raw:
            texts = [str(raw)]
        for text in texts:
            for m in _EMAIL_RE.finditer(text):
                addr = normalize_handle(m.group(0))
                if not addr:
                    continue
                if addr in parsed_addrs_by_field.get(field, set()):
                    continue
                # Display name before <addr> or Outlook [mailto:addr]
                dn = ""
                angle = re.search(
                    rf"([^<>\[]*?)\s*<\s*{re.escape(m.group(0))}\s*>",
                    text,
                    flags=re.I,
                )
                if angle:
                    dn = angle.group(1).strip().strip('"')
                if not dn:
                    mailto = re.search(
                        rf"([^\[\]<>]*?)\s*\[\s*mailto\s*:\s*{re.escape(m.group(0))}\s*\]",
                        text,
                        flags=re.I,
                    )
                    if mailto:
                        dn = mailto.group(1).strip().strip('"').rstrip(",")
                out.append(
                    {
                        "address": addr,
                        "display_name": dn,
                        "header_field": field,
                    }
                )
    # people[] is co-occurrence, never a From display used to confirm ownership.
    # Dedupe: prefer non-empty display for the same address+field family.
    best: dict[tuple[str, str], dict[str, str]] = {}
    for rec in out:
        addr = rec["address"]
        field_family = "from" if str(rec.get("header_field") or "").startswith("from") else str(
            rec.get("header_field") or ""
        )
        key = (addr, field_family)
        prev = best.get(key)
        if prev is None:
            best[key] = rec
            continue
        prev_dn = (prev.get("display_name") or "").strip()
        cur_dn = (rec.get("display_name") or "").strip()
        if not prev_dn and cur_dn:
            best[key] = rec
    return list(best.values())


def _display_matches_person(display_name: str, known_forms: list[str]) -> str | None:
    """Return match strength: 'full' | 'alias_full' | 'nickname_full' | None.

    First-name-only display (\"Peggy\") is never enough. Multi-token nickname
    headers (\"Peg Legg\") may match Person \"Peggy George\" as nickname_full.
    """
    dn = _norm_name(display_name)
    if not dn or not known_forms:
        return None
    tokens = _name_tokens(dn)
    if len(tokens) < 2:
        # Single-token display ("Peggy") is ambiguous by policy.
        return None
    for form in known_forms:
        if dn == form:
            return "full" if form == known_forms[0] else "alias_full"
        # Allow "Last, First" vs "First Last"
        form_toks = _name_tokens(form)
        if len(form_toks) >= 2 and set(tokens) == set(form_toks):
            return "full"
    # Nickname first-token + multi-token surname (Peg Legg ↔ Peggy George)
    for form in known_forms:
        form_toks = _name_tokens(form)
        if not form_toks:
            continue
        person_first = form_toks[0]
        nicks = _FIRST_NAME_NICKNAMES.get(person_first) or {person_first}
        dn_nicks = _FIRST_NAME_NICKNAMES.get(tokens[0]) or {tokens[0]}
        if tokens[0] in nicks or person_first in dn_nicks:
            return "nickname_full"
    return None


def _related_person_ids(person_id: str) -> set[str]:
    try:
        from memorybox.profile.relationships import list_relationship_assertions
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    try:
        for a in list_relationship_assertions(person_id):
            d = a.to_dict() if hasattr(a, "to_dict") else dict(a)
            for key in ("from_person_id", "to_person_id"):
                pid = str(d.get(key) or "")
                if pid and pid != person_id:
                    out.add(pid)
    except Exception:  # noqa: BLE001
        return out
    return out


def discover_email_candidates_from_archive(
    person_id: str,
    *,
    known_forms: list[str] | None = None,
    limit_scan: int = 50_000,
) -> list[dict[str, Any]]:
    """Scan email headers for display-name/address pairs matching the Person.

    SQL prefilter ORs **all** multi-token known forms (display + aliases). Using only
    the longest form misses cases like display ``Peggy George`` with header/alias
    ``Peg Legg``.
    """
    snap = person_identity_snapshot(person_id) if known_forms is None else None
    forms = list(known_forms or (snap or {}).get("known_name_forms") or [])
    if not forms:
        return []
    # Prefer multi-token forms for header prefilter; fall back to longest single token.
    multi = [f for f in forms if " " in f.strip()]
    prefilter_forms = multi or [sorted(forms, key=len, reverse=True)[0]]
    nicks = sorted(_nickname_tokens_for_person(forms))
    patterns = [f"%{f}%" for f in prefilter_forms]
    # Peg Legg / Peg <addr> when Person is Peggy George
    for n in nicks:
        patterns.append(f"%{n} %")
        patterns.append(f"{n} %")
    patterns = list(dict.fromkeys(patterns))
    candidates: dict[str, dict[str, Any]] = {}
    scanned = 0
    try:
        with connection() as conn:
            # Header-oriented prefilter — never body_text.
            # ``to``/``cc`` are JSON arrays: use (payload_json->'to')::text, not ->>.
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
                    OR lower(coalesce((payload_json->'from_parsed')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'to_parsed')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'cc_parsed')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'bcc_parsed')::text, '')) LIKE ANY(%s)
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
                    patterns,
                    patterns,
                    patterns,
                    limit_scan,
                ),
            ).fetchall()
    except Exception:  # noqa: BLE001
        rows = []

    for r in rows:
        scanned += 1
        raw = r.get("payload_json")
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        header_hit = False
        for rec in _header_records(payload):
            strength = _display_matches_person(rec["display_name"], forms)
            if not strength:
                continue
            header_hit = True
            addr = rec["address"]
            slot = candidates.setdefault(
                addr,
                {
                    "address": addr,
                    "display_names": {},
                    "header_fields": set(),
                    "evidence_ids": [],
                    "match_strength": strength,
                    "occurrences": 0,
                },
            )
            slot["occurrences"] += 1
            dn = rec["display_name"]
            if dn:
                slot["display_names"][dn] = int(slot["display_names"].get(dn) or 0) + 1
            slot["header_fields"].add(rec["header_field"])
            eid = str(r.get("id") or "")
            if eid and eid not in slot["evidence_ids"]:
                slot["evidence_ids"].append(eid)
            if strength == "full":
                slot["match_strength"] = "full"
        if not header_hit:
            continue

    out = []
    for addr, slot in candidates.items():
        out.append(
            {
                "address": addr,
                "display_names": slot["display_names"],
                "header_fields": sorted(slot["header_fields"]),
                "evidence_ids": slot["evidence_ids"][:24],
                "match_strength": slot["match_strength"],
                "occurrences": slot["occurrences"],
                "rows_scanned": scanned,
            }
        )
    out.sort(key=lambda c: (-int(c["occurrences"]), c["address"]))
    return out


def corroborate_email_candidate(
    person_id: str,
    candidate: dict[str, Any],
    *,
    known_forms: list[str] | None = None,
    related_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Conservative corroboration. Ambiguity → unresolved (not attached)."""
    addr = normalize_handle(str(candidate.get("address") or ""))
    result: dict[str, Any] = {
        "address": addr,
        "accepted": False,
        "reason": "unreviewed",
        "corroboration": [],
    }
    if not addr or "@" not in addr:
        result["reason"] = "invalid_address"
        return result

    claimants = _address_claimed_by(addr)
    if claimants and person_id not in claimants:
        result["reason"] = "address_claimed_by_other_person"
        result["claimed_by"] = claimants
        return result
    if person_id in claimants:
        result["accepted"] = True
        result["reason"] = "already_confirmed_for_person"
        result["corroboration"].append("existing_contact")
        return result

    snap = person_identity_snapshot(person_id)
    forms = known_forms or snap.get("known_name_forms") or []
    display_names = candidate.get("display_names") or {}
    best_strength = None
    best_dn = None
    for dn, _n in sorted(display_names.items(), key=lambda kv: -int(kv[1])):
        strength = _display_matches_person(dn, forms)
        if strength:
            best_strength = strength
            best_dn = dn
            break
    if not best_strength:
        result["reason"] = "no_full_display_name_match"
        return result
    result["corroboration"].append(f"display_name_{best_strength}:{best_dn}")

    # First-name ambiguity: multiple People share first name and display is weak.
    first = (_name_tokens(best_dn or "") or [""])[0]
    sibling_rows: list[dict[str, Any]] = []
    try:
        nicks = sorted(_FIRST_NAME_NICKNAMES.get(first) or {first})
        with connection() as conn:
            sibling_rows = list(
                conn.execute(
                    """
                    SELECT id, display_name FROM people
                    WHERE status IN ('confirmed', 'unresolved')
                      AND lower(split_part(display_name, ' ', 1)) = ANY(%s)
                    """,
                    (nicks,),
                ).fetchall()
            )
    except Exception:  # noqa: BLE001
        sibling_rows = [{"id": sid} for sid in _people_sharing_first_name(first)]
    siblings = [str(r["id"]) for r in sibling_rows]
    multi_sibs = [
        str(r["id"])
        for r in sibling_rows
        if " " in str(r.get("display_name") or "").strip()
    ]
    if best_strength == "nickname_full":
        # Peg Legg → Peggy George: prefer a unique multi-token Person in the
        # first-name family (ignore Immich single-token stubs like \"Peggy\").
        # When several Peggy* exist (Smith/Jones/George), still accept if this
        # Person is the unique full/alias form match among those siblings —
        # otherwise Ask auto-resolve cannot attach peggo417 without operator repair.
        if len(multi_sibs) > 1:
            form_matches = [
                str(r["id"])
                for r in sibling_rows
                if str(r["id"]) in multi_sibs
                and _display_matches_person(str(r.get("display_name") or ""), forms)
                in {"full", "alias_full"}
            ]
            if person_id not in form_matches or len(set(form_matches)) != 1:
                result["reason"] = "ambiguous_nickname_among_people"
                result["ambiguous_person_ids"] = multi_sibs
                return result
            result["corroboration"].append(
                f"nickname_unique_form_match_among_{len(multi_sibs)}_siblings"
            )
        elif multi_sibs and person_id not in multi_sibs:
            result["reason"] = "nickname_belongs_to_other_person"
            result["ambiguous_person_ids"] = multi_sibs
            return result
        if not any(" " in f for f in forms):
            result["reason"] = "person_lacks_multi_token_name_for_nickname"
            return result
        # Fail closed: nickname first-token alone must not attach every
        # "Peg *" mailbox. Require same-address full/alias observation
        # (structured or quoted), or the nickname already seeded as alias.
        same_addr_full = False
        for dn, _n in display_names.items():
            s = _display_matches_person(str(dn), forms)
            if s in {"full", "alias_full"}:
                same_addr_full = True
                result["corroboration"].append(f"same_address_full:{dn}")
                break
        inv = candidate.get("inventory") if isinstance(candidate.get("inventory"), dict) else {}
        if not same_addr_full and inv:
            # Quoted/body headers are diagnostic only — never same-address ownership.
            block = inv.get("structured_header") or {}
            for slot in block.get("distinct_display_names") or []:
                if not isinstance(slot, dict):
                    continue
                dn = str(slot.get("display_name") or "")
                s = _display_matches_person(dn, forms)
                if s in {"full", "alias_full"}:
                    same_addr_full = True
                    result["corroboration"].append(
                        f"same_address_structured_header_full:{dn}"
                    )
                    break
        alias_forms = {
            _norm_name(str(a.get("alias_text") or ""))
            for a in (snap.get("aliases") or [])
            if isinstance(a, dict) and a.get("alias_text")
        } | {
            _norm_name(a)
            for a in (snap.get("aliases") or [])
            if isinstance(a, str)
        }
        # known_name_forms may already include seeded Peg Legg alias
        nick_is_known_alias = _norm_name(best_dn or "") in {
            f for f in forms if f != _norm_name(snap.get("display_name") or "")
        } or _norm_name(best_dn or "") in alias_forms
        if nick_is_known_alias:
            result["corroboration"].append(f"nickname_is_known_alias:{best_dn}")
        if not same_addr_full and not nick_is_known_alias:
            result["reason"] = "nickname_needs_same_address_full_name_or_alias"
            return result
    elif len(siblings) > 1 and best_strength not in {"full", "alias_full"}:
        result["reason"] = "ambiguous_first_name_among_people"
        result["ambiguous_person_ids"] = siblings
        return result
    # Even with full match, if another live Person has the exact same full display name → ambiguous.
    full_matches = []
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT id, display_name FROM people
                WHERE status IN ('confirmed', 'unresolved')
                  AND lower(display_name) = %s
                """,
                (_norm_name(best_dn),),
            ).fetchall()
            full_matches = [str(r["id"]) for r in rows]
    except Exception:  # noqa: BLE001
        full_matches = [person_id]
    if len(full_matches) > 1:
        result["reason"] = "ambiguous_full_display_name_multiple_people"
        result["ambiguous_person_ids"] = full_matches
        return result

    occ = int(candidate.get("occurrences") or 0)
    if occ < _MIN_PAIR_OCCURRENCES:
        result["reason"] = "insufficient_occurrences"
        return result
    result["corroboration"].append(f"occurrences:{occ}")

    # Bonus: recurring correspondence with already-identified family (non-blocking).
    related = related_ids if related_ids is not None else _related_person_ids(person_id)
    if related and candidate.get("evidence_ids"):
        result["corroboration"].append("family_graph_available")

    result["accepted"] = True
    result["reason"] = "corroborated_header_identity"
    result["matched_display_name"] = best_dn
    result["match_strength"] = best_strength
    return result


def ensure_confirmed_email_contact(
    person_id: str,
    address: str,
    *,
    provenance: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Persist a corroborated email onto person_contact_points (idempotent)."""
    from memorybox.person.phone_map import ensure_confirmed_phone_contact

    norm = normalize_handle(address)
    if not norm or "@" not in norm:
        return {"upserted": False, "reason": "invalid_address"}
    prov = dict(provenance or {})
    prov.setdefault("source", "comm_identity_expand")
    prov.setdefault("normalized", norm)
    upserted = ensure_confirmed_phone_contact(
        person_id,
        norm,
        provenance=prov,
    )
    source = str(prov.get("source") or "")
    actor = (
        "comm_identity_operator_attested"
        if source in {"comm_identity_operator_attested", "operator_attest"}
        or prov.get("operator_attested") is True
        else "comm_identity_expand"
    )
    if note:
        try:
            with connection() as conn:
                conn.execute(
                    """
                    UPDATE person_contact_points
                    SET note = COALESCE(note, %s),
                        updated_at = now()
                    WHERE person_id = %s
                      AND contact_kind = 'email'
                      AND lower(value_text) = %s
                    """,
                    (note, person_id, norm),
                )
        except Exception:  # noqa: BLE001
            pass
    from memorybox.person.trusted_identity import apply_email_contact_trust

    trust_stamp = apply_email_contact_trust(person_id, norm, actor_key=actor, provenance=prov)
    # Keep address-centric ledger in sync with confirmed Person contacts.
    # Probe upsert leaves rows as observed; repair/attach must promote them.
    # Direct SQL — do not re-inventory the archive on every contact ensure.
    ledger_promote: dict[str, Any] = {"ok": False}
    try:
        with connection() as conn:
            ledger_status = (
                "confirmed"
                if str((trust_stamp or {}).get("retrieval_trust") or "") == "trusted"
                else "observed"
            )
            updated = conn.execute(
                """
                UPDATE communication_identities
                SET resolved_person_id = %s::uuid,
                    resolution_status = %s,
                    updated_at = now()
                WHERE identity_kind = 'email'
                  AND address_normalized = %s
                """,
                (person_id, ledger_status, norm),
            )
            # rowcount may be 0 when probe never ran — insert a stub.
            if getattr(updated, "rowcount", None) == 0:
                conn.execute(
                    """
                    INSERT INTO communication_identities (
                        address_normalized, identity_kind, observed_display_names,
                        evidence_ids_sample, header_occurrence_count,
                        quoted_body_occurrence_count, resolved_person_id,
                        resolution_status, provenance_json, updated_at
                    ) VALUES (
                        %s, 'email', '{}'::jsonb, '[]'::jsonb, 0, 0,
                        %s::uuid, %s,
                        %s::jsonb, now()
                    )
                    ON CONFLICT (identity_kind, address_normalized) DO UPDATE SET
                        resolved_person_id = EXCLUDED.resolved_person_id,
                        resolution_status = EXCLUDED.resolution_status,
                        updated_at = now()
                    """,
                    (
                        norm,
                        person_id,
                        ledger_status,
                        json.dumps(
                            {
                                "source": "ensure_confirmed_email_contact",
                                "person_id": person_id,
                                "retrieval_trust": (trust_stamp or {}).get(
                                    "retrieval_trust"
                                ),
                            }
                        ),
                    ),
                )
            ledger_promote = {"ok": True, "address": norm, "person_id": person_id}
    except Exception as exc:  # noqa: BLE001
        ledger_promote = {
            "ok": False,
            "error": str(exc),
            "address": norm,
            "person_id": person_id,
        }
    return {
        "upserted": bool(upserted),
        "address": norm,
        "person_id": person_id,
        "ledger_promote": ledger_promote,
        "retrieval_trust": (trust_stamp or {}).get("retrieval_trust"),
        "trust_reason": (trust_stamp or {}).get("reason"),
    }


def backfill_email_person_ids(
    person_id: str,
    addresses: set[str] | list[str],
    *,
    limit: int = 100_000,
) -> dict[str, Any]:
    """Stamp person_id onto email evidence payloads that carry these header addresses."""
    addrs = {normalize_handle(a) for a in addresses if normalize_handle(a) and "@" in normalize_handle(a)}
    if not addrs or not person_id:
        return {"updated": 0, "scanned": 0}
    updated = 0
    scanned = 0
    patterns = [f"%{a}%" for a in sorted(addrs)]
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
                    OR lower(coalesce((payload_json->'from_parsed')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'to_parsed')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'cc_parsed')::text, '')) LIKE ANY(%s)
                    OR lower(coalesce((payload_json->'bcc_parsed')::text, '')) LIKE ANY(%s)
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
                    patterns,
                    patterns,
                    patterns,
                    limit,
                ),
            ).fetchall()
            for r in rows:
                scanned += 1
                raw = r.get("payload_json")
                payload = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
                header_addrs = {rec["address"] for rec in _header_records(payload)}
                if not (header_addrs & addrs):
                    continue
                pids = [str(x) for x in (payload.get("person_ids") or []) if x]
                if person_id in pids:
                    continue
                pids.append(person_id)
                payload["person_ids"] = list(dict.fromkeys(pids))
                ir = dict(payload.get("identity_resolution") or {})
                mapped = list(ir.get("mapped") or [])
                for addr in sorted(header_addrs & addrs):
                    if any(
                        isinstance(m, dict)
                        and normalize_handle(str(m.get("normalized") or "")) == addr
                        and str(m.get("person_id")) == person_id
                        for m in mapped
                    ):
                        continue
                    mapped.append(
                        {
                            "handle": addr,
                            "normalized": addr,
                            "person_id": person_id,
                            "status": "auto_mapped",
                            "source": "comm_identity_expand_backfill",
                        }
                    )
                ir["mapped"] = mapped
                payload["identity_resolution"] = ir
                conn.execute(
                    """
                    UPDATE evidence
                    SET payload_json = %s::jsonb, updated_at = now()
                    WHERE id = %s
                    """,
                    (json.dumps(payload, default=str), r["id"]),
                )
                updated += 1
    except Exception as exc:  # noqa: BLE001
        return {"updated": updated, "scanned": scanned, "error": str(exc)}
    return {"updated": updated, "scanned": scanned, "addresses": sorted(addrs)}


def expand_person_communication_identities(
    person_ids: list[str] | set[str] | tuple[str, ...],
    *,
    persist: bool = True,
    backfill: bool = True,
    max_rounds: int = _MAX_EXPAND_ROUNDS,
    discover: bool = True,
) -> dict[str, Any]:
    """Bounded identity expansion for one or more People.

    Person → names → header candidates → corroborate → persist → backfill → repeat.
    """
    ids = [str(p) for p in person_ids if str(p).strip()]
    report: dict[str, Any] = {
        "person_ids": ids,
        "rounds": [],
        "accepted": [],
        "rejected": [],
        "emails_by_person": {},
        "llm_calls": 0,
    }
    if not ids:
        return report

    for pid in ids:
        related = _related_person_ids(pid)
        seen_addrs: set[str] = set()
        for round_i in range(max(1, int(max_rounds))):
            snap = person_identity_snapshot(pid)
            forms = snap.get("known_name_forms") or []
            existing = {
                normalize_handle(str(c.get("value_text") or ""))
                for c in (snap.get("emails") or [])
            }
            existing = {e for e in existing if e and "@" in e}
            round_rec: dict[str, Any] = {
                "person_id": pid,
                "round": round_i,
                "existing_emails": sorted(existing),
                "candidates": [],
                "accepted_this_round": [],
                "rejected_this_round": [],
            }
            # Confirmed People emails: always backfill person_ids. Still run one
            # discovery pass for additional header identities (e.g. Peg Legg /
            # peggo417@hotmail.com) that are not yet on the contact card.
            if existing and round_i == 0:
                report["emails_by_person"][pid] = sorted(existing)
                round_rec["confirmed_reuse"] = True
                if backfill:
                    round_rec["backfill"] = backfill_email_person_ids(pid, existing)

            new_this_round: list[str] = []
            if discover and forms:
                candidates = discover_email_candidates_from_archive(
                    pid, known_forms=forms
                )
                for cand in candidates:
                    addr = normalize_handle(str(cand.get("address") or ""))
                    if not addr or addr in seen_addrs or addr in existing:
                        continue
                    seen_addrs.add(addr)
                    decision = corroborate_email_candidate(
                        pid, cand, known_forms=forms, related_ids=related
                    )
                    round_rec["candidates"].append(
                        {"candidate": cand, "decision": decision}
                    )
                    if decision.get("accepted") and decision.get("reason") != "already_confirmed_for_person":
                        if persist:
                            ensure_confirmed_email_contact(
                                pid,
                                addr,
                                provenance={
                                    "source": "comm_identity_expand",
                                    "reason": decision.get("reason"),
                                    "corroboration": decision.get("corroboration"),
                                    "matched_display_name": decision.get(
                                        "matched_display_name"
                                    ),
                                    "match_strength": decision.get("match_strength"),
                                    "evidence_ids_sample": (cand.get("evidence_ids") or [])[
                                        :8
                                    ],
                                    "occurrences": cand.get("occurrences"),
                                    "header_fields": cand.get("header_fields"),
                                },
                                note=(
                                    "Discovered from communication headers; "
                                    "corroborated display-name/address pair"
                                ),
                            )
                            seeded = _seed_header_display_aliases(
                                pid,
                                list((cand.get("display_names") or {}).keys()),
                                known_forms=forms,
                                address=addr,
                            )
                            if seeded:
                                round_rec.setdefault("seeded_aliases", []).extend(seeded)
                        new_this_round.append(addr)
                        round_rec["accepted_this_round"].append(decision)
                        report["accepted"].append(
                            {"person_id": pid, "round": round_i, **decision}
                        )
                    elif decision.get("reason") == "already_confirmed_for_person":
                        pass
                    else:
                        round_rec["rejected_this_round"].append(decision)
                        report["rejected"].append(
                            {"person_id": pid, "round": round_i, **decision}
                        )

            # Refresh contacts after persist.
            snap2 = person_identity_snapshot(pid)
            emails_now = {
                normalize_handle(str(c.get("value_text") or ""))
                for c in (snap2.get("emails") or [])
            }
            emails_now = {e for e in emails_now if e and "@" in e}
            report["emails_by_person"][pid] = sorted(emails_now)

            if backfill and new_this_round:
                bf = backfill_email_person_ids(pid, set(new_this_round) | emails_now)
                round_rec["backfill"] = bf
            elif backfill and emails_now and round_i == 0:
                # First discovery attach path may need initial stamp even when
                # new_this_round filled above; handled in new_this_round branch.
                pass

            report["rounds"].append(round_rec)
            if not new_this_round:
                break
    return report


def expand_emails_for_retrieve(
    person_ids: set[str] | list[str],
    *,
    force_rediscover: bool = False,
) -> dict[str, Any]:
    """Ask/Gallery hook: trusted-identity retrieve keys only.

    Discover/resolve may create candidates. Retrieve addresses are emails
    classified trusted from auditable provenance — never all confirmed
    contacts or confirmed ledger rows.
    """
    from memorybox.person.trusted_identity import trusted_emails_for_people

    ids = [str(p) for p in person_ids if str(p).strip()]
    emails_by_person: dict[str, list[str]] = {
        pid: sorted(trusted_emails_for_people({pid})) for pid in ids
    }
    trusted_addrs: set[str] = set()
    for addrs in emails_by_person.values():
        trusted_addrs.update(addrs)

    if trusted_addrs and not force_rediscover:
        return {
            "addresses": trusted_addrs,
            "expansion": {
                "person_ids": ids,
                "emails_by_person": emails_by_person,
                "pipeline": ["retrieve"],
                "cache_hit": True,
                "trusted_only": True,
                "skipped_archive_discover": True,
                "accepted": [
                    {"address": a, "source": "trusted_identity"}
                    for a in sorted(trusted_addrs)
                ],
                "llm_calls": 0,
                "rounds": [],
                "rejected": [],
            },
        }

    address_reports: list[dict[str, Any]] = []
    expansion: dict[str, Any] = {
        "person_ids": ids,
        "emails_by_person": emails_by_person,
        "pipeline": ["retrieve"],
        "cache_hit": False,
        "trusted_only": True,
        "accepted": [],
        "llm_calls": 0,
        "rounds": [],
        "rejected": [],
    }
    if force_rediscover:
        for pid in ids:
            try:
                from memorybox.person.comm_address_index import (
                    resolve_and_attach_addresses_for_person,
                )

                address_reports.append(
                    resolve_and_attach_addresses_for_person(
                        pid, persist=True, backfill=True, inventory_attached=True
                    )
                )
            except Exception as exc:  # noqa: BLE001
                address_reports.append({"person_id": pid, "error": str(exc)})
        try:
            expansion = expand_person_communication_identities(
                ids, persist=True, backfill=True, discover=True
            )
        except Exception as exc:  # noqa: BLE001
            expansion = {"error": str(exc), "person_ids": ids}
        expansion["address_centric_resolve"] = address_reports
        expansion["pipeline"] = ["discover", "resolve", "retrieve"]
        expansion["cache_hit"] = False
        emails_by_person = {
            pid: sorted(trusted_emails_for_people({pid})) for pid in ids
        }
        trusted_addrs = set()
        for addrs in emails_by_person.values():
            trusted_addrs.update(addrs)
    expansion["emails_by_person"] = emails_by_person
    expansion["trusted_only"] = True
    expansion["accepted"] = [
        {"address": a, "source": "trusted_identity"} for a in sorted(trusted_addrs)
    ]
    return {"addresses": trusted_addrs, "expansion": expansion}


def _seed_header_display_aliases(
    person_id: str,
    display_names: list[str],
    *,
    known_forms: list[str] | None = None,
    address: str | None = None,
) -> list[dict[str, Any]]:
    """Persist multi-token header display names as alternate_name aliases when new.

    Example: Person ``Peggy George`` with hotmail header ``Peg Legg`` — after
    operator-attested address attach, seed ``Peg Legg`` so later discovery ORs it.
    """
    forms = {_norm_name(f) for f in (known_forms or []) if f}
    seeded: list[dict[str, Any]] = []
    seen: set[str] = set(forms)
    try:
        from memorybox.profile.facts import add_alias
    except Exception:  # noqa: BLE001
        return seeded
    for raw in display_names:
        text = str(raw or "").strip()
        n = _norm_name(text)
        if not n or n in seen or " " not in n:
            continue
        if len(_name_tokens(text)) < 2:
            continue
        seen.add(n)
        try:
            add_alias(
                person_id,
                alias_kind="alternate_name",
                alias_text=text,
                actor_key="comm_identity_expand",
                note="Seeded from email header display name paired with known address",
                provenance={
                    "source": "comm_identity_header_alias",
                    "address": address,
                    "normalized_alias": n,
                },
            )
            seeded.append({"alias_text": text, "normalized": n})
        except Exception:  # noqa: BLE001
            # Duplicate or profile rule — skip; identity attach still succeeded.
            continue
    return seeded


def attach_known_email_if_corroborated(
    person_id: str,
    address: str,
    *,
    persist: bool = True,
    backfill: bool = True,
    operator_attested: bool = False,
) -> dict[str, Any]:
    """Attach a known address when headers corroborate Person display-name pairing.

    Used when an address is already known (e.g. peggo417@hotmail.com) but not yet
    on person_contact_points. Requires the address in From/To/CC headers — not body
    text alone.

    Auto path (operator_attested=False): full display-name corroboration required.
    Operator path (operator_attested=True, from repair ``--address``): if the address
    appears in headers and is unclaimed, attach with provenance. Hotmail/Outlook often
    store first-name-only or bare addresses, so silent auto-expand cannot pair them;
    an explicit ``--person-id`` + ``--address`` is the disambiguation.
    """
    addr = normalize_handle(address)
    snap = person_identity_snapshot(person_id)
    forms = snap.get("known_name_forms") or []
    if not addr or "@" not in addr:
        return {"accepted": False, "reason": "missing_address_or_names", "address": addr}
    if not forms and not operator_attested:
        return {"accepted": False, "reason": "missing_address_or_names", "address": addr}

    claimants = _address_claimed_by(addr)
    reclaimed_from: list[str] = []
    if claimants and person_id not in claimants:
        if not operator_attested:
            return {
                "accepted": False,
                "reason": "address_claimed_by_other_person",
                "claimed_by": claimants,
                "address": addr,
            }
        # Explicit repair --person-id + --address: reclaim from prior wrong Person.
        for other in claimants:
            rev = _revoke_confirmed_email_contact(other, addr)
            if rev.get("revoked"):
                reclaimed_from.append(other)
        claimants = _address_claimed_by(addr)
        if claimants and person_id not in claimants:
            return {
                "accepted": False,
                "reason": "address_claimed_by_other_person",
                "claimed_by": claimants,
                "address": addr,
                "reclaim_attempted": reclaimed_from,
            }
    if person_id in claimants:
        if backfill:
            bf = backfill_email_person_ids(person_id, {addr})
        else:
            bf = {}
        return {
            "accepted": True,
            "reason": "already_confirmed_for_person",
            "address": addr,
            "backfill": bf,
        }

    like = f"%{addr}%"
    angle = f"%<{addr}>%"
    mailto = f"%[mailto:{addr}]%"
    name_likes = [f"%{f}%" for f in forms if " " in f] or (
        [f"%{forms[0]}%"] if forms else []
    )
    rows = []
    try:
        with connection() as conn:
            # Same structured-first + spam/trash skip as inventory — operator
            # attest must agree with probe on messy Takeout (LIMIT without
            # ORDER BY used to sample random body-adjacent / spam rows).
            rows = conn.execute(
                """
                SELECT id, payload_json
                FROM evidence
                WHERE evidence_kind = 'communication'
                  AND lower(coalesce(payload_json->>'evidence_channel', 'email'))
                      NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs')
                  AND lower(coalesce(payload_json->>'mailbox_skip',
                                     payload_json->>'skip_reason', ''))
                      NOT IN ('spam', 'trash')
                  AND (
                    lower(coalesce(payload_json->>'from', '')) = %s
                    OR lower(coalesce(payload_json->>'from', '')) LIKE %s
                    OR lower(coalesce(payload_json->>'from', '')) LIKE %s
                    OR lower(coalesce(payload_json->>'from', '')) LIKE %s
                    OR lower(coalesce((payload_json->'to')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'cc')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'bcc')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'from_parsed')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'to_parsed')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'cc_parsed')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'bcc_parsed')::text, '')) LIKE %s
                  )
                ORDER BY CASE
                  WHEN lower(coalesce(payload_json->>'from', '')) = %s
                    OR lower(coalesce(payload_json->>'from', '')) LIKE %s
                    OR lower(coalesce(payload_json->>'from', '')) LIKE %s
                    OR lower(coalesce((payload_json->'from_parsed')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'to')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'cc')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'bcc')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'to_parsed')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'cc_parsed')::text, '')) LIKE %s
                    OR lower(coalesce((payload_json->'bcc_parsed')::text, '')) LIKE %s
                  THEN 0
                  ELSE 1
                END,
                id
                LIMIT 5000
                """,
                (
                    addr,
                    angle,
                    mailto,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    addr,
                    angle,
                    mailto,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                ),
            ).fetchall()
    except Exception as exc:  # noqa: BLE001
        return {"accepted": False, "reason": "scan_error", "error": str(exc), "address": addr}

    display_names: dict[str, int] = {}
    evidence_ids: list[str] = []
    header_fields: set[str] = set()
    sample_raw_displays: list[str] = []
    for r in rows:
        raw = r.get("payload_json")
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        for rec in _header_records(payload):
            if rec["address"] != addr:
                continue
            header_fields.add(rec["header_field"])
            dn = rec.get("display_name") or ""
            if dn and len(sample_raw_displays) < 12:
                sample_raw_displays.append(dn)
            if _display_matches_person(dn, forms):
                display_names[dn] = int(display_names.get(dn) or 0) + 1
            # people[] is co-occurrence only — never a display used to confirm.
            # Header raw text may include "Peggy George <addr>"
            blob = " ".join(
                [
                    str(payload.get("from") or ""),
                    str(payload.get("to") or ""),
                    str(payload.get("cc") or ""),
                    str(payload.get("bcc") or ""),
                ]
            ).lower()
            for form in forms:
                if " " in form and form in blob:
                    display_names[form] = int(display_names.get(form) or 0) + 1
            eid = str(r.get("id") or "")
            if eid and eid not in evidence_ids:
                evidence_ids.append(eid)

    candidate = {
        "address": addr,
        "display_names": display_names,
        "occurrences": max(sum(display_names.values()), len(evidence_ids)),
        "evidence_ids": evidence_ids[:24],
        "header_fields": sorted(header_fields),
        "sample_raw_display_names": sample_raw_displays,
    }
    decision = corroborate_email_candidate(person_id, candidate, known_forms=forms)

    # Explicit repair --address: address present in headers + unclaimed + targeted
    # Person id is enough. Do not silently attach during Ask auto-expand.
    if (
        not decision.get("accepted")
        and operator_attested
        and len(rows) > 0
        and len(evidence_ids) > 0
    ):
        decision = {
            "address": addr,
            "accepted": True,
            "reason": "operator_attested_address_in_headers",
            "corroboration": [
                "operator_attested",
                f"rows_with_address:{len(rows)}",
                f"header_fields:{','.join(sorted(header_fields)) or 'none'}",
            ],
            "matched_display_name": next(iter(display_names), None)
            or (snap.get("display_name") if snap else None),
            "match_strength": "operator_attested",
            "prior_auto_reason": decision.get("reason"),
        }

    if decision.get("accepted") and persist:
        ensure_confirmed_email_contact(
            person_id,
            addr,
            provenance={
                "source": (
                    "comm_identity_operator_attested"
                    if decision.get("reason") == "operator_attested_address_in_headers"
                    else "comm_identity_known_address"
                ),
                "reason": decision.get("reason"),
                "corroboration": decision.get("corroboration"),
                "matched_display_name": decision.get("matched_display_name"),
                "evidence_ids_sample": evidence_ids[:8],
                "name_likes_checked": name_likes,
                "operator_attested": bool(operator_attested),
                "sample_raw_display_names": sample_raw_displays[:8],
            },
            note=(
                "Operator-attested known address present in communication headers"
                if decision.get("reason") == "operator_attested_address_in_headers"
                else "Known address corroborated via communication headers"
            ),
        )
    bf = {}
    if decision.get("accepted") and backfill:
        bf = backfill_email_person_ids(person_id, {addr})
    seeded_aliases: list[dict[str, Any]] = []
    if decision.get("accepted") and persist:
        # Seed header names like "Peg Legg" so future discovery ORs the alias.
        seeded_aliases = _seed_header_display_aliases(
            person_id,
            sample_raw_displays,
            known_forms=forms,
            address=addr,
        )
    hint = None
    if not decision.get("accepted") and len(rows) > 0:
        hint = (
            "Address exists in email headers but auto corroboration failed "
            f"({decision.get('reason')}). Headers may use a different full name "
            f"(e.g. Peg Legg vs Peggy George); samples={sample_raw_displays[:5]!r}. "
            "Teach that name as an alias on the Person, or re-run "
            "repair-email-identities --person-id <ID> --address <addr>."
        )
    elif not decision.get("accepted") and len(rows) == 0:
        hint = (
            "Address not found in From/To/CC headers of ingested email. "
            "Confirm the spelling and that the mbox containing it was ingested."
        )
    return {
        "accepted": bool(decision.get("accepted")),
        "address": addr,
        "candidate": candidate,
        "decision": decision,
        "rows_with_address": len(rows),
        "backfill": bf,
        "operator_attested": bool(operator_attested),
        "seeded_aliases": seeded_aliases,
        "reclaimed_from": reclaimed_from,
        "hint": hint,
    }



def explain_address_for_person(person_id: str, address: str) -> dict[str, Any]:
    """Diagnostic: why an address is/isn't supported for a Person (e.g. peggo417)."""
    snap = person_identity_snapshot(person_id)
    forms = snap.get("known_name_forms") or []
    addr = normalize_handle(address)
    candidates = discover_email_candidates_from_archive(person_id, known_forms=forms)
    match = next((c for c in candidates if c.get("address") == addr), None)
    known_attach = attach_known_email_if_corroborated(
        person_id, addr, persist=False, backfill=False, operator_attested=False
    )
    operator_probe = attach_known_email_if_corroborated(
        person_id, addr, persist=False, backfill=False, operator_attested=True
    )
    if match is None:
        match = {
            "address": addr,
            "display_names": {snap.get("display_name") or "": 0},
            "occurrences": 0,
            "evidence_ids": [],
            "header_fields": [],
            "match_strength": None,
        }
        decision = {
            "address": addr,
            "accepted": False,
            "reason": "address_not_found_in_header_scan_for_person_names",
            "corroboration": [],
        }
        if addr in {
            normalize_handle(str(c.get("value_text") or ""))
            for c in (snap.get("emails") or [])
        }:
            decision = {
                "address": addr,
                "accepted": True,
                "reason": "already_confirmed_for_person",
                "corroboration": ["existing_contact"],
            }
        elif known_attach.get("accepted"):
            decision = known_attach.get("decision") or decision
    else:
        decision = corroborate_email_candidate(person_id, match, known_forms=forms)
    next_step = None
    rows_n = int(known_attach.get("rows_with_address") or 0)
    if rows_n > 0 and not known_attach.get("accepted"):
        next_step = (
            "python -m memorybox repair-email-identities "
            f"--person-id {person_id} --address {addr}"
        )
    elif rows_n == 0 and not known_attach.get("accepted"):
        next_step = (
            "Address absent from ingested email headers — check spelling / mbox ingest"
        )
    return {
        "person": snap,
        "address": addr,
        "candidate": match,
        "decision": decision,
        "known_address_probe": known_attach,
        "operator_attested_probe": operator_probe,
        "hint": (known_attach.get("hint") or operator_probe.get("hint")),
        "next_step_if_blocked": next_step,
    }


def diagnose_email_retrieve_gap(
    person_ids: set[str] | list[str],
    *,
    address_hint: str | None = None,
) -> dict[str, Any]:
    """Explain why Person-scoped email retrieve may be empty (FlightSim diag).

    Prefer trusted-for-retrieval contacts — no hardcoded person address.
    Optional address_hint only when the operator wants to probe a specific spelling.
    """
    from memorybox.person.trusted_identity import trusted_emails_for_people

    ids = [str(p) for p in person_ids if str(p).strip()]
    trusted = trusted_emails_for_people(ids)
    out: dict[str, Any] = {
        "person_ids": ids,
        "address_hint": normalize_handle(address_hint) if address_hint else None,
        "snapshots": [],
        "confirmed_emails": [],
        "trusted_emails": sorted(trusted),
        "expand_preview": None,
        "address_hint_explanation": None,
        "likely_blocker": None,
    }
    observed_emails: set[str] = set()
    for pid in ids:
        snap = person_identity_snapshot(pid)
        emails = [
            normalize_handle(str(c.get("value_text") or ""))
            for c in (snap.get("emails") or [])
        ]
        emails = [e for e in emails if e and "@" in e]
        observed_emails.update(emails)
        out["snapshots"].append(
            {
                "person_id": pid,
                "display_name": snap.get("display_name"),
                "known_name_forms": snap.get("known_name_forms"),
                "contact_emails": emails,
                "trusted_emails": sorted(trusted_emails_for_people({pid})),
                "alias_count": len(snap.get("aliases") or []),
            }
        )
    out["observed_contact_emails"] = sorted(observed_emails)
    out["confirmed_emails"] = sorted(trusted)

    # If no explicit hint, probe the first confirmed People email (source of truth).
    hint = out.get("address_hint") or (out["confirmed_emails"][0] if out["confirmed_emails"] else None)
    out["address_hint"] = hint
    out["pipeline"] = ["discover", "resolve", "retrieve"]

    if ids:
        try:
            expanded = expand_emails_for_retrieve(ids)
            out["expand_preview"] = {
                "addresses": sorted(expanded.get("addresses") or []),
                "expansion_accepted": (expanded.get("expansion") or {}).get("accepted"),
                "expansion_rejected_sample": (
                    (expanded.get("expansion") or {}).get("rejected") or []
                )[:8],
                "emails_by_person": (expanded.get("expansion") or {}).get(
                    "emails_by_person"
                ),
                "address_centric_resolve": (expanded.get("expansion") or {}).get(
                    "address_centric_resolve"
                ),
                "backfill_sample": [
                    (r.get("backfill") if isinstance(r, dict) else None)
                    for r in ((expanded.get("expansion") or {}).get("rounds") or [])[:3]
                ],
            }
            trusted.update(expanded.get("addresses") or [])
            out["trusted_emails"] = sorted(trusted)
            out["confirmed_emails"] = sorted(trusted)
            if not hint and out["confirmed_emails"]:
                hint = out["confirmed_emails"][0]
                out["address_hint"] = hint
        except Exception as exc:  # noqa: BLE001
            out["expand_preview"] = {"error": str(exc)}

    # Inventory every confirmed address (structured vs quoted display names).
    # Also inventory ledger addresses that match Person forms even before confirm —
    # so FlightSim diag shows peggo417 after probe when attach has not yet run.
    inventories: list[dict[str, Any]] = []
    try:
        from memorybox.person.comm_address_index import (
            find_ledger_addresses_for_person_forms,
            inventory_email_address,
        )

        for addr in out["confirmed_emails"][:8]:
            inventories.append(inventory_email_address(addr, include_quoted_body=True))
        if hint and hint not in out["confirmed_emails"]:
            inventories.append(inventory_email_address(hint, include_quoted_body=True))
        if not out["confirmed_emails"]:
            forms: list[str] = []
            for snap in out["snapshots"]:
                forms.extend(snap.get("known_name_forms") or [])
            for cand in find_ledger_addresses_for_person_forms(forms)[:4]:
                addr = str(cand.get("address") or "")
                if addr and addr not in {normalize_handle(a) for a in out["confirmed_emails"]}:
                    inventories.append(
                        inventory_email_address(addr, include_quoted_body=True)
                    )
                    if not hint:
                        hint = addr
                        out["address_hint"] = addr
    except Exception as exc:  # noqa: BLE001
        inventories = [{"error": str(exc)}]
    out["address_inventories"] = inventories

    if hint and ids:
        try:
            out["address_hint_explanation"] = explain_address_for_person(ids[0], hint)
        except Exception as exc:  # noqa: BLE001
            out["address_hint_explanation"] = {"error": str(exc)}

    rows = int(
        ((out.get("address_hint_explanation") or {}).get("known_address_probe") or {}).get(
            "rows_with_address"
        )
        or 0
    )
    # Prefer structured inventory occurrence count when available
    for inv in inventories:
        if inv.get("address") == hint:
            rows = max(
                rows,
                int((inv.get("structured_header") or {}).get("occurrence_count") or 0),
            )
    if not ids:
        out["likely_blocker"] = "no_person_ids_on_plan"
    elif not out["confirmed_emails"]:
        # Surface nickname fail-closed reasons from address-centric resolve when present.
        nick_rejects: list[str] = []
        for rep in ((out.get("expand_preview") or {}).get("address_centric_resolve") or []):
            if not isinstance(rep, dict):
                continue
            for entry in rep.get("rejected") or []:
                dec = (entry.get("decision") if isinstance(entry, dict) else None) or {}
                reason = str(dec.get("reason") or "")
                if "nickname" in reason:
                    nick_rejects.append(reason)
        if nick_rejects:
            out["likely_blocker"] = (
                "nickname_attach_fail_closed — "
                + nick_rejects[0]
                + "; need same-address full/alias observation, seeded Peg Legg alias, "
                "or --repair-address <addr>"
            )
        else:
            out["likely_blocker"] = (
                "no_confirmed_email_on_people — address discovery/resolve did not attach; "
                "run probe-email-address --address <addr> and check structured display names"
            )
    elif out["confirmed_emails"] and rows == 0 and hint:
        out["likely_blocker"] = (
            f"people_has_{hint}_but_not_in_ingested_headers — confirm the "
            "People contact spelling matches From/To/CC in the archive "
            "(e.g. peggo417 vs peggo01417)"
        )
    elif out["confirmed_emails"] and rows > 0:
        out["likely_blocker"] = None
        out["identity_closure_ok"] = True
    else:
        out["likely_blocker"] = "unknown"
    return out


def repair_email_identity_contacts(
    person_id: str | None = None,
    *,
    force_rediscover: bool = False,
    known_address: str | None = None,
) -> dict[str, Any]:
    """Discover/persist corroborated email contacts for People missing them.

    When person_id is set, expand that Person only. Otherwise expand live People
    that have a multi-token display name and zero confirmed emails.
    Optional known_address (e.g. peggo417@hotmail.com) is corroborated via headers.
    """
    ids: list[str] = []
    if person_id:
        ids = [str(person_id)]
    else:
        try:
            with connection() as conn:
                rows = conn.execute(
                    """
                    SELECT p.id, p.display_name
                    FROM people p
                    WHERE p.status IN ('confirmed', 'unresolved')
                      AND position(' ' in trim(p.display_name)) > 0
                      AND NOT EXISTS (
                        SELECT 1 FROM person_contact_points c
                        WHERE c.person_id = p.id
                          AND c.contact_kind = 'email'
                          AND c.retrieval_trust = 'trusted'
                      )
                    ORDER BY p.display_name
                    LIMIT 500
                    """
                ).fetchall()
                ids = [str(r["id"]) for r in rows]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "person_ids": []}

    known_results = []
    address_reports: list[dict[str, Any]] = []
    # Address-centric path first (ledger + archive discover → resolve → backfill).
    try:
        from memorybox.person.comm_address_index import (
            resolve_and_attach_addresses_for_person,
        )

        for pid in ids:
            address_reports.append(
                resolve_and_attach_addresses_for_person(
                    pid, persist=True, backfill=True, inventory_attached=True
                )
            )
    except Exception as exc:  # noqa: BLE001
        address_reports.append({"error": str(exc)})

    if known_address and ids:
        if not person_id:
            return {
                "ok": False,
                "error": (
                    "--address requires --person-id (operator attestation must "
                    "target one Person; will not attach across the people list)"
                ),
                "person_ids": ids,
                "address_centric_resolve": address_reports,
            }
        # Explicit --address + --person-id is operator attestation.
        # Auto Ask expand never sets operator_attested.
        known_results.append(
            attach_known_email_if_corroborated(
                ids[0],
                known_address,
                persist=True,
                backfill=True,
                operator_attested=True,
            )
        )

    if force_rediscover:
        reports = []
        for pid in ids:
            snap = person_identity_snapshot(pid)
            forms = snap.get("known_name_forms") or []
            cands = discover_email_candidates_from_archive(pid, known_forms=forms)
            accepted = []
            for cand in cands:
                decision = corroborate_email_candidate(pid, cand, known_forms=forms)
                if decision.get("accepted") and decision.get("reason") != "already_confirmed_for_person":
                    ensure_confirmed_email_contact(
                        pid,
                        str(decision.get("address")),
                        provenance={
                            "source": "comm_identity_repair",
                            "reason": decision.get("reason"),
                            "corroboration": decision.get("corroboration"),
                            "matched_display_name": decision.get("matched_display_name"),
                        },
                    )
                    accepted.append(decision)
            emails = {
                normalize_handle(str(c.get("value_text") or ""))
                for c in (person_identity_snapshot(pid).get("emails") or [])
            }
            emails = {e for e in emails if e and "@" in e}
            bf = backfill_email_person_ids(pid, emails) if emails else {}
            reports.append(
                {
                    "person_id": pid,
                    "accepted": accepted,
                    "emails": sorted(emails),
                    "backfill": bf,
                }
            )
        return {
            "ok": True,
            "mode": "force_rediscover",
            "results": reports,
            "known_address_results": known_results,
            "address_centric_resolve": address_reports,
        }

    expansion = expand_person_communication_identities(
        ids, persist=True, backfill=True, discover=True
    )
    return {
        "ok": True,
        "mode": "expand",
        "person_ids": ids,
        "expansion": expansion,
        "known_address_results": known_results,
        "address_centric_resolve": address_reports,
    }
