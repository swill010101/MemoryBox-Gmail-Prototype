"""Resolve Immich asset ids for /library/media/photo/{id}.

Face-evidence and person-thumb metadata sometimes store an Immich thumb
disk path (``/data/thumbs/{userId}/../{assetId}.jpeg``) instead of the
asset UUID. Using that path as the proxy id 404s as
``/library/media/photo//data/thumbs/...``.
"""
from __future__ import annotations

import re

_UUID_RE = re.compile(
    r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_UUID_FILE_RE = re.compile(
    r"(?i)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"\.(jpe?g|webp|png|gif)$"
)


def photo_proxy_asset_id(raw: object) -> str | None:
    """Return an Immich asset UUID, or None if the ref is not usable."""
    s = str(raw or "").strip()
    if not s:
        return None
    path = s.replace("\\", "/")
    if "/" not in path and _UUID_RE.fullmatch(s):
        return s
    file_hit = _UUID_FILE_RE.search(path)
    if file_hit:
        return file_hit.group(1)
    found = _UUID_RE.findall(path)
    if found:
        return found[-1]
    return None


def photo_proxy_url(raw: object) -> str | None:
    aid = photo_proxy_asset_id(raw)
    if not aid:
        return None
    return f"/library/media/photo/{aid}"
