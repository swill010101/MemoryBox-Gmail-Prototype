"""Ask-time authored communication text. Raw Email remains source of truth."""
from __future__ import annotations

import re
from typing import Any

_GT_QUOTE = re.compile(r"(?m)^>+.*$")
_SIG = re.compile(
    r"(?m)^(--)[ \t]*$|^Sent from my iPhone.*$|^Get Outlook for.*$",
)
_QUOTE_CUT = re.compile(
    r"(?is)"
    r"(?:\n|^)\s*On .{8,400}?\bwrote:\s*"
    r"|-----Original Message-----"
    r"|(?:\n|^)_{8,}\s*\nFrom:"
    r"|(?:\n|^)Begin forwarded message:"
    r"|(?:\n|^)From:\s+.+\nSent:"
)


def plain_email_body(payload: dict[str, Any] | None, *, excerpt: str = "") -> str:
    """Plain text from Takeout payload. Hotmail rows are often HTML-only."""
    data = payload if isinstance(payload, dict) else {}
    text = str(data.get("body_text") or "").strip()
    if text:
        return text
    html = str(data.get("body_html") or data.get("html") or "").strip()
    if html:
        import html as htmlmod

        cleaned = re.sub(r"(?is)<(script|style|head)\b[^>]*>.*?</\1>", " ", html)
        cleaned = re.sub(r"(?is)<!--.*?-->", " ", cleaned)
        converted = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
        converted = re.sub(r"(?i)</(p|div|tr|h[1-6]|li)>", "\n", converted)
        converted = re.sub(r"<[^>]+>", " ", converted)
        converted = htmlmod.unescape(re.sub(r"[ \t]+\n", "\n", converted))
        converted = re.sub(r"\n{3,}", "\n\n", converted).strip()
        if converted:
            return converted
    return str(data.get("snippet") or data.get("text") or excerpt or "").strip()


def authored_email_text(body: str) -> tuple[str, dict[str, bool]]:
    from memorybox.explore.email_attach import split_quoted_email
    flags = {"quote_uncertain": False, "boilerplate_uncertain": False}
    turns = split_quoted_email(body or "")
    lead = str((turns[0] or {}).get("body") or "").strip() if turns else (body or "").strip()
    if not lead and body:
        lead = body.strip()
        flags["quote_uncertain"] = True
    cut_m = _QUOTE_CUT.search("\n" + lead)
    if cut_m and cut_m.start() > 1:
        lead = lead[: cut_m.start() - 1].strip()
    stripped = _GT_QUOTE.sub("", lead).strip()
    if stripped != lead.strip():
        lead = stripped
    cut = _SIG.sub("", lead).strip()
    if cut and cut != lead:
        lead = cut
    if len(turns) > 1 and not turns[0].get("body"):
        flags["quote_uncertain"] = True
    if not lead:
        flags["quote_uncertain"] = True
        lead = (body or "").strip()[:4000]
    return lead[:8000], flags


def sms_location_assertions(
    body: str,
    *,
    attachments: list[dict[str, Any]] | None = None,
    shared_location: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Timestamp is never a location basis."""
    out: list[dict[str, Any]] = []
    text = body or ""
    if shared_location and (
        shared_location.get("latitude") is not None
        or shared_location.get("place")
        or shared_location.get("url")
    ):
        out.append(
            {
                "place": shared_location.get("place") or shared_location.get("url"),
                "latitude": shared_location.get("latitude"),
                "longitude": shared_location.get("longitude"),
                "basis": "shared_location_payload",
            }
        )
    if re.search(
        r"(?i)\b(?:i(?:['’]m| am) (?:at|in)|we(?:['’]re| are) (?:at|in))\s+[A-Z]",
        text,
    ) or re.search(r"(?i)https?://(?:maps\.google|goo\.gl/maps|maps\.app\.goo\.gl)", text):
        m = re.search(
            r"(?i)(?:i(?:['’]m| am) (?:at|in)|we(?:['’]re| are) (?:at|in))\s+([^.\n]{3,80})",
            text,
        )
        place = (m.group(1).strip() if m else None) or "maps link in message"
        out.append({"place": place, "basis": "authored_text"})
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        exif = att.get("exif") or att.get("gps") or {}
        if isinstance(exif, dict) and (
            exif.get("latitude") is not None or exif.get("GPSLatitude")
        ):
            out.append(
                {
                    "place": att.get("filename") or "attachment",
                    "latitude": exif.get("latitude") or exif.get("GPSLatitude"),
                    "longitude": exif.get("longitude") or exif.get("GPSLongitude"),
                    "basis": "attachment_exif",
                }
            )
    return out
