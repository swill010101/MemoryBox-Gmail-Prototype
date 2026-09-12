"""P2-I14 record-key normalization. No persistence and no ingest."""
from __future__ import annotations

import hashlib
import re

EMAIL_RFC = "email_rfc_message_id"
EMAIL_VENDOR = "email_vendor_message_id"
EMAIL_FULL = "email_full_sha256"
CAL_UID_RID = "calendar_uid_recurrence"
CAL_UID_START = "calendar_uid_dtstart"
CAL_FULL = "calendar_full_sha256"
SMS_PROVIDER = "sms_provider_id"
SMS_NORM = "sms_normalized_sha256"

_RFC_ID = re.compile(r"^<[^<>@\s]{1,247}@[A-Za-z0-9.-]{1,253}>$")
_ROW_FALLBACK = re.compile(r"\|[0-9]+$")

Alias = tuple[str, str, str]


def sha256_text(*parts: str) -> str:
    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def normalize_rfc_message_id(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if not (text.startswith("<") and text.endswith(">")):
        text = f"<{text.strip('<>')}>"
    lower = text.lower()
    if not _RFC_ID.match(lower):
        return None
    if not (3 <= len(lower) <= 512):
        return None
    if "@" not in lower[1:-1]:
        return None
    return lower


def is_genuine_provider_message_id(value: str | None, *, source_row: int | None = None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if source_row is not None and text.endswith(f"|{source_row}"):
        return False
    if _ROW_FALLBACK.search(text) and "|" in text:
        return False
    return True


def _email_full_alias(
    *,
    rfc_message_id: str,
    vendor: str,
    date_header: str,
    from_addr: str,
    to_addrs: str,
    body: str,
    attachment_hashes: list[str] | None,
) -> Alias:
    att = ",".join(sorted(h for h in (attachment_hashes or []) if h))
    digest = sha256_text(
        "email_v1",
        rfc_message_id,
        vendor,
        date_header,
        from_addr,
        to_addrs,
        body,
        att,
    )
    return EMAIL_FULL, f"sha256:{digest}", "fallback_hash"


def email_identity_aliases(
    *,
    rfc_message_id: str | None = None,
    vendor_message_id: str | None = None,
    date_header: str = "",
    from_addr: str = "",
    to_addrs: str = "",
    body: str = "",
    attachment_hashes: list[str] | None = None,
) -> list[Alias]:
    """All aliases for one email. RFC and vendor do not replace the full hash."""
    out: list[Alias] = []
    rfc = normalize_rfc_message_id(rfc_message_id)
    if rfc:
        out.append((EMAIL_RFC, f"rfc:{rfc}", "rfc_message_id"))
    vendor = (vendor_message_id or "").strip()
    if vendor:
        out.append((EMAIL_VENDOR, f"vendor:{vendor.lower()}", "gmail_msgid"))
    out.append(
        _email_full_alias(
            rfc_message_id=rfc or "",
            vendor=vendor,
            date_header=date_header,
            from_addr=from_addr,
            to_addrs=to_addrs,
            body=body,
            attachment_hashes=attachment_hashes,
        )
    )
    return out


def email_record_identity(
    *,
    rfc_message_id: str | None = None,
    vendor_message_id: str | None = None,
    date_header: str = "",
    from_addr: str = "",
    to_addrs: str = "",
    body: str = "",
    attachment_hashes: list[str] | None = None,
) -> Alias:
    """Preferred alias: RFC, else vendor, else full SHA-256. Never subject-only."""
    return email_identity_aliases(
        rfc_message_id=rfc_message_id,
        vendor_message_id=vendor_message_id,
        date_header=date_header,
        from_addr=from_addr,
        to_addrs=to_addrs,
        body=body,
        attachment_hashes=attachment_hashes,
    )[0]


def calendar_identity_aliases(
    *,
    uid: str | None = None,
    recurrence_id: str | None = None,
    dtstart: str = "",
    dtend: str = "",
    rrule: str = "",
    summary: str = "",
    location: str = "",
    description: str = "",
) -> list[Alias]:
    out: list[Alias] = []
    uid_n = (uid or "").strip()
    rid = (recurrence_id or "").strip()
    if uid_n and rid:
        out.append((CAL_UID_RID, f"uid:{uid_n}|rid:{rid}", "calendar_uid"))
    elif uid_n and dtstart:
        out.append((CAL_UID_START, f"uid:{uid_n}|dtstart:{dtstart}", "calendar_uid"))
    digest = sha256_text(
        "calendar_v1",
        uid_n,
        rid,
        dtstart,
        dtend,
        rrule,
        summary,
        location,
        description,
    )
    out.append((CAL_FULL, f"sha256:{digest}", "fallback_hash"))
    return out


def calendar_record_identity(
    *,
    uid: str | None = None,
    recurrence_id: str | None = None,
    dtstart: str = "",
    dtend: str = "",
    rrule: str = "",
    summary: str = "",
    location: str = "",
    description: str = "",
) -> Alias:
    return calendar_identity_aliases(
        uid=uid,
        recurrence_id=recurrence_id,
        dtstart=dtstart,
        dtend=dtend,
        rrule=rrule,
        summary=summary,
        location=location,
        description=description,
    )[0]


def sms_identity_aliases(
    *,
    provider_message_id: str | None = None,
    source_row: int | None = None,
    participants: list[str] | None = None,
    direction: str = "",
    sent_at: str = "",
    body: str = "",
    attachment_hashes: list[str] | None = None,
) -> list[Alias]:
    out: list[Alias] = []
    if is_genuine_provider_message_id(provider_message_id, source_row=source_row):
        mid = (provider_message_id or "").strip().lower()
        out.append((SMS_PROVIDER, f"provider:{mid}", "sms_guid"))
    parts = ",".join(sorted((p or "").strip().lower() for p in (participants or []) if p))
    att = ",".join(sorted(h for h in (attachment_hashes or []) if h))
    digest = sha256_text("sms_v1", parts, direction.lower().strip(), sent_at, body, att)
    out.append((SMS_NORM, f"sha256:{digest}", "fallback_hash"))
    return out


def sms_record_identity(
    *,
    provider_message_id: str | None = None,
    source_row: int | None = None,
    participants: list[str] | None = None,
    direction: str = "",
    sent_at: str = "",
    body: str = "",
    attachment_hashes: list[str] | None = None,
) -> Alias:
    return sms_identity_aliases(
        provider_message_id=provider_message_id,
        source_row=source_row,
        participants=participants,
        direction=direction,
        sent_at=sent_at,
        body=body,
        attachment_hashes=attachment_hashes,
    )[0]
