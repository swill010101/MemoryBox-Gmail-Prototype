"""Guided Capture email adapter — Marvin Gmail lineage behind a Capture-channel interface.

Do not invent a second email architecture. Harness uses FakeGuidedEmailAdapter;
FlightSim uses Marvin live Gmail client when configured.
"""
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

# Reuse Marvin reply extraction (derived text only; raw remains authoritative)
from application.marvin_capture.plus_address import (
    build_plus_address,
    parse_plus_tag,
)
from application.marvin_capture.reply_extract import extract_reply_text, make_subject

GC_PLUS_PREFIX = "gc-"
SUBJECT_TOKEN_RE = re.compile(r"\[MB-GC-([A-Za-z0-9]+)\]", re.IGNORECASE)


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
    has_audio: bool = False
    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    ambiguous: bool = False
    raw_headers: dict[str, str] = field(default_factory=dict)
    skip_reason: str | None = None
    in_reply_to: str | None = None


GC_OUTBOUND_MARKER = "— MemoryBox Guided Capture"
GC_OUTBOUND_PLEASE_REPLY = "(Please reply to this email.)"


def _is_pure_outbound_template(text: str) -> bool:
    """True when text is essentially only our question email body."""
    t = (text or "").strip()
    if not t:
        return False
    if GC_OUTBOUND_MARKER not in t or GC_OUTBOUND_PLEASE_REPLY not in t:
        return False
    # Real replies usually have content before the quoted "Hi Name," / marker.
    m = re.search(r"(?m)^Hi .+,\s*$", t)
    if m and m.start() > 15:
        return False
    if t.find(GC_OUTBOUND_MARKER) > 80:
        return False
    return bool(re.match(r"(?is)^Hi\s+", t)) or len(t) < 600


def looks_like_gc_outbound_body(text: str | None) -> bool:
    """True when body is our outbound question template, not a respondent reply.

    Quoted originals inside a real reply still contain the marker — those must
    NOT be treated as outbound echoes (that was skipping good Poll results).
    """
    return _is_pure_outbound_template((text or "").strip())


def refine_gc_reply_text(text: str | None) -> str:
    """Drop quoted outbound question template when a real reply precedes it."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t or GC_OUTBOUND_MARKER not in t:
        return t
    # Common: reply text, then blank line, then "Hi Name," + question + marker
    m = re.search(r"\n\nHi [^\n]+,\n\n", t)
    if m and GC_OUTBOUND_MARKER in t[m.start() :]:
        head = t[: m.start()].strip()
        if head:
            return head
    # Gmail often leaves "On ... wrote:" — extract_reply_text usually cuts that;
    # if marker remains mid-body, keep prefix when it's clearly a reply.
    idx = t.find(GC_OUTBOUND_MARKER)
    if idx > 20:
        head = t[:idx].strip()
        # Drop a trailing quoted "Hi Name," block if present
        hm = re.search(r"\n\nHi [^\n]+,\s*$", head)
        if hm:
            head = head[: hm.start()].strip()
        if head and not _is_pure_outbound_template(head):
            return head
    return t



class GuidedEmailAdapter(Protocol):
    def send_question(
        self,
        *,
        to_email: str,
        respondent_name: str,
        question_body: str,
        correlation_token: str,
        campaign_title: str | None = None,
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
        if tag and tag.lower().startswith(GC_PLUS_PREFIX):
            return tag[len(GC_PLUS_PREFIX) :].lower()
    if headers:
        for key in ("delivered-to", "x-original-to", "to", "Delivered-To", "To"):
            raw = headers.get(key) or ""
            for part in re.split(r",\s*", raw):
                tag = parse_plus_tag(part.strip())
                if tag and tag.lower().startswith(GC_PLUS_PREFIX):
                    return tag[len(GC_PLUS_PREFIX) :].lower()
    return None


def _preserve_bytes(data: bytes, *, stem: str, root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{stem}.eml"
    path.write_bytes(data)
    return path.resolve().as_uri()


class FakeGuidedEmailAdapter:
    """In-memory outbound/inbound for prove-guided-capture (no live Gmail)."""

    provider_key = "fake_guided_email"

    def __init__(self, *, fail_next_send: bool = False, user_email: str = "owner@example.com") -> None:
        self.user_email = user_email
        self.sent: list[dict[str, Any]] = []
        self.inbox: list[dict[str, Any]] = []
        self.processed: set[str] = set()
        self.fail_next_send = fail_next_send
        self._root = Path.cwd() / ".memorybox_gc_fake_mail"
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
    ) -> OutboundSendResult:
        if self.fail_next_send:
            self.fail_next_send = False
            return OutboundSendResult(ok=False, fail_detail="synthetic_send_failure")
        reply_to = build_plus_address(self.user_email, f"{GC_PLUS_PREFIX}{correlation_token}")
        subject = make_subject("GC", campaign_title or "MemoryBox question", correlation_token)
        # Override Marvin default token placement — keep [MB-GC-token]
        subject = f"[MB-GC-{correlation_token}] {campaign_title or 'MemoryBox question'}"
        body = (
            f"Hi {respondent_name},\n\n"
            f"{question_body}\n\n"
            f"— MemoryBox Guided Capture\n"
            f"(Reply to this message; keep the subject if possible.)\n"
        )
        mid = self._next_id("out")
        tid = self._next_id("thr")
        raw = f"Message-ID: {mid}\nTo: {to_email}\nReply-To: {reply_to}\nSubject: {subject}\n\n{body}".encode()
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
            }
        )
        return OutboundSendResult(
            ok=True,
            outbound_message_id=mid,
            thread_id=tid,
            preserved_raw_uri=uri,
            reply_to=reply_to,
        )

    def inject_reply(
        self,
        *,
        correlation_token: str | None,
        from_addr: str,
        text: str,
        subject: str | None = None,
        inbound_message_id: str | None = None,
        audio_bytes: bytes | None = None,
        audio_filename: str | None = None,
        ambiguous: bool = False,
    ) -> str:
        mid = inbound_message_id or self._next_id("in")
        subj = subject or (
            f"[MB-GC-{correlation_token}] Re: MemoryBox question"
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
                "audio_bytes": audio_bytes,
                "audio_filename": audio_filename,
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
            out.append(
                InboundMailItem(
                    inbound_message_id=mid,
                    correlation_token=item.get("correlation_token"),
                    from_addr=item["from_addr"],
                    subject=item["subject"],
                    extracted_text=item["text"],
                    preserved_raw_uri=item["uri"],
                    has_audio=bool(item.get("audio_bytes")),
                    audio_bytes=item.get("audio_bytes"),
                    audio_filename=item.get("audio_filename"),
                    ambiguous=bool(item.get("ambiguous")),
                )
            )
        return out

    def mark_processed(self, inbound_message_id: str) -> None:
        self.processed.add(inbound_message_id)


class MarvinGmailGuidedEmailAdapter:
    """Live Gmail via application.marvin_capture.gmail_client (FlightSim).

    Sends as the authenticated owner (`userId=me`) so mail appears in the owner's
    Gmail Sent. Polls the same account inbox for replies (plus-tag / [MB-GC-token]).
    """

    provider_key = "marvin_gmail"

    def __init__(self, client: Any, *, user_email: str, preserve_root: Path | None = None) -> None:
        self.client = client
        self.user_email = user_email
        self._root = preserve_root or Path(
            os.environ.get("MEMORYBOX_GC_MAIL_DIR", str(Path.cwd() / ".memorybox_gc_mail"))
        )
        self._label = "MemoryBox/GC-Processed"

    def send_question(
        self,
        *,
        to_email: str,
        respondent_name: str,
        question_body: str,
        correlation_token: str,
        campaign_title: str | None = None,
    ) -> OutboundSendResult:
        reply_to = build_plus_address(self.user_email, f"{GC_PLUS_PREFIX}{correlation_token}")
        subject = f"[MB-GC-{correlation_token}] {campaign_title or 'MemoryBox question'}"
        body = (
            f"Hi {respondent_name},\n\n"
            f"{question_body}\n\n"
            f"— MemoryBox Guided Capture\n"
            f"(Please reply to this email.)\n"
        )
        try:
            result = self.client.send_message(
                to=to_email,
                subject=subject,
                body=body,
                reply_to=reply_to,
            )
        except Exception as exc:  # noqa: BLE001
            return OutboundSendResult(ok=False, fail_detail=str(exc))
        mid = str(result.get("id") or "")
        tid = str(result.get("threadId") or "") or None
        raw = f"To: {to_email}\nReply-To: {reply_to}\nSubject: {subject}\n\n{body}".encode()
        uri = _preserve_bytes(raw, stem=mid or str(uuid4()), root=self._root)
        return OutboundSendResult(
            ok=True,
            outbound_message_id=mid or None,
            thread_id=tid,
            preserved_raw_uri=uri,
            reply_to=reply_to,
        )

    def poll_inbound(self) -> list[InboundMailItem]:
        """Poll the owner's Gmail inbox for Guided Capture replies.

        Exclude Sent / outbound echoes. Subject [MB-GC-] alone would otherwise
        ingest the question email as a "response" (esp. send-to-self tests).
        """
        local, domain = self.user_email.split("@", 1)
        label_query = self._label.replace("/", "-")
        # Inbox GC traffic. Do NOT use -in:sent: self-replies (and many Reply
        # flows) carry both INBOX and SENT and would be invisible to Poll.
        # Outbound echoes are filtered by known outbound ids + pure-template detect.
        q = (
            f"in:inbox -in:trash -label:{label_query} "
            f"(to:{local}+{GC_PLUS_PREFIX}*@{domain} OR "
            f"deliveredto:{local}+{GC_PLUS_PREFIX}*@{domain} OR "
            f"subject:[MB-GC- OR subject:Re: [MB-GC-)"
        )
        try:
            label_id = self.client.ensure_label(self._label)
            if hasattr(self.client, "service"):
                result = (
                    self.client.service.users()
                    .messages()
                    .list(userId="me", q=q, maxResults=50)
                    .execute()
                )
                msgs = result.get("messages") or []
            else:
                msgs = self.client.list_unread_or_unprocessed(
                    processed_label=self._label,
                    user_email=self.user_email,
                    query_extra=(
                        f"in:inbox "
                        f"(to:{local}+{GC_PLUS_PREFIX}*@{domain} OR subject:[MB-GC-)"
                    ),
                )
        except Exception:
            return []
        out: list[InboundMailItem] = []
        for meta in msgs or []:
            mid = str(meta.get("id") or "")
            if not mid:
                continue
            try:
                raw = self.client.get_message_raw(mid)
            except Exception:
                continue
            msg = message_from_bytes(raw, policy=email_default)
            subject = str(msg.get("Subject") or "")
            from_addr = str(msg.get("From") or "")
            in_reply_to = str(msg.get("In-Reply-To") or "") or None
            headers = {
                "to": str(msg.get("To") or ""),
                "delivered-to": str(msg.get("Delivered-To") or ""),
                "x-original-to": str(msg.get("X-Original-To") or ""),
                "from": from_addr,
                "in-reply-to": in_reply_to or "",
            }
            token = extract_correlation_token(
                subject=subject,
                to_addrs=[headers["to"], headers["delivered-to"], headers["x-original-to"]],
                headers=headers,
            )
            body = ""
            audio_bytes = None
            audio_filename = None
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition") or "")
                    if ctype.startswith("audio/") or (
                        "attachment" in disp
                        and any(
                            (part.get_filename() or "").lower().endswith(ext)
                            for ext in (".webm", ".wav", ".mp3", ".m4a", ".ogg")
                        )
                    ):
                        try:
                            audio_bytes = part.get_payload(decode=True)
                            audio_filename = part.get_filename() or "voice.webm"
                        except Exception:
                            pass
                    elif ctype == "text/plain" and not body:
                        try:
                            body = part.get_content()
                        except Exception:
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body = payload.decode("utf-8", errors="replace")
                    elif ctype == "text/html" and not body:
                        try:
                            body = extract_reply_text(part.get_content(), is_html=True)
                        except Exception:
                            pass
            else:
                try:
                    body = msg.get_content()
                except Exception:
                    payload = msg.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="replace")
            extracted = refine_gc_reply_text(
                extract_reply_text(body or "", is_html=False)
            )
            uri = _preserve_bytes(raw, stem=mid, root=self._root)
            skip_reason = None
            if looks_like_gc_outbound_body(extracted) and not in_reply_to:
                skip_reason = "outbound_echo"
            elif looks_like_gc_outbound_body(extracted) and len(extracted.strip()) < 120:
                skip_reason = "outbound_echo"
            out.append(
                InboundMailItem(
                    inbound_message_id=mid,
                    correlation_token=token,
                    from_addr=from_addr,
                    subject=subject,
                    extracted_text=extracted,
                    preserved_raw_uri=uri,
                    thread_id=str(meta.get("threadId") or "") or None,
                    has_audio=bool(audio_bytes),
                    audio_bytes=audio_bytes,
                    audio_filename=audio_filename,
                    ambiguous=token is None,
                    raw_headers=headers,
                    skip_reason=skip_reason,
                    in_reply_to=in_reply_to,
                )
            )
            _ = label_id
        return out

    def mark_processed(self, inbound_message_id: str) -> None:
        try:
            lid = self.client.ensure_label(self._label)
            self.client.apply_label(inbound_message_id, lid)
        except Exception:
            pass


_ADAPTER: GuidedEmailAdapter | None = None
_ADAPTER_STATUS: dict[str, Any] = {
    "provider_key": None,
    "ok": False,
    "detail": "not_initialized",
    "user_email": None,
    "live": False,
}


def set_email_adapter(adapter: GuidedEmailAdapter | None) -> None:
    global _ADAPTER
    _ADAPTER = adapter
    if adapter is None:
        _ADAPTER_STATUS.update(
            {
                "provider_key": None,
                "ok": False,
                "detail": "cleared",
                "user_email": None,
                "live": False,
            }
        )


def _is_placeholder_email(email: str) -> bool:
    e = (email or "").strip().lower()
    if not e or "@" not in e:
        return True
    return e.startswith("your_gmail@") or e.startswith("you@") or "example.com" in e


def _owner_email_from_memorybox_json() -> str | None:
    path = _REPO_ROOT / "config" / "memorybox.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        emails = (((data.get("memory_box") or {}).get("owner") or {}).get("emails")) or []
        for e in emails:
            if isinstance(e, str) and "@" in e and not _is_placeholder_email(e):
                return e.strip()
    except Exception:
        return None
    return None


def resolve_guided_capture_user_email(cfg: dict[str, Any] | None = None) -> str | None:
    """Owner Gmail for send/Reply-To — same Marvin account, never a separate mailbox."""
    env = (os.environ.get("MEMORYBOX_GC_USER_EMAIL") or "").strip()
    if env and not _is_placeholder_email(env):
        return env
    if cfg is None:
        try:
            from application.marvin_capture.config import load_config

            cfg = load_config()
        except Exception:
            cfg = {}
    raw = ((cfg or {}).get("gmail") or {}).get("user_email") or ""
    if raw and not _is_placeholder_email(str(raw)):
        return str(raw).strip()
    return _owner_email_from_memorybox_json()


class UnavailableGuidedEmailAdapter:
    """Visible degrade — do not pretend Sent when live Gmail is not wired."""

    provider_key = "unavailable"

    def __init__(self, detail: str, *, user_email: str | None = None) -> None:
        self.detail = detail
        self.user_email = user_email or ""

    def send_question(
        self,
        *,
        to_email: str,
        respondent_name: str,
        question_body: str,
        correlation_token: str,
        campaign_title: str | None = None,
    ) -> OutboundSendResult:
        return OutboundSendResult(ok=False, fail_detail=self.detail)

    def poll_inbound(self) -> list[InboundMailItem]:
        return []

    def mark_processed(self, inbound_message_id: str) -> None:
        return


def email_adapter_status() -> dict[str, Any]:
    """Snapshot for UI / tick — whether owner Gmail is live or degraded."""
    get_email_adapter()  # ensure initialized
    return dict(_ADAPTER_STATUS)


def get_email_adapter() -> GuidedEmailAdapter:
    global _ADAPTER
    if _ADAPTER is not None:
        return _ADAPTER
    mode = (os.environ.get("MEMORYBOX_GC_EMAIL_PROVIDER") or "auto").strip().lower()
    if mode == "fake":
        _ADAPTER = FakeGuidedEmailAdapter()
        _ADAPTER_STATUS.update(
            {
                "provider_key": "fake_guided_email",
                "ok": True,
                "detail": "MEMORYBOX_GC_EMAIL_PROVIDER=fake (harness only — no real Gmail)",
                "user_email": _ADAPTER.user_email,
                "live": False,
            }
        )
        return _ADAPTER

    last_err = ""
    try:
        from application.marvin_capture.config import load_config
        from application.marvin_capture.gmail_client import build_live_gmail_client

        cfg = load_config()
        gmail = cfg.get("gmail") or {}
        creds_path = Path(gmail.get("credentials_file") or "")
        token_path = Path(gmail.get("token_file") or "")
        user_email = resolve_guided_capture_user_email(cfg)
        has_creds = creds_path.is_file()
        has_token = token_path.is_file()

        if mode in ("auto", "marvin", "gmail") and has_creds and has_token:
            if not user_email:
                last_err = (
                    "Marvin Gmail token/credentials found, but user_email is missing "
                    "or still a placeholder in config/marvin_capture.json. "
                    "Set gmail.user_email to your real address (e.g. swill01@gmail.com) "
                    "or MEMORYBOX_GC_USER_EMAIL."
                )
            else:
                client = build_live_gmail_client(cfg)
                # Prefer live profile address when placeholder was wrong
                try:
                    profile = client.service.users().getProfile(userId="me").execute()
                    profile_email = (profile or {}).get("emailAddress") or ""
                    if profile_email and not _is_placeholder_email(profile_email):
                        user_email = profile_email
                except Exception:
                    pass
                _ADAPTER = MarvinGmailGuidedEmailAdapter(client, user_email=user_email)
                _ADAPTER_STATUS.update(
                    {
                        "provider_key": "marvin_gmail",
                        "ok": True,
                        "detail": (
                            f"Live owner Gmail via Marvin Capture token "
                            f"({user_email}); send goes to Sent; poll owner inbox"
                        ),
                        "user_email": user_email,
                        "live": True,
                    }
                )
                return _ADAPTER
        elif mode in ("marvin", "gmail"):
            last_err = (
                f"MEMORYBOX_GC_EMAIL_PROVIDER={mode} but credentials/token missing "
                f"(creds={has_creds} token={has_token} at {creds_path} / {token_path})"
            )
        elif mode == "auto" and not (has_creds and has_token):
            last_err = (
                "No Marvin Gmail credentials/token under config/; "
                "refusing silent fake send. Copy POC gmail_credentials.json + "
                "gmail_token.json and set user_email, or set "
                "MEMORYBOX_GC_EMAIL_PROVIDER=fake for harness only."
            )
    except Exception as exc:  # noqa: BLE001
        last_err = f"Marvin Gmail adapter failed: {exc}"

    # Visible degrade — never pretend outbound succeeded on fake when owner expects Gmail
    detail = last_err or "Guided Capture email provider unavailable"
    _ADAPTER = UnavailableGuidedEmailAdapter(detail, user_email=resolve_guided_capture_user_email())
    _ADAPTER_STATUS.update(
        {
            "provider_key": "unavailable",
            "ok": False,
            "detail": detail,
            "user_email": getattr(_ADAPTER, "user_email", None) or None,
            "live": False,
        }
    )
    return _ADAPTER
