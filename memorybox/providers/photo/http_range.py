"""HTTP bytes-range helpers for media proxies."""
from __future__ import annotations


def apply_http_range(data: bytes, range_header: str | None) -> tuple[int, bytes, dict[str, str]]:
    """Apply a bytes Range to an in-memory body when the origin ignored Range."""
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(len(data))}
    if not range_header or not data:
        return 200, data, headers
    units, _, rng = range_header.partition("=")
    if units.strip().lower() != "bytes":
        return 200, data, headers
    start_s, _, end_s = rng.partition("-")
    total = len(data)
    try:
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else total - 1
    except ValueError:
        return 200, data, headers
    start = max(0, min(start, total - 1))
    end = max(start, min(end, total - 1))
    chunk = data[start : end + 1]
    return (
        206,
        chunk,
        {
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(len(chunk)),
        },
    )
