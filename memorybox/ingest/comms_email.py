"""Email mbox → Source + Evidence (evidence_kind=communication)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.ingest import store as store
from memorybox.ingest.sms_attach_cache import put_media_object
from memorybox.person.phone_map import (
    _index_confirmed_handles,
    ensure_confirmed_phone_contact,
    normalize_handle,
    resolve_handles,
)
from memorybox.providers.email_read.dto import EmailMessageDto, EmailSourceRef
from memorybox.providers.email_read.mbox import MboxEmailReadProvider
from memorybox.providers.email_read.mbox_parse import (
    PARSER_VERSION,
    default_email_source_path,
    inspect_mbox,
)

OWNER_ENV = "MEMORYBOX_OWNER_EMAIL"


def email_cache_root() -> Path:
    raw = (os.environ.get("MEMORYBOX_EMAIL_ATTACH_CACHE") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "working" / "email-attachments"


def owner_emails() -> set[str]:
    raw = (os.environ.get(OWNER_ENV) or "").strip()
    out: set[str] = set()
    if raw:
        for part in raw.split(","):
            n = normalize_handle(part)
            if n and "@" in n:
                out.add(n)
    return out


def inspect_default_or_uri(uri: str | None = None, *, limit: int | None = None) -> dict[str, Any]:
    from memorybox.ingest.sources_paths import email_source_candidates

    if uri:
        path = Path(uri)
        if not path.exists():
            return {
                "ok": False,
                "error": "not_found",
                "path": str(path),
                "note": (
                    "That --uri does not exist. Missing source is not zero messages."
                ),
            }
        return inspect_mbox(path, limit=limit)
    path = default_email_source_path()
    if path is None:
        tried = [str(p) for p in email_source_candidates()]
        return {
            "ok": False,
            "error": "not_found",
            "tried": tried,
            "note": (
                "No staged mbox/Maildir found. Default is "
                r"P:\photos\memorybox\sources\email\all mail including spam and trash-002.mbox. "
                "Pass --uri, or set MEMORYBOX_MBOX_URI / MEMORYBOX_SOURCES_ROOT. "
                "Missing source is not zero messages."
            ),
        }
    return inspect_mbox(path, limit=limit)


def _people_handles(msg: EmailMessageDto) -> list[str]:
    addrs: list[str] = []
    for rec in (*msg.from_parsed, *msg.to_parsed, *msg.cc_parsed):
        addrs.append(rec.address)
    return addrs


def _direction(msg: EmailMessageDto, owners: set[str]) -> tuple[str, bool]:
    from_norm = {a.normalized for a in msg.from_parsed}
    if owners and from_norm & owners:
        return "outbound", True
    return "inbound", False


def _payload_from_dto(
    msg: EmailMessageDto,
    *,
    job_id: UUID,
    handle_index: dict[str, list[str]] | None,
    owners: set[str],
) -> dict[str, Any]:
    handles = _people_handles(msg)
    resolved = resolve_handles(handles, index=handle_index)
    person_ids = [m["person_id"] for m in resolved["mapped"]]
    direction, from_owner = _direction(msg, owners)
    people_labels: list[str] = []
    for rec in (*msg.from_parsed, *msg.to_parsed, *msg.cc_parsed):
        label = rec.display_name or rec.address
        if label not in people_labels:
            people_labels.append(label)
    attachments = [
        {
            "filename": p.filename,
            "mime_type": p.mime_type,
            "byte_size": p.byte_size,
            "content_hash": p.content_hash,
            "disposition": p.disposition,
            "content_id": p.content_id,
            "kind": p.kind,
            "promoted_to_immich": False,
            "standalone_explore_media": False,
            "artifact_id": None,
            "bytes_ingested": False,
        }
        for p in msg.attachments
    ]
    return {
        "evidence_channel": "email",
        "message_id": msg.external_id,
        "rfc_message_id": msg.rfc_message_id,
        "subject": msg.subject,
        "from": msg.from_addr,
        "from_raw": msg.from_addr,
        "from_parsed": [
            {
                "raw": a.raw,
                "display_name": a.display_name,
                "address": a.address,
                "normalized": a.normalized,
            }
            for a in msg.from_parsed
        ],
        "to": list(msg.to_addrs),
        "to_parsed": [
            {
                "raw": a.raw,
                "display_name": a.display_name,
                "address": a.address,
                "normalized": a.normalized,
            }
            for a in msg.to_parsed
        ],
        "cc": list(msg.cc_addrs),
        "cc_parsed": [
            {
                "raw": a.raw,
                "display_name": a.display_name,
                "address": a.address,
                "normalized": a.normalized,
            }
            for a in msg.cc_parsed
        ],
        "bcc": [],
        "sent_at": msg.date_utc.isoformat() if msg.date_utc else None,
        "body_text": msg.body_text or "",
        "body_html": msg.body_html or "",
        "html_only": bool(msg.html_only),
        "direction": direction,
        "from_owner": from_owner,
        "people": people_labels,
        "person_ids": person_ids,
        "identity_resolution": resolved,
        "source_locator": msg.source_uri
        + (f"#mid={msg.external_id}" if msg.external_id else f"#hash={msg.content_hash}"),
        "source_metadata": {
            "headers": {k: v for k, v in msg.header_provenance},
        },
        "header_provenance": {k: v for k, v in msg.header_provenance},
        "provenance": {
            "provider_key": msg.provider_key,
            "ingest_job_id": str(job_id),
            "parser_version": PARSER_VERSION,
            "authority": "system",
            "original_untouched": True,
        },
        "content_hash": msg.content_hash,
        "in_reply_to": msg.in_reply_to,
        "references": msg.references,
        "in_reply_to_ids": list(msg.in_reply_to_ids),
        "reference_ids": list(msg.reference_ids),
        "vendor_thread_id": msg.vendor_thread_id,
        "thread_id": msg.thread_id,
        "thread_status": msg.thread_status,
        "thread_completeness": "n/a" if msg.thread_status == "unthreaded" else "pending",
        "attachments": attachments,
        "is_artifact": False,
        "gmail_labels": list(msg.gmail_labels),
        "mailbox_skip": msg.mailbox_skip,
    }


def _store_attachments(
    msg: EmailMessageDto,
    payload: dict[str, Any],
    *,
    source_id: UUID,
    conn: Any,
) -> int:
    stored = 0
    atts = payload.get("attachments") or []
    for part, att in zip(msg.attachments, atts):
        if not isinstance(att, dict):
            continue
        if not part.data:
            att["bytes_ingested"] = False
            att["bytes_missing"] = True
            continue
        rec = put_media_object(
            part.data,
            part.filename,
            source_id=source_id,
            conn=conn,
            mime_type=part.mime_type,
            origin="email_ingest",
            store_root=email_cache_root(),
        )
        if rec is None:
            att["bytes_ingested"] = False
            att["bytes_missing"] = True
            continue
        att["media_object_id"] = rec["media_object_id"]
        att["bytes_ingested"] = True
        att["bytes_present"] = True
        att["byte_size"] = rec.get("byte_size") or part.byte_size
        att["content_hash"] = rec.get("content_hash") or part.content_hash
        att["source_relationship"] = "email_mime_part"
        stored += 1
    payload["attachments"] = atts
    return stored


def _persist_unique_email_contacts(resolved: dict[str, Any], conn: Any) -> None:
    for m in resolved.get("mapped") or []:
        if not isinstance(m, dict):
            continue
        handle = str(m.get("normalized") or m.get("handle") or "")
        pid = str(m.get("person_id") or "")
        if "@" not in handle or not pid:
            continue
        ensure_confirmed_phone_contact(
            pid,
            handle,
            conn=conn,
            provenance={"source": "email_auto_map", "handle": handle},
        )


def _apply_thread_completeness(source_id: UUID, conn: Any) -> dict[str, int]:
    rows = store.list_evidence_for_source(source_id, conn=conn)
    known: set[str] = set()
    payloads: list[tuple[Any, dict[str, Any]]] = []
    for row in rows:
        raw = row.get("payload_json")
        payload = raw if isinstance(raw, dict) else {}
        if str(payload.get("evidence_channel") or "").lower() != "email":
            continue
        mid = str(payload.get("rfc_message_id") or payload.get("message_id") or "").strip()
        if mid:
            known.add(mid)
        payloads.append((row["id"], payload))
    stats = {"complete": 0, "incomplete": 0, "unthreaded": 0, "vendor": 0}
    for eid, payload in payloads:
        status = str(payload.get("thread_status") or "unthreaded")
        refs = [
            str(x)
            for x in (
                list(payload.get("in_reply_to_ids") or [])
                + list(payload.get("reference_ids") or [])
            )
            if str(x)
        ]
        if status == "unthreaded":
            payload["thread_completeness"] = "n/a"
            stats["unthreaded"] += 1
        elif status in {"vendor", "vendor+rfc"}:
            payload["thread_completeness"] = "vendor"
            if status == "vendor+rfc":
                payload["thread_completeness"] = (
                    "complete" if any(r in known for r in refs) else "incomplete"
                )
            stats["vendor"] += 1
            if payload["thread_completeness"] == "incomplete":
                stats["incomplete"] += 1
            elif payload["thread_completeness"] == "complete":
                stats["complete"] += 1
        elif refs and any(r in known for r in refs):
            payload["thread_completeness"] = "complete"
            stats["complete"] += 1
        elif refs:
            payload["thread_completeness"] = "incomplete"
            stats["incomplete"] += 1
        else:
            payload["thread_completeness"] = "incomplete"
            stats["incomplete"] += 1
        store.update_evidence_payload(eid, payload, conn=conn)
    return stats


def ingest_mbox(
    mbox_uri: str,
    *,
    limit: int | None = None,
    label: str | None = None,
    include_spam_trash: bool = False,
) -> dict[str, Any]:
    path = Path(mbox_uri)
    job_id = store.start_job(
        "ingest_email",
        message="ingest mbox locator configured",
        payload={"source_kind": "mbox_import", "parser_version": PARSER_VERSION},
    )
    try:
        if not path.exists():
            raise FileNotFoundError(f"mbox not found: {path}")
        _size = path.stat().st_size if path.is_file() else None
        source_id = store.upsert_source(
            source_kind="mbox_import",
            label=label or f"mbox:{path.name}",
            uri=str(path.resolve()),
            metadata={
                "fixture_or_smoke": True,
                "byte_size": _size,
                "original_untouched": True,
                "parser_version": PARSER_VERSION,
            },
        )
        provider = MboxEmailReadProvider()
        inserted = 0
        skipped = 0
        skipped_spam = 0
        skipped_trash = 0
        skipped_error = 0
        error_samples: list[str] = []
        upgraded = 0
        attachments_stored = 0
        evidence_ids: list[str] = []
        owners = owner_emails()
        with connection() as conn:
            handle_index = _index_confirmed_handles(conn)
            existing_hashes = store.hashes_for_source(source_id, conn=conn)
            for msg in provider.iter_messages(
                EmailSourceRef(provider_key="mbox", uri=str(path)),
                limit=limit,
                skip_spam_trash=not include_spam_trash,
            ):
                try:
                    existing = existing_hashes.get(msg.content_hash)
                    payload = _payload_from_dto(
                        msg, job_id=job_id, handle_index=handle_index, owners=owners
                    )
                    attachments_stored += _store_attachments(
                        msg, payload, source_id=source_id, conn=conn
                    )
                    _persist_unique_email_contacts(
                        payload.get("identity_resolution") or {}, conn
                    )
                    if existing:
                        row = store.get_evidence(existing, conn=conn)
                        old_raw = (row or {}).get("payload_json")
                        old = old_raw if isinstance(old_raw, dict) else {}
                        old_ver = str(
                            (old.get("provenance") or {}).get("parser_version") or ""
                        )
                        if old_ver != PARSER_VERSION:
                            store.update_evidence_payload(existing, payload, conn=conn)
                            upgraded += 1
                        else:
                            skipped += 1
                        evidence_ids.append(str(existing))
                        conn.commit()
                        continue
                    eid = store.insert_evidence(
                        evidence_kind="communication",
                        source_id=source_id,
                        summary=(msg.subject or "(no subject)")[:500],
                        payload=payload,
                        conn=conn,
                    )
                    existing_hashes[msg.content_hash] = eid
                    inserted += 1
                    evidence_ids.append(str(eid))
                    conn.commit()
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    skipped_error += 1
                    if len(error_samples) < 8:
                        loc = msg.rfc_message_id or msg.subject or msg.content_hash
                        error_samples.append(f"{str(loc)[:80]}: {exc}"[:400])
            skipped_spam = int(getattr(provider, "skipped_spam", 0) or 0)
            skipped_trash = int(getattr(provider, "skipped_trash", 0) or 0)
            thread_stats = _apply_thread_completeness(source_id, conn)
        store.finish_job(
            job_id,
            status="done",
            message=(
                f"inserted={inserted} skipped={skipped} upgraded={upgraded} "
                f"skipped_spam={skipped_spam} skipped_trash={skipped_trash} "
                f"skipped_error={skipped_error} "
                f"attachments_stored={attachments_stored}"
            ),
        )
        return {
            "ok": True,
            "job_id": str(job_id),
            "source_id": str(source_id),
            "inserted": inserted,
            "skipped": skipped,
            "skipped_spam": skipped_spam,
            "skipped_trash": skipped_trash,
            "skipped_error": skipped_error,
            "error_samples": error_samples,
            "include_spam_trash": include_spam_trash,
            "upgraded": upgraded,
            "attachments_stored": attachments_stored,
            "thread_stats": thread_stats,
            "evidence_ids": evidence_ids,
            "mbox_bytes": _size,
            "parser_version": PARSER_VERSION,
            "original_untouched": True,
        }
    except Exception as exc:  # noqa: BLE001
        store.finish_job(
            job_id, status="error", message="ingest failed", error_message=str(exc)
        )
        return {"ok": False, "job_id": str(job_id), "error": str(exc)}
