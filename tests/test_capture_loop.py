"""End-to-end capture loop with FakeGmailClient."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import db as store  # noqa: E402
from marvin_capture.gmail_client import FakeGmailClient  # noqa: E402
from marvin_capture.plus_address import build_plus_address  # noqa: E402
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


def test_send_reply_capture_preserve_and_trash(tmp_path: Path):
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

    jrn_addr = build_plus_address(cfg["gmail"]["user_email"], "journal")
    reply_body = (
        "Met Sarah for lunch. Attached a photo.\n\n"
        "On Wed, Aug 6, 2026 at 6:00 PM Marvin wrote:\n"
        "> What happened today?\n"
    )
    photo = b"\xff\xd8\xfffakejpeg"
    voice = b"fake-m4a-bytes"
    mid = client.inject_reply(
        thread_id=thread_id,
        subject="Re: What happened today?",
        body=reply_body,
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
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
    assert len(detail["attachments"]) == 2

    assert mid in client.trashed
    assert FakeGmailClient.TRASH_LABEL in client.messages[mid].label_ids

    assert process_message(conn, client, cfg, mid) is None
    conn.close()


def test_journal_compose_to_plus_jrn(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    jrn_addr = build_plus_address(cfg["gmail"]["user_email"], "jrn")
    mid = client.inject_reply(
        thread_id="thr-adhoc-jrn",
        subject="Tuesday notes",
        body="Walked to the gym.",
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "captured"
    assert result["response"]["prompt_id"] == "JRN"
    assert mid in client.trashed
    conn.close()


def test_subject_only_without_plus_is_unmatched(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    mid = client.inject_reply(
        thread_id="thr-old-tag",
        subject="[MB-JRN] legacy subject only",
        body="Should not capture.",
        to_addr="tom@local.test",
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "unmatched"
    assert mid not in client.trashed
    conn.close()


def test_mem_adhoc_plus_unmatched(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    mem_addr = build_plus_address(cfg["gmail"]["user_email"], "MEM")
    mid = client.inject_reply(
        thread_id="thr-mem-adhoc",
        subject="Random MEM note",
        body="Not a bank answer.",
        to_addr=mem_addr,
        delivered_to=mem_addr,
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "unmatched"
    assert mid not in client.trashed
    conn.close()


def test_mem_reply_thread_bound_and_trash(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    sent = send_prompt(
        conn,
        client,
        cfg,
        prompt_type="MEM",
        token="1",
        headline="Grade-school days",
        body="Tell me about your grade-school days.",
        reply_to=build_plus_address(cfg["gmail"]["user_email"], "MEM"),
    )
    mem_addr = build_plus_address(cfg["gmail"]["user_email"], "MEM")
    mid = client.inject_reply(
        thread_id=sent["gmail"]["threadId"],
        subject="Re: Grade-school days",
        body="I loved recess.",
        to_addr=mem_addr,
        delivered_to=mem_addr,
    )
    result = process_message(conn, client, cfg, mid)
    assert result["status"] == "captured"
    assert result["response"]["prompt_id"] == "MEM-1"
    assert mid in client.trashed
    conn.close()


def test_duplicate_skipped_trashes_message(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    jrn_addr = build_plus_address(cfg["gmail"]["user_email"], "journal")
    body = "Same journal entry."
    mid1 = client.inject_reply(
        thread_id="thr-dup",
        subject="Journal",
        body=body,
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
    )
    assert process_message(conn, client, cfg, mid1)["status"] == "captured"
    mid2 = client.inject_reply(
        thread_id="thr-dup",
        subject="Journal",
        body=body,
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
    )
    r2 = process_message(conn, client, cfg, mid2)
    assert r2["status"] == "duplicate_skipped"
    assert mid2 in client.trashed
    conn.close()


def test_poll_once_and_unmatched(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])

    mem_addr = build_plus_address(cfg["gmail"]["user_email"], "MEM")
    mid = client.inject_reply(
        thread_id="thr-unknown",
        subject="Hello random",
        body="not a marvin reply",
        to_addr=mem_addr,
        delivered_to=mem_addr,
    )
    results = poll_once(conn, client, cfg)
    unmatched = [r for r in results if r.get("status") == "unmatched"]
    assert unmatched
    assert Path(unmatched[0]["raw_email_path"]).is_file()
    assert mid not in client.trashed
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
        reply_to=build_plus_address(cfg["gmail"]["user_email"], "MEM"),
    )
    mem_addr = build_plus_address(cfg["gmail"]["user_email"], "MEM")
    mid = client.inject_reply(
        thread_id=sent["gmail"]["threadId"],
        subject="Re: Voice",
        body="See voice memo.",
        to_addr=mem_addr,
        delivered_to=mem_addr,
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


def test_adhoc_jrn_soft_dedupe_and_sent_only(tmp_path: Path):
    cfg = _cfg(tmp_path)
    client = FakeGmailClient()
    conn = store.init_db(cfg["sqlite_path"])
    jrn_addr = build_plus_address(cfg["gmail"]["user_email"], "journal")

    body = "Grandkids went home to TX. Sports starting back up."
    mid1 = client.inject_reply(
        thread_id="thr-jrn-1",
        subject="Journal",
        body=body,
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
        label_ids=["INBOX", "SENT"],
    )
    r1 = process_message(conn, client, cfg, mid1)
    assert r1["status"] == "captured"
    assert "Ad-hoc journal" in r1["response"]["prompt_body"]

    mid2 = client.inject_reply(
        thread_id="thr-jrn-1",
        subject="Journal",
        body="Grandkids went home to TX.\nSports starting back up.",
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
        label_ids=["INBOX", "SENT"],
    )
    r2 = process_message(conn, client, cfg, mid2)
    assert r2["status"] == "duplicate_skipped"

    inbox = store.list_responses(conn, reviewed=False)
    assert len(inbox) == 1

    mid3 = client.inject_reply(
        thread_id="thr-jrn-1",
        subject="Journal",
        body=body + " extra should not matter for sent-only skip",
        to_addr=jrn_addr,
        delivered_to=jrn_addr,
        label_ids=["SENT"],
    )
    r3 = process_message(conn, client, cfg, mid3)
    assert r3["status"] == "sent_only_skipped"
    assert len(store.list_responses(conn, reviewed=False)) == 1
    conn.close()


def test_auto_review_duplicate_bodies(tmp_path: Path):
    cfg = _cfg(tmp_path)
    conn = store.init_db(cfg["sqlite_path"])
    store.insert_prompt(
        conn,
        prompt_id="JRN",
        prompt_type="JRN",
        subject="Journal",
        body="(Ad-hoc journal — you emailed this in; Marvin did not send an outbound prompt.)",
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text="Same day note.",
        raw_email_path=str(tmp_path / "a.eml"),
        gmail_message_id="m1",
        gmail_thread_id="t1",
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text="Same   day\nnote.",
        raw_email_path=str(tmp_path / "b.eml"),
        gmail_message_id="m2",
        gmail_thread_id="t1",
    )
    n = store.auto_review_duplicate_bodies(conn)
    assert n == 1
    rows = store.list_responses(conn, reviewed=False)
    assert len(rows) == 1
    assert rows[0]["gmail_message_id"] == "m1"
    conn.close()


def test_auto_review_near_duplicate_journals(tmp_path: Path):
    cfg = _cfg(tmp_path)
    conn = store.init_db(cfg["sqlite_path"])
    store.insert_prompt(
        conn,
        prompt_id="JRN",
        prompt_type="JRN",
        subject="Journal",
        body="(Ad-hoc journal)",
    )
    base = (
        "Today, the grandkids and Laura went home to TX. They have school coming up "
        "and sports starting back up again. Baseball, Hockey for Sam and Softball for Ava. "
        "We had a great time here in St. Louis, playing games, Top Golf, Mini Golf, "
        "Sky Zone, Main Event Games, a game night, Ava's Ice Cream shop."
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=base,
        raw_email_path=str(tmp_path / "a.eml"),
        gmail_message_id="j1",
        gmail_thread_id="tj",
        received_date="2026-08-07T14:50:47",
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=base + " Have a great day!",
        raw_email_path=str(tmp_path / "b.eml"),
        gmail_message_id="j2",
        gmail_thread_id="tj",
        received_date="2026-08-07T14:55:50",
    )
    n = store.auto_review_duplicate_bodies(conn)
    assert n == 1
    assert len(store.list_responses(conn, reviewed=False)) == 1
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=(
            "Walked to Crunch Gym this morning. Joined as part of Medicare. "
            "People seem nice. Going to start walking tomorrow and the next day."
        ),
        raw_email_path=str(tmp_path / "c.eml"),
        gmail_message_id="j3",
        gmail_thread_id="tj2",
        received_date="2026-08-07T18:00:00",
    )
    assert store.auto_review_duplicate_bodies(conn) == 0
    assert len(store.list_responses(conn, reviewed=False)) == 2
    conn.close()


def test_auto_review_jrn_time_window(tmp_path: Path):
    cfg = _cfg(tmp_path)
    conn = store.init_db(cfg["sqlite_path"])
    store.insert_prompt(
        conn,
        prompt_id="JRN",
        prompt_type="JRN",
        subject="Journal",
        body="(Ad-hoc journal)",
    )
    a = (
        "Today the grandkids went home to Texas. School and sports are starting. "
        "We had fun in St Louis with Top Golf and Sky Zone."
    )
    b = (
        "Today the grandkids went home to TX. School and sports starting soon. "
        "We had fun in St. Louis with Top Golf and Sky Zone."
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=a,
        raw_email_path=str(tmp_path / "a.eml"),
        gmail_message_id="t1",
        gmail_thread_id="thr-a",
        received_date="2026-08-07T14:50:47",
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=b,
        raw_email_path=str(tmp_path / "b.eml"),
        gmail_message_id="t2",
        gmail_thread_id="thr-b",
        received_date="2026-08-07T14:55:50",
    )
    assert store.auto_review_duplicate_bodies(conn) == 1
    assert len(store.list_responses(conn, reviewed=False)) == 1
    conn.close()


def test_auto_review_keeps_new_jrn_reply_on_same_thread(tmp_path: Path):
    cfg = _cfg(tmp_path)
    conn = store.init_db(cfg["sqlite_path"])
    store.insert_prompt(
        conn,
        prompt_id="JRN",
        prompt_type="JRN",
        subject="Journal",
        body="(Ad-hoc journal)",
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=(
            "Today, the grandkids and Laura went home to TX. They have school "
            "coming up and sports starting back up again."
        ),
        raw_email_path=str(tmp_path / "a.eml"),
        gmail_message_id="old",
        gmail_thread_id="thr-jrn-shared",
        received_date="2026-08-07T14:50:47",
    )
    store.insert_response(
        conn,
        prompt_id="JRN",
        response_text=(
            "Today I got up, and the doors in the hall were open. That told me "
            "that the house was quiet after the grandkids left. On the MemoryBox "
            "front, I completed the first pass of the business plan."
        ),
        raw_email_path=str(tmp_path / "b.eml"),
        gmail_message_id="new",
        gmail_thread_id="thr-jrn-shared",
        received_date="2026-08-08T06:10:42",
    )
    assert store.auto_review_duplicate_bodies(conn) == 0
    inbox = store.list_responses(conn, reviewed=False)
    assert len(inbox) == 2
    conn.close()
