"""Derived Qdrant index rebuild from authoritative PostgreSQL Evidence."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from memorybox.config import Settings, settings
from memorybox.ingest import store
from memorybox.providers.llm.fake import FakeLlmProvider


_MEMORY_CLIENT = None


def _qdrant_client(cfg: Settings):
    from qdrant_client import QdrantClient

    global _MEMORY_CLIENT
    url = cfg.qdrant_url
    if url in (":memory:", "memory", "mem"):
        if _MEMORY_CLIENT is None:
            _MEMORY_CLIENT = QdrantClient(location=":memory:")
        return _MEMORY_CLIENT
    if url.startswith("path:"):
        return QdrantClient(path=url[5:])
    return QdrantClient(url=url, timeout=60)


def _ensure_collection(client, name: str, dim: int) -> None:
    from qdrant_client.http import models as qm

    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        info = client.get_collection(name)
        # recreate if dim mismatch
        try:
            current = info.config.params.vectors.size  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            current = dim
        if current != dim:
            client.delete_collection(name)
            existing.discard(name)
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )


def _point_id(evidence_id: UUID) -> str:
    # Qdrant accepts UUID strings
    return str(evidence_id)


def _embed_text(payload: dict[str, Any], summary: str, kind: str) -> str:
    if kind == "communication":
        return "\n".join(
            [
                payload.get("subject") or "",
                payload.get("from") or "",
                payload.get("body_text") or "",
            ]
        ).strip() or summary
    return "\n".join(
        [
            payload.get("title") or payload.get("summary") or "",
            payload.get("location") or "",
            payload.get("description") or "",
            payload.get("start") or "",
        ]
    ).strip() or summary


def _llm_embedder(cfg: Settings):
    """Prefer Fake embedder for deterministic acceptance; Ollama when configured + reachable."""
    if not cfg.ollama_base_url:
        return FakeLlmProvider()
    try:
        from memorybox.providers.llm.ollama import OllamaLlmProvider

        p = OllamaLlmProvider(
            base_url=cfg.ollama_base_url,
            chat_model=cfg.ollama_chat_model,
            embed_model=cfg.ollama_embed_model,
        )
        if p.health().ok:
            return p
    except Exception:  # noqa: BLE001
        pass
    return FakeLlmProvider()


def clear_collection(cfg: Settings | None = None) -> dict[str, Any]:
    cfg = cfg or settings
    client = _qdrant_client(cfg)
    name = cfg.qdrant_collection
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        client.delete_collection(name)
    return {"ok": True, "cleared": name, "qdrant_url": cfg.qdrant_url}


def rebuild_comms_index(cfg: Settings | None = None) -> dict[str, Any]:
    cfg = cfg or settings
    job_id = store.start_job(
        "rebuild_comms_index",
        message="rebuild derived Qdrant from PostgreSQL Evidence",
        payload={"collection": cfg.qdrant_collection},
    )
    try:
        rows = store.list_indexable_evidence()
        if not rows:
            store.finish_job(job_id, status="done", message="no evidence to index")
            return {
                "ok": True,
                "job_id": str(job_id),
                "indexed": 0,
                "evidence_ids": [],
                "collection": cfg.qdrant_collection,
            }
        embedder = _llm_embedder(cfg)
        # probe dim
        probe = embedder.embed("dimension probe", purpose="document")
        dim = len(probe.vector)
        client = _qdrant_client(cfg)
        _ensure_collection(client, cfg.qdrant_collection, dim)

        from qdrant_client.http import models as qm

        points = []
        evidence_ids: list[str] = []
        for row in rows:
            eid = row["id"]
            payload = row["payload_json"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            text = _embed_text(payload, row["summary"] or "", row["evidence_kind"])
            vec = embedder.embed(text, purpose="document").vector
            points.append(
                qm.PointStruct(
                    id=_point_id(eid),
                    vector=list(vec),
                    payload={
                        "evidence_id": str(eid),
                        "evidence_kind": row["evidence_kind"],
                        "summary": row["summary"],
                        "content_hash": payload.get("content_hash"),
                        "embed_model": getattr(embedder, "embed_model", None)
                        or "fake-embed",
                    },
                )
            )
            evidence_ids.append(str(eid))
        client.upsert(collection_name=cfg.qdrant_collection, points=points)
        store.finish_job(
            job_id, status="done", message=f"indexed={len(points)}"
        )
        return {
            "ok": True,
            "job_id": str(job_id),
            "indexed": len(points),
            "evidence_ids": evidence_ids,
            "collection": cfg.qdrant_collection,
            "vector_dim": dim,
            "embedder": type(embedder).__name__,
        }
    except Exception as exc:  # noqa: BLE001
        store.finish_job(
            job_id, status="error", message="rebuild failed", error_message=str(exc)
        )
        return {"ok": False, "job_id": str(job_id), "error": str(exc)}


def indexed_evidence_ids(cfg: Settings | None = None) -> list[str]:
    cfg = cfg or settings
    client = _qdrant_client(cfg)
    name = cfg.qdrant_collection
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        return []
    ids: list[str] = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=name, limit=100, offset=offset, with_payload=True
        )
        for r in records:
            payload = r.payload or {}
            eid = payload.get("evidence_id") or str(r.id)
            ids.append(str(eid))
        if offset is None:
            break
    return ids


def fixed_retrieval_test(
    *,
    query_text: str,
    expected_evidence_ids: list[str],
    cfg: Settings | None = None,
) -> dict[str, Any]:
    """Retrieve top-k; require all expected Evidence IDs appear in hits."""
    cfg = cfg or settings
    embedder = _llm_embedder(cfg)
    vec = list(embedder.embed(query_text, purpose="query").vector)
    client = _qdrant_client(cfg)
    result = client.query_points(
        collection_name=cfg.qdrant_collection,
        query=vec,
        limit=max(10, len(expected_evidence_ids) + 5),
    )
    hits = result.points if hasattr(result, "points") else result
    hit_ids = []
    for h in hits:
        payload = h.payload or {}
        hit_ids.append(str(payload.get("evidence_id") or h.id))
    missing = [e for e in expected_evidence_ids if e not in hit_ids]
    return {
        "ok": not missing,
        "query": query_text,
        "hit_ids": hit_ids,
        "expected": expected_evidence_ids,
        "missing": missing,
    }


def assert_no_forbidden_hardcodes(root: Any = None) -> list[str]:
    """Scan memorybox package for forbidden host/path literals in application .py files."""
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1]
    # Build needles without storing contiguous forbidden host tokens in this checker.
    needles = [
        "Flight" + "Sim",
        "media" + "-server",
        "Media" + "-Server",
    ]
    patterns = [re.escape(n) for n in needles] + [
        r"192\.168\.",
        r"[A-Za-z]:\\\\memorybox",
        r"[A-Za-z]:/memorybox",
    ]
    problems: list[str] = []
    for path in pkg.rglob("*.py"):
        if path.name == "rebuild_index.py":
            # this file only defines the scanner needles above
            continue
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            if re.search(pat, text):
                problems.append(f"{path.name}: matched /{pat}/")
    return problems
