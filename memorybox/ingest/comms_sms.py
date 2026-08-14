"""SMS / iMessage / MMS export → Source + Evidence (evidence_kind=communication)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.ingest import store as store
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
        evidence_ids: list[str] = []
        headers: list[str] = []
        written_contacts: set[tuple[str, str]] = set()
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
                    continue
                payload = _payload(
                    msg,
                    job_id=job_id,
                    source_uri=str(path),
                    ingested_at=ingested_at,
                    handle_index=handle_index,
                )
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
            message=f"inserted={inserted} skipped={skipped} untouched={untouched}",
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
            "evidence_ids": evidence_ids,
            "sms_bytes": size,
            "original_untouched": untouched,
        }
    except Exception as exc:  # noqa: BLE001
        store.finish_job(
            job_id, status="error", message="ingest failed", error_message=str(exc)
        )
        return {"ok": False, "job_id": str(job_id), "error": str(exc)}


def inspect_default_or_uri(uri: str | None = None) -> dict[str, Any]:
    path = Path(uri) if uri else default_sms_export_path()
    if path is None or not path.is_file():
        return {
            "ok": False,
            "error": "SMS export not found",
            "tried": uri or str(default_sms_export_path()),
        }
    return inspect_sms_export(path, sample_rows=0)
