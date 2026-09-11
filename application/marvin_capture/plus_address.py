"""Gmail plus-address parsing and capture routing helpers (MBC-004)."""
from __future__ import annotations

import re
from typing import Any

# local+tag@domain — tag is case-insensitive for routing
PLUS_TAG_RE = re.compile(
    r"^([^+@]+)\+([^@]+)@(.+)$",
    re.IGNORECASE,
)

JOURNAL_ALIASES = frozenset({"journal", "jrn"})
MEM_ALIAS = "mem"


def split_user_email(user_email: str) -> tuple[str, str]:
    """Return (local_part, domain) for a plain user@domain address."""
    user_email = (user_email or "").strip()
    if "@" not in user_email:
        raise ValueError(f"invalid user_email: {user_email!r}")
    local, domain = user_email.split("@", 1)
    return local, domain


def build_plus_address(user_email: str, tag: str) -> str:
    """Build user+tag@domain from configured plain user_email."""
    local, domain = split_user_email(user_email)
    return f"{local}+{tag}@{domain}"


def parse_plus_tag(address: str | None) -> str | None:
    """Extract the plus-tag from an email address, or None."""
    if not address:
        return None
    # Handle "Name <user+tag@domain>" forms
    addr = address.strip()
    if "<" in addr and ">" in addr:
        m = re.search(r"<([^>]+)>", addr)
        if m:
            addr = m.group(1).strip()
    m = PLUS_TAG_RE.match(addr)
    if not m:
        return None
    return m.group(2).lower()


def map_alias_to_prompt_type(tag: str | None) -> str | None:
    """Map a plus-tag to JRN or MEM; unknown tags return None."""
    if not tag:
        return None
    lowered = tag.lower()
    if lowered in JOURNAL_ALIASES:
        return "JRN"
    if lowered == MEM_ALIAS:
        return "MEM"
    return None


def _normalize_addr_token(addr: str) -> str | None:
    """Return lowercased plus-tag if addr is user+tag@domain."""
    addr = addr.strip()
    if "<" in addr and ">" in addr:
        m = re.search(r"<([^>]+)>", addr)
        if m:
            addr = m.group(1).strip()
    m = PLUS_TAG_RE.match(addr)
    if not m:
        return None
    return m.group(2).lower()


def extract_plus_routing(
    headers: dict[str, str] | None,
    *,
    user_email: str,
) -> tuple[str | None, str | None]:
    """Return (prompt_type, matched_address) from To/Delivered-To/X-Original-To.

    Only tags on the configured user_email local+tag@domain are accepted.
    """
    if not headers or not user_email:
        return None, None
    local, domain = split_user_email(user_email)
    domain_l = domain.lower()
    local_l = local.lower()

    header_names = ("delivered-to", "x-original-to", "to")
    seen: set[str] = set()
    for name in header_names:
        raw = headers.get(name) or headers.get(name.title()) or ""
        if not raw:
            continue
        for part in re.split(r",\s*", raw):
            part = part.strip()
            if not part or part in seen:
                continue
            seen.add(part)
            addr = part
            if "<" in addr:
                inner = re.search(r"<([^>]+)>", addr)
                addr = inner.group(1).strip() if inner else addr
            m = PLUS_TAG_RE.match(addr)
            if not m:
                continue
            if m.group(1).lower() != local_l or m.group(3).lower() != domain_l:
                continue
            tag = m.group(2).lower()
            prompt_type = map_alias_to_prompt_type(tag)
            if prompt_type:
                return prompt_type, addr
    return None, None


def capture_addresses(cfg: dict[str, Any]) -> list[dict[str, str]]:
    """Address → destination table for UI and docs."""
    user_email = (cfg.get("gmail") or {}).get("user_email") or ""
    if not user_email or "@" not in user_email:
        return []
    local, domain = split_user_email(user_email)
    base = f"{local}@{domain}"
    return [
        {
            "address": f"{local}+journal@{domain}",
            "destination": "Journal (JRN)",
            "notes": "You may compose or reply",
        },
        {
            "address": f"{local}+jrn@{domain}",
            "destination": "Journal (JRN)",
            "notes": "Same as +journal",
        },
        {
            "address": f"{local}+MEM@{domain}",
            "destination": "Memory bank answers only",
            "notes": "Reply to Marvin's MEM email",
        },
        {"address": base, "destination": "(plain inbox)", "notes": "MEM questions arrive here"},
    ]


def build_poll_query(user_email: str, *, processed_label: str) -> str:
    """Gmail search: plus-alias inbound, not processed, not in trash."""
    local, domain = split_user_email(user_email)
    to_clauses = [
        f"to:{local}+journal@{domain}",
        f"to:{local}+jrn@{domain}",
        f"to:{local}+MEM@{domain}",
        f"to:{local}+mem@{domain}",
    ]
    label_query = processed_label.replace("/", "-")
    alias_q = "(" + " OR ".join(to_clauses) + ")"
    not_sent_only = "-{in:sent -in:inbox}"
    return (
        f"in:anywhere newer_than:30d -in:trash -label:{label_query} "
        f"{alias_q} {not_sent_only}"
    )
