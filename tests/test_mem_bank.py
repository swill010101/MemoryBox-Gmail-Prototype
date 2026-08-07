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
from marvin_capture.mem_bank import (  # noqa: E402
    export_mem_bank,
    tick_mem_bank,
    validate_questions_file,
)
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
            "interval_days": 2,
            "resend_after_days": 7,
        },
        "schedule": {"daily_journal": {"enabled": False}},
        "use_fake_gmail": True,
    }


def test_every_other_day_resend_once_and_complete(tmp_path: Path):
    questions = [
        {"id": 1, "text": "Q one?"},
        {"id": 2, "text": "Q two?"},
    ]
    cfg = _cfg(tmp_path, questions)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    # Turn on Aug 9 → first send tomorrow Aug 10
    store.arm_mem_sends(conn, enabled=True, now=datetime(2026, 8, 9, 12, 0))
    assert store.get_mem_bank_state(conn)["next_initial_date"] == "2026-08-10"

    # Aug 10 01:05 — Q1
    r1 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 10, 1, 5))
    assert any(a["kind"] == "initial" and a["question_id"] == 1 for a in r1["actions"])
    assert store.get_mem_bank_state(conn)["next_initial_date"] == "2026-08-12"

    # Aug 11 — no new question (every other day)
    r_skip = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 11, 1, 5))
    assert not any(a["kind"] == "initial" for a in r_skip.get("actions") or [])

    # Aug 12 — Q2 while Q1 still unanswered
    r2 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 12, 1, 5))
    assert any(a["kind"] == "initial" and a["question_id"] == 2 for a in r2["actions"])

    # Aug 17 — Q1 due for one-time resend (7 days); Q2 only 5 days
    r3 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 17, 1, 5))
    kinds = [(a["kind"], a.get("question_id")) for a in r3["actions"]]
    assert ("resend", 1) in kinds
    assert ("resend", 2) not in kinds

    # Aug 18 — Q1 must NOT resend again
    r4 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 18, 1, 5))
    assert ("resend", 1) not in [(a["kind"], a.get("question_id")) for a in r4.get("actions") or []]

    for qid, body in ((1, "Answer one"), (2, "Answer two")):
        last = store.last_mem_send(conn, qid)
        mid = client.inject_reply(
            thread_id=last["gmail_thread_id"],
            subject=f"Re: [MB-MEM-{qid}] Q",
            body=body,
        )
        assert process_message(conn, client, cfg, mid)["status"] == "captured"

    r5 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 19, 1, 5))
    assert any(a.get("kind") == "complete" for a in r5.get("actions") or [])
    exported = export_mem_bank(conn, cfg)
    assert exported["count"] == 2
    conn.close()


def test_sends_toggle_skips_tick(tmp_path: Path):
    cfg = _cfg(tmp_path, [{"id": 1, "text": "Q?"}])
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    store.arm_mem_sends(conn, enabled=False, now=datetime(2026, 8, 9, 12, 0))
    r = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 10, 1, 5), force=False)
    assert r["skipped"] and r["reason"] == "disabled"
    store.arm_mem_sends(conn, enabled=True, now=datetime(2026, 8, 9, 12, 0))
    # armed for Aug 10 — tick Aug 10 sends
    r2 = tick_mem_bank(conn, client, cfg, now=datetime(2026, 8, 10, 1, 5), force=False)
    assert not r2["skipped"]
    conn.close()


def test_validate_questions_ok_and_gap(tmp_path: Path):
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps({"questions": [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]}),
        encoding="utf-8",
    )
    assert validate_questions_file(good)["ok"] is True
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"questions": [{"id": 1, "text": "A"}, {"id": 3, "text": "C"}]}),
        encoding="utf-8",
    )
    report = validate_questions_file(bad)
    assert report["ok"] is False
    assert any("contiguous" in e or "missing" in e for e in report["errors"])


def test_voice_only_promotes_whisper_to_answer(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, [{"id": 1, "text": "Speak"}])
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    store.set_mem_bank_state(conn, sends_enabled=1, next_initial_date="2026-08-10")
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
