"""Tests for subject tags and reply extraction."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture.reply_extract import (  # noqa: E402
    extract_reply_text,
    make_subject,
    parse_subject_tag,
)


def test_parse_journal_tag():
    tag = parse_subject_tag("[MB-JRN-20260806] What happened today?")
    assert tag is not None
    assert tag.prompt_type == "JRN"
    assert tag.token == "20260806"
    assert tag.prompt_id == "JRN-20260806"


def test_parse_mem_tag_in_re_subject():
    tag = parse_subject_tag("Re: [MB-MEM-000123] Tell me about your grade-school days.")
    assert tag is not None
    assert tag.prompt_id == "MEM-000123"


def test_make_subject():
    assert make_subject("JRN", "20260806", "What happened today?") == (
        "[MB-JRN-20260806] What happened today?"
    )


def test_extract_strips_gmail_quote():
    body = (
        "Had coffee with Dad and walked the dog.\n"
        "\n"
        "On Wed, Aug 6, 2026 at 6:00 PM Marvin <marvin@example.com> wrote:\n"
        "> What happened today?\n"
    )
    assert extract_reply_text(body) == "Had coffee with Dad and walked the dog."


def test_extract_strips_line_quotes():
    body = "Short reply.\n> quoted\n> more"
    assert extract_reply_text(body) == "Short reply."


def test_extract_html_gmail_quote():
    html = (
        "<div>Voice note later.<br></div>"
        '<div class="gmail_quote">On Tue wrote:<blockquote>prompt</blockquote></div>'
    )
    assert extract_reply_text(html, is_html=True) == "Voice note later."


def test_extract_empty_ok():
    assert extract_reply_text("") == ""
