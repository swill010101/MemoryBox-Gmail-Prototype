"""MEM question-bank scheduler, export, and helpers."""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import db as store
from .service import send_prompt

log = logging.getLogger("marvin.mem_bank")

SAFE_RE = re.compile(r"[^\w.\-]+", re.UNICODE)


def ensure_questions_file(path: str | Path, *, example: str | Path | None = None) -> Path:
    """Create questions file from example if missing; return resolved path."""
    path = Path(path)
    if path.is_file():
        return path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if example and Path(example).is_file():
        path.write_text(Path(example).read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "title": "Memory interview",
                    "questions": [
                        {"id": 1, "text": "What is your earliest childhood memory?"}
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return path.resolve()


def open_questions_file_in_editor(path: str | Path) -> str:
    """Open the JSON in the OS default editor (local PoC server only)."""
    import os
    import subprocess
    import sys

    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    if sys.platform == "win32":
        os.startfile(str(resolved))  # noqa: S606 — intentional local open
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(resolved)], shell=False)  # noqa: S603
    else:
        subprocess.Popen(["xdg-open", str(resolved)], shell=False)  # noqa: S603
    return str(resolved)


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    questions = data.get("questions") or data
    out: list[dict[str, Any]] = []
    for q in questions:
        qid = int(q["id"])
        text = str(q.get("text") or "").strip()
        if not text:
            raise ValueError(f"MEM question {qid} has empty text")
        out.append({"id": qid, "text": text})
    out.sort(key=lambda x: x["id"])
    ids = [q["id"] for q in out]
    if ids != list(range(1, len(ids) + 1)):
        raise ValueError(
            f"MEM questions must be contiguous 1..N, got {ids[:5]}… (n={len(ids)})"
        )
    return out


def mem_prompt_id(question_id: int) -> str:
    return f"MEM-{question_id}"


def is_mem_bank_question_id(prompt_id: str) -> bool:
    return bool(re.fullmatch(r"MEM-\d+", prompt_id or ""))


def question_answered(conn: Any, question_id: int) -> bool:
    return store.prompt_has_response(conn, mem_prompt_id(question_id))


def _weekday_ok(now: datetime, days: list[int]) -> bool:
    # Python: Mon=0 … Sun=6
    return now.weekday() in days


def _past_send_time(now: datetime, hour: int, minute: int) -> bool:
    return (now.hour, now.minute) >= (hour, minute)


def send_mem_question(
    conn: Any,
    client: Any,
    cfg: dict[str, Any],
    *,
    question: dict[str, Any],
    kind: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    qid = int(question["id"])
    text = question["text"]
    bank = cfg.get("mem_bank") or {}
    to = bank.get("to") or cfg.get("gmail", {}).get("user_email")
    body = (
        f"{text}\n\n"
        "Reply to this email with your answer. "
        "You can type, dictate, or attach photos, documents, or voice memos.\n"
        "No special formatting required."
    )
    result = send_prompt(
        conn,
        client,
        cfg,
        prompt_type="MEM",
        token=str(qid),
        headline=text if len(text) <= 120 else text[:117] + "...",
        body=body,
        to=to,
    )
    sent_at = (now or datetime.now()).replace(microsecond=0).isoformat()
    store.log_mem_send(
        conn,
        question_id=qid,
        kind=kind,
        gmail_message_id=result["gmail"]["id"],
        gmail_thread_id=result["gmail"]["threadId"],
        sent_at=sent_at,
    )
    log.info("MEM bank sent question %s (%s)", qid, kind)
    return result


def send_completion_email(conn: Any, client: Any, cfg: dict[str, Any], total: int) -> None:
    bank = cfg.get("mem_bank") or {}
    to = bank.get("to") or cfg.get("gmail", {}).get("user_email")
    subject = "[MB-MEM] Interview complete"
    body = (
        f"Interview complete — {total} questions answered.\n\n"
        "You can export the full set from the Marvin Capture review UI "
        "(Extract MEM).\n"
    )
    # Use type MEM with no numeric token — completion notice, not a bank question
    client.send_message(to=to, subject=subject, body=body)
    store.set_mem_bank_state(conn, completion_email_sent=1, completed_at=store.utc_now_iso())
    log.info("MEM bank completion email sent (%s questions)", total)


def tick_mem_bank(
    conn: Any,
    client: Any,
    cfg: dict[str, Any],
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run once per scheduled day: resends due + next unsent; completion when done."""
    bank = cfg.get("mem_bank") or {}
    if not bank.get("enabled") and not force:
        return {"skipped": True, "reason": "disabled"}

    questions_path = bank.get("questions_file")
    if not questions_path or not Path(questions_path).is_file():
        return {"skipped": True, "reason": "missing_questions_file"}

    questions = load_questions(questions_path)
    now = now or datetime.now()
    hour = int(bank.get("hour", 1))
    minute = int(bank.get("minute", 0))
    days = bank.get("days_mon_through_fri")
    if days is None:
        days = [0, 1, 2, 3, 4]
    resend_after = int(bank.get("resend_after_days", 7))

    state = store.get_mem_bank_state(conn)
    if state.get("completion_email_sent"):
        return {"skipped": True, "reason": "already_complete"}

    if not force:
        if not _weekday_ok(now, list(days)):
            return {"skipped": True, "reason": "not_weekday"}
        if not _past_send_time(now, hour, minute):
            return {"skipped": True, "reason": "before_send_time"}
        today = now.date().isoformat()
        if state.get("last_tick_date") == today:
            return {"skipped": True, "reason": "already_ticked_today"}

    actions: list[dict[str, Any]] = []

    # 1) Resend unanswered whose last send was >= resend_after days ago
    for q in questions:
        qid = q["id"]
        if question_answered(conn, qid):
            continue
        last = store.last_mem_send(conn, qid)
        if not last:
            continue
        sent_day = _parse_day(last["sent_at"])
        if sent_day is None:
            continue
        if now.date() - sent_day >= timedelta(days=resend_after):
            actions.append(
                {
                    "kind": "resend",
                    "question_id": qid,
                    **send_mem_question(
                        conn, client, cfg, question=q, kind="resend", now=now
                    ),
                }
            )

    # 2) Send next never-sent question
    next_q = None
    for q in questions:
        if store.last_mem_send(conn, q["id"]) is None:
            next_q = q
            break
    if next_q is not None:
        actions.append(
            {
                "kind": "initial",
                "question_id": next_q["id"],
                **send_mem_question(
                    conn, client, cfg, question=next_q, kind="initial", now=now
                ),
            }
        )

    # 3) Completion when every question has an answer
    all_answered = all(question_answered(conn, q["id"]) for q in questions)
    if all_answered and not state.get("completion_email_sent"):
        send_completion_email(conn, client, cfg, total=len(questions))
        actions.append({"kind": "complete", "total": len(questions)})

    store.set_mem_bank_state(conn, last_tick_date=now.date().isoformat())
    return {"skipped": False, "actions": actions, "total_questions": len(questions)}


def _parse_day(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def _safe(name: str) -> str:
    return SAFE_RE.sub("_", name).strip("._")[:120] or "file"


def export_mem_bank(
    conn: Any,
    cfg: dict[str, Any],
    *,
    export_root: str | Path | None = None,
) -> dict[str, Any]:
    """Write combined + per-question text files and copy attachments with linkable names."""
    bank = cfg.get("mem_bank") or {}
    questions_path = bank.get("questions_file")
    questions = load_questions(questions_path) if questions_path and Path(questions_path).is_file() else []
    qmap = {q["id"]: q["text"] for q in questions}

    root = Path(export_root or bank.get("export_dir") or (Path(cfg["attachment_storage"]).parent / "mem_exports"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch = root / f"mem_batch_{stamp}"
    batch.mkdir(parents=True, exist_ok=True)

    items = store.list_mem_bank_qa(conn)
    combined_blocks: list[str] = []
    files_written: list[str] = []

    for item in items:
        prompt_id = item["prompt_id"]
        m = re.fullmatch(r"MEM-(\d+)", prompt_id or "")
        if not m:
            continue
        qid = int(m.group(1))
        received = item.get("received_date") or ""
        day = (received[:10] if received else "unknown").replace("-", "")
        base = f"MEM-{qid}_{day}"
        question_text = qmap.get(qid) or item.get("prompt_body") or ""
        answer = (item.get("response_text") or "").strip()
        subject = item.get("subject") or item.get("prompt_subject") or ""

        att_lines: list[str] = []
        for att in item.get("attachments") or []:
            src = Path(att["storage_path"])
            ext = src.suffix or ""
            dest_name = f"{base}_{_safe(Path(att['filename']).stem)}{ext}"
            dest = batch / dest_name
            if src.is_file():
                shutil.copy2(src, dest)
            att_lines.append(dest_name)
            if att.get("transcript"):
                tname = f"{base}_{_safe(Path(att['filename']).stem)}_transcript.txt"
                (batch / tname).write_text(att["transcript"], encoding="utf-8")
                att_lines.append(tname)

        block = (
            f"=== MEM-{qid} ===\n"
            f"received: {received}\n"
            f"subject: {subject}\n"
            f"question:\n{question_text}\n"
            f"---\n"
            f"answer:\n{answer}\n"
        )
        if att_lines:
            block += "attachments:\n" + "\n".join(f"  - {n}" for n in att_lines) + "\n"
        combined_blocks.append(block)

        text_path = batch / f"{base}.txt"
        text_path.write_text(block, encoding="utf-8")
        files_written.append(str(text_path))

    combined_path = batch / "mem_all.txt"
    combined_path.write_text(
        "\n\n".join(combined_blocks) + ("\n" if combined_blocks else "=== MEM export ===\n(no answers yet)\n"),
        encoding="utf-8",
    )
    files_written.append(str(combined_path))
    return {
        "batch_dir": str(batch),
        "combined": str(combined_path),
        "files": files_written,
        "count": len(combined_blocks),
    }
