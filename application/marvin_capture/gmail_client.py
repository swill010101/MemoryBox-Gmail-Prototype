"""Gmail API client for Marvin Capture.

Supports a FakeGmailClient for tests and dry-run without credentials.
"""
from __future__ import annotations

import base64
import email.mime.multipart
import email.mime.text
from dataclasses import dataclass, field
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Any, Protocol


class GmailClient(Protocol):
    def send_message(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, str]: ...

    def list_unread_or_unprocessed(
        self,
        *,
        processed_label: str,
        query_extra: str = "",
    ) -> list[dict[str, Any]]: ...

    def get_message_raw(self, message_id: str) -> bytes: ...

    def get_message_metadata(self, message_id: str) -> dict[str, Any]: ...

    def ensure_label(self, name: str) -> str: ...

    def apply_label(self, message_id: str, label_id: str) -> None: ...


@dataclass
class FakeMessage:
    id: str
    thread_id: str
    subject: str
    raw: bytes
    label_ids: list[str] = field(default_factory=lambda: ["INBOX", "UNREAD"])


class FakeGmailClient:
    """In-memory Gmail stand-in for tests and local dry-runs."""

    def __init__(self) -> None:
        self.messages: dict[str, FakeMessage] = {}
        self.labels: dict[str, str] = {}
        self.sent: list[dict[str, Any]] = []
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq:04d}"

    def send_message(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        mid = self._next_id("msg")
        tid = thread_id or self._next_id("thr")
        mime = email.mime.text.MIMEText(body, "plain", "utf-8")
        mime["To"] = to
        mime["From"] = "marvin@local.test"
        mime["Subject"] = subject
        mime["Message-ID"] = f"<{mid}@local.test>"
        raw = mime.as_bytes()
        self.messages[mid] = FakeMessage(id=mid, thread_id=tid, subject=subject, raw=raw)
        self.sent.append({"id": mid, "threadId": tid, "to": to, "subject": subject})
        return {"id": mid, "threadId": tid}

    def inject_reply(
        self,
        *,
        thread_id: str,
        subject: str,
        body: str,
        attachments: list[tuple[str, str, bytes]] | None = None,
        from_addr: str = "tom@local.test",
    ) -> str:
        mid = self._next_id("msg")
        if attachments:
            mime: email.mime.multipart.MIMEMultipart | email.mime.text.MIMEText = (
                email.mime.multipart.MIMEMultipart()
            )
            mime.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
            for filename, mime_type, data in attachments:
                main, _, sub = mime_type.partition("/")
                part = MIMEBase(main or "application", sub or "octet-stream")
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                mime.attach(part)
        else:
            mime = email.mime.text.MIMEText(body, "plain", "utf-8")
        mime["To"] = "marvin@local.test"
        mime["From"] = from_addr
        mime["Subject"] = subject
        mime["Message-ID"] = f"<{mid}@local.test>"
        raw = mime.as_bytes()
        self.messages[mid] = FakeMessage(id=mid, thread_id=thread_id, subject=subject, raw=raw)
        return mid

    def list_unread_or_unprocessed(
        self,
        *,
        processed_label: str,
        query_extra: str = "",
    ) -> list[dict[str, Any]]:
        label_id = self.labels.get(processed_label)
        out = []
        for msg in self.messages.values():
            if label_id and label_id in msg.label_ids:
                continue
            # skip outbound-only messages from marvin if desired — include all unmatched
            out.append({"id": msg.id, "threadId": msg.thread_id})
        return out

    def get_message_raw(self, message_id: str) -> bytes:
        return self.messages[message_id].raw

    def get_message_metadata(self, message_id: str) -> dict[str, Any]:
        msg = self.messages[message_id]
        return {
            "id": msg.id,
            "threadId": msg.thread_id,
            "labelIds": list(msg.label_ids),
            "subject": msg.subject,
        }

    def ensure_label(self, name: str) -> str:
        if name not in self.labels:
            self.labels[name] = f"Label_{len(self.labels) + 1}"
        return self.labels[name]

    def apply_label(self, message_id: str, label_id: str) -> None:
        msg = self.messages[message_id]
        if label_id not in msg.label_ids:
            msg.label_ids.append(label_id)


def build_live_gmail_client(cfg: dict[str, Any]) -> Any:
    """Build a live Gmail API client from OAuth credentials.

    Requires google-api-python-client and google-auth-oauthlib.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    gmail_cfg = cfg["gmail"]
    scopes = gmail_cfg["scopes"]
    creds_path = Path(gmail_cfg["credentials_file"])
    token_path = Path(gmail_cfg["token_file"])

    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.is_file():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {creds_path}. "
                    "Download OAuth desktop client JSON from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return LiveGmailClient(service)


class LiveGmailClient:
    def __init__(self, service: Any) -> None:
        self.service = service
        self._label_cache: dict[str, str] = {}

    def send_message(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        mime = email.mime.text.MIMEText(body, "plain", "utf-8")
        mime["To"] = to
        mime["Subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
        payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        result = (
            self.service.users()
            .messages()
            .send(userId="me", body=payload)
            .execute()
        )
        return {"id": result["id"], "threadId": result["threadId"]}

    def list_unread_or_unprocessed(
        self,
        *,
        processed_label: str,
        query_extra: str = "",
    ) -> list[dict[str, Any]]:
        # Nested Gmail labels use hyphens in search: MB/Processed → mb-processed
        label_query = processed_label.replace("/", "-")
        # Prefer Marvin-tagged threads; also catch Re: replies still in inbox.
        q = (
            f"in:inbox -label:{label_query} "
            f'(subject:[MB- OR subject:"[MB-")'
        )
        if query_extra:
            q = f"{q} {query_extra}"
        result = (
            self.service.users()
            .messages()
            .list(userId="me", q=q, maxResults=50)
            .execute()
        )
        messages = result.get("messages") or []
        # Fallback: any inbox mail not yet processed (self-replies sometimes
        # drop brackets from search indexing).
        if not messages:
            q2 = f"in:inbox -label:{label_query}"
            if query_extra:
                q2 = f"{q2} {query_extra}"
            result = (
                self.service.users()
                .messages()
                .list(userId="me", q=q2, maxResults=50)
                .execute()
            )
            messages = result.get("messages") or []
        return messages

    def get_message_raw(self, message_id: str) -> bytes:
        result = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )
        return base64.urlsafe_b64decode(result["raw"])

    def get_message_metadata(self, message_id: str) -> dict[str, Any]:
        result = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date", "Message-ID"],
            )
            .execute()
        )
        headers = {
            h["name"].lower(): h["value"]
            for h in (result.get("payload") or {}).get("headers") or []
        }
        return {
            "id": result["id"],
            "threadId": result["threadId"],
            "labelIds": result.get("labelIds") or [],
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "headers": headers,
        }

    def ensure_label(self, name: str) -> str:
        if name in self._label_cache:
            return self._label_cache[name]
        existing = self.service.users().labels().list(userId="me").execute()
        for label in existing.get("labels") or []:
            if label.get("name") == name:
                self._label_cache[name] = label["id"]
                return label["id"]
        created = (
            self.service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._label_cache[name] = created["id"]
        return created["id"]

    def apply_label(self, message_id: str, label_id: str) -> None:
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()
