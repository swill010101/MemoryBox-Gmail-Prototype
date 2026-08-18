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
        self,
        source: EmailSourceRef,
        *,
        limit: int | None = None,
        skip_spam_trash: bool = False,
    ) -> Iterator[EmailMessageDto]:
        if source.provider_key not in (self.provider_key, "filesystem"):
            raise ProviderError(
                f"MboxEmailReadProvider cannot read provider_key={source.provider_key}"
            )
        path = Path(source.uri)
        if not path.exists():
            raise ProviderUnavailable(f"mbox not found: {path}")
        self.skipped_spam = 0
        self.skipped_trash = 0
        yielded = 0
        for raw in mbox_parse.iter_rfc822_bytes(path):
            try:
                msg = email.message_from_bytes(raw, policy=email.policy.default)
            except Exception:  # noqa: BLE001
                continue
            labels = mbox_parse.parse_gmail_labels(msg)
            mailbox_skip = mbox_parse.mailbox_skip_reason(labels)
            if skip_spam_trash and mailbox_skip:
                if mailbox_skip == "spam":
                    self.skipped_spam += 1
                else:
                    self.skipped_trash += 1
                continue
            if limit is not None and yielded >= limit:
                break
            text, html = mbox_parse.extract_bodies(msg)
            sn = mbox_parse.strip_nul
            mid = msg.get("Message-ID")
            rfc_id = sn(str(mid).strip()) if mid else None
            subject_raw = msg.get("Subject")
            subject = sn(str(subject_raw)) if subject_raw else None
            date_hdr = msg.get("Date")
            body_for_hash = text or html
            irt_raw = sn(str(msg.get("In-Reply-To"))) if msg.get("In-Reply-To") else None
            ref_raw = sn(str(msg.get("References"))) if msg.get("References") else None
            irt_ids = mbox_parse.parse_message_ids(irt_raw)
            ref_ids = mbox_parse.parse_message_ids(ref_raw)
            vendor = mbox_parse.vendor_thread_id(msg)
            if vendor:
                vendor = sn(vendor)
            thread_id, thread_status = mbox_parse.thread_fields(
                rfc_message_id=rfc_id,
                in_reply_to_ids=irt_ids,
                reference_ids=ref_ids,
                vendor=vendor,
            )
            from_raw = sn(str(msg.get("From"))) if msg.get("From") else None
            to_vals = tuple(sn(str(v)) for v in (msg.get_all("To") or []))
            cc_vals = tuple(sn(str(v)) for v in (msg.get_all("Cc") or []))
            yield EmailMessageDto(
                provider_key=self.provider_key,
                external_id=rfc_id,
                content_hash=mbox_parse.content_hash(
                    rfc_id,
                    sn(str(date_hdr)) if date_hdr else None,
                    subject,
                    body_for_hash,
                ),
                date_utc=mbox_parse.parse_date(msg),
                subject=subject,
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
                gmail_labels=labels,
                mailbox_skip=mailbox_skip,
            )
            yielded += 1
