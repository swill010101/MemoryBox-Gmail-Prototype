"""Evidence + photo retrieval for Ask (PostgreSQL / Qdrant / PhotoProvider)."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from memorybox.config import Settings, settings
from memorybox.db import connection
from memorybox.ingest import rebuild_index
from memorybox.planner import QueryPlan
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.photo.dto import PhotoAssetDto, PhotoSearchQuery
from memorybox.providers.photo.protocol import PhotoProvider


@dataclass
class EvidenceHit:
    evidence_id: str
    evidence_kind: str
    summary: str
    score: float
    excerpt: str
    source: str  # qdrant | postgres_keyword

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PhotoHit:
    provider_key: str
    external_id: str
    taken_at: str | None
    people: list[str]
    location: str | None
    thumb_url: str | None
    web_url: str | None
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StoryHit:
    story_id: str
    version: int
    title: str | None
    excerpt: str
    narrator_person_id: str | None
    narrator_display_name: str | None
    provenance_kind: str
    attribution: str
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _payload_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _excerpt(payload: dict[str, Any], kind: str, limit: int = 280) -> str:
    if kind == "communication":
        text = payload.get("body_text") or payload.get("subject") or ""
    else:
        text = (
            payload.get("description")
            or payload.get("summary")
            or payload.get("title")
            or ""
        )
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:limit]


def search_evidence_pg(plan: QueryPlan, *, limit: int = 20) -> list[EvidenceHit]:
    """Keyword search over authoritative PostgreSQL Evidence (always available)."""
    kinds: list[str] = []
    if plan.want_communication:
        kinds.append("communication")
    if plan.want_calendar:
        kinds.append("calendar_event")
    if not kinds:
        return []

    terms: list[str] = []
    # Rule G: prefer explicit retrieval constraints when present
    for name in plan.retrieval_constraints or ():
        terms.append(name)
    for name in plan.person_names:
        terms.append(name)
    for name in plan.place_names:
        terms.append(name)
    for name in plan.trip_labels:
        terms.append(name)
    for name in plan.event_labels:
        if name.lower().startswith("trip:"):
            terms.append(name.split(":", 1)[1])
        else:
            terms.append(name)
    # tokens from original ask (drop tiny words)
    for tok in re.findall(r"[A-Za-z0-9']{3,}", plan.original_ask):
        if tok.lower() not in {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "show",
            "me",
            "just",
            "ones",
            "what",
            "else",
            "have",
            "happened",
            "after",
            "right",
            "pictures",
            "photos",
            "emails",
            "email",
            "calendar",
        }:
            terms.append(tok)
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for t in terms:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    if not uniq:
        uniq = ["a"]  # fall through to recent evidence of requested kinds

    hits: list[EvidenceHit] = []
    with connection() as conn:
        clauses = []
        params: list[Any] = []
        for t in uniq[:12]:
            like = f"%{t}%"
            clauses.append("(summary ILIKE %s OR payload_json::text ILIKE %s)")
            params.extend([like, like])
        where_terms = " OR ".join(clauses) if clauses else "TRUE"
        kind_ph = ",".join(["%s"] * len(kinds))
        sql = f"""
            SELECT id, evidence_kind, summary, payload_json
            FROM evidence
            WHERE evidence_kind IN ({kind_ph})
              AND ({where_terms})
            ORDER BY created_at DESC
            LIMIT %s
        """
        params = list(kinds) + params + [limit * 3]
        rows = conn.execute(sql, params).fetchall()
        scored: list[EvidenceHit] = []
        distinctive = [t for t in uniq if len(t) >= 4]
        # Capitalized tokens from the ask are strong constraints (people/places/proper nouns).
        required = [
            m.group(0)
            for m in re.finditer(r"\b[A-Z][A-Za-z]{2,}\b", plan.original_ask or "")
            if m.group(0).lower()
            not in {
                "show",
                "what",
                "just",
                "only",
                "from",
                "with",
                "that",
                "this",
                "have",
                "else",
                "after",
                "right",
                "pictures",
                "photos",
                "emails",
                "email",
                "christmas",
                "grandpa",
                "tell",
                "know",
                "about",
            }
        ]
        for r in rows:
            payload = _payload_dict(r["payload_json"])
            blob = f"{r['summary'] or ''} {json.dumps(payload)}".lower()
            if required and not any(t.lower() in blob for t in required):
                continue
            match_n = sum(1 for t in distinctive if t.lower() in blob)
            if distinctive and match_n == 0:
                continue
            scored.append(
                EvidenceHit(
                    evidence_id=str(r["id"]),
                    evidence_kind=r["evidence_kind"],
                    summary=r["summary"] or "",
                    score=float(match_n) + 0.1,
                    excerpt=_excerpt(payload, r["evidence_kind"]),
                    source="postgres_keyword",
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        hits = scored[:limit]
    if plan.retrieval_constraints:
        hits = filter_hits_by_constraints(hits, plan.retrieval_constraints)
    return hits


def filter_hits_by_constraints(
    hits: list[EvidenceHit], constraints: tuple[str, ...] | list[str]
) -> list[EvidenceHit]:
    """Rule G: keep hits that match at least one resolved context constraint.

    If no hit matches, return empty (insufficient) rather than unconstrained
    vector/keyword leftovers.
    """
    cons = [c for c in constraints if c and len(c) >= 2]
    if not cons:
        return hits
    kept: list[EvidenceHit] = []
    for h in hits:
        blob = f"{h.summary} {h.excerpt}".lower()
        if any(c.lower() in blob for c in cons):
            kept.append(h)
    return kept


def search_evidence_qdrant(
    plan: QueryPlan, *, limit: int = 12, cfg: Settings | None = None
) -> tuple[list[EvidenceHit], dict[str, Any]]:
    """Derived Qdrant semantic search. Returns (hits, status)."""
    cfg = cfg or settings
    status: dict[str, Any] = {"ok": False, "detail": ""}
    try:
        embedder = rebuild_index._llm_embedder(cfg)
        vec = list(embedder.embed(plan.effective_ask, purpose="query").vector)
        client = rebuild_index._qdrant_client(cfg)
        name = cfg.qdrant_collection
        existing = {c.name for c in client.get_collections().collections}
        if name not in existing:
            status["detail"] = "collection_missing"
            return [], status
        result = client.query_points(collection_name=name, query=vec, limit=limit)
        points = result.points if hasattr(result, "points") else result
        hits: list[EvidenceHit] = []
        distinctive = [
            t
            for t in re.findall(r"[A-Za-z0-9']{4,}", plan.original_ask)
            if t.lower()
            not in {
                "show",
                "emails",
                "email",
                "about",
                "what",
                "else",
                "have",
                "from",
                "that",
                "this",
                "with",
                "just",
                "ones",
                "pictures",
                "photos",
                "after",
                "right",
                "happened",
                "secret",
                "family",
                "signed",
                "year",
                "sign",
                "did",
            }
        ]
        if plan.retrieval_constraints:
            # Rule G: constraints outrank bare ask tokens for semantic neighbors
            required = list(plan.retrieval_constraints)
        else:
            required = [
                m.group(0)
                for m in re.finditer(r"\b[A-Z][A-Za-z]{2,}\b", plan.original_ask or "")
                if m.group(0).lower()
                not in {
                    "show",
                    "what",
                    "just",
                    "only",
                    "from",
                    "with",
                    "christmas",
                    "grandpa",
                    "tell",
                    "know",
                    "about",
                }
            ]
        for p in points:
            payload = p.payload or {}
            kind = str(payload.get("evidence_kind") or "")
            if kind == "communication" and not plan.want_communication:
                continue
            if kind == "calendar_event" and not plan.want_calendar:
                continue
            eid = str(payload.get("evidence_id") or p.id)
            row = None
            try:
                row = __import__("memorybox.ingest.store", fromlist=["store"]).store.get_evidence(
                    UUID(eid)
                )
            except Exception:  # noqa: BLE001
                row = None
            summary = (payload.get("summary") or "") if not row else (row.get("summary") or "")
            excerpt = ""
            blob = str(summary).lower()
            if row:
                excerpt = _excerpt(_payload_dict(row.get("payload_json")), kind)
                blob = f"{summary} {excerpt} {json.dumps(_payload_dict(row.get('payload_json')))}".lower()
            if required and not any(t.lower() in blob for t in required):
                continue
            if distinctive and not any(t.lower() in blob for t in distinctive):
                continue
            hits.append(
                EvidenceHit(
                    evidence_id=eid,
                    evidence_kind=kind or "unknown",
                    summary=str(summary),
                    score=float(getattr(p, "score", 0.0) or 0.0),
                    excerpt=excerpt,
                    source="qdrant",
                )
            )
        status["ok"] = True
        if plan.retrieval_constraints:
            hits = filter_hits_by_constraints(hits, plan.retrieval_constraints)
            status["detail"] = f"hits={len(hits)}_constrained"
        else:
            status["detail"] = f"hits={len(hits)}"
        return hits, status
    except Exception as exc:  # noqa: BLE001
        status["detail"] = str(exc)
        return [], status


def merge_evidence_hits(*groups: list[EvidenceHit], limit: int = 20) -> list[EvidenceHit]:
    by_id: dict[str, EvidenceHit] = {}
    for group in groups:
        for h in group:
            prev = by_id.get(h.evidence_id)
            if prev is None or h.score > prev.score:
                by_id[h.evidence_id] = h
    ranked = sorted(by_id.values(), key=lambda x: x.score, reverse=True)
    return ranked[:limit]


def search_photos(
    plan: QueryPlan, photo: PhotoProvider, *, limit: int = 24
) -> tuple[list[PhotoHit], dict[str, Any]]:
    """Search photos via PhotoProvider. Provider failure → status, not empty success."""
    status: dict[str, Any] = {
        "provider_key": getattr(photo, "provider_key", "photo"),
        "ok": False,
        "unavailable": False,
        "detail": "",
    }
    if not plan.want_still and not plan.want_photo:
        status["ok"] = True
        status["detail"] = "not_requested"
        return [], status
    try:
        health = photo.health()
        if not health.ok:
            status["unavailable"] = True
            status["detail"] = health.detail or "photo provider unhealthy"
            return [], status

        person_ext: list[str] = []
        for name in plan.person_names:
            refs = photo.list_people(query=name, limit=5)
            for r in refs:
                if r.display_name and name.lower() in r.display_name.lower():
                    person_ext.append(r.external_id)
                elif not plan.place_names:
                    # still accept close name matches from provider
                    if r.display_name and r.display_name.lower().startswith(name.lower()[:3]):
                        person_ext.append(r.external_id)

        text_bits = list(plan.place_names) + list(plan.person_names)
        text = " ".join(text_bits) if text_bits else (plan.original_ask or None)

        query = PhotoSearchQuery(
            person_external_ids=tuple(dict.fromkeys(person_ext)),
            text=text,
            limit=limit,
        )
        assets: list[PhotoAssetDto] = photo.search_assets(query)
        hits: list[PhotoHit] = []
        for a in assets:
            loc = None
            if a.location:
                parts = [a.location.city, a.location.state, a.location.country]
                loc = ", ".join(p for p in parts if p)
            # Optional place filter when provider returns location
            if plan.place_names and loc:
                if not any(p.lower() in loc.lower() for p in plan.place_names):
                    # keep if text search already applied; soft filter
                    pass
            hits.append(
                PhotoHit(
                    provider_key=a.provider_key,
                    external_id=a.external_id,
                    taken_at=a.taken_at.isoformat() if a.taken_at else None,
                    people=[p.display_name for p in a.people if p.display_name],
                    location=loc,
                    thumb_url=a.thumb_url,
                    web_url=a.web_url,
                )
            )
        status["ok"] = True
        status["detail"] = f"hits={len(hits)}"
        return hits, status
    except ProviderUnavailable as exc:
        status["unavailable"] = True
        status["detail"] = str(exc)
        return [], status
    except ProviderError as exc:
        status["unavailable"] = True
        status["detail"] = str(exc)
        return [], status
    except Exception as exc:  # noqa: BLE001
        status["unavailable"] = True
        status["detail"] = str(exc)
        return [], status


def search_stories(plan: QueryPlan, *, limit: int = 12) -> list[StoryHit]:
    """Retrieve current Story versions relevant to plan constraints / ask tokens.

    Queries stories/story_versions (+ person relationships) directly — no silo,
    no required story_passage Evidence materialization for I5.
    """
    if not getattr(plan, "want_story", False):
        return []
    tokens = [t for t in plan.retrieval_constraints if t and len(t) >= 2]
    if not tokens:
        tokens = [
            t
            for t in re.findall(r"[A-Za-z][A-Za-z']{2,}", plan.original_ask or "")
            if t.lower()
            not in {
                "what",
                "you",
                "know",
                "about",
                "tell",
                "have",
                "from",
                "our",
                "the",
                "trip",
                "show",
                "me",
                "emails",
                "photos",
            }
        ]
    if not tokens:
        return []

    hits: list[StoryHit] = []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id AS story_id,
                s.title,
                s.narrator_person_id,
                s.current_version,
                sv.body_text,
                sv.version,
                p.display_name AS narrator_name
            FROM stories s
            JOIN story_versions sv
              ON sv.story_id = s.id AND sv.version = s.current_version
            LEFT JOIN people p ON p.id = s.narrator_person_id
            WHERE s.status = 'active'
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (limit * 8,),
        ).fetchall()

        # Also gather person names linked via about_person
        rel_people: dict[str, list[str]] = {}
        if rows:
            ids = [r["story_id"] for r in rows]
            # psycopg handles list for ANY
            rrows = conn.execute(
                """
                SELECT r.from_id, p.display_name
                FROM relationships r
                JOIN people p ON p.id = r.to_id
                WHERE r.from_type = 'story'
                  AND r.to_type = 'person'
                  AND r.from_id = ANY(%s)
                """,
                (ids,),
            ).fetchall()
            for rr in rrows:
                rel_people.setdefault(str(rr["from_id"]), []).append(
                    rr["display_name"] or ""
                )

        for r in rows:
            sid = str(r["story_id"])
            blob = " ".join(
                [
                    r["title"] or "",
                    r["body_text"] or "",
                    r["narrator_name"] or "",
                    " ".join(rel_people.get(sid, [])),
                ]
            ).lower()
            match_n = sum(1 for t in tokens if t.lower() in blob)
            if match_n == 0:
                continue
            narrator = r["narrator_name"] or "owner"
            body = r["body_text"] or ""
            excerpt = body[:200] + ("…" if len(body) > 200 else "")
            hits.append(
                StoryHit(
                    story_id=sid,
                    version=int(r["version"]),
                    title=r["title"],
                    excerpt=excerpt,
                    narrator_person_id=str(r["narrator_person_id"])
                    if r["narrator_person_id"]
                    else None,
                    narrator_display_name=r["narrator_name"],
                    provenance_kind="owner_narrator_recollection",
                    attribution=f"{narrator} recalled (Story v{int(r['version'])})",
                    score=float(match_n),
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]
