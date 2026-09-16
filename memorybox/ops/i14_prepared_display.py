"""Displayability vs voice for stored prepared household-email text.

Length and character class never decide authored display by themselves.
Voice still requires authenticated From and quote_quality=clean at load time.
This module only answers: is the stored cleaned text substantive authored
content, a signoff, debris, device output, or a confirmed fragment to omit.
"""
from __future__ import annotations

import re
from typing import Any

from memorybox.ops.i14_prepared_text import classify_residue

KIND_DISPLAYABLE_AUTHORED = "displayable_authored"
KIND_SIGNATURE_CLOSING = "signature_closing"
KIND_ENCODING_DEBRIS = "encoding_debris"
KIND_AUTOMATED_FRAGMENT = "automated_fragment"
KIND_UNCERTAIN_FRAGMENT = "uncertain_fragment"
KIND_BLANK = "blank"

VOICE_ELIGIBLE_KINDS = frozenset({KIND_DISPLAYABLE_AUTHORED})

DISPOSITION_AUTHORED = "authored_displayable"
DISPOSITION_NON_SUBSTANTIVE = "non_substantive"
DISPOSITION_UNAVAILABLE = "prepared_text_unavailable"
DISPOSITION_ATTACHMENT = "attachment_only"
DISPOSITION_EMPTY = "correctly_empty"
DISPOSITION_UNCERTAIN = "uncertain"
PREPARED_TEXT_DISPOSITIONS = (
    DISPOSITION_AUTHORED,
    DISPOSITION_NON_SUBSTANTIVE,
    DISPOSITION_UNAVAILABLE,
    DISPOSITION_ATTACHMENT,
    DISPOSITION_EMPTY,
    DISPOSITION_UNCERTAIN,
)
VOICE_FORBIDDEN_DISPOSITIONS = frozenset(
    {
        DISPOSITION_NON_SUBSTANTIVE,
        DISPOSITION_UNAVAILABLE,
        DISPOSITION_ATTACHMENT,
        DISPOSITION_EMPTY,
        DISPOSITION_UNCERTAIN,
    }
)

_BOM = "\ufeff"
_ZW = "\u200b"
_MAC = re.compile(r"(?i)\[(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\]")
_PRINTER = re.compile(r"(?i)\bKM-\d{3,6}\b")
_LINK_FRAG = re.compile(r"(?i)^\+?\s*Link\s*-?\s*$")
_SEPARATOR = re.compile(r"^[\s_—\-–]+$")
_VOCATIVE_SIGNOFF = re.compile(r"^[A-Za-z][A-Za-z''.\-]{0,40},$")
_QUESTION_ONLY = re.compile(r"^\?+$")
_CONFIRMED_FRAGMENT = re.compile(
    r"(?is)^A\s+a\s+ml\b.*_{3,}\s*$"
)


def _strip_invisible(text: str) -> str:
    return (text or "").replace(_BOM, "").replace(_ZW, "")


def classify_stored_prepared(text: str, *, from_person: str = "") -> str:
    """Classify already-cleaned stored prepared text. Does not re-prepare."""
    del from_person
    raw = text or ""
    visible = _strip_invisible(raw)
    if not visible.strip():
        if raw.strip() or _BOM in raw or _ZW in raw:
            return KIND_ENCODING_DEBRIS
        return KIND_BLANK

    t = visible.strip()
    if classify_residue(t):
        return KIND_ENCODING_DEBRIS
    if _SEPARATOR.match(t):
        return KIND_SIGNATURE_CLOSING
    if _CONFIRMED_FRAGMENT.match(t):
        return KIND_UNCERTAIN_FRAGMENT
    if _MAC.search(t) or _PRINTER.search(t):
        return KIND_AUTOMATED_FRAGMENT
    if _LINK_FRAG.match(t):
        return KIND_AUTOMATED_FRAGMENT
    if _VOCATIVE_SIGNOFF.match(t):
        return KIND_SIGNATURE_CLOSING
    if _QUESTION_ONLY.match(t):
        return KIND_DISPLAYABLE_AUTHORED
    return KIND_DISPLAYABLE_AUTHORED


def is_displayable(kind: str) -> bool:
    return kind == KIND_DISPLAYABLE_AUTHORED


def is_voice_eligible_kind(kind: str) -> bool:
    return kind in VOICE_ELIGIBLE_KINDS


def prepared_text_is_displayable(text: str, *, from_person: str = "") -> bool:
    return is_displayable(classify_stored_prepared(text, from_person=from_person))


def kind_to_stored_disposition(kind: str) -> str | None:
    """Map a stored-cleaned kind to a disposition when text is present or omitted junk."""
    if kind == KIND_DISPLAYABLE_AUTHORED:
        return DISPOSITION_AUTHORED
    if kind in {
        KIND_SIGNATURE_CLOSING,
        KIND_ENCODING_DEBRIS,
        KIND_AUTOMATED_FRAGMENT,
        KIND_UNCERTAIN_FRAGMENT,
    }:
        return DISPOSITION_NON_SUBSTANTIVE
    if kind == KIND_BLANK:
        return None
    return DISPOSITION_UNCERTAIN


def empty_category_to_disposition(category: str, *, has_attachments: bool = False) -> str:
    if category == "authored_prepared":
        return DISPOSITION_AUTHORED
    if category == "attachment_only":
        return DISPOSITION_ATTACHMENT
    if category in {"cleanup_removed_meaningful", "html_only_or_alt_part"}:
        return DISPOSITION_UNAVAILABLE
    if category in {
        "encoding_or_parser_failure",
        "commercial_or_automated_shell",
        "other_known",
    }:
        return DISPOSITION_NON_SUBSTANTIVE
    if category in {
        "original_genuinely_empty",
        "quoted_history_only",
        "forward_history_only",
    }:
        if has_attachments and category == "original_genuinely_empty":
            return DISPOSITION_ATTACHMENT
        return DISPOSITION_EMPTY
    if category == "unexplained":
        return DISPOSITION_UNCERTAIN
    return DISPOSITION_UNCERTAIN


def decide_prepared_row(
    text: str,
    *,
    from_authenticated: bool,
    quote_quality: str,
    from_person: str = "",
    has_attachments: bool = False,
    empty_category: str = "",
) -> dict[str, Any]:
    kind = classify_stored_prepared(text, from_person=from_person)
    mapped = kind_to_stored_disposition(kind)
    if mapped == DISPOSITION_AUTHORED:
        voice = bool(
            from_authenticated and str(quote_quality or "") == "clean"
        )
        return {
            "kind": kind,
            "displayable": True,
            "voice_eligible_kind": True,
            "voice_corpus": voice,
            "stored_cleaned": text or "",
            "prepared_text_disposition": DISPOSITION_AUTHORED,
        }
    if mapped == DISPOSITION_NON_SUBSTANTIVE:
        return {
            "kind": kind,
            "displayable": False,
            "voice_eligible_kind": False,
            "voice_corpus": False,
            "stored_cleaned": "",
            "prepared_text_disposition": DISPOSITION_NON_SUBSTANTIVE,
        }
    if mapped == DISPOSITION_UNCERTAIN:
        return {
            "kind": kind,
            "displayable": False,
            "voice_eligible_kind": False,
            "voice_corpus": False,
            "stored_cleaned": "",
            "prepared_text_disposition": DISPOSITION_UNCERTAIN,
        }
    disposition = empty_category_to_disposition(
        empty_category, has_attachments=has_attachments
    )
    if has_attachments and disposition == DISPOSITION_EMPTY and not (text or "").strip():
        disposition = DISPOSITION_ATTACHMENT
    if not empty_category:
        if has_attachments:
            disposition = DISPOSITION_ATTACHMENT
        else:
            disposition = DISPOSITION_EMPTY
    return {
        "kind": kind,
        "displayable": False,
        "voice_eligible_kind": False,
        "voice_corpus": False,
        "stored_cleaned": "",
        "prepared_text_disposition": disposition,
    }


def display_and_voice_for_stored(
    text: str,
    *,
    from_authenticated: bool,
    quote_quality: str,
    from_person: str = "",
    has_attachments: bool = False,
    empty_category: str = "",
) -> dict[str, Any]:
    return decide_prepared_row(
        text,
        from_authenticated=from_authenticated,
        quote_quality=quote_quality,
        from_person=from_person,
        has_attachments=has_attachments,
        empty_category=empty_category,
    )


def empty_category_for_kind(kind: str) -> tuple[str, str]:
    """Empty-body category/disposition when stored text is omitted, not missing."""
    if kind == KIND_SIGNATURE_CLOSING:
        return "other_known", "correct_empty"
    if kind == KIND_ENCODING_DEBRIS:
        return "encoding_or_parser_failure", "safe_nondisplayable"
    if kind == KIND_AUTOMATED_FRAGMENT:
        return "commercial_or_automated_shell", "correct_empty"
    if kind == KIND_UNCERTAIN_FRAGMENT:
        return "other_known", "safe_nondisplayable"
    if kind == KIND_BLANK:
        return "original_genuinely_empty", "correct_empty"
    return "other_known", "safe_nondisplayable"


# Founder-reviewed short-text outcomes (v2 stored cleaned). Do not treat as live data.
FOUNDER_SHORT_TEXT_V3 = (
    ("Thanks", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("Ok", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("Yes", "Sarah", KIND_DISPLAYABLE_AUTHORED, True),
    ("No!", "Michelle", KIND_DISPLAYABLE_AUTHORED, True),
    ("Great.", "Sarah", KIND_DISPLAYABLE_AUTHORED, True),
    ("Good job", "Jeff", KIND_DISPLAYABLE_AUTHORED, True),
    ("FYI\n\nTom", "Tom", KIND_DISPLAYABLE_AUTHORED, True),
    ("Tom", "Tom", KIND_DISPLAYABLE_AUTHORED, True),
    ("Love,\n\nTom", "Tom", KIND_DISPLAYABLE_AUTHORED, True),
    ("Sue - 6363462342\nTom - 3144023997", "Tom", KIND_DISPLAYABLE_AUTHORED, True),
    ("What day?", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("Update......", "Tom", KIND_DISPLAYABLE_AUTHORED, True),
    ("Nice!", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("👍🎉🙌🏖", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("Thanks!", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("Thanks !", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("??????", "Sue", KIND_DISPLAYABLE_AUTHORED, True),
    ("Ed,", "Tom", KIND_SIGNATURE_CLOSING, False),
    ("A a ml\n\n________________________________", "ph", KIND_UNCERTAIN_FRAGMENT, False),
    ("________________________________", "Cathy", KIND_SIGNATURE_CLOSING, False),
    ("\ufeff", "Sarah", KIND_ENCODING_DEBRIS, False),
    ("KM-3060\n[00:c0:ee:1f:4a:31]\n-------------------", "Greg", KIND_AUTOMATED_FRAGMENT, False),
    ("+ Link -", "Bob", KIND_AUTOMATED_FRAGMENT, False),
)

V2_SHORT_NONBLANK_CLEANUP = 180
V3_SHORT_DISPLAYABLE = 165
V3_SHORT_OMITTED = 15
V3_VOICE_IN_180 = 22
V2_VOICE_IN_180 = 22


def html_recovery_beyond_v2_eight_letter(payload: dict) -> bool:
    """True when v2's 8-letter preference would keep unusable plain and skip HTML authored text."""
    from memorybox.ops.i14_prepared_text import (
        html_to_plain,
        prepare_message_text,
        select_authored_source,
        source_is_meaningful,
    )

    body = str(payload.get("body_text") or payload.get("body") or "")
    html_raw = str(payload.get("body_html") or "")
    if not html_raw.strip():
        return False
    html_plain = html_to_plain(html_raw)
    body_after = prepare_message_text(body).authored
    html_after = prepare_message_text(html_plain).authored
    v2_prefers_body = source_is_meaningful(body)
    body_unusable = not prepared_text_is_displayable(body_after)
    html_usable = prepared_text_is_displayable(html_after)
    new_src = select_authored_source(payload)
    return bool(
        v2_prefers_body
        and body_unusable
        and html_usable
        and new_src.kind in {"html", "alt_part"}
    )
