"""Live Gmail adapter for Historian Capture mailbox (memorybox@marvinbot.net)."""
from __future__ import annotations

import json
import os
import re
from email import message_from_bytes
from email.policy import default as email_default
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.historian_capture.email_adapter import (
    HC_MAILBOX,
    HC_OUTBOUND_MARKER,
    HC_PLUS_PREFIX,
    HC_REMINDER_MARKER,
    InboundMailItem,
    OutboundSendResult,
    _preserve_bytes,
    extract_correlation_token,
)

try:
    from application.marvin_capture.plus_address import build_plus_address
    from application.marvin_capture.reply_extract import extract_reply_text
except ImportError:  # pragma: no cover

    def build_plus_address(local: str, domain: str, tag: str) -> str:
        return f"{local}+{tag}@{domain}"

    def extract_reply_text(raw: str | bytes, *, is_html: bool = False) -> str:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        return (raw or "").strip()

_REPO_ROOT = Path(__file__).resolve().parents[2]
HC_PROCESSED_LABEL = "MemoryBox/HC-Processed"


def refine_hc_reply_text(text: str | None) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t or HC_OUTBOUND_MARKER not in t:
        return t
    m = re.search(r"\n\nHi [^\n]+,\n\n", t)
    if m and HC_OUTBOUND_MARKER in t[m.start() :]:
        head = t[: m.start()].strip()
        if head:
            return head
    idx = t.find(HC_OUTBOUND_MARKER)
    if idx > 20:
        return t[:idx].strip()
    return t


def looks_like_hc_outbound_body(text: str | None) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return HC_OUTBOUND_MARKER in t and len(t) < 800


def resolve_historian_user_email(cfg: dict[str, Any] | None = None) -> str:
    env = (os.environ.get("MEMORYBOX_HC_USER_EMAIL") or "").strip()
    if env and "@" in env:
        return env
    if cfg:
        raw = ((cfg.get("gmail") or {}).get("user_email") or "").strip()
        if raw and "@" in raw:
            return raw
    return HC_MAILBOX


def load_historian_gmail_config() -> dict[str, Any]:
    """Historian Capture Gmail OAuth paths — separate from owner Guided Capture."""
    cfg_path = (
        os.environ.get("MEMORYBOX_HC_CONFIG")
        or str(_REPO_ROOT / "config" / "historian_capture.json")
    )
    gmail: dict[str, Any] = {
        "credentials_file": os.environ.get(
            "MEMORYBOX_HC_GMAIL_CREDENTIALS",
            str(_REPO_ROOT / "config" / "historian_capture_gmail_credentials.json"),
        ),
        "token_file": os.environ.get(
            "MEMORYBOX_HC_GMAIL_TOKEN",
            str(_REPO_ROOT / "config" / "historian_capture_gmail_token.json"),
        ),
        "user_email": resolve_historian_user_email(),
        "scopes": [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
        ],
    }
    path = Path(cfg_path)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            gmail.update(data.get("gmail") or {})
        except Exception:
            pass
    return {"gmail": gmail}


def build_historian_gmail_client(cfg: dict[str, Any] | None = None) -> Any:
    cfg = cfg or load_historian_gmail_config()
    try:
        from application.marvin_capture.gmail_client import build_live_gmail_client

        return build_live_gmail_client(cfg)
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "application.marvin_capture required for live Historian Gmail on FlightSim"
        ) from exc


class MarvinGmailHistorianEmailAdapter:
    """Live Gmail for dedicated Historian Capture mailbox — label only, never Trash."""

    provider_key = "marvin_historian_gmail"

    def __init__(self, client: Any, *, user_email: str, preserve_root: Path | None = None) -> None:
        self.client = client
        self.user_email = user_email
        self._root = preserve_root or Path(
            os.environ.get(
                "MEMORYBOX_HC_MAIL_DIR",
                str(Path.cwd() / ".memorybox_hc_mail"),
            )
        )
        self._label = HC_PROCESSED_LABEL
        self.last_poll_debug: dict[str, Any] = {}

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
        local, domain = self.user_email.split("@", 1)
        reply_to = build_plus_address(local, domain, f"{HC_PLUS_PREFIX}{correlation_token}")
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
        try:
            result = self.client.send_message(to=to_email, subject=subject, body=body)
        except Exception as exc:  # noqa: BLE001
            return OutboundSendResult(ok=False, fail_detail=str(exc))
        mid = str(result.get("id") or "")
        raw = f"To: {to_email}\nSubject: {subject}\n\n{body}".encode()
        uri = _preserve_bytes(raw, stem=mid or str(uuid4()), root=self._root)
        return OutboundSendResult(
            ok=True,
            outbound_message_id=mid or None,
            preserved_raw_uri=uri,
        )

    def poll_inbound(self) -> list[InboundMailItem]:
        """Poll Capture inbox — apply processed label; never Trash."""
        local, _domain = self.user_email.split("@", 1)
        label_query = self._label.replace("/", "-")
        queries = [
            (
                f"in:inbox newer_than:30d -in:trash -label:{label_query} "
                f"to:({local}+{HC_PLUS_PREFIX})"
            ),
            (
                f"in:inbox newer_than:30d -in:trash -label:{label_query} "
                f'subject:"[MB-HC-"'
            ),
            (
                f"in:inbox newer_than:30d -in:trash -label:{label_query} "
                f"deliveredto:({local}+{HC_PLUS_PREFIX})"
            ),
        ]
        self.last_poll_debug = {"queries": queries, "query_hits": {}, "error": None}
        try:
            label_id = self.client.ensure_label(self._label)
        except Exception as exc:  # noqa: BLE001
            self.last_poll_debug["error"] = f"ensure_label: {exc}"
            return []

        seen: set[str] = set()
        msgs: list[dict[str, Any]] = []
        if not hasattr(self.client, "service"):
            self.last_poll_debug["error"] = "gmail client has no service (not live)"
            return []
        for q in queries:
            try:
                result = (
                    self.client.service.users()
                    .messages()
                    .list(userId="me", q=q, maxResults=50)
                    .execute()
                )
                batch = result.get("messages") or []
                self.last_poll_debug["query_hits"][q] = len(batch)
                for m in batch:
                    mid = str(m.get("id") or "")
                    if mid and mid not in seen:
                        seen.add(mid)
                        msgs.append(m)
            except Exception as exc:  # noqa: BLE001
                self.last_poll_debug["query_hits"][q] = f"error: {exc}"

        out: list[InboundMailItem] = []
        for meta in msgs:
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
                "message-id": str(msg.get("Message-ID") or mid),
            }
            token = extract_correlation_token(
                subject=subject,
                to_addrs=[headers["to"], headers["delivered-to"], headers["x-original-to"]],
                headers=headers,
            )
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain" and not body:
                        try:
                            body = part.get_content()
                        except Exception:
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body = payload.decode("utf-8", errors="replace")
            else:
                try:
                    body = msg.get_content()
                except Exception:
                    payload = msg.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="replace")
            extracted = refine_hc_reply_text(
                extract_reply_text(body or "", is_html=False)
            )
            uri = _preserve_bytes(raw, stem=mid, root=self._root)
            skip_reason = None
            if looks_like_hc_outbound_body(extracted) and not in_reply_to:
                skip_reason = "outbound_echo"
            elif looks_like_hc_outbound_body(extracted) and len(extracted.strip()) < 120:
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
                    ambiguous=token is None,
                    raw_headers=headers,
                    skip_reason=skip_reason,
                    in_reply_to=in_reply_to,
                    raw_bytes=raw,
                )
            )
            _ = label_id
        self.last_poll_debug["merged"] = len(msgs)
        return out

    def mark_processed(self, inbound_message_id: str) -> None:
        """Apply processed label only — inbound mail stays in mailbox (evidence)."""
        try:
            lid = self.client.ensure_label(self._label)
            self.client.apply_label(inbound_message_id, lid)
        except Exception:
            pass

    def connection_probe(self) -> dict[str, Any]:
        """Stage 1: verify Gmail profile + label without sending mail."""
        out: dict[str, Any] = {"ok": False, "user_email": self.user_email}
        try:
            profile = self.client.service.users().getProfile(userId="me").execute()
            out["profile_email"] = (profile or {}).get("emailAddress")
            out["ok"] = True
            lid = self.client.ensure_label(self._label)
            out["processed_label"] = self._label
            out["processed_label_id"] = lid
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)
        return out
