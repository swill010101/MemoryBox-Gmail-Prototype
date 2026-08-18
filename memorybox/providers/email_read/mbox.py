"""Mbox / Maildir EmailReadProvider — files only; no SQLite dual-write."""
from __future__ import annotations

import email
import email.policy
from collections.abc import Iterator
from pathlib import Path

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.email_read.dto import EmailMessageDto, EmailSourceRef
from memorybox.providers.email_read import mbox_parse


class MboxEmailReadProvider:
    provider_key = "mbox"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key, ok=True, detail="filesystem mbox reader"
        )

    def iter_messages(
        self, source: EmailSourceRef, *, limit: int | None = None
    ) -> Iterator[EmailMessageDto]:
        if source.provider_key not in (self.provider_key, "filesystem"):
            raise ProviderError(
                f"MboxEmailReadProvider cannot read provider_key={source.provider_key}"
            )
        path = Path(source.uri)
        if not path.exists():
            raise ProviderUnavailable(f"mbox not found: {path}")
        yielded = 0
        for raw in mbox_parse.iter_rfc822_bytes(path):
            if limit is not None and yielded >= limit:
                break
            try:
                msg = email.message_from_bytes(raw, policy=email.policy.default)
            except Exception:  # noqa: BLE001
                continue
            text, html = mbox_parse.extract_bodies(msg)
            mid = msg.get("Message-ID")
            rfc_id = str(mid).strip() if mid else None
            subject = msg.get("Subject")
            date_hdr = msg.get("Date")
            body_for_hash = text or html
            irt_raw = str(msg.get("In-Reply-To")) if msg.get("In-Reply-To") else None
            ref_raw = str(msg.get("References")) if msg.get("References") else None
            irt_ids = mbox_parse.parse_message_ids(irt_raw)
            ref_ids = mbox_parse.parse_message_ids(ref_raw)
            vendor = mbox_parse.vendor_thread_id(msg)
            thread_id, thread_status = mbox_parse.thread_fields(
                rfc_message_id=rfc_id,
                in_reply_to_ids=irt_ids,
                reference_ids=ref_ids,
                vendor=vendor,
            )
            from_raw = str(msg.get("From")) if msg.get("From") else None
            to_vals = tuple(str(v) for v in (msg.get_all("To") or []))
            cc_vals = tuple(str(v) for v in (msg.get_all("Cc") or []))
            yield EmailMessageDto(
                provider_key=self.provider_key,
                external_id=rfc_id,
                content_hash=mbox_parse.content_hash(
                    str(mid) if mid else None,
                    str(date_hdr) if date_hdr else None,
                    str(subject) if subject else None,
                    body_for_hash,
                ),
                date_utc=mbox_parse.parse_date(msg),
                subject=str(subject) if subject else None,
                from_addr=from_raw,
                to_addrs=to_vals,
                cc_addrs=cc_vals,
                body_text=text,
                body_html=html,
                in_reply_to=irt_raw,
                references=ref_raw,
                source_uri=str(path),
                from_parsed=mbox_parse.addr_records(from_raw),
                to_parsed=mbox_parse.addr_records(*to_vals),
                cc_parsed=mbox_parse.addr_records(*cc_vals),
                attachments=mbox_parse.extract_attachments(msg, include_bytes=True),
                vendor_thread_id=vendor,
                rfc_message_id=rfc_id,
                in_reply_to_ids=irt_ids,
                reference_ids=ref_ids,
                thread_id=thread_id,
                thread_status=thread_status,
                header_provenance=mbox_parse.header_provenance(msg),
                html_only=bool(html) and not (text or "").strip(),
            )
            yielded += 1
