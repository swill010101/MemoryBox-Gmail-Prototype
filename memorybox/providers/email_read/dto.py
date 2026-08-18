"""Email-read DTOs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EmailSourceRef:
    provider_key: str
    uri: str


@dataclass(frozen=True)
class EmailPartDto:
    """One MIME part that is not the primary text/html body."""

    filename: str
    mime_type: str
    byte_size: int
    content_hash: str
    disposition: str
    content_id: str | None
    kind: str  # attachment | inline
    data: bytes


@dataclass(frozen=True)
class EmailAddressDto:
    raw: str
    display_name: str
    address: str
    normalized: str


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
    from_parsed: tuple[EmailAddressDto, ...] = ()
    to_parsed: tuple[EmailAddressDto, ...] = ()
    cc_parsed: tuple[EmailAddressDto, ...] = ()
    attachments: tuple[EmailPartDto, ...] = ()
    vendor_thread_id: str | None = None
    rfc_message_id: str | None = None
    in_reply_to_ids: tuple[str, ...] = ()
    reference_ids: tuple[str, ...] = ()
    thread_id: str | None = None
    thread_status: str = "unthreaded"
    header_provenance: tuple[tuple[str, str], ...] = ()
    html_only: bool = False
    gmail_labels: tuple[str, ...] = ()
    mailbox_skip: str | None = None
