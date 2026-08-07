"""Subject tag parsing and reply-body extraction.

Extraction is derived only — the raw email remains authoritative.
"""
from __future__ import annotations

import re
from typing import NamedTuple

# [MB-JRN] headline   or legacy [MB-JRN-20260806] headline
SUBJECT_TAG_RE = re.compile(r"\[MB-([A-Z]+)(?:-([A-Za-z0-9]+))?\]")

# Common reply quote markers
ON_WROTE_RE = re.compile(
    r"^\s*On\s.+wrote:\s*$",
    re.IGNORECASE | re.MULTILINE,
)
OUTLOOK_HEADER_RE = re.compile(
    r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
FROM_BLOCK_RE = re.compile(
    r"^\s*From:\s+.+$",
    re.IGNORECASE | re.MULTILINE,
)
GMAIL_QUOTE_ATTR = re.compile(r'<div[^>]*class="[^"]*gmail_quote[^"]*"[^>]*>', re.IGNORECASE)

# Mobile / client footers — not part of the real reply
SENT_FROM_RE = re.compile(
    r"(?im)^[ \t]*(?:Tom\s+)?Sent from (?:Gmail|my iPhone|my iPad|my Android|"
    r"Mail for Windows|Yahoo Mail|Outlook for iOS|Outlook for Android)"
    r"(?:\s+Mobile)?[ \t]*$"
)
SENT_FROM_INLINE_RE = re.compile(
    r"(?i)(?:\s*)(?:Tom\s+)?Sent from (?:Gmail|my iPhone|my iPad|my Android|"
    r"Mail for Windows|Yahoo Mail|Outlook for iOS|Outlook for Android)"
    r"(?:\s+Mobile)?\s*$"
)


class SubjectTag(NamedTuple):
    prompt_type: str
    token: str  # empty when subject is [MB-TYPE] only
    prompt_id: str  # TYPE or TYPE-TOKEN
    raw: str


def parse_subject_tag(subject: str | None) -> SubjectTag | None:
    if not subject:
        return None
    match = SUBJECT_TAG_RE.search(subject)
    if not match:
        return None
    prompt_type = match.group(1).upper()
    token = (match.group(2) or "").strip()
    prompt_id = f"{prompt_type}-{token}" if token else prompt_type
    return SubjectTag(
        prompt_type=prompt_type,
        token=token,
        prompt_id=prompt_id,
        raw=match.group(0),
    )


def make_subject(prompt_type: str, headline: str, token: str = "") -> str:
    """Build outbound subject. Token is optional (legacy); prefer [MB-TYPE] only."""
    if token:
        tag = f"[MB-{prompt_type.upper()}-{token}]"
    else:
        tag = f"[MB-{prompt_type.upper()}]"
    headline = headline.strip()
    return f"{tag} {headline}" if headline else tag


def html_to_text(html: str) -> str:
    """Minimal HTML → text for reply extraction (not a full renderer)."""
    text = GMAIL_QUOTE_ATTR.split(html, maxsplit=1)[0]
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
    )
    return text


def normalize_for_dedupe(text: str) -> str:
    """Collapse whitespace so soft-wrap / resend variants compare equal."""
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def unwrap_soft_line_breaks(text: str) -> str:
    """Join Gmail soft-wraps; keep blank-line paragraph breaks.

    Single newlines between non-empty lines are treated as soft wraps (no way
    to distinguish hard Enter from wrap in plain Gmail). Double+ newlines stay.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n", text)
    rebuilt: list[str] = []
    for para in paragraphs:
        parts = [ln.strip() for ln in para.split("\n") if ln.strip() != ""]
        if not parts:
            continue
        joined = parts[0]
        for nxt in parts[1:]:
            if joined.endswith("-") and not joined.endswith("--"):
                joined = joined[:-1] + nxt
            else:
                joined = f"{joined} {nxt}"
            joined = re.sub(r"[ \t]{2,}", " ", joined)
        rebuilt.append(joined.strip())
    return "\n\n".join(rebuilt).strip()


def strip_mobile_signatures(text: str) -> str:
    text = SENT_FROM_RE.sub("", text)
    text = SENT_FROM_INLINE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_reply_text(body: str, *, is_html: bool = False) -> str:
    """Return only the newly written reply content.

    Strips quoted threads, mobile signatures, and soft wraps.
    Never mutates the raw email.
    """
    if is_html:
        body = html_to_text(body)

    text = body.replace("\r\n", "\n").replace("\r", "\n")

    cut_points: list[int] = []
    for pattern in (ON_WROTE_RE, OUTLOOK_HEADER_RE):
        m = pattern.search(text)
        if m:
            cut_points.append(m.start())

    for m in FROM_BLOCK_RE.finditer(text):
        before = text[: m.start()]
        if not before.endswith("\n\n") and not before.rstrip(" ").endswith("\n\n"):
            continue
        window = text[m.start() : m.start() + 240]
        if re.search(r"(?im)^(sent|to|subject):", window):
            cut_points.append(m.start())

    if cut_points:
        text = text[: min(cut_points)]

    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith(">"):
            continue
        if line.strip() in ("--", "-- "):
            break
        if SENT_FROM_RE.match(line):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = strip_mobile_signatures(cleaned)
    cleaned = unwrap_soft_line_breaks(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
