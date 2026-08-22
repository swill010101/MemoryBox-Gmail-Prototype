"""Outbound prompt sending and inbound poll/process loop."""
from __future__ import annotations

import logging
from datetime import datetime
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
from .plus_address import extract_plus_routing
from .reply_extract import normalize_for_dedupe

log = logging.getLogger("marvin.capture")

ADHOC_JRN_BODY = (
    "(Ad-hoc journal — you emailed this in; Marvin did not send an outbound prompt.)"
)


def get_gmail_client(cfg: dict[str, Any], *, fake: bool = False) -> GmailClient:
    if fake or cfg.get("use_fake_gmail"):
        return FakeGmailClient()
    return build_live_gmail_client(cfg)


def _outbound_subject(prompt_type: str, headline: str, body: str) -> str:
    """Plain subject for outbound mail (no [MB-…] tags)."""
    headline = (headline or "").strip()
    if headline:
        return headline
    first = (body or "").strip().split("\n", 1)[0].strip()
    return first[:200] if first else prompt_type


def send_prompt(
    conn: Any,
    client: GmailClient,
    cfg: dict[str, Any],
    *,
    prompt_type: str,
    headline: str,
    body: str,
    token: str = "",
    to: str | None = None,
    reply_to: str | None = None,
) -> dict[str, Any]:
    to_addr = to or cfg["gmail"].get("user_email")
    if not to_addr:
        if cfg.get("use_fake_gmail") or isinstance(client, FakeGmailClient):
            to_addr = "tom@local.test"
        else:
            raise ValueError("gmail.user_email (or to=) is required to send a prompt")

    prompt_type = prompt_type.upper()
    subject = _outbound_subject(prompt_type, headline, body)
    prompt_id = f"{prompt_type}-{token}" if token else prompt_type

    result = client.send_message(
        to=to_addr,
        subject=subject,
        body=body,
        reply_to=reply_to,
    )
    row = store.insert_prompt(
        conn,
        prompt_id=prompt_id,
        prompt_type=prompt_type,
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
    if store.mem_sends_are_enabled(conn, cfg) and not force:
        return None

    journal = cfg.get("schedule", {}).get("daily_journal") or {}
    if not journal.get("enabled", True) and not force:
        return None

    now = now or datetime.now()
    today = now.date()

    if not force and store.journal_sent_on_date(conn, today):
        return None

    if not force:
        hour = int(journal.get("hour", 18))
        minute = int(journal.get("minute", 0))
        if (now.hour, now.minute) < (hour, minute):
            return None

    subject_template = journal.get("subject_template", "What happened today?")
    rendered = subject_template.replace("{date}", today.strftime("%Y%m%d"))
    # Strip legacy [MB-JRN] prefix if present in template
    headline = rendered
    if headline.upper().startswith("[MB-JRN]"):
        headline = headline[8:].strip()
    if not headline:
        headline = "What happened today?"

    body = journal.get("body") or "What happened today?"
    return send_prompt(
        conn,
        client,
        cfg,
        prompt_type="JRN",
        headline=headline,
        body=body,
        token="",
    )


def _message_headers(meta: dict[str, Any], msg: Any) -> dict[str, str]:
    headers = dict(meta.get("headers") or {})
    if not headers.get("to") and meta.get("to"):
        headers["to"] = meta["to"]
    if not headers.get("delivered-to") and meta.get("delivered-to"):
        headers["delivered-to"] = meta["delivered-to"]
    if not headers.get("to"):
        headers["to"] = str(msg.get("To") or "")
    if not headers.get("delivered-to"):
        headers["delivered-to"] = str(msg.get("Delivered-To") or headers.get("to", ""))
    return headers


def _resolve_prompt_by_plus(
    conn: Any,
    *,
    route_type: str,
    thread_id: str,
    subject: str,
) -> dict[str, Any] | None:
    """Bind inbound mail to a prompt using plus-address rules (MBC-004)."""
    route_type = route_type.upper()
    prompt = store.find_prompt_by_thread(conn, thread_id)

    if route_type == "MEM":
        if not prompt or (prompt.get("type") or "").upper() != "MEM":
            return None
        return prompt

    # JRN: reply to Marvin outbound, or ad-hoc compose to +journal/+jrn
    if prompt and (prompt.get("type") or "").upper() == "JRN":
        return prompt
    return store.insert_prompt(
        conn,
        prompt_id="JRN",
        prompt_type="JRN",
        subject=subject,
        body=ADHOC_JRN_BODY,
        sent_date=None,
        gmail_thread_id=thread_id,
    )


def _verify_and_trash(
    conn: Any,
    client: GmailClient,
    message_id: str,
    *,
    existing_response_id: int | None = None,
) -> bool:
    """Trash message after DB verify. Returns True if trashed."""
    verified = store.response_exists(conn, message_id)
    if not verified and existing_response_id is not None:
        verified = store.get_response(conn, existing_response_id) is not None
    if verified:
        try:
            client.trash_message(message_id)
            log.info("trashed gmail message %s after verify", message_id)
            return True
        except Exception:  # noqa: BLE001
            log.exception("failed to trash message %s", message_id)
    return False


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
        _verify_and_trash(conn, client, message_id)
        return None

    meta = client.get_message_metadata(message_id)
    thread_id = meta["threadId"]
    raw = client.get_message_raw(message_id)
    msg = parse_raw_email(raw)
    subject = message_subject(msg) or meta.get("subject") or ""
    headers = _message_headers(meta, msg)
    user_email = cfg["gmail"].get("user_email") or ""

    prompt_by_out = conn.execute(
        "SELECT id FROM prompt WHERE gmail_message_id = ?",
        (message_id,),
    ).fetchone()
    if prompt_by_out:
        if apply_label:
            label_name = cfg["gmail"].get("processed_label") or "MB/Processed"
            label_id = client.ensure_label(label_name)
            client.apply_label(message_id, label_id)
        return None

    labels = {str(x) for x in (meta.get("labelIds") or [])}
    if "SENT" in labels and "INBOX" not in labels:
        prior = conn.execute(
            "SELECT id FROM response WHERE gmail_thread_id = ? LIMIT 1",
            (thread_id,),
        ).fetchone()
        if prior:
            if apply_label:
                label_name = cfg["gmail"].get("processed_label") or "MB/Processed"
                label_id = client.ensure_label(label_name)
                client.apply_label(message_id, label_id)
            log.info(
                "skip sent-only duplicate on thread %s (response %s); message %s",
                thread_id,
                prior["id"],
                message_id,
            )
            return {
                "status": "sent_only_skipped",
                "existing_response_id": prior["id"],
                "gmail_message_id": message_id,
            }

    route_type, matched_addr = extract_plus_routing(headers, user_email=user_email)
    raw_dir = Path(cfg["raw_email_storage"])
    att_root = Path(cfg["attachment_storage"])

    if not route_type:
        hold = raw_dir / "unmatched"
        path = save_raw_email(raw, hold, message_id)
        log.warning(
            "unmatched reply saved to %s (subject=%r, no plus-address)",
            path,
            subject,
        )
        return {
            "status": "unmatched",
            "raw_email_path": str(path),
            "gmail_message_id": message_id,
            "subject": subject,
        }

    prompt = _resolve_prompt_by_plus(
        conn, route_type=route_type, thread_id=thread_id, subject=subject
    )
    if not prompt:
        hold = raw_dir / "unmatched"
        path = save_raw_email(raw, hold, message_id)
        log.warning(
            "unmatched %s to %r (subject=%r, no thread-bound prompt)",
            route_type,
            matched_addr,
            subject,
        )
        return {
            "status": "unmatched",
            "raw_email_path": str(path),
            "gmail_message_id": message_id,
            "subject": subject,
            "route_type": route_type,
        }

    prompt_id = prompt["id"]
    raw_path = save_raw_email(raw, raw_dir / prompt_id, message_id)
    reply_text = derive_reply_text(msg)

    norm = normalize_for_dedupe(reply_text)
    if norm:
        existing = store.find_response_by_normalized_text(
            conn, prompt_id=prompt_id, normalized_text=norm
        )
        if not existing:
            import difflib

            rows = conn.execute(
                """
                SELECT id, response_text FROM response
                WHERE prompt_id = ? AND length(trim(response_text)) > 0
                ORDER BY id ASC
                """,
                (prompt_id,),
            ).fetchall()
            for row in rows:
                prev = normalize_for_dedupe(row["response_text"])
                if not prev:
                    continue
                ratio = difflib.SequenceMatcher(None, prev, norm).ratio()
                need = 0.88 if min(len(prev), len(norm)) >= 80 else 0.97
                if ratio >= need or (
                    min(len(prev), len(norm)) >= 40 and (prev in norm or norm in prev)
                ):
                    existing = dict(row)
                    break
        if existing:
            if apply_label:
                label_name = cfg["gmail"].get("processed_label") or "MB/Processed"
                label_id = client.ensure_label(label_name)
                client.apply_label(message_id, label_id)
            log.info(
                "duplicate body skipped for prompt %s (existing response %s); raw kept at %s",
                prompt_id,
                existing["id"],
                raw_path,
            )
            _verify_and_trash(
                conn, client, message_id, existing_response_id=existing["id"]
            )
            return {
                "status": "duplicate_skipped",
                "existing_response_id": existing["id"],
                "raw_email_path": str(raw_path),
                "gmail_message_id": message_id,
            }

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
        subject=subject,
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

    _verify_and_trash(conn, client, message_id)

    detail = store.get_response_detail(conn, response["id"])
    log.info(
        "captured response %s for prompt %s (%s attachments)",
        response["id"],
        prompt_id,
        len(saved_atts),
    )
    return {"status": "captured", "response": detail}


def reextract_all_responses(conn: Any) -> int:
    """Re-derive response_text from preserved raw .eml (additive cleanup)."""
    rows = conn.execute(
        """
        SELECT r.id, r.raw_email_path
        FROM response r
        WHERE r.raw_email_path IS NOT NULL
        """
    ).fetchall()
    updated = 0
    for row in rows:
        path = Path(row["raw_email_path"])
        if not path.is_file():
            continue
        try:
            msg = parse_raw_email(path.read_bytes())
            text = derive_reply_text(msg)
            store.update_response_text(conn, row["id"], text)
            updated += 1
        except Exception:  # noqa: BLE001
            log.exception("reextract failed for response %s", row["id"])
    return updated


def poll_once(
    conn: Any,
    client: GmailClient,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    processed_label = cfg["gmail"].get("processed_label") or "MB/Processed"
    user_email = cfg["gmail"].get("user_email") or ""
    messages = client.list_unread_or_unprocessed(
        processed_label=processed_label,
        user_email=user_email,
    )
    log.info("poll listed %s candidate message(s)", len(messages))
    results: list[dict[str, Any]] = []
    for item in messages:
        mid = item["id"]
        try:
            result = process_message(conn, client, cfg, mid)
            if result:
                results.append(result)
                log.info("poll result %s → %s", mid, result.get("status"))
        except Exception as exc:  # noqa: BLE001
            log.exception("failed processing %s: %s", mid, exc)
            results.append({"status": "error", "gmail_message_id": mid, "error": str(exc)})
    return results
