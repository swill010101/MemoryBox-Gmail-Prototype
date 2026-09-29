"""Model-visible request identity. Execution IDs stay outside the prompt."""
from __future__ import annotations


def stable_packet_id(packet_sha256: str) -> str:
    digest = (packet_sha256 or "").strip().lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("packet_id requires the packet SHA-256 hex digest")
    return f"i14pkt-{digest}"
