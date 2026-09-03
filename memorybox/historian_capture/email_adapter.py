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
        for key in ("delivered-to", "x-original-to", "to", "Delivered-To", "To"):
            raw = headers.get(key) or ""
            for part in re.split(r",\s*", raw):
                tag = parse_plus_tag(part.strip())
                if tag and tag.lower().startswith(HC_PLUS_PREFIX):
                    return tag[len(HC_PLUS_PREFIX) :].lower()
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
        subject = f"[MB-HC-{correlation_token}] {campaign_title or 'MemoryBox question'}"
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
        token_part = f"[MB-HC-{correlation_token}] " if correlation_token else ""
        subject = f"{token_part}Thank you — MemoryBox"
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


_ADAPTER: HistorianEmailAdapter | None = None
_ADAPTER_STATUS: dict[str, Any] = {
    "provider_key": None,
    "ok": False,
    "detail": "not_initialized",
    "user_email": HC_MAILBOX,
    "live": False,
}


def set_email_adapter(adapter: HistorianEmailAdapter | None) -> None:
    global _ADAPTER
    _ADAPTER = adapter
    if adapter is None:
        _ADAPTER_STATUS.update(
            {
                "provider_key": None,
                "ok": False,
                "detail": "cleared",
                "user_email": HC_MAILBOX,
                "live": False,
            }
        )


def email_adapter_status() -> dict[str, Any]:
    get_email_adapter()
    return dict(_ADAPTER_STATUS)


def get_email_adapter() -> HistorianEmailAdapter:
    global _ADAPTER
    if _ADAPTER is not None:
        return _ADAPTER
    mode = (os.environ.get("MEMORYBOX_HC_EMAIL_PROVIDER") or os.environ.get("MEMORYBOX_GC_EMAIL_PROVIDER") or "auto").strip().lower()
    if mode == "fake":
        _ADAPTER = FakeHistorianEmailAdapter()
        _ADAPTER_STATUS.update(
            {
                "provider_key": "fake_historian_email",
                "ok": True,
                "detail": "MEMORYBOX_HC_EMAIL_PROVIDER=fake (harness only)",
                "user_email": HC_MAILBOX,
                "live": False,
            }
        )
        return _ADAPTER

    last_err = ""
    if mode in ("auto", "marvin", "gmail", "live"):
        try:
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
            has_creds = creds_path.is_file()
            has_token = token_path.is_file()

            if has_creds and has_token:
                client = build_historian_gmail_client(cfg)
                try:
                    profile = client.service.users().getProfile(userId="me").execute()
                    profile_email = (profile or {}).get("emailAddress") or ""
                    if profile_email and "@" in profile_email:
                        user_email = profile_email
                except Exception:
                    pass
                _ADAPTER = MarvinGmailHistorianEmailAdapter(client, user_email=user_email)
                _ADAPTER_STATUS.update(
                    {
                        "provider_key": "marvin_historian_gmail",
                        "ok": True,
                        "detail": (
                            f"Live Historian Capture Gmail ({user_email}); "
                            "poll uses label MemoryBox/HC-Processed — never Trash"
                        ),
                        "user_email": user_email,
                        "live": True,
                    }
                )
                return _ADAPTER
            if mode in ("marvin", "gmail", "live"):
                last_err = (
                    f"MEMORYBOX_HC_EMAIL_PROVIDER={mode} but credentials/token missing "
                    f"(creds={has_creds} token={has_token} at {creds_path} / {token_path})"
                )
            elif mode == "auto":
                last_err = (
                    "No Historian Capture Gmail credentials/token; "
                    "set MEMORYBOX_HC_GMAIL_CREDENTIALS + MEMORYBOX_HC_GMAIL_TOKEN "
                    "or MEMORYBOX_HC_EMAIL_PROVIDER=fake for harness."
                )
        except Exception as exc:  # noqa: BLE001
            last_err = f"Historian Gmail adapter failed: {exc}"

    detail = last_err or "Historian Capture email provider unavailable"
    _ADAPTER = UnavailableHistorianEmailAdapter(detail, user_email=HC_MAILBOX)
    _ADAPTER_STATUS.update(
        {
            "provider_key": "unavailable",
            "ok": False,
            "detail": detail,
            "user_email": HC_MAILBOX,
            "live": False,
        }
    )
    return _ADAPTER
