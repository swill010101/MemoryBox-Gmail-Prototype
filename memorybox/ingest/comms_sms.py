"""SMS / iMessage / MMS export → Source + Evidence (evidence_kind=communication)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.ingest import store as store
from memorybox.ingest.sms_attach_cache import (
    media_object_path,
    put_media_object,
    sms_folder_has_attachment_bytes,
)
from memorybox.ingest.sms_parse import (
    PARSER_VERSION,
    SmsMessage,
    inspect_sms_export,
    iter_sms_messages,
)
from memorybox.person.phone_map import (
    _index_confirmed_handles,
    ensure_confirmed_phone_contact,
    resolve_handles,
)


def default_sms_export_path() -> Path | None:
    env = (
        os.environ.get("MEMORYBOX_SMS_URI")
        or os.environ.get("MEMORYBOX_SMOKE_SMS_URI")
        or ""
    ).strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    roots: list[Path] = []
    src = (os.environ.get("MEMORYBOX_SOURCES_ROOT") or "").strip()
    if src:
        roots.append(Path(src) / "sms")
    roots.append(Path(r"\\media-server\photos\MemoryBox\Sources\sms"))
    named = "Messages - 1085 chat sessions.csv"
    for d in roots:
        hit = d / named
        if hit.is_file():
            return hit
        try:
            if d.is_dir():
                csvs = sorted(d.glob("*.csv"))
                if csvs:
                    return csvs[0]
        except OSError:
            continue
    return None


def _payload(
    msg: SmsMessage,
    *,
    job_id: UUID,
    source_uri: str,
    ingested_at: str,
    handle_index: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    handles = [msg.sender_handle, *msg.recipients, *msg.participants]
    resolved = resolve_handles(handles, index=handle_index)
    person_ids = [m["person_id"] for m in resolved["mapped"]]
    return {
        "evidence_channel": msg.service or "text",
        "service": msg.service,
        "message_id": msg.message_id,
        "body_text": msg.body_text,
        "subject": msg.subject,
        "sent_at": msg.sent_at,
        "delivered_at": msg.delivered_at,
        "read_at": msg.read_at,
        "edited_at": msg.edited_at,
        "deleted_at": msg.deleted_at,
        "direction": msg.direction,
        "from_owner": msg.from_owner,
        "sender_handle": msg.sender_handle,
        "sender_name": msg.sender_name,
        "recipients": list(msg.recipients),
        "participants": list(msg.participants),
        "thread_id": msg.thread_id,
        "group_name": msg.group_name or None,
        "group_participants": list(msg.participants) if msg.group_name or (
            msg.thread_id and len(msg.participants) > 2
        ) else None,
        "status": msg.status,
        "reply_to": msg.reply_to or None,
        "tapback": msg.tapback or None,
        "unsend": msg.unsend or None,
        "attachments": list(msg.attachments),
        "latitude": msg.latitude or None,
        "longitude": msg.longitude or None,
        "shared_location": msg.shared_location or None,
        "person_ids": person_ids,
        "identity_resolution": resolved,
        "source_locator": f"{source_uri}#row={msg.source_row}",
        "source_row": msg.source_row,
        "source_metadata": msg.source_metadata,
        "ingest_timestamp": ingested_at,
        "source_coverage": {
            "account_scope": "staged_sms_export",
            "import_path": source_uri,
        },
        "provenance": {
            "provider_key": "sms_export",
            "ingest_job_id": str(job_id),
            "parser_version": PARSER_VERSION,
            "authority": "system",
            "original_untouched": True,
        },
        "content_hash": msg.content_hash,
    }


def _locate_attachment_file(
    att: dict[str, Any], payload: dict[str, Any] | None, *, hunt: bool = True
) -> Path | None:
    raw = str(att.get("resolved_path") or "").strip()
    if raw:
        p = Path(raw)
        try:
            if p.is_file() and p.stat().st_size:
                return p
        except OSError:
            pass
    mid = str(att.get("media_object_id") or "").strip()
    if mid:
        hit = media_object_path(mid)
        if hit is not None:
            return hit
    if not hunt:
        return None
    from memorybox.explore.sms_attach import resolve_attachment_file

    try:
        return resolve_attachment_file(att, payload, build_index=False)
    except OSError:
        return None


def _ingest_attachment_bytes(
    attachments: list[dict[str, Any]],
    *,
    source_id: UUID,
    conn: Any,
    payload: dict[str, Any] | None = None,
    hunt: bool = True,
) -> tuple[int, int]:
    """Copy export files into media_objects. Returns (stored, missing). Not Immich."""
    stored = 0
    missing = 0
    for att in attachments:
        if not isinstance(att, dict):
            continue
        mid = str(att.get("media_object_id") or "").strip()
        if mid and media_object_path(mid, conn=conn) is not None:
            att["bytes_ingested"] = True
            att["bytes_present"] = True
            continue
        path = _locate_attachment_file(att, payload, hunt=hunt)
        if path is None:
            att["bytes_ingested"] = False
            missing += 1
            continue
        try:
            data = path.read_bytes()
        except OSError:
            att["bytes_ingested"] = False
            missing += 1
            continue
        rec = put_media_object(
            data,
            str(att.get("filename") or path.name),
            source_id=source_id,
            conn=conn,
            mime_type=str(att.get("mime_type") or "") or None,
        )
        if rec is None:
            att["bytes_ingested"] = False
            missing += 1
            continue
        att["media_object_id"] = rec["media_object_id"]
        att["content_hash"] = rec["content_hash"]
        att["byte_size"] = rec["byte_size"]
        att["mime_type"] = rec.get("mime_type") or att.get("mime_type")
        att["resolved_path"] = rec["uri"]
        att["bytes_present"] = True
        att["bytes_ingested"] = True
        att["promoted_to_immich"] = False
        att["standalone_explore_media"] = False
        stored += 1
    return stored, missing


def _backfill_existing_attachments(
    evidence_id: UUID,
    msg: SmsMessage,
    *,
    source_id: UUID,
    conn: Any,
    payload_template: dict[str, Any],
    hunt: bool = True,
) -> tuple[int, int]:
    row = store.get_evidence(evidence_id, conn=conn)
    if not row:
        return 0, 0
    raw = row.get("payload_json")
    payload = dict(raw) if isinstance(raw, dict) else json.loads(raw or "{}")
    atts = [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]
    if not atts:
        atts = [dict(a) for a in (msg.attachments or []) if isinstance(a, dict)]
    if not atts:
        return 0, 0
    if all(str(a.get("media_object_id") or "").strip() and a.get("bytes_ingested") for a in atts):
        if all(media_object_path(str(a.get("media_object_id")), conn=conn) for a in atts):
            return 0, 0
    stored, missing = _ingest_attachment_bytes(
        atts,
        source_id=source_id,
        conn=conn,
        payload=payload or payload_template,
        hunt=hunt,
    )
    if stored:
        payload["attachments"] = atts
        store.update_evidence_payload(evidence_id, payload, conn=conn)
    return stored, missing


def ingest_sms(
    uri: str | None = None,
    *,
    limit: int | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    path = Path(uri) if uri else default_sms_export_path()
    job_id = store.start_job(
        "ingest_sms",
        message="ingest sms/imessage export",
        payload={"source_kind": "sms_export"},
    )
    try:
        if path is None or not path.is_file():
            raise FileNotFoundError(
                "SMS export not found. Set MEMORYBOX_SMS_URI or place the file at "
                r"\\media-server\photos\MemoryBox\Sources\sms\Messages - 1085 chat sessions.csv"
            )
        before = path.stat()
        size = before.st_size
        ingested_at = datetime.now(timezone.utc).isoformat()
        source_id = store.upsert_source(
            source_kind="sms_export",
            label=label or f"sms:{path.name}",
            uri=str(path),
            metadata={
                "byte_size": size,
                "original_untouched": True,
                "parser_version": PARSER_VERSION,
            },
        )
        inserted = 0
        skipped = 0
        contacts_upserted = 0
        attachments_stored = 0
        attachments_missing = 0
        evidence_ids: list[str] = []
        headers: list[str] = []
        written_contacts: set[tuple[str, str]] = set()
        hunt_attach = sms_folder_has_attachment_bytes(path)
        # One PG connection for the 90k-row FlightSim export. Opening a socket
        # per row exhausts Windows ephemeral ports (WSAEADDRINUSE 10048).
        with connection() as conn:
            handle_index = _index_confirmed_handles(conn)
            known = store.hashes_for_source(source_id, conn=conn)
            for headers, msg in iter_sms_messages(path, limit=limit):
                existing = known.get(msg.content_hash)
                if existing:
                    skipped += 1
                    if len(evidence_ids) < 64:
                        evidence_ids.append(str(existing))
                    if msg.attachments and hunt_attach:
                        try:
                            stored, missing = _backfill_existing_attachments(
                                existing,
                                msg,
                                source_id=source_id,
                                conn=conn,
                                payload_template={
                                    "source_coverage": {"import_path": str(path)},
                                    "source_locator": f"{path}#row={msg.source_row}",
                                },
                                hunt=True,
                            )
                            attachments_stored += stored
                            attachments_missing += missing
                            if attachments_stored and attachments_stored % 200 == 0:
                                conn.commit()
                        except OSError:
                            attachments_missing += len(msg.attachments)
                    elif msg.attachments:
                        attachments_missing += len(msg.attachments)
                    continue
                payload = _payload(
                    msg,
                    job_id=job_id,
                    source_uri=str(path),
                    ingested_at=ingested_at,
                    handle_index=handle_index,
                )
                stored, missing = _ingest_attachment_bytes(
                    list(payload.get("attachments") or []),
                    source_id=source_id,
                    conn=conn,
                    payload=payload,
                    hunt=hunt_attach,
                )
                attachments_stored += stored
                attachments_missing += missing
                for mapped in (payload.get("identity_resolution") or {}).get("mapped") or []:
                    pid = str(mapped.get("person_id") or "")
                    handle = str(mapped.get("normalized") or mapped.get("handle") or "")
                    key = (pid, handle)
                    if not pid or not handle or key in written_contacts:
                        continue
                    written_contacts.add(key)
                    if ensure_confirmed_phone_contact(
                        pid,
                        handle,
                        conn=conn,
                        provenance={"source": "sms_auto_map", "handle": handle},
                    ):
                        contacts_upserted += 1
                summary = (
                    msg.body_text or msg.thread_id or msg.subject or "text message"
                )[:500]
                eid = store.insert_evidence(
                    evidence_kind="communication",
                    source_id=source_id,
                    summary=summary,
                    payload=payload,
                    conn=conn,
                )
                known[msg.content_hash] = eid
                inserted += 1
                if len(evidence_ids) < 64:
                    evidence_ids.append(str(eid))
                if inserted % 1000 == 0:
                    conn.commit()
        after = path.stat()
        untouched = (
            before.st_mtime_ns == after.st_mtime_ns and before.st_size == after.st_size
        )
        store.finish_job(
            job_id,
            status="done",
            message=(
                f"inserted={inserted} skipped={skipped} untouched={untouched} "
                f"attachments_stored={attachments_stored} attachments_missing={attachments_missing}"
            ),
        )
        return {
            "ok": True,
            "job_id": str(job_id),
            "source_id": str(source_id),
            "path": str(path),
            "headers": headers,
            "inserted": inserted,
            "skipped": skipped,
            "contacts_upserted": contacts_upserted,
            "attachments_stored": attachments_stored,
            "attachments_missing": attachments_missing,
            "evidence_ids": evidence_ids,
            "sms_bytes": size,
            "original_untouched": untouched,
            "attachment_bytes_hunted": hunt_attach,
        }
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        filename = getattr(exc, "filename", None)
        if filename:
            detail = f"{detail} ({filename})"
        store.finish_job(
            job_id, status="error", message="ingest failed", error_message=detail
        )
        return {"ok": False, "job_id": str(job_id), "error": detail}


def inspect_default_or_uri(uri: str | None = None) -> dict[str, Any]:
    path = Path(uri) if uri else default_sms_export_path()
    if path is None or not path.is_file():
        return {
            "ok": False,
            "error": "SMS export not found",
            "tried": uri or str(default_sms_export_path()),
        }
    return inspect_sms_export(path, sample_rows=0)
