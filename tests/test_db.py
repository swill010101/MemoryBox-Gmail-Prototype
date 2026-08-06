"""SQLite storage tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import db as store  # noqa: E402


def test_prompt_response_attachment_roundtrip(tmp_path: Path):
    db_path = tmp_path / "t.db"
    conn = store.init_db(db_path)

    store.insert_prompt(
        conn,
        prompt_id="JRN-20260806",
        prompt_type="JRN",
        subject="[MB-JRN-20260806] What happened today?",
        body="What happened today?",
        gmail_message_id="out1",
        gmail_thread_id="thr1",
    )
    raw = tmp_path / "raw.eml"
    raw.write_text("raw evidence", encoding="utf-8")
    resp = store.insert_response(
        conn,
        prompt_id="JRN-20260806",
        response_text="Walked the dog.",
        raw_email_path=str(raw),
        gmail_message_id="in1",
        gmail_thread_id="thr1",
    )
    audio = tmp_path / "note.m4a"
    audio.write_bytes(b"fake-audio")
    att = store.insert_attachment(
        conn,
        response_id=resp["id"],
        filename="note.m4a",
        mime_type="audio/mp4",
        storage_path=str(audio),
    )
    assert att["is_audio"] == 1
    assert att["transcript_status"] == "pending"

    inbox = store.list_responses(conn, reviewed=False)
    assert len(inbox) == 1
    detail = store.get_response_detail(conn, resp["id"])
    assert detail["response_text"] == "Walked the dog."
    assert detail["attachments"][0]["filename"] == "note.m4a"

    store.update_transcript(conn, att["id"], transcript="hello world", status="done")
    store.mark_reviewed(conn, resp["id"], True)
    conn.commit()

    reviewed = store.list_responses(conn, reviewed=True)
    assert len(reviewed) == 1
    detail2 = store.get_response_detail(conn, resp["id"])
    assert detail2["attachments"][0]["transcript"] == "hello world"
    # Original path still present — never replaced
    assert Path(detail2["raw_email_path"]).read_text(encoding="utf-8") == "raw evidence"
    assert Path(detail2["attachments"][0]["storage_path"]).read_bytes() == b"fake-audio"
    conn.close()
