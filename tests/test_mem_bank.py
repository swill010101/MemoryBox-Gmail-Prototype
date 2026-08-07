"""MEM question-bank scheduler and export tests."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import db as store  # noqa: E402
from marvin_capture.gmail_client import FakeGmailClient  # noqa: E402
from marvin_capture.mem_bank import export_mem_bank, tick_mem_bank  # noqa: E402
from marvin_capture.service import process_message  # noqa: E402
from marvin_capture.whisper_client import process_pending_transcriptions  # noqa: E402


def _cfg(tmp_path: Path, questions: list[dict]) -> dict:
    qpath = tmp_path / "mem_questions.json"
    qpath.write_text(json.dumps({"questions": questions}), encoding="utf-8")
    return {
        "gmail": {"user_email": "swill01@gmail.com", "processed_label": "MB/Processed"},
        "sqlite_path": str(tmp_path / "marvin.db"),
        "attachment_storage": str(tmp_path / "atts"),
        "raw_email_storage": str(tmp_path / "raw"),
        "whisper": {
            "endpoint": "http://127.0.0.1:9/v1/audio/transcriptions",
            "model": "whisper-1",
            "timeout_seconds": 1,
        },
        "mem_bank": {
            "enabled": True,
            "questions_file": str(qpath),
            "export_dir": str(tmp_path / "exports"),
            "to": "swill01@gmail.com",
            "hour": 1,
            "minute": 0,
            "days_mon_through_fri": [0, 1, 2, 3, 4],
            "resend_after_days": 7,
        },
        "schedule": {"daily_journal": {"enabled": False}},
        "use_fake_gmail": True,
    }


def test_tick_sends_next_then_resend_and_complete(tmp_path: Path):
    questions = [
        {"id": 1, "text": "Q one?"},
        {"id": 2, "text": "Q two?"},
    ]
    cfg = _cfg(tmp_path, questions)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    # Monday 01:05 — send Q1
    mon = datetime(2026, 8, 10, 1, 5)  # Monday
    r1 = tick_mem_bank(conn, client, cfg, now=mon, force=False)
    assert not r1["skipped"]
    assert any(a["kind"] == "initial" and a["question_id"] == 1 for a in r1["actions"])

    # Same day again — skip
    r1b = tick_mem_bank(conn, client, cfg, now=mon.replace(hour=2), force=False)
    assert r1b["skipped"]

    # Tuesday — send Q2 even though Q1 unanswered
    tue = datetime(2026, 8, 11, 1, 5)
    r2 = tick_mem_bank(conn, client, cfg, now=tue, force=False)
    assert any(a["kind"] == "initial" and a["question_id"] == 2 for a in r2["actions"])

    # Following Monday — resend Q1 only (sent Mon 10 → Mon 17 = 7 days).
    # Q2 was sent Tue 11 → only 6 days, not yet due.
    next_mon = datetime(2026, 8, 17, 1, 5)
    r3 = tick_mem_bank(conn, client, cfg, now=next_mon, force=False)
    kinds = [(a["kind"], a.get("question_id")) for a in r3["actions"]]
    assert ("resend", 1) in kinds
    assert ("resend", 2) not in kinds
    assert not any(a["kind"] == "initial" for a in r3["actions"])

    # Answer both via tagged replies
    for qid, body in ((1, "Answer one"), (2, "Answer two")):
        last = store.last_mem_send(conn, qid)
        mid = client.inject_reply(
            thread_id=last["gmail_thread_id"],
            subject=f"Re: [MB-MEM-{qid}] Q",
            body=body,
        )
        assert process_message(conn, client, cfg, mid)["status"] == "captured"

    # Next tick → completion email
    wed = datetime(2026, 8, 18, 1, 5)  # Tuesday actually wait - Aug 18 2026 is Tuesday
    # use force to ignore weekday if needed - Aug 17 was Mon, Aug 18 Tue
    r4 = tick_mem_bank(conn, client, cfg, now=wed, force=False)
    assert any(a.get("kind") == "complete" for a in r4.get("actions") or [])
    assert store.get_mem_bank_state(conn)["completion_email_sent"] == 1

    exported = export_mem_bank(conn, cfg)
    assert exported["count"] == 2
    assert Path(exported["combined"]).is_file()
    assert "Answer one" in Path(exported["combined"]).read_text(encoding="utf-8")
    conn.close()


def test_sends_toggle_skips_tick(tmp_path: Path):
    cfg = _cfg(tmp_path, [{"id": 1, "text": "Q?"}])
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    store.set_mem_bank_state(conn, sends_enabled=0)
    r = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 10, 1, 5), force=False)
    assert r["skipped"] and r["reason"] == "disabled"
    store.set_mem_bank_state(conn, sends_enabled=1)
    r2 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 10, 1, 5), force=False)
    assert not r2["skipped"]
    conn.close()


def test_voice_only_promotes_whisper_to_answer(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, [{"id": 1, "text": "Speak"}])
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    store.set_mem_bank_state(conn, sends_enabled=1)
    tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 10, 1, 5), force=True)
    last = store.last_mem_send(conn, 1)
    mid = client.inject_reply(
        thread_id=last["gmail_thread_id"],
        subject="Re: [MB-MEM-1] Speak",
        body="",
        attachments=[("note.m4a", "audio/mp4", b"audio")],
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "captured"
    assert result["response"]["response_text"] == ""

    monkeypatch.setattr(
        "marvin_capture.whisper_client.transcribe_file",
        lambda path, **kwargs: "spoken answer words",
    )
    tx = process_pending_transcriptions(conn, cfg["whisper"])
    assert tx[0]["promoted_to_answer"] is True
    detail = store.get_response_detail(conn, result["response"]["id"])
    assert detail["response_text"] == "spoken answer words"
    assert Path(detail["attachments"][0]["storage_path"]).read_bytes() == b"audio"
    conn.close()
