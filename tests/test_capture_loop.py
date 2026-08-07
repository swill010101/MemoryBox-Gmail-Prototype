"""End-to-end capture loop with FakeGmailClient."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import db as store  # noqa: E402
from marvin_capture.gmail_client import FakeGmailClient  # noqa: E402
from marvin_capture.service import poll_once, process_message, send_prompt  # noqa: E402
from marvin_capture.whisper_client import process_pending_transcriptions  # noqa: E402


def _cfg(tmp_path: Path) -> dict:
    return {
        "gmail": {
            "user_email": "tom@local.test",
            "processed_label": "MB/Processed",
        },
        "sqlite_path": str(tmp_path / "marvin.db"),
        "attachment_storage": str(tmp_path / "atts"),
        "raw_email_storage": str(tmp_path / "raw"),
        "whisper": {
            "endpoint": "http://127.0.0.1:9/v1/audio/transcriptions",
            "api_key": "",
            "model": "whisper-1",
            "timeout_seconds": 1,
        },
        "use_fake_gmail": True,
    }


def test_send_reply_capture_preserve(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    sent = send_prompt(
        conn,
        client,
        cfg,
        prompt_type="JRN",
        headline="What happened today?",
        body="What happened today?",
    )
    thread_id = sent["gmail"]["threadId"]
    prompt_id = sent["prompt"]["id"]
    assert prompt_id == "JRN"

    reply_body = (
        "Met Sarah for lunch. Attached a photo.\n\n"
        "On Wed, Aug 6, 2026 at 6:00 PM Marvin wrote:\n"
        "> What happened today?\n"
    )
    photo = b"\xff\xd8\xfffakejpeg"
    voice = b"fake-m4a-bytes"
    mid = client.inject_reply(
        thread_id=thread_id,
        subject="Re: [MB-JRN] What happened today?",
        body=reply_body,
        attachments=[
            ("lunch.jpg", "image/jpeg", photo),
            ("memo.m4a", "audio/mp4", voice),
        ],
    )

    result = process_message(conn, client, cfg, mid)
    assert result is not None
    assert result["status"] == "captured"
    detail = result["response"]
    assert detail["response_text"] == "Met Sarah for lunch. Attached a photo."
    assert detail["prompt_id"] == "JRN"
    assert detail["subject"] == "Re: [MB-JRN] What happened today?"
    assert len(detail["attachments"]) == 2

    raw_path = Path(detail["raw_email_path"])
    assert raw_path.is_file()

    for att in detail["attachments"]:
        assert Path(att["storage_path"]).is_file()
        if att["filename"].endswith(".m4a"):
            assert att["is_audio"] == 1
            assert Path(att["storage_path"]).read_bytes() == voice

    label_id = client.labels["MB/Processed"]
    assert label_id in client.messages[mid].label_ids
    assert process_message(conn, client, cfg, mid) is None

    tx = process_pending_transcriptions(conn, cfg["whisper"])
    assert tx and tx[0]["status"] == "error"
    conn.close()


def test_evs_tokenless_extract_and_delete(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    mid = client.inject_reply(
        thread_id="thr-evs",
        subject="[MB-EVS] Pocket watch",
        body="The pocket watch belonged to Dad.\n",
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "captured"
    assert result["response"]["prompt_id"] == "EVS"

    items = store.list_responses_by_type(conn, "EVS")
    assert len(items) == 1
    export = store.format_evs_export(items)
    assert "Pocket watch" in export
    assert "belonged to Dad" in export

    wiped = store.delete_responses_by_type(conn, "EVS")
    assert wiped["responses_deleted"] == 1
    assert store.list_responses_by_type(conn, "EVS") == []
    conn.close()


def test_poll_once_and_unmatched(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    send_prompt(
        conn,
        client,
        cfg,
        prompt_type="MEM",
        headline="Grade-school days",
        body="Tell me about your grade-school days.",
    )
    mid = client.inject_reply(
        thread_id="thr-unknown",
        subject="Hello random",
        body="not a marvin reply",
    )
    results = poll_once(conn, client, cfg)
    unmatched = [r for r in results if r.get("status") == "unmatched"]
    assert unmatched
    assert Path(unmatched[0]["raw_email_path"]).is_file()
    assert client.messages[mid].raw
    conn.close()


def test_transcript_success_keeps_audio(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    sent = send_prompt(
        conn,
        client,
        cfg,
        prompt_type="MEM",
        headline="Voice",
        body="Say something",
    )
    mid = client.inject_reply(
        thread_id=sent["gmail"]["threadId"],
        subject="Re: [MB-MEM] Voice",
        body="See voice memo.",
        attachments=[("v.wav", "audio/wav", b"RIFF....")],
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "captured"

    monkeypatch.setattr(
        "marvin_capture.whisper_client.transcribe_file",
        lambda path, **kwargs: "transcribed words",
    )
    tx = process_pending_transcriptions(conn, cfg["whisper"])
    assert tx[0]["status"] == "done"
    detail = store.get_response_detail(conn, result["response"]["id"])
    att = detail["attachments"][0]
    assert att["transcript"] == "transcribed words"
    assert Path(att["storage_path"]).read_bytes() == b"RIFF...."
    conn.close()
