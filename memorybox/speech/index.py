"""Index Spoken Moments into Qdrant (derived transcript embeddings). SQL remains source of truth."""
from __future__ import annotations

from typing import Any

from memorybox.config import Settings, settings
from memorybox.speech.constants import QDRANT_COLLECTION


def _client(cfg: Settings | None = None):
    from memorybox.ingest.rebuild_index import _qdrant_client

    return _qdrant_client(cfg or settings)


def _ensure(client, dim: int) -> None:
    from memorybox.ingest.rebuild_index import _ensure_collection

    _ensure_collection(client, QDRANT_COLLECTION, dim)


def _embedder(cfg: Settings | None = None):
    from memorybox.ingest.rebuild_index import _llm_embedder

    return _llm_embedder(cfg or settings)


def upsert_moments(moments: list[dict[str, Any]], *, cfg: Settings | None = None) -> int:
    if not moments:
        return 0
    s = cfg or settings
    try:
        llm = _embedder(s)
        vecs: list[list[float]] = []
        for m in moments:
            text = str(m.get("text") or "")
            dto = llm.embed(text)
            vec = list(getattr(dto, "vector", None) or [])
            if not vec:
                return 0
            vecs.append([float(x) for x in vec])
        client = _client(s)
        _ensure(client, len(vecs[0]))
        from qdrant_client.http import models as qm

        points = []
        for m, vec in zip(moments, vecs, strict=True):
            mid = str(m.get("id") or "")
            if not mid:
                continue
            points.append(
                qm.PointStruct(
                    id=mid,
                    vector=vec,
                    payload={
                        "kind": "spoken_moment",
                        "text": m.get("text"),
                        "video_external_id": m.get("video_external_id"),
                        "person_id": m.get("person_id"),
                        "t_start": m.get("t_start"),
                        "t_end": m.get("t_end"),
                    },
                )
            )
        if not points:
            return 0
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        from memorybox.speech.store import set_moment_qdrant_id

        for m in moments:
            if m.get("id"):
                set_moment_qdrant_id(str(m["id"]), str(m["id"]))
        return len(points)
    except Exception:
        return 0


def search_similar(text: str, *, limit: int = 24, cfg: Settings | None = None) -> list[dict[str, Any]]:
    q = (text or "").strip()
    if not q:
        return []
    s = cfg or settings
    try:
        llm = _embedder(s)
        dto = llm.embed(q)
        vec = list(getattr(dto, "vector", None) or [])
        if not vec:
            return []
        client = _client(s)
        hits = client.search(collection_name=QDRANT_COLLECTION, query_vector=list(vec), limit=limit)
        out = []
        for h in hits:
            payload = dict(getattr(h, "payload", None) or {})
            payload["score"] = float(getattr(h, "score", 0) or 0)
            payload["id"] = str(getattr(h, "id", "") or payload.get("id") or "")
            out.append(payload)
        return out
    except Exception:
        return []
