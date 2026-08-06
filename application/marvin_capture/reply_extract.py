"""Subject tag parsing and reply-body extraction.

Extraction is derived only — the raw email remains authoritative.
"""
from __future__ import annotations

import re
from typing import NamedTuple

# [MB-JRN-20260806] or [MB-MEM-000123]
SUBJECT_TAG_RE = re.compile(r"\[MB-([A-Z]+)-([A-Za-z0-9]+)\]")

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


class SubjectTag(NamedTuple):
    prompt_type: str
    token: str
    prompt_id: str  # TYPE-TOKEN e.g. JRN-20260806
    raw: str


def parse_subject_tag(subject: str | None) -> SubjectTag | None:
    if not subject:
        return None
    match = SUBJECT_TAG_RE.search(subject)
    if not match:
        return None
    prompt_type, token = match.group(1).upper(), match.group(2)
    return SubjectTag(
        prompt_type=prompt_type,
        token=token,
        prompt_id=f"{prompt_type}-{token}",
        raw=match.group(0),
    )


def make_subject(prompt_type: str, token: str, headline: str) -> str:
    tag = f"[MB-{prompt_type.upper()}-{token}]"
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


def extract_reply_text(body: str, *, is_html: bool = False) -> str:
    """Return only the newly written reply content.

    Strips quoted threads and common reply headers. Never mutates the raw email.
    """
    if is_html:
        body = html_to_text(body)

    text = body.replace("\r\n", "\n").replace("\r", "\n")

    cut_points: list[int] = []
    for pattern in (ON_WROTE_RE, OUTLOOK_HEADER_RE):
        m = pattern.search(text)
        if m:
            cut_points.append(m.start())

    # Outlook-style From: block after a blank line, followed by Sent/To/Subject
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
        # stop at signature delimiter if remaining is short signature-like
        if line.strip() == "--":
            break
        if line.strip() == "-- ":
            break
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    # collapse excessive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned
