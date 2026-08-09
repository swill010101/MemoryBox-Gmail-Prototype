"""Email-read DTOs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EmailSourceRef:
    provider_key: str
    uri: str


@dataclass(frozen=True)
class EmailMessageDto:
    provider_key: str
    external_id: str | None
    content_hash: str
    date_utc: datetime | None
    subject: str | None
    from_addr: str | None
    to_addrs: tuple[str, ...]
    cc_addrs: tuple[str, ...]
    body_text: str
    body_html: str
    in_reply_to: str | None
    references: str | None
    source_uri: str
