"""Namecheap Private Email IMAP/SMTP transport for Historian Capture."""
from __future__ import annotations

import imaplib
import json
import os
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.policy import default as email_default
from email.utils import formataddr, make_msgid
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.historian_capture.email_adapter import (
    FAMILY_GMAIL_FILENAMES,
    HC_MAILBOX,
    HC_OUTBOUND_MARKER,
    HC_PLUS_PREFIX,
    HC_REMINDER_MARKER,
    HC_TOKEN_HEADER,
    InboundMailItem,
    OutboundSendResult,
    _preserve_bytes,
    build_plus_address,
    extract_correlation_token,
    format_question_subject,
    format_thankyou_subject,
)
from memorybox.historian_capture.gmail_live import (
    looks_like_hc_outbound_body,
    refine_hc_reply_text,
)

try:
    from application.marvin_capture.reply_extract import extract_reply_text
except ImportError:  # pragma: no cover
    def extract_reply_text(raw: str | bytes, *, is_html: bool = False) -> str:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        return (raw or "").strip()

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAP_HOST = "mail.privateemail.com"
DEFAULT_SMTP_HOST = "mail.privateemail.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_PORT = 465
DEFAULT_FROM_DISPLAY = "MemoryBox Historian for Tom"
DEFAULT_TIMEOUT_SEC = 20
PROVIDER_KEY = "namecheap_privateemail_imap_smtp"
PLACEHOLDER_PASSWORDS = frozenset({"", "changeme", "your-app-password", "REDACTED"})

SKIP_FOLDER_NAMES = frozenset(
    {
        "sent",
        "sent items",
        "sent messages",
        "trash",
        "deleted",
        "deleted items",
        "junk",
        "spam",
        "drafts",
        "draft",
        "outbox",
        "archive",
    }
)


def _timeout_sec() -> float:
    raw = (os.environ.get("MEMORYBOX_HC_MAIL_TIMEOUT") or "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return float(DEFAULT_TIMEOUT_SEC)


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _is_family_gmail_filename(path: Path) -> bool:
    return path.name.lower() in FAMILY_GMAIL_FILENAMES


def load_privateemail_config() -> dict[str, Any]:
    """Load dedicated Private Email settings. Never reads family Gmail files."""
    creds_path = Path(
        (
            os.environ.get("MEMORYBOX_HC_PRIVATEEMAIL_CREDENTIALS")
            or str(_REPO_ROOT / "config" / "historian_capture_privateemail_credentials.json")
        ).strip()
    )
    if _is_family_gmail_filename(creds_path):
        return {
            "username": "",
            "password": "",
            "imap_host": DEFAULT_IMAP_HOST,
            "imap_port": DEFAULT_IMAP_PORT,
            "smtp_host": DEFAULT_SMTP_HOST,
            "smtp_port": DEFAULT_SMTP_PORT,
            "from_display_name": DEFAULT_FROM_DISPLAY,
            "family_gmail_rejected": True,
            "credentials_path": creds_path,
            "has_password": False,
        }
    file_data: dict[str, Any] = {}
    if creds_path.is_file():
        try:
            parsed = json.loads(creds_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                file_data = parsed
        except Exception:
            file_data = {}
    username = (os.environ.get("MEMORYBOX_HC_USER_EMAIL") or "").strip() or str(
        file_data.get("username") or ""
    ).strip()
    password = (os.environ.get("MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD") or "").strip()
    if not password:
        password = str(file_data.get("password") or "").strip()
    imap_host = (
        (os.environ.get("MEMORYBOX_HC_IMAP_HOST") or "").strip()
        or str(file_data.get("imap_host") or "").strip()
        or DEFAULT_IMAP_HOST
    )
    smtp_host = (
        (os.environ.get("MEMORYBOX_HC_SMTP_HOST") or "").strip()
        or str(file_data.get("smtp_host") or "").strip()
        or DEFAULT_SMTP_HOST
    )
    imap_port = int(
        os.environ.get("MEMORYBOX_HC_IMAP_PORT")
        or file_data.get("imap_port")
        or DEFAULT_IMAP_PORT
    )
    smtp_port = int(
        os.environ.get("MEMORYBOX_HC_SMTP_PORT")
        or file_data.get("smtp_port")
        or DEFAULT_SMTP_PORT
    )
    display = (
        (os.environ.get("MEMORYBOX_HC_FROM_DISPLAY_NAME") or "").strip()
        or str(file_data.get("from_display_name") or "").strip()
        or DEFAULT_FROM_DISPLAY
    )
    return {
        "username": username,
        "password": password,
        "imap_host": imap_host,
        "imap_port": imap_port,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "from_display_name": display,
        "family_gmail_rejected": False,
        "credentials_path": creds_path,
        "has_password": bool(password) and password.lower() not in PLACEHOLDER_PASSWORDS,
    }


def _state_root() -> Path:
    home = (
        os.environ.get("MEMORYBOX_HC_STATE_DIR")
        or os.environ.get("MEMORYBOX_HOME")
        or os.environ.get("MEMORYBOX_DATA_DIR")
        or ""
    ).strip()
    if home:
        return Path(home)
    return _REPO_ROOT


def _mailbox_slug(email: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (email or "unconfigured").strip().lower()).strip("_")[:80] or "unconfigured"


def checkpoint_path(*, username: str | None = None) -> Path:
    override = (os.environ.get("MEMORYBOX_HC_IMAP_CHECKPOINT") or "").strip()
    if override:
        return Path(override)
    user = (username or "").strip()
    if not user:
        user = str(load_privateemail_config().get("username") or "unconfigured")
    name = f"imap_checkpoint__{PROVIDER_KEY}__{_mailbox_slug(user)}.json"
    return _state_root() / ".memorybox_hc_state" / name


def load_checkpoint(path: Path | None = None) -> dict[str, Any]:
    p = path or checkpoint_path()
    if not p.is_file():
        return {"processed_ids": [], "folders": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"processed_ids": [], "folders": {}}
        data.setdefault("processed_ids", [])
        data.setdefault("folders", {})
        return data
    except Exception:
        return {"processed_ids": [], "folders": {}}


def save_checkpoint(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or checkpoint_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    ids = list(dict.fromkeys(str(x) for x in (data.get("processed_ids") or []) if x))
    data = {"processed_ids": ids[-4000:], "folders": data.get("folders") or {}}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def classify_mail_error(exc: BaseException, *, stage: str) -> str:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "auth" in name or "authentication" in text or "invalid credentials" in text or "login" in text:
        if "timeout" not in text:
            return "authentication_failed"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "authentication_failed"
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in text:
        return "smtp_unavailable" if stage == "smtp" else "imap_unavailable"
    if isinstance(exc, smtplib.SMTPException) or stage == "smtp":
        return "smtp_unavailable"
    if isinstance(exc, imaplib.IMAP4.error) or stage == "imap":
        if "auth" in text or "login" in text:
            return "authentication_failed"
        return "imap_unavailable"
    return "unavailable"


def open_imap(cfg: dict[str, Any]) -> imaplib.IMAP4_SSL:
    client = imaplib.IMAP4_SSL(
        host=str(cfg["imap_host"]),
        port=int(cfg["imap_port"]),
        timeout=_timeout_sec(),
        ssl_context=_ssl_context(),
    )
    typ, _ = client.login(str(cfg["username"]), str(cfg["password"]))
    if typ != "OK":
        raise imaplib.IMAP4.error("IMAP login failed")
    return client


def open_smtp(cfg: dict[str, Any]) -> smtplib.SMTP_SSL:
    client = smtplib.SMTP_SSL(
        host=str(cfg["smtp_host"]),
        port=int(cfg["smtp_port"]),
        timeout=_timeout_sec(),
        context=_ssl_context(),
    )
    client.login(str(cfg["username"]), str(cfg["password"]))
    return client


def probe_privateemail(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_privateemail_config()
    imap_client = None
    smtp_client = None
    try:
        imap_client = open_imap(cfg)
        imap_client.select("INBOX", readonly=True)
        smtp_client = open_smtp(cfg)
        return {"ok": True, "reason": "live_ok"}
    except Exception as exc:
        stage = "smtp" if imap_client is not None else "imap"
        return {"ok": False, "reason": classify_mail_error(exc, stage=stage)}
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except Exception:
                pass
        if imap_client is not None:
            try:
                imap_client.logout()
            except Exception:
                pass


def _folder_leaf(name: str) -> str:
    cleaned = name.strip().strip('"').strip("'")
    for sep in ("/", ".", "\\"):
        if sep in cleaned:
            cleaned = cleaned.split(sep)[-1]
    return cleaned


def is_relevant_hc_folder(name: str) -> bool:
    raw = (name or "").strip().strip('"')
    if not raw:
        return False
    leaf = _folder_leaf(raw).lower()
    if leaf in SKIP_FOLDER_NAMES:
        return False
    if raw.upper() == "INBOX" or leaf == "inbox":
        return True
    return "hc-" in raw.lower()


def parse_list_folders(imap_client: Any) -> list[str]:
    typ, rows = imap_client.list()
    if typ != "OK" or not rows:
        return ["INBOX"]
    names: list[str] = []
    for row in rows:
        if row is None:
            continue
        text = row.decode("utf-8", errors="replace") if isinstance(row, bytes) else str(row)
        text = text.strip()
        if text.endswith('"') and text.count('"') >= 2:
            name = text.rsplit('"', 2)[-2]
        else:
            name = text.split()[-1].strip('"')
        name = name.strip()
        if name and name not in names:
            names.append(name)
    if "INBOX" not in names:
        names.insert(0, "INBOX")
    return names


def _uidvalidity(imap_client: Any) -> str:
    raw = imap_client.response("UIDVALIDITY")
    if not raw:
        return ""
    payload = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else raw
    if isinstance(payload, (list, tuple)) and payload:
        item = payload[0]
        if isinstance(item, bytes):
            return item.decode("ascii", errors="replace")
        return str(item or "")
    return str(payload or "")


def _search_uids(imap_client: Any, last_uid: int) -> list[int]:
    if last_uid > 0:
        typ, data = imap_client.uid("SEARCH", None, f"{last_uid + 1}:*")
    else:
        typ, data = imap_client.uid("SEARCH", None, "ALL")
    if typ != "OK" or not data or data[0] in (None, b""):
        return []
    blob = data[0]
    text = blob.decode("ascii", errors="replace") if isinstance(blob, bytes) else str(blob)
    out: list[int] = []
    for part in text.split():
        try:
            uid = int(part)
        except ValueError:
            continue
        if uid > last_uid:
            out.append(uid)
    return out


def _fetch_peek(imap_client: Any, uid: int) -> bytes | None:
    typ, data = imap_client.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if typ != "OK" or not data:
        return None
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
        if isinstance(item, bytes) and b"\n" in item:
            return item
    return None


def _parse_inbound(
    raw: bytes,
    *,
    folder: str,
    uid: int,
    uidvalidity: str,
    preserve_root: Path,
) -> InboundMailItem:
    from email import message_from_bytes

    msg = message_from_bytes(raw, policy=email_default)
    subject = str(msg.get("Subject") or "")
    from_addr = str(msg.get("From") or "")
    in_reply_to = str(msg.get("In-Reply-To") or "") or None
    rfc_id = str(msg.get("Message-ID") or "").strip()
    inbound_id = rfc_id or f"imap:{folder}:{uidvalidity}:{uid}"
    headers = {
        "to": str(msg.get("To") or ""),
        "delivered-to": str(msg.get("Delivered-To") or ""),
        "x-original-to": str(msg.get("X-Original-To") or ""),
        "from": from_addr,
        "in-reply-to": in_reply_to or "",
        "message-id": rfc_id or inbound_id,
        "x-memorybox-hc-token": str(msg.get(HC_TOKEN_HEADER) or ""),
        "x-mb-imap-folder": folder,
        "x-mb-imap-uid": str(uid),
        "x-mb-imap-uidvalidity": uidvalidity,
    }
    token = extract_correlation_token(
        subject=subject,
        to_addrs=[headers["to"], headers["delivered-to"], headers["x-original-to"]],
        headers=headers,
    )
    if not token:
        leaf = _folder_leaf(folder)
        if leaf.lower().startswith(HC_PLUS_PREFIX):
            token = leaf[len(HC_PLUS_PREFIX) :].lower()
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not body:
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
    extracted = refine_hc_reply_text(extract_reply_text(body or "", is_html=False))
    uri = _preserve_bytes(raw, stem=str(uuid4()), root=preserve_root)
    skip_reason = None
    if looks_like_hc_outbound_body(extracted) and not in_reply_to:
        skip_reason = "outbound_echo"
    elif looks_like_hc_outbound_body(extracted) and len(extracted.strip()) < 120:
        skip_reason = "outbound_echo"
    return InboundMailItem(
        inbound_message_id=inbound_id,
        correlation_token=token,
        from_addr=from_addr,
        subject=subject,
        extracted_text=extracted,
        preserved_raw_uri=uri,
        thread_id=in_reply_to or rfc_id or None,
        ambiguous=token is None,
        raw_headers=headers,
        skip_reason=skip_reason,
        in_reply_to=in_reply_to,
        raw_bytes=raw,
    )


class NamecheapPrivateEmailAdapter:
    provider_key = PROVIDER_KEY

    def __init__(self, cfg: dict[str, Any] | None = None, *, preserve_root: Path | None = None) -> None:
        self.cfg = cfg or load_privateemail_config()
        self.user_email = str(self.cfg.get("username") or HC_MAILBOX)
        self._root = preserve_root or Path(
            os.environ.get("MEMORYBOX_HC_MAIL_DIR", str(Path.cwd() / ".memorybox_hc_mail"))
        )
        self._checkpoint_file = checkpoint_path(username=self.user_email)
        self._pending: dict[str, dict[str, Any]] = {}
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
        return self._smtp_send(
            to_email=to_email,
            subject=subject,
            body=body,
            reply_to=reply_to,
            correlation_token=correlation_token,
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
        return self._smtp_send(
            to_email=to_email,
            subject=subject,
            body=body,
            reply_to=None,
            correlation_token=correlation_token,
        )

    def _smtp_send(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        reply_to: str | None,
        correlation_token: str | None = None,
    ) -> OutboundSendResult:
        domain = self.user_email.split("@", 1)[-1]
        message_id = make_msgid(domain=domain)
        msg = EmailMessage()
        msg["From"] = formataddr((str(self.cfg.get("from_display_name") or DEFAULT_FROM_DISPLAY), self.user_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Message-ID"] = message_id
        if reply_to:
            msg["Reply-To"] = reply_to
        if correlation_token:
            msg[HC_TOKEN_HEADER] = correlation_token
        msg.set_content(body)
        sent = False
        client = None
        try:
            client = open_smtp(self.cfg)
            client.send_message(msg)
            sent = True
        except Exception:
            if sent:
                uri = _preserve_bytes(msg.as_bytes(), stem=str(uuid4()), root=self._root)
                return OutboundSendResult(
                    ok=True,
                    outbound_message_id=message_id,
                    thread_id=message_id,
                    preserved_raw_uri=uri,
                    reply_to=reply_to,
                )
            return OutboundSendResult(ok=False, fail_detail="smtp_send_failed")
        finally:
            if client is not None:
                try:
                    client.quit()
                except Exception:
                    if sent:
                        pass
        uri = _preserve_bytes(msg.as_bytes(), stem=str(uuid4()), root=self._root)
        return OutboundSendResult(
            ok=True,
            outbound_message_id=message_id,
            thread_id=message_id,
            preserved_raw_uri=uri,
            reply_to=reply_to,
        )

    def poll_inbound(self) -> list[InboundMailItem]:
        state = load_checkpoint(self._checkpoint_file)
        processed = {str(x) for x in (state.get("processed_ids") or [])}
        folders_state: dict[str, Any] = dict(state.get("folders") or {})
        self._pending = {}
        client = None
        out: list[InboundMailItem] = []
        seen_ids: set[str] = set()
        self.last_poll_debug = {"folders": [], "error": None}
        try:
            client = open_imap(self.cfg)
            names = [n for n in parse_list_folders(client) if is_relevant_hc_folder(n)]
            self.last_poll_debug["folders"] = names
            for folder in names:
                typ, _ = client.select(folder, readonly=True)
                if typ != "OK":
                    continue
                uidvalidity = _uidvalidity(client)
                prev = folders_state.get(folder) or {}
                last_uid = int(prev.get("last_uid") or 0)
                if uidvalidity and prev.get("uidvalidity") and str(prev.get("uidvalidity")) != str(uidvalidity):
                    last_uid = 0
                    folders_state[folder] = {"uidvalidity": uidvalidity, "last_uid": 0}
                for uid in _search_uids(client, last_uid):
                    raw = _fetch_peek(client, uid)
                    if not raw:
                        continue
                    item = _parse_inbound(
                        raw,
                        folder=folder,
                        uid=uid,
                        uidvalidity=uidvalidity,
                        preserve_root=self._root,
                    )
                    if item.inbound_message_id in processed or item.inbound_message_id in seen_ids:
                        self._pending[item.inbound_message_id] = {
                            "folder": folder,
                            "uid": uid,
                            "uidvalidity": uidvalidity,
                        }
                        continue
                    seen_ids.add(item.inbound_message_id)
                    self._pending[item.inbound_message_id] = {
                        "folder": folder,
                        "uid": uid,
                        "uidvalidity": uidvalidity,
                    }
                    out.append(item)
        except Exception:
            self.last_poll_debug["error"] = "imap_poll_failed"
            return []
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
        save_checkpoint({"processed_ids": list(processed), "folders": folders_state}, self._checkpoint_file)
        return out

    def mark_processed(self, inbound_message_id: str) -> None:
        state = load_checkpoint(self._checkpoint_file)
        ids = [str(x) for x in (state.get("processed_ids") or [])]
        if inbound_message_id and inbound_message_id not in ids:
            ids.append(inbound_message_id)
        folders = dict(state.get("folders") or {})
        meta = self._pending.get(inbound_message_id) or {}
        folder = meta.get("folder")
        if folder:
            uid = int(meta.get("uid") or 0)
            uidvalidity = str(meta.get("uidvalidity") or "")
            prev = dict(folders.get(folder) or {})
            if uidvalidity and prev.get("uidvalidity") and str(prev.get("uidvalidity")) != uidvalidity:
                prev = {"uidvalidity": uidvalidity, "last_uid": 0}
            prev["uidvalidity"] = uidvalidity or prev.get("uidvalidity") or ""
            prev["last_uid"] = max(int(prev.get("last_uid") or 0), uid)
            folders[folder] = prev
        save_checkpoint({"processed_ids": ids, "folders": folders}, self._checkpoint_file)
