"""Historian Capture email adapter — dedicated mailbox path with fake harness support."""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
from dataclasses import dataclass, field
from email import message_from_bytes
from email.policy import default as email_default
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from application.marvin_capture.plus_address import (
        build_plus_address as _poc_build_plus_address,
        parse_plus_tag,
    )
    from application.marvin_capture.reply_extract import extract_reply_text
except ImportError:  # pragma: no cover
    _poc_build_plus_address = None

    def parse_plus_tag(addr: str) -> str | None:  # type: ignore[misc]
        if "+" not in (addr or ""):
            return None
        local = (addr or "").split("@", 1)[0]
        parts = local.split("+", 1)
        return parts[1] if len(parts) == 2 else None

    def extract_reply_text(raw: str | bytes, *, is_html: bool = False) -> str:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        return (raw or "").strip()


def build_plus_address(user_email: str, tag: str) -> str:
    """PoC-compatible plus-address: build_plus_address(user_email, tag)."""
    if _poc_build_plus_address is not None:
        return _poc_build_plus_address(user_email, tag)
    local, domain = user_email.split("@", 1)
    return f"{local}+{tag}@{domain}"


HC_PLUS_PREFIX = "hc-"
HC_MAILBOX = "memorybox@marvinbot.net"
SUBJECT_TOKEN_RE = re.compile(r"\[MB-HC-([A-Za-z0-9]+)\]", re.IGNORECASE)
STOP_KEYWORDS = frozenset({"stop", "unsubscribe", "opt out", "opt-out"})
HC_TOKEN_HEADER = "X-MemoryBox-HC-Token"

DEFAULT_QUESTION_SUBJECT_TEMPLATE = "[MB-HC-{token}] {title}"
DEFAULT_THANKYOU_SUBJECT_TEMPLATE = "[MB-HC-{token}] Thank you — MemoryBox"
# Founder-review samples only — not production defaults until approved:
PROPOSED_QUESTION_SUBJECT_TEMPLATE = "A MemoryBox question from Tom about {title}"
PROPOSED_THANKYOU_SUBJECT_TEMPLATE = "Thank you for sharing this memory"

HC_OUTBOUND_MARKER = "— MemoryBox Historian Capture"
HC_REMINDER_MARKER = "— Friendly reminder"


@dataclass
class OutboundSendResult:
    ok: bool
    outbound_message_id: str | None = None
    thread_id: str | None = None
    preserved_raw_uri: str | None = None
    fail_detail: str | None = None
    reply_to: str | None = None


@dataclass
class InboundMailItem:
    inbound_message_id: str
    correlation_token: str | None
    from_addr: str
    subject: str
    extracted_text: str
    preserved_raw_uri: str
    thread_id: str | None = None
    raw_headers: dict[str, str] = field(default_factory=dict)
    skip_reason: str | None = None
    ambiguous: bool = False
    in_reply_to: str | None = None
    raw_bytes: bytes | None = None


class HistorianEmailAdapter(Protocol):
    def send_question(
        self,
        *,
        to_email: str,
        respondent_name: str,
        question_body: str,
        correlation_token: str,
        campaign_title: str | None = None,
        is_reminder: bool = False,
    ) -> OutboundSendResult: ...

    def send_thank_you(
        self,
        *,
        to_email: str,
        respondent_name: str,
        body: str,
        correlation_token: str | None = None,
    ) -> OutboundSendResult: ...

    def poll_inbound(self) -> list[InboundMailItem]: ...

    def mark_processed(self, inbound_message_id: str) -> None: ...


def new_correlation_token() -> str:
    return secrets.token_hex(6)


def format_question_subject(*, correlation_token: str, campaign_title: str | None = None) -> str:
    title = (campaign_title or "MemoryBox question").strip() or "MemoryBox question"
    tmpl = (
        os.environ.get("MEMORYBOX_HC_QUESTION_SUBJECT_TEMPLATE") or DEFAULT_QUESTION_SUBJECT_TEMPLATE
    ).strip()
    try:
        return tmpl.format(token=correlation_token, title=title, person=title)
    except (KeyError, ValueError, IndexError):
        return DEFAULT_QUESTION_SUBJECT_TEMPLATE.format(token=correlation_token, title=title)


def format_thankyou_subject(*, correlation_token: str | None = None) -> str:
    tmpl = (
        os.environ.get("MEMORYBOX_HC_THANKYOU_SUBJECT_TEMPLATE") or DEFAULT_THANKYOU_SUBJECT_TEMPLATE
    ).strip()
    token = (correlation_token or "").strip()
    if not token and tmpl == DEFAULT_THANKYOU_SUBJECT_TEMPLATE:
        return "Thank you — MemoryBox"
    try:
        return tmpl.format(token=token, title="MemoryBox")
    except (KeyError, ValueError, IndexError):
        if token:
            return DEFAULT_THANKYOU_SUBJECT_TEMPLATE.format(token=token)
        return "Thank you — MemoryBox"


def extract_correlation_token(
    *,
    subject: str | None = None,
    to_addrs: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> str | None:
    if subject:
        m = SUBJECT_TOKEN_RE.search(subject)
        if m:
            return m.group(1).lower()
    for addr in to_addrs or []:
        tag = parse_plus_tag(addr)
        if tag and tag.lower().startswith(HC_PLUS_PREFIX):
            return tag[len(HC_PLUS_PREFIX) :].lower()
    if headers:
        for key in ("delivered-to", "x-original-to", "to", "Delivered-To", "To", "reply-to", "Reply-To"):
            raw = headers.get(key) or ""
            for part in re.split(r",\s*", raw):
                tag = parse_plus_tag(part.strip())
                if tag and tag.lower().startswith(HC_PLUS_PREFIX):
                    return tag[len(HC_PLUS_PREFIX) :].lower()
        header_token = (
            headers.get(HC_TOKEN_HEADER)
            or headers.get(HC_TOKEN_HEADER.lower())
            or headers.get("x-memorybox-hc-token")
            or ""
        ).strip()
        if header_token:
            return header_token.lower()
    return None


def is_stop_message(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    first = t.split()[0] if t.split() else ""
    if first in STOP_KEYWORDS:
        return True
    return t in STOP_KEYWORDS


def _preserve_bytes(data: bytes, *, stem: str, root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{stem}.eml"
    path.write_bytes(data)
    return path.resolve().as_uri()


def _looks_like_outbound_echo(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return HC_OUTBOUND_MARKER in t and len(t) < 800


class FakeHistorianEmailAdapter:
    """In-memory outbound/inbound for prove-historian-capture (no live Gmail)."""

    provider_key = "fake_historian_email"

    def __init__(
        self,
        *,
        fail_next_send: bool = False,
        user_email: str = HC_MAILBOX,
    ) -> None:
        self.user_email = user_email
        self.sent: list[dict[str, Any]] = []
        self.inbox: list[dict[str, Any]] = []
        self.processed: set[str] = set()
        self.fail_next_send = fail_next_send
        self.poll_error: str | None = None
        self.last_poll_debug: dict[str, Any] = {}
        self._root = Path.cwd() / ".memorybox_hc_fake_mail"
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq:04d}"

    def send_question(
        self,
        *,
        to_email: str,
        respondent_name: str,
        question_body: str,
        correlation_token: str,
        campaign_title: str | None = None,
        is_reminder: bool = False,
    ) -> OutboundSendResult:
        if self.fail_next_send:
            self.fail_next_send = False
            return OutboundSendResult(ok=False, fail_detail="synthetic_send_failure")
        reply_to = build_plus_address(self.user_email, f"{HC_PLUS_PREFIX}{correlation_token}")
        subject = format_question_subject(
            correlation_token=correlation_token, campaign_title=campaign_title
        )
        if is_reminder:
            body = (
                f"Hi {respondent_name},\n\n"
                f"{HC_REMINDER_MARKER}\n\n"
                f"{question_body}\n\n"
                f"{HC_OUTBOUND_MARKER}\n"
                f"(Please reply to this message; keep the subject if possible.)\n"
            )
        else:
            body = (
                f"Hi {respondent_name},\n\n"
                f"{question_body}\n\n"
                f"{HC_OUTBOUND_MARKER}\n"
                f"(Please reply to this message; keep the subject if possible.)\n"
            )
        mid = self._next_id("out")
        tid = self._next_id("thr")
        raw = (
            f"Message-ID: {mid}\nTo: {to_email}\nReply-To: {reply_to}\nSubject: {subject}\n\n{body}"
        ).encode()
        uri = _preserve_bytes(raw, stem=mid, root=self._root)
        self.sent.append(
            {
                "id": mid,
                "thread_id": tid,
                "to": to_email,
                "subject": subject,
                "body": body,
                "reply_to": reply_to,
                "correlation_token": correlation_token,
                "is_reminder": is_reminder,
            }
        )
        return OutboundSendResult(
            ok=True,
            outbound_message_id=mid,
            thread_id=tid,
            preserved_raw_uri=uri,
            reply_to=reply_to,
        )

    def send_thank_you(
        self,
        *,
        to_email: str,
        respondent_name: str,
        body: str,
        correlation_token: str | None = None,
    ) -> OutboundSendResult:
        subject = format_thankyou_subject(correlation_token=correlation_token)
        mid = self._next_id("ty")
        raw = f"Message-ID: {mid}\nTo: {to_email}\nSubject: {subject}\n\n{body}".encode()
        uri = _preserve_bytes(raw, stem=mid, root=self._root)
        self.sent.append(
            {
                "id": mid,
                "to": to_email,
                "subject": subject,
                "body": body,
                "kind": "thank_you",
            }
        )
        return OutboundSendResult(
            ok=True,
            outbound_message_id=mid,
            preserved_raw_uri=uri,
        )

    def inject_reply(
        self,
        *,
        correlation_token: str | None,
        from_addr: str,
        text: str,
        subject: str | None = None,
        inbound_message_id: str | None = None,
        ambiguous: bool = False,
    ) -> str:
        mid = inbound_message_id or self._next_id("in")
        subj = subject or (
            f"[MB-HC-{correlation_token}] Re: MemoryBox question"
            if correlation_token
            else "Re: (no token)"
        )
        raw = f"From: {from_addr}\nSubject: {subj}\n\n{text}".encode()
        uri = _preserve_bytes(raw, stem=mid, root=self._root)
        self.inbox.append(
            {
                "id": mid,
                "correlation_token": correlation_token,
                "from_addr": from_addr,
                "subject": subj,
                "text": text,
                "uri": uri,
                "raw_bytes": raw,
                "ambiguous": ambiguous,
            }
        )
        return mid

    def poll_inbound(self) -> list[InboundMailItem]:
        self.last_poll_debug = {"error": self.poll_error}
        if self.poll_error:
            return []
        out: list[InboundMailItem] = []
        for item in self.inbox:
            mid = item["id"]
            if mid in self.processed:
                continue
            raw = item.get("raw_bytes") or item.get("text", "").encode()
            out.append(
                InboundMailItem(
                    inbound_message_id=mid,
                    correlation_token=item.get("correlation_token"),
                    from_addr=item["from_addr"],
                    subject=item["subject"],
                    extracted_text=item["text"],
                    preserved_raw_uri=item["uri"],
                    ambiguous=bool(item.get("ambiguous")),
                    raw_bytes=raw if isinstance(raw, bytes) else str(raw).encode(),
                )
            )
        return out

    def mark_processed(self, inbound_message_id: str) -> None:
        self.processed.add(inbound_message_id)


class UnavailableHistorianEmailAdapter:
    provider_key = "unavailable"

    def __init__(self, detail: str, *, user_email: str | None = None) -> None:
        self.detail = detail
        self.user_email = user_email or HC_MAILBOX

    def send_question(self, **kwargs: Any) -> OutboundSendResult:
        return OutboundSendResult(ok=False, fail_detail=self.detail)

    def send_thank_you(self, **kwargs: Any) -> OutboundSendResult:
        return OutboundSendResult(ok=False, fail_detail=self.detail)

    def poll_inbound(self) -> list[InboundMailItem]:
        return []

    def mark_processed(self, inbound_message_id: str) -> None:
        return


FAMILY_GMAIL_FILENAMES = frozenset({"gmail_credentials.json", "gmail_token.json"})

PUBLIC_REASON_DETAIL = {
    "not_initialized": "Historian Capture email status has not been checked yet.",
    "cleared": "Historian Capture email is not connected on this host.",
    "fake_ok": "Historian Capture test email provider is connected.",
    "live_ok": "Historian Capture email is connected.",
    "missing_user_email": (
        "The dedicated Historian Capture mailbox address is not configured on this host."
    ),
    "missing_credentials": (
        "Dedicated Historian Capture credentials are not configured on this host. "
        "Family Gmail files are not used."
    ),
    "missing_token": (
        "Dedicated Historian Capture Gmail authorization is not configured on this host."
    ),
    "missing_transport": (
        "Historian Capture Gmail transport is not installed on this host."
    ),
    "family_gmail_rejected": (
        "Family Gmail cannot be used for Historian Capture. "
        "Configure the dedicated capture mailbox instead."
    ),
    "imap_unavailable": "Historian Capture IMAP is not available on this host.",
    "smtp_unavailable": "Historian Capture SMTP is not available on this host.",
    "authentication_failed": (
        "Historian Capture email authentication failed. The dedicated app password was not accepted."
    ),
    "configuration_invalid": "Historian Capture email configuration is invalid on this host.",
    "unavailable": "Historian Capture email is not connected on this host.",
}


def _is_family_gmail_path(path: Path) -> bool:
    return path.name.lower() in FAMILY_GMAIL_FILENAMES


def _status_payload(
    *,
    ok: bool,
    reason: str,
    provider_key: str | None,
    live: bool,
    configured_email: str | None = None,
    transport_email: str | None = None,
    user_email: str | None = None,
    has_dedicated_credentials: bool | None = None,
    has_dedicated_token: bool | None = None,
) -> dict[str, Any]:
    detail = PUBLIC_REASON_DETAIL.get(reason, PUBLIC_REASON_DETAIL["unavailable"])
    channel = ""
    if configured_email and "@" in configured_email:
        channel = configured_email
    if ok and reason == "live_ok" and transport_email and "@" in transport_email:
        if channel and transport_email.lower() != channel.lower():
            detail = (
                f"Capture channel {channel} is connected "
                f"(Gmail account {transport_email})."
            )
        else:
            detail = f"Capture channel {transport_email} is connected."
            channel = transport_email
    elif ok and reason == "live_ok" and channel:
        detail = f"Capture channel {channel} is connected."
    payload: dict[str, Any] = {
        "provider_key": provider_key,
        "ok": ok,
        "reason": reason,
        "detail": detail,
        "capture_mailbox": channel,
        "configured_email": configured_email,
        "transport_email": transport_email,
        "user_email": user_email or channel,
        "live": live,
    }
    if has_dedicated_credentials is not None:
        payload["has_dedicated_credentials"] = has_dedicated_credentials
    if has_dedicated_token is not None:
        payload["has_dedicated_token"] = has_dedicated_token
    return payload


_ADAPTER: HistorianEmailAdapter | None = None
_ADAPTER_STATUS: dict[str, Any] = _status_payload(
    ok=False,
    reason="not_initialized",
    provider_key=None,
    live=False,
)


def set_email_adapter(adapter: HistorianEmailAdapter | None) -> None:
    global _ADAPTER
    _ADAPTER = adapter
    if adapter is None:
        _ADAPTER_STATUS.clear()
        _ADAPTER_STATUS.update(
            _status_payload(
                ok=False,
                reason="cleared",
                provider_key=None,
                live=False,
            )
        )
        return
    key = getattr(adapter, "provider_key", None)
    user_email = getattr(adapter, "user_email", None)
    if key == "unavailable":
        _ADAPTER_STATUS.clear()
        _ADAPTER_STATUS.update(
            _status_payload(
                ok=False,
                reason="unavailable",
                provider_key="unavailable",
                live=False,
                user_email=user_email,
            )
        )
        return
    fake = key == "fake_historian_email"
    _ADAPTER_STATUS.clear()
    _ADAPTER_STATUS.update(
        _status_payload(
            ok=True,
            reason="fake_ok" if fake else "live_ok",
            provider_key=key,
            live=not fake,
            configured_email=user_email,
            transport_email=user_email,
            user_email=user_email,
        )
    )


def email_adapter_status() -> dict[str, Any]:
    get_email_adapter()
    return dict(_ADAPTER_STATUS)


def _fail_adapter(
    fail_reason: str,
    *,
    user_email: str = "",
    has_creds: bool = False,
    has_token: bool = False,
) -> HistorianEmailAdapter:
    global _ADAPTER
    _ADAPTER = UnavailableHistorianEmailAdapter(
        PUBLIC_REASON_DETAIL.get(fail_reason, PUBLIC_REASON_DETAIL["unavailable"]),
        user_email=user_email or None,
    )
    _ADAPTER_STATUS.clear()
    _ADAPTER_STATUS.update(
        _status_payload(
            ok=False,
            reason=fail_reason,
            provider_key="unavailable",
            live=False,
            configured_email=user_email or None,
            user_email=user_email or None,
            has_dedicated_credentials=has_creds if fail_reason != "family_gmail_rejected" else False,
            has_dedicated_token=has_token if fail_reason != "family_gmail_rejected" else False,
        )
    )
    return _ADAPTER


def _try_privateemail_adapter() -> HistorianEmailAdapter:
    from memorybox.historian_capture.privateemail import (
        NamecheapPrivateEmailAdapter,
        load_privateemail_config,
        probe_privateemail,
    )

    cfg = load_privateemail_config()
    user_email = str(cfg.get("username") or "").strip()
    if cfg.get("family_gmail_rejected"):
        return _fail_adapter("family_gmail_rejected", user_email=user_email)
    if not user_email or "@" not in user_email:
        return _fail_adapter("missing_user_email")
    has_password = bool(cfg.get("has_password"))
    if not has_password:
        return _fail_adapter(
            "missing_credentials",
            user_email=user_email,
            has_creds=False,
        )
    probe = probe_privateemail(cfg)
    if not probe.get("ok"):
        return _fail_adapter(
            str(probe.get("reason") or "unavailable"),
            user_email=user_email,
            has_creds=True,
        )
    adapter = NamecheapPrivateEmailAdapter(cfg)
    _ADAPTER_STATUS.clear()
    _ADAPTER_STATUS.update(
        _status_payload(
            ok=True,
            reason="live_ok",
            provider_key=adapter.provider_key,
            live=True,
            configured_email=user_email,
            transport_email=user_email,
            user_email=user_email,
            has_dedicated_credentials=True,
        )
    )
    return adapter


def _try_gmail_adapter() -> HistorianEmailAdapter:
    from memorybox.historian_capture.gmail_live import (
        MarvinGmailHistorianEmailAdapter,
        build_historian_gmail_client,
        load_historian_gmail_config,
        resolve_historian_user_email,
    )

    cfg = load_historian_gmail_config()
    gmail = cfg.get("gmail") or {}
    creds_path = Path(gmail.get("credentials_file") or "")
    token_path = Path(gmail.get("token_file") or "")
    user_email = resolve_historian_user_email(cfg)
    family = _is_family_gmail_path(creds_path) or _is_family_gmail_path(token_path)
    if family:
        return _fail_adapter("family_gmail_rejected", user_email=user_email)
    if not user_email or "@" not in user_email:
        return _fail_adapter("missing_user_email")
    has_creds = creds_path.is_file()
    has_token = token_path.is_file()
    if not has_creds:
        return _fail_adapter(
            "missing_credentials",
            user_email=user_email,
            has_creds=False,
            has_token=has_token,
        )
    if not has_token:
        return _fail_adapter(
            "missing_token",
            user_email=user_email,
            has_creds=True,
            has_token=False,
        )
    try:
        client = build_historian_gmail_client(cfg)
    except ImportError:
        return _fail_adapter(
            "missing_transport",
            user_email=user_email,
            has_creds=True,
            has_token=True,
        )
    except Exception:
        return _fail_adapter(
            "unavailable",
            user_email=user_email,
            has_creds=True,
            has_token=True,
        )
    transport_email = user_email
    try:
        profile = client.service.users().getProfile(userId="me").execute()
        profile_email = (profile or {}).get("emailAddress") or ""
        if profile_email and "@" in profile_email:
            transport_email = profile_email
            user_email = profile_email
    except Exception:
        pass
    adapter = MarvinGmailHistorianEmailAdapter(client, user_email=user_email)
    _ADAPTER_STATUS.clear()
    _ADAPTER_STATUS.update(
        _status_payload(
            ok=True,
            reason="live_ok",
            provider_key="marvin_historian_gmail",
            live=True,
            configured_email=resolve_historian_user_email(cfg),
            transport_email=transport_email,
            user_email=transport_email,
            has_dedicated_credentials=True,
            has_dedicated_token=True,
        )
    )
    return adapter


def get_email_adapter() -> HistorianEmailAdapter:
    global _ADAPTER
    if _ADAPTER is not None:
        return _ADAPTER
    mode = (
        os.environ.get("MEMORYBOX_HC_EMAIL_PROVIDER")
        or os.environ.get("MEMORYBOX_GC_EMAIL_PROVIDER")
        or "privateemail"
    ).strip().lower()
    if mode == "fake":
        _ADAPTER = FakeHistorianEmailAdapter()
        _ADAPTER_STATUS.clear()
        _ADAPTER_STATUS.update(
            _status_payload(
                ok=True,
                reason="fake_ok",
                provider_key="fake_historian_email",
                live=False,
                transport_email=HC_MAILBOX,
            )
        )
        return _ADAPTER

    if mode in ("privateemail", "namecheap", "imap", "imap_smtp"):
        _ADAPTER = _try_privateemail_adapter()
        return _ADAPTER

    if mode in ("gmail", "marvin", "live"):
        try:
            _ADAPTER = _try_gmail_adapter()
        except ImportError:
            _ADAPTER = _fail_adapter("missing_transport")
        except Exception:
            _ADAPTER = _fail_adapter("unavailable")
        return _ADAPTER

    if mode == "auto":
        from memorybox.historian_capture.privateemail import load_privateemail_config

        pe = load_privateemail_config()
        pe_ready = (
            not pe.get("family_gmail_rejected")
            and bool(pe.get("has_password"))
            and "@" in str(pe.get("username") or "")
        )
        if pe_ready:
            _ADAPTER = _try_privateemail_adapter()
            return _ADAPTER
        if pe.get("family_gmail_rejected"):
            _ADAPTER = _fail_adapter("family_gmail_rejected")
            return _ADAPTER
        try:
            _ADAPTER = _try_gmail_adapter()
        except ImportError:
            _ADAPTER = _fail_adapter("missing_transport")
        except Exception:
            _ADAPTER = _fail_adapter("unavailable")
        return _ADAPTER

    _ADAPTER = _fail_adapter("configuration_invalid")
    return _ADAPTER
