"""Email mbox → Source + Evidence (evidence_kind=communication)."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ingest import store as store
from memorybox.providers.email_read.dto import EmailSourceRef
from memorybox.providers.email_read.mbox import MboxEmailReadProvider

PARSER_VERSION = "i3-email-1"


def _payload_from_dto(msg, *, job_id: UUID) -> dict[str, Any]:
    return {
        "evidence_channel": "email",
        "message_id": msg.external_id,
        "subject": msg.subject,
        "from": msg.from_addr,
        "to": list(msg.to_addrs),
        "cc": list(msg.cc_addrs),
        "bcc": [],
        "sent_at": msg.date_utc.isoformat() if msg.date_utc else None,
        "body_text": msg.body_text or "",
        "source_locator": msg.source_uri
        + (f"#mid={msg.external_id}" if msg.external_id else f"#hash={msg.content_hash}"),
        "provenance": {
            "provider_key": msg.provider_key,
            "ingest_job_id": str(job_id),
            "parser_version": PARSER_VERSION,
            "authority": "system",
        },
        "content_hash": msg.content_hash,
        "in_reply_to": msg.in_reply_to,
        "references": msg.references,
    }


def ingest_mbox(
    mbox_uri: str,
    *,
    limit: int | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    path = Path(mbox_uri)
    job_id = store.start_job(
        "ingest_email",
        message=f"ingest mbox locator configured",
        payload={"source_kind": "mbox_import"},
    )
    try:
        if not path.is_file():
            raise FileNotFoundError(f"mbox not found: {path}")
        # Touch-read only — do not rewrite
        _size = path.stat().st_size
        source_id = store.upsert_source(
            source_kind="mbox_import",
            label=label or f"mbox:{path.name}",
            uri=str(path.resolve()),
            metadata={
                "fixture_or_smoke": True,
                "byte_size": _size,
                "original_untouched": True,
            },
        )
        provider = MboxEmailReadProvider()
        inserted = 0
        skipped = 0
        evidence_ids: list[str] = []
        for msg in provider.iter_messages(
            EmailSourceRef(provider_key="mbox", uri=str(path)), limit=limit
        ):
            existing = store.evidence_exists_by_hash(source_id, msg.content_hash)
            if existing:
                skipped += 1
                evidence_ids.append(str(existing))
                continue
            payload = _payload_from_dto(msg, job_id=job_id)
            eid = store.insert_evidence(
                evidence_kind="communication",
                source_id=source_id,
                summary=(msg.subject or "(no subject)")[:500],
                payload=payload,
            )
            inserted += 1
            evidence_ids.append(str(eid))
        store.finish_job(
            job_id,
            status="done",
            message=f"inserted={inserted} skipped={skipped}",
        )
        return {
            "ok": True,
            "job_id": str(job_id),
            "source_id": str(source_id),
            "inserted": inserted,
            "skipped": skipped,
            "evidence_ids": evidence_ids,
            "mbox_bytes": _size,
        }
    except Exception as exc:  # noqa: BLE001
        store.finish_job(
            job_id, status="error", message="ingest failed", error_message=str(exc)
        )
        return {"ok": False, "job_id": str(job_id), "error": str(exc)}
