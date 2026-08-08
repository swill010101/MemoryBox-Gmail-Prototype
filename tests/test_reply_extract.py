"""Tests for plus-address parsing and reply extraction."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture.plus_address import (  # noqa: E402
    build_plus_address,
    build_poll_query,
    capture_addresses,
    extract_plus_routing,
    map_alias_to_prompt_type,
    parse_plus_tag,
)
from marvin_capture.reply_extract import (  # noqa: E402
    extract_reply_text,
    make_subject,
    parse_subject_tag,
)


def test_parse_plus_tag():
    assert parse_plus_tag("tom+journal@gmail.com") == "journal"
    assert parse_plus_tag("tom+MEM@gmail.com") == "mem"
    assert parse_plus_tag("Tom <tom+jrn@gmail.com>") == "jrn"
    assert parse_plus_tag("tom@gmail.com") is None


def test_map_alias_to_prompt_type():
    assert map_alias_to_prompt_type("journal") == "JRN"
    assert map_alias_to_prompt_type("JRN") == "JRN"
    assert map_alias_to_prompt_type("mem") == "MEM"
    assert map_alias_to_prompt_type("memorybox") is None


def test_extract_plus_routing_headers():
    headers = {
        "to": "Marvin <marvin@local.test>",
        "delivered-to": "tom+journal@gmail.com",
    }
    ptype, addr = extract_plus_routing(headers, user_email="tom@gmail.com")
    assert ptype == "JRN"
    assert "journal" in addr


def test_build_plus_address_and_poll_query():
    assert build_plus_address("tom@gmail.com", "MEM") == "tom+MEM@gmail.com"
    q = build_poll_query("tom@gmail.com", processed_label="MB/Processed")
    assert "-in:trash" in q
    assert "to:tom+journal@gmail.com" in q


def test_capture_addresses_table():
    cfg = {"gmail": {"user_email": "tom@gmail.com"}}
    rows = capture_addresses(cfg)
    assert any("journal" in r["address"] for r in rows)
    assert any("+MEM@" in r["address"] for r in rows)


def test_parse_subject_tag_legacy():
    tag = parse_subject_tag("[MB-JRN-20260806] What happened today?")
    assert tag is not None
    assert tag.prompt_id == "JRN-20260806"


def test_make_subject_legacy():
    assert make_subject("JRN", "What happened today?") == "[MB-JRN] What happened today?"


def test_extract_strips_gmail_quote():
    body = (
        "Had coffee with Dad and walked the dog.\n"
        "\n"
        "On Wed, Aug 6, 2026 at 6:00 PM Marvin <marvin@example.com> wrote:\n"
        "> What happened today?\n"
    )
    assert extract_reply_text(body) == "Had coffee with Dad and walked the dog."


def test_unwrap_soft_line_breaks_keeps_paragraphs():
    body = (
        "Today we went to see Meet Me in St. Louis at the Muny and one of the\n"
        "highlights of the movie and play is the singing of Have Yourself a Merry\n"
        "Little Christmas.\n"
        "\n"
        "I miss you terribly.\n"
        "Tom Sent from Gmail Mobile\n"
    )
    out = extract_reply_text(body)
    assert "\n" not in out.split("\n\n")[0]
    assert "Muny and one of the highlights" in out
    assert "I miss you terribly." in out
    assert "Sent from Gmail" not in out


def test_strip_sent_from_variants():
    assert "hello" == extract_reply_text("hello\nSent from my iPhone\n")
    assert "hello" == extract_reply_text("hello\nSent from Gmail Mobile\n")


def test_extract_empty_ok():
    assert extract_reply_text("") == ""
