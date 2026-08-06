"""Outbound prompt sending and inbound poll/process loop."""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import db as store
from .gmail_client import FakeGmailClient, GmailClient, build_live_gmail_client
from .mail_store import (
    derive_reply_text,
    extract_attachments,
    message_subject,
    parse_raw_email,
    save_attachments,
    save_raw_email,
)
from .reply_extract import make_subject, parse_subject_tag

log = logging.getLogger("marvin.capture")


def get_gmail_client(cfg: dict[str, Any], *, fake: bool = False) -> GmailClient:
    if fake or cfg.get("use_fake_gmail"):
        return FakeGmailClient()
    return build_live_gmail_client(cfg)


def send_prompt(
    conn: Any,
    client: GmailClient,
    cfg: dict[str, Any],
    *,
    prompt_type: str,
    token: str,
    headline: str,
    body: str,
    to: str | None = None,
) -> dict[str, Any]:
    to_addr = to or cfg["gmail"].get("user_email")
    if not to_addr:
        if cfg.get("use_fake_gmail") or isinstance(client, FakeGmailClient):
            to_addr = "tom@local.test"
        else:
            raise ValueError("gmail.user_email (or to=) is required to send a prompt")

    subject = make_subject(prompt_type, token, headline)
    prompt_id = f"{prompt_type.upper()}-{token}"

    result = client.send_message(to=to_addr, subject=subject, body=body)
    row = store.insert_prompt(
        conn,
        prompt_id=prompt_id,
        prompt_type=prompt_type.upper(),
        subject=subject,
        body=body,
        sent_date=store.utc_now_iso(),
        gmail_message_id=result["id"],
        gmail_thread_id=result["threadId"],
    )
    log.info("sent prompt %s message=%s thread=%s", prompt_id, result["id"], result["threadId"])
    return {"prompt": row, "gmail": result}


def send_daily_journal_if_due(
    conn: Any,
    client: GmailClient,
    cfg: dict[str, Any],
    *,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    journal = cfg.get("schedule", {}).get("daily_journal") or {}
    if not journal.get("enabled", True) and not force:
        return None

    now = now or datetime.now()
    today = now.date()
    token = today.strftime("%Y%m%d")
    prompt_id = f"JRN-{token}"

    existing = store.get_prompt(conn, prompt_id)
    if existing and existing.get("gmail_message_id") and not force:
        return None

    if not force:
        hour = int(journal.get("hour", 18))
        minute = int(journal.get("minute", 0))
        if (now.hour, now.minute) < (hour, minute):
            return None

    subject_template = journal.get(
        "subject_template",
        "[MB-JRN-{date}] What happened today?",
    )
    # subject_template may already include the tag; extract headline after tag if present
    rendered = subject_template.replace("{date}", token)
    tag = parse_subject_tag(rendered)
    headline = rendered
    if tag:
        headline = rendered.replace(tag.raw, "").strip()
    if not headline:
        headline = "What happened today?"

    body = journal.get("body") or "What happened today?"
    return send_prompt(
        conn,
        client,
        cfg,
        prompt_type="JRN",
        token=token,
        headline=headline,
        body=body,
    )


def _resolve_prompt(conn: Any, subject: str, thread_id: str) -> dict[str, Any] | None:
    tag = parse_subject_tag(subject)
    if tag:
        prompt = store.get_prompt(conn, tag.prompt_id)
        if prompt:
            return prompt
        # Auto-register unknown tagged prompt so we never drop the reply
        return store.insert_prompt(
            conn,
            prompt_id=tag.prompt_id,
            prompt_type=tag.prompt_type,
            subject=subject,
            body="(prompt inferred from reply subject; original outbound not in DB)",
            sent_date=None,
            gmail_thread_id=thread_id,
        )
    return store.find_prompt_by_thread(conn, thread_id)


def process_message(
    conn: Any,
    client: GmailClient,
    cfg: dict[str, Any],
    message_id: str,
    *,
    apply_label: bool = True,
) -> dict[str, Any] | None:
    """Preserve raw mail + attachments, extract reply, store, label Processed."""
    if store.response_exists(conn, message_id):
        log.debug("skip already-processed %s", message_id)
        return None

    meta = client.get_message_metadata(message_id)
    thread_id = meta["threadId"]
    raw = client.get_message_raw(message_id)
    msg = parse_raw_email(raw)
    subject = message_subject(msg) or meta.get("subject") or ""

    # Skip our own outbound prompts (same subject, already in prompt table by message id)
    prompt_by_out = conn.execute(
        "SELECT id FROM prompt WHERE gmail_message_id = ?",
        (message_id,),
    ).fetchone()
    if prompt_by_out:
        return None

    prompt = _resolve_prompt(conn, subject, thread_id)
    raw_dir = Path(cfg["raw_email_storage"])
    att_root = Path(cfg["attachment_storage"])

    if not prompt:
        # Never discard: hold unmatched raw email for inspection
        hold = raw_dir / "unmatched"
        path = save_raw_email(raw, hold, message_id)
        log.warning("unmatched reply saved to %s (subject=%r)", path, subject)
        return {
            "status": "unmatched",
            "raw_email_path": str(path),
            "gmail_message_id": message_id,
            "subject": subject,
        }

    prompt_id = prompt["id"]
    raw_path = save_raw_email(raw, raw_dir / prompt_id, message_id)
    reply_text = derive_reply_text(msg)
    attachments = extract_attachments(msg)
    att_dir = att_root / prompt_id / message_id
    saved_atts = save_attachments(attachments, att_dir)

    response = store.insert_response(
        conn,
        prompt_id=prompt_id,
        response_text=reply_text,
        raw_email_path=str(raw_path),
        gmail_message_id=message_id,
        gmail_thread_id=thread_id,
    )

    for att in saved_atts:
        store.insert_attachment(
            conn,
            response_id=response["id"],
            filename=att["filename"],
            mime_type=att["mime_type"],
            storage_path=att["storage_path"],
        )

    if apply_label:
        label_name = cfg["gmail"].get("processed_label") or "MB/Processed"
        label_id = client.ensure_label(label_name)
        client.apply_label(message_id, label_id)

    detail = store.get_response_detail(conn, response["id"])
    log.info(
        "captured response %s for prompt %s (%s attachments)",
        response["id"],
        prompt_id,
        len(saved_atts),
    )
    return {"status": "captured", "response": detail}


def poll_once(
    conn: Any,
    client: GmailClient,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    processed_label = cfg["gmail"].get("processed_label") or "MB/Processed"
    messages = client.list_unread_or_unprocessed(processed_label=processed_label)
    results: list[dict[str, Any]] = []
    for item in messages:
        mid = item["id"]
        try:
            result = process_message(conn, client, cfg, mid)
            if result:
                results.append(result)
        except Exception as exc:  # noqa: BLE001
            log.exception("failed processing %s: %s", mid, exc)
            results.append({"status": "error", "gmail_message_id": mid, "error": str(exc)})
    return results
