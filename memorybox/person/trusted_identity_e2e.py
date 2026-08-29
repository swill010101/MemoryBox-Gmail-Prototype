"""Local Postgres prove: retrieve uses trusted emails only (no FlightSim)."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.person.phone_map import normalize_handle

_KIND = "communication"
_PREFIX = "ffffffff-aaaa-4aa1-8aa1-"


def _eid(n: int) -> UUID:
    return UUID(f"{_PREFIX}{n:012d}")


def _cleanup(person_id: str | None, addrs: list[str]) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM evidence WHERE id::text LIKE %s", (_PREFIX + "%",))
        for a in addrs:
            n = normalize_handle(a)
            conn.execute(
                "DELETE FROM person_contact_points WHERE lower(value_text) = %s",
                (n,),
            )
            conn.execute(
                "DELETE FROM communication_identities WHERE address_normalized = %s",
                (n,),
            )
        if person_id:
            conn.execute("DELETE FROM person_contact_points WHERE person_id = %s::uuid", (person_id,))
            conn.execute("DELETE FROM people WHERE id = %s::uuid", (person_id,))


def _email_payload(addr: str, display: str, subject: str, sent_at: str) -> dict[str, Any]:
    return {
        "evidence_channel": "email",
        "from": f"{display} <{addr}>",
        "to": ["Owner <owner@example.test>"],
        "cc": [],
        "bcc": [],
        "from_parsed": [
            {"display_name": display, "address": addr, "normalized": addr}
        ],
        "to_parsed": [
            {
                "display_name": "Owner",
                "address": "owner@example.test",
                "normalized": "owner@example.test",
            }
        ],
        "people": [display, "Owner"],
        "subject": subject,
        "body_text": f"body {subject}",
        "sent_at": sent_at,
        "person_ids": [],
    }


def run_trusted_identity_db_e2e() -> dict[str, Any]:
    from memorybox.ask.i11a.trusted_fev2_chunking import compare_chunked_vs_unchunked
    from memorybox.ask.i11a.trusted_full_evidence_v2 import freeze_trusted_full_evidence_v2
    from memorybox.ask.retrieve import search_email_messages
    from memorybox.person import resolve_person_by_name
    from memorybox.person.comm_identity import (
        ensure_confirmed_email_contact,
        expand_emails_for_retrieve,
    )
    from memorybox.person.trusted_identity import (
        reclassify_person_email_trust,
        report_person_identity_and_retrieve,
    )
    from memorybox.planner import QueryPlan
    from memorybox.profile.facts import add_contact
    from pathlib import Path
    import tempfile

    display = f"Trusted Probe {uuid4().hex[:8]}"
    trusted_addr = f"trusted.{uuid4().hex[:8]}@example.test"
    noise_addr = f"noise.{uuid4().hex[:8]}@example.test"
    promote_addr = f"promote.{uuid4().hex[:8]}@example.test"
    person_id = None
    problems: list[str] = []
    checks: list[str] = []

    def _ok(name: str, cond: bool, detail: Any = None) -> None:
        checks.append(name)
        if not cond:
            problems.append(f"{name}: {detail}")

    try:
        resolved = resolve_person_by_name(display, create_if_missing=True, confirm=True)
        person_id = resolved.person_id
        add_contact(
            person_id,
            contact_kind="email",
            value_text=trusted_addr,
            actor_key="owner",
            provenance={"source": "person_profile"},
        )
        ensure_confirmed_email_contact(
            person_id,
            noise_addr,
            provenance={"source": "comm_identity_expand"},
            note="auto-expand noise",
        )
        rec = reclassify_person_email_trust(person_id)
        trusted = {str(x.get("address")) for x in rec.get("trusted") or []}
        _ok("owner_profile_trusted", trusted_addr in trusted, trusted)
        _ok("auto_expand_not_trusted", noise_addr not in trusted, rec.get("demoted"))

        ensure_confirmed_email_contact(
            person_id,
            trusted_addr,
            provenance={"source": "comm_identity_expand"},
            note="auto-expand must not clobber owner profile contact",
        )
        rec_keep = reclassify_person_email_trust(person_id)
        trusted_keep = {str(x.get("address")) for x in rec_keep.get("trusted") or []}
        _ok(
            "owner_profile_survives_auto_expand_stamp",
            trusted_addr in trusted_keep,
            rec_keep.get("demoted"),
        )

        with connection() as conn:
            for i, (addr, dn) in enumerate(
                (
                    (trusted_addr, "Trusted Person"),
                    (trusted_addr, "Trusted Person"),
                    (trusted_addr, "Trusted Person"),
                    (noise_addr, "Noise Mailbox"),
                    (noise_addr, "Noise Mailbox"),
                ),
                start=1,
            ):
                payload = _email_payload(
                    addr, dn, f"msg {i}", f"2021-01-{i:02d}T12:00:00Z"
                )
                conn.execute(
                    """
                    INSERT INTO evidence (id, evidence_kind, summary, payload_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (_eid(i), _KIND, payload["subject"], json.dumps(payload)),
                )

        expanded = expand_emails_for_retrieve({person_id})
        addrs = {normalize_handle(a) for a in (expanded.get("addresses") or set())}
        _ok("expand_only_trusted", addrs == {trusted_addr}, sorted(addrs))
        _ok("expand_excludes_noise", noise_addr not in addrs, sorted(addrs))

        ensure_confirmed_email_contact(
            person_id,
            promote_addr,
            provenance={"source": "comm_identity_expand"},
            note="auto-expand first",
        )
        add_contact(
            person_id,
            contact_kind="email",
            value_text=promote_addr,
            actor_key="owner",
            provenance={"source": "person_profile"},
        )
        rec_promote = reclassify_person_email_trust(person_id)
        trusted_promote = {str(x.get("address")) for x in rec_promote.get("trusted") or []}
        _ok(
            "owner_add_promotes_existing_auto_expand",
            promote_addr in trusted_promote,
            rec_promote,
        )

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
        hits = search_email_messages(plan, limit=10_000)
        hit_ids = {str(h.evidence_id) for h in hits}
        want = {str(_eid(1)), str(_eid(2)), str(_eid(3))}
        noise_ids = {str(_eid(4)), str(_eid(5))}
        _ok("retrieve_has_trusted_mail", want <= hit_ids, sorted(hit_ids))
        _ok("retrieve_excludes_untrusted_mail", not (hit_ids & noise_ids), sorted(hit_ids))

        report = report_person_identity_and_retrieve(person_id)
        _ok(
            "report_unsupported_zero",
            not report.get("unsupported_retrieve_addresses")
            and not report.get("unsupported_retrieve_hit_count"),
            report.get("unsupported_retrieve_hits"),
        )
        only_via = report.get("unique_only_via_trusted_address") or {}
        _ok(
            "report_unique_only_via_trusted",
            int(only_via.get(trusted_addr) or 0) == 3,
            only_via,
        )

        tmp = Path(tempfile.mkdtemp(prefix="fev2-"))
        freeze = freeze_trusted_full_evidence_v2(
            person_id=person_id,
            ask="tell me about this person",
            out_dir=tmp,
        )
        complete = freeze_trusted_full_evidence_v2(
            person_id=person_id,
            ask="tell me about this person",
            out_dir=tmp,
            complete_trusted=True,
        )
        _ok("complete_trusted_freeze_ok", bool(complete.get("ok")), complete.get("error"))
        if complete.get("fixture_path"):
            from memorybox.ask.i11a.trusted_fev2_chunking import (
                compare_chunked_vs_unchunked as _cmp2,
            )

            big = _cmp2(complete["fixture_path"])
            _ok("larger_trusted_set_chunk_structure_ok", bool(big.get("ok")), big)
        _ok("freeze_ok", bool(freeze.get("ok")), freeze.get("error"))
        _ok(
            "freeze_email_ids",
            bool(freeze.get("email_evidence_ids")),
            freeze.get("email_evidence_ids"),
        )
        ctx = (freeze.get("fixture") or {}).get("person_context") or {}
        focals = list(ctx.get("focal_subjects") or [])
        card0 = focals[0] if focals else {}
        slim_addrs = " ".join(
            str(r.get("value_text") or "")
            for r in (card0.get("communication_identities") or [])
            if isinstance(r, dict)
        )
        _ok(
            "freeze_slim_includes_trusted_email",
            trusted_addr in slim_addrs,
            slim_addrs,
        )
        paste = str((freeze.get("fixture") or {}).get("user_message") or "")
        _ok("freeze_paste_includes_trusted_email", trusted_addr in paste, paste[:240])
        from memorybox.ask.i11a.trusted_full_evidence_v2 import validate_fev2_document

        email_ids = {str(x) for x in (freeze.get("email_evidence_ids") or []) if x}
        allowed = set(email_ids)
        for it in (freeze.get("fixture") or {}).get("items") or []:
            for key in ("evidence_id", "item_id", "id"):
                if it.get(key):
                    allowed.add(str(it.get(key)))
        grounded = {
            "episodes": [
                {
                    "title": "Trusted mail",
                    "when": "2021-01",
                    "summary": "mail",
                    "evidence_ids": sorted(email_ids)[:1],
                }
            ],
            "claims": [
                {
                    "text": "Person used the trusted address",
                    "evidence_ids": sorted(email_ids)[:1],
                }
            ],
            "relationships": [],
        }
        ground = validate_fev2_document(
            grounded, allowed_ids=allowed, email_evidence_ids=email_ids
        )
        _ok("synthetic_grounding_requires_email_ids", bool(ground.get("ok")), ground)
        if freeze.get("fixture_path"):
            chunk = compare_chunked_vs_unchunked(freeze["fixture_path"])
            _ok("chunk_structure_ok", bool(chunk.get("ok")), chunk)
        else:
            _ok("chunk_structure_ok", False, "no fixture")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"e2e_exception: {type(exc).__name__}:{exc}")
    finally:
        _cleanup(person_id, [trusted_addr, noise_addr, promote_addr])

    return {
        "ok": not problems,
        "prove": "trusted_identity_db_e2e",
        "checks": checks,
        "problems": problems,
        "person_display": display,
    }
