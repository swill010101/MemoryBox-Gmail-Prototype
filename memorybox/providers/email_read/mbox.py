"""Mbox EmailReadProvider — files only; no SQLite dual-write."""
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
        if not path.is_file():
            raise ProviderUnavailable(f"mbox not found: {path}")
        yielded = 0
        for raw in mbox_parse.iter_mbox_bytes(path):
            if limit is not None and yielded >= limit:
                break
            try:
                msg = email.message_from_bytes(raw, policy=email.policy.default)
            except Exception:  # noqa: BLE001
                continue
            text, html = mbox_parse.extract_bodies(msg)
            mid = msg.get("Message-ID")
            subject = msg.get("Subject")
            date_hdr = msg.get("Date")
            body_for_hash = text or html
            yield EmailMessageDto(
                provider_key=self.provider_key,
                external_id=str(mid).strip() if mid else None,
                content_hash=mbox_parse.content_hash(
                    str(mid) if mid else None,
                    str(date_hdr) if date_hdr else None,
                    str(subject) if subject else None,
                    body_for_hash,
                ),
                date_utc=mbox_parse.parse_date(msg),
                subject=str(subject) if subject else None,
                from_addr=str(msg.get("From")) if msg.get("From") else None,
                to_addrs=tuple(str(v) for v in (msg.get_all("To") or [])),
                cc_addrs=tuple(str(v) for v in (msg.get_all("Cc") or [])),
                body_text=text,
                body_html=html,
                in_reply_to=str(msg.get("In-Reply-To")) if msg.get("In-Reply-To") else None,
                references=str(msg.get("References")) if msg.get("References") else None,
                source_uri=str(path),
            )
            yielded += 1
