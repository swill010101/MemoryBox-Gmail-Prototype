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
    split_evs_segments,
)


def test_parse_tokenless_types():
    for raw, typ in (
        ("[MB-JRN] What happened today?", "JRN"),
        ("[MB-MEM] Grade school", "MEM"),
        ("[MB-EVS] Pocket watch", "EVS"),
    ):
        tag = parse_subject_tag(raw)
        assert tag is not None
        assert tag.prompt_type == typ
        assert tag.token == ""
        assert tag.prompt_id == typ


def test_parse_legacy_token_still_works():
    tag = parse_subject_tag("[MB-JRN-20260806] What happened today?")
    assert tag is not None
    assert tag.prompt_id == "JRN-20260806"
    assert tag.token == "20260806"


def test_parse_re_subject_tokenless():
    tag = parse_subject_tag("Re: [MB-EVS] Day you met Mom")
    assert tag is not None
    assert tag.prompt_id == "EVS"


def test_make_subject_tokenless():
    assert make_subject("JRN", "What happened today?") == "[MB-JRN] What happened today?"
    assert make_subject("EVS", "") == "[MB-EVS]"


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
    assert "\n" not in out.split("\n\n")[0]  # first para unwrapped
    assert "Muny and one of the highlights" in out
    assert "I miss you terribly." in out
    assert "Sent from Gmail" not in out
    assert out.count("\n\n") >= 1


def test_strip_sent_from_variants():
    assert "hello" == extract_reply_text("hello\nSent from my iPhone\n")
    assert "hello" == extract_reply_text("hello\nSent from Gmail Mobile\n")


def test_extract_empty_ok():
    assert extract_reply_text("") == ""


def test_split_evs_segments_stop_delimiter():
    text = (
        "Find all the pics of Laura. Stop. "
        "Find all the pictures of grandpa's funny hat. Stop."
    )
    segs = split_evs_segments(text)
    assert len(segs) == 2
    assert segs[0].endswith("Laura.")
    assert "funny hat" in segs[1]
    # Trailing Stop ignored (no follow-on)
    assert split_evs_segments(segs[1] + " Stop.") == [segs[1]]


def test_split_evs_no_stop_single():
    assert split_evs_segments("Just one ask about the watch.") == [
        "Just one ask about the watch."
    ]


def test_split_evs_mid_sentence_stop_kept():
    text = "Please don't stop looking for the album."
    assert split_evs_segments(text) == [text]


def test_split_evs_asr_case_variants():
    text = "Ask one. stop Ask two. STOP! Ask three."
    segs = split_evs_segments(text)
    assert len(segs) == 3
    assert segs[0] == "Ask one."
    assert segs[1] == "Ask two."
    assert segs[2] == "Ask three."
