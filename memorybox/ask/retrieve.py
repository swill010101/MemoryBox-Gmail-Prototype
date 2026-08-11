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
    identity_trust: str = "confirmed"  # confirmed | trusted_provider | candidate
    mb_person_id: str | None = None
    mb_person_name: str | None = None
    attribution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoHit:
    provider_key: str
    external_id: str
    video_external_id: str
    start_sec: float
    end_sec: float
    face_external_id: str | None = None
    label: str | None = None
    play_url: str | None = None
    identity_trust: str = "confirmed"  # confirmed | trusted_provider | candidate
    mb_person_id: str | None = None
    mb_person_name: str | None = None
    attribution: str | None = None

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
    """Search photos via PhotoProvider with I6/I7 identity authority rules.

    Confirmed and trusted-provider-seeded MB Persons retrieve via provider_identities.
    Unconfirmed Immich name matches remain candidates and never become confirmed.
    """
    from memorybox.person import (
        AUTHORITY_TRUSTED_PROVIDER,
        AmbiguousIdentityError,
        find_ask_person_by_name,
        find_confirmed_person_by_name,
        is_negative,
        list_provider_external_ids_for_person,
    )

    status: dict[str, Any] = {
        "provider_key": getattr(photo, "provider_key", "photo"),
        "ok": False,
        "unavailable": False,
        "detail": "",
        "identity_mode": "none",
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

        photo_pk = getattr(photo, "provider_key", "immich") or "immich"
        lookup_keys = [photo_pk]
        if photo_pk == "fake_photo":
            lookup_keys = ["fake_photo", "immich"]
        elif photo_pk == "immich":
            lookup_keys = ["immich", "fake_photo"]

        mapped_ext: list[str] = []
        mapped_meta: list[dict[str, str]] = []
        mapped_names: list[str] = []
        unmapped_resolvable_names: list[str] = []
        ambiguous_names: list[str] = []

        # I9A: prefer MB Person ids from relational resolve (owner ? Relationship ? id)
        from memorybox.person import get_person as _get_person_by_id

        resolved_by_id: set[str] = set()
        for pid in getattr(plan, "person_ids", ()) or ():
            person = _get_person_by_id(pid)
            if not person:
                continue
            resolved_by_id.add(person.id)
            name = person.display_name or pid
            ids: list[str] = []
            for pk in lookup_keys:
                ids.extend(list_provider_external_ids_for_person(person.id, pk))
            ids = list(dict.fromkeys(ids))
            if ids:
                mapped_names.append(name)
                mapping_auth = person.identity_authority
                for m in person.provider_mappings:
                    if (
                        m.get("provider_key") in lookup_keys
                        and m.get("external_id") in ids
                    ):
                        mapping_auth = (
                            m.get("identity_authority") or person.identity_authority
                        )
                        break
                trust = (
                    "trusted_provider"
                    if mapping_auth == AUTHORITY_TRUSTED_PROVIDER
                    else "confirmed"
                )
                for eid in ids:
                    mapped_ext.append(eid)
                    mapped_meta.append(
                        {
                            "external_id": eid,
                            "person_id": person.id,
                            "name": name,
                            "trust": trust,
                        }
                    )
            else:
                unmapped_resolvable_names.append(name)

        for name in plan.person_names:
            try:
                person = find_ask_person_by_name(name, photo=photo, lazy_seed=True)
            except AmbiguousIdentityError as exc:
                ambiguous_names.append(name)
                status["disclosure"] = str(exc)
                continue
            if person:
                if person.id in resolved_by_id:
                    continue
                ids: list[str] = []
                for pk in lookup_keys:
                    ids.extend(list_provider_external_ids_for_person(person.id, pk))
                ids = list(dict.fromkeys(ids))
                if ids:
                    mapped_names.append(name)
                    mapping_auth = person.identity_authority
                    for m in person.provider_mappings:
                        if (
                            m.get("provider_key") in lookup_keys
                            and m.get("external_id") in ids
                        ):
                            mapping_auth = (
                                m.get("identity_authority") or person.identity_authority
                            )
                            break
                    trust = (
                        "trusted_provider"
                        if mapping_auth == AUTHORITY_TRUSTED_PROVIDER
                        else "confirmed"
                    )
                    for eid in ids:
                        mapped_ext.append(eid)
                        mapped_meta.append(
                            {
                                "external_id": eid,
                                "person_id": person.id,
                                "name": name,
                                "trust": trust,
                            }
                        )
                else:
                    unmapped_resolvable_names.append(name)

        hits: list[PhotoHit] = []

        def _asset_to_hit(
            a: PhotoAssetDto,
            *,
            trust: str,
            person_id: str | None = None,
            person_name: str | None = None,
        ) -> PhotoHit:
            loc = None
            if a.location:
                parts = [a.location.city, a.location.state, a.location.country]
                loc = ", ".join(p for p in parts if p)
            if trust == "confirmed":
                attrib = (
                    f"MB Person {person_name} via owner-confirmed Immich mapping"
                    if person_name
                    else "owner-confirmed MB Person mapping"
                )
            elif trust == "trusted_provider":
                attrib = (
                    f"MB Person {person_name} via trusted Immich/provider identity "
                    "(not owner-confirmed)"
                    if person_name
                    else "trusted-provider-seeded MB Person mapping (not owner-confirmed)"
                )
            else:
                attrib = (
                    "unconfirmed Immich name candidate (not MB-confirmed identity)"
                )
            return PhotoHit(
                provider_key=a.provider_key,
                external_id=a.external_id,
                taken_at=a.taken_at.isoformat() if a.taken_at else None,
                people=[p.display_name for p in a.people if p.display_name],
                location=loc,
                thumb_url=a.thumb_url,
                web_url=a.web_url,
                identity_trust=trust,
                mb_person_id=person_id,
                mb_person_name=person_name,
                attribution=attrib,
            )

        if mapped_ext:
            trusts = {m.get("trust") for m in mapped_meta}
            if trusts == {"trusted_provider"}:
                status["identity_mode"] = "trusted_provider_mapping"
            elif "trusted_provider" in trusts:
                status["identity_mode"] = "mixed_mapping"
            else:
                status["identity_mode"] = "confirmed_mapping"
            query = PhotoSearchQuery(
                person_external_ids=tuple(dict.fromkeys(mapped_ext)),
                limit=limit,
            )
            assets = photo.search_assets(query)
            by_person_ext = {m["external_id"]: m for m in mapped_meta}
            for a in assets:
                meta: dict[str, str] = {}
                for pref in a.people or ():
                    hit_meta = by_person_ext.get(pref.external_id)
                    if hit_meta:
                        meta = hit_meta
                        break
                if not meta and mapped_meta:
                    meta = mapped_meta[0]
                hits.append(
                    _asset_to_hit(
                        a,
                        trust=meta.get("trust") or "confirmed",
                        person_id=meta.get("person_id"),
                        person_name=meta.get("name"),
                    )
                )
            status["ok"] = True
            status["detail"] = (
                f"mapped_hits={len(hits)} mapped_names={mapped_names}"
            )
            if ambiguous_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + f" Ambiguous identity for: {ambiguous_names}."
                ).strip()
            return hits[:limit], status

        status["identity_mode"] = (
            "candidate_unmapped_person"
            if unmapped_resolvable_names
            else "candidate_provider_name"
        )
        if ambiguous_names:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            return [], status

        person_ext: list[str] = []
        for name in plan.person_names:
            confirmed = find_confirmed_person_by_name(name)
            refs = photo.list_people(query=name, limit=5)
            for r in refs:
                name_hit = bool(
                    r.display_name
                    and (
                        name.lower() in r.display_name.lower()
                        or r.display_name.lower().startswith(name.lower()[:3])
                    )
                )
                if not name_hit:
                    continue
                if confirmed and is_negative(
                    provider_key=photo_pk,
                    external_id=r.external_id,
                    person_id=confirmed.id,
                ):
                    continue
                person_ext.append(r.external_id)

        text_bits = list(plan.place_names) + list(plan.person_names)
        text = " ".join(text_bits) if text_bits else (plan.original_ask or None)
        query = PhotoSearchQuery(
            person_external_ids=tuple(dict.fromkeys(person_ext)),
            text=text,
            limit=limit,
        )
        assets = photo.search_assets(query)
        for a in assets:
            hits.append(_asset_to_hit(a, trust="candidate"))
        status["ok"] = True
        status["detail"] = (
            f"candidate_hits={len(hits)} "
            f"unmapped_resolvable={unmapped_resolvable_names or []}"
        )
        if unmapped_resolvable_names:
            status["disclosure"] = (
                "Resolvable MB Person(s) exist without Immich mapping; "
                "Immich name matches are unconfirmed candidates only."
            )
        return hits[:limit], status
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


def search_videos(
    plan: QueryPlan,
    video: Any,
    *,
    limit: int = 24,
    photo: Any | None = None,
) -> tuple[list[VideoHit], dict[str, Any]]:
    """Search video presence spans with I6/I7 identity authority rules."""
    from memorybox.person import (
        AUTHORITY_TRUSTED_PROVIDER,
        AmbiguousIdentityError,
        find_ask_person_by_name,
        list_provider_external_ids_for_person,
    )
    from memorybox.providers.video.dto import VideoSearchQuery

    status: dict[str, Any] = {
        "provider_key": getattr(video, "provider_key", "video"),
        "ok": False,
        "unavailable": False,
        "detail": "",
        "identity_mode": "none",
    }
    if not getattr(plan, "want_video", False):
        status["ok"] = True
        status["detail"] = "not_requested"
        return [], status
    try:
        health = video.health()
        if not health.ok:
            status["unavailable"] = True
            status["detail"] = health.detail or "video provider unhealthy"
            return [], status

        mapped_ext: list[str] = []
        mapped_meta: list[dict[str, str]] = []
        unmapped: list[str] = []
        ambiguous_names: list[str] = []
        provider_key = getattr(video, "provider_key", "hvrt")
        lookup_keys = [provider_key]
        if provider_key == "fake_video":
            lookup_keys = ["fake_video", "hvrt"]

        if photo is None:
            try:
                from memorybox.ask.deps import build_photo

                photo = build_photo()
            except Exception:  # noqa: BLE001
                photo = None

        from memorybox.person import get_person as _get_person_by_id

        seen_pids: set[str] = set()
        for pid in getattr(plan, "person_ids", ()) or ():
            person = _get_person_by_id(pid)
            if not person:
                continue
            seen_pids.add(person.id)
            ids: list[str] = []
            for pk in lookup_keys:
                ids.extend(list_provider_external_ids_for_person(person.id, pk))
            ids = list(dict.fromkeys(ids))
            if ids:
                for eid in ids:
                    trust = "confirmed"
                    for m in person.provider_mappings:
                        if m.get("external_id") == eid:
                            if m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER:
                                trust = "trusted_provider"
                            break
                    mapped_ext.append(eid)
                    mapped_meta.append(
                        {
                            "external_id": eid,
                            "person_id": person.id,
                            "name": person.display_name or pid,
                            "trust": trust,
                        }
                    )
            else:
                unmapped.append(person.display_name or pid)

        for name in plan.person_names:
            try:
                person = find_ask_person_by_name(name, photo=photo, lazy_seed=True)
            except AmbiguousIdentityError as exc:
                ambiguous_names.append(name)
                status["disclosure"] = str(exc)
                continue
            if not person:
                continue
            if person.id in seen_pids:
                continue
            ids: list[str] = []
            for pk in lookup_keys:
                ids.extend(list_provider_external_ids_for_person(person.id, pk))
            ids = list(dict.fromkeys(ids))
            if ids:
                for eid in ids:
                    trust = "confirmed"
                    for m in person.provider_mappings:
                        if m.get("external_id") == eid:
                            if m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER:
                                trust = "trusted_provider"
                            break
                    mapped_ext.append(eid)
                    mapped_meta.append(
                        {
                            "external_id": eid,
                            "person_id": person.id,
                            "name": name,
                            "trust": trust,
                        }
                    )
            else:
                unmapped.append(name)

        hits: list[VideoHit] = []
        if mapped_ext:
            trusts = {m.get("trust") for m in mapped_meta}
            if trusts == {"trusted_provider"}:
                status["identity_mode"] = "trusted_provider_mapping"
            elif "trusted_provider" in trusts:
                status["identity_mode"] = "mixed_mapping"
            else:
                status["identity_mode"] = "confirmed_mapping"
            q = VideoSearchQuery(
                person_external_ids=tuple(dict.fromkeys(mapped_ext)),
                limit=limit,
            )
            segs = video.search_segments(q)
            by_face = {m["external_id"]: m for m in mapped_meta}
            for s in segs:
                meta = by_face.get(s.face_external_id or "") or (
                    mapped_meta[0] if mapped_meta else {}
                )
                trust = meta.get("trust") or "confirmed"
                if trust == "trusted_provider":
                    attrib = (
                        f"MB Person {meta.get('name')} via trusted-provider video mapping "
                        "(not owner-confirmed)"
                        if meta.get("name")
                        else "trusted-provider video mapping (not owner-confirmed)"
                    )
                else:
                    attrib = (
                        f"MB Person {meta.get('name')} via owner-confirmed video mapping"
                        if meta.get("name")
                        else "owner-confirmed MB Person video mapping"
                    )
                hits.append(
                    VideoHit(
                        provider_key=s.provider_key,
                        external_id=s.external_id,
                        video_external_id=s.video_external_id,
                        start_sec=s.start_sec,
                        end_sec=s.end_sec,
                        face_external_id=s.face_external_id,
                        label=s.label,
                        play_url=s.play_url,
                        identity_trust=trust,
                        mb_person_id=meta.get("person_id"),
                        mb_person_name=meta.get("name"),
                        attribution=attrib,
                    )
                )
            status["ok"] = True
            status["detail"] = f"mapped_video_hits={len(hits)}"
            return hits[:limit], status

        if ambiguous_names:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            return [], status

        status["identity_mode"] = (
            "candidate_unmapped_person" if unmapped else "candidate_provider_name"
        )
        text = " ".join(plan.person_names) if plan.person_names else plan.original_ask
        segs = video.search_segments(VideoSearchQuery(text=text, limit=limit))
        for s in segs:
            hits.append(
                VideoHit(
                    provider_key=s.provider_key,
                    external_id=s.external_id,
                    video_external_id=s.video_external_id,
                    start_sec=s.start_sec,
                    end_sec=s.end_sec,
                    face_external_id=s.face_external_id,
                    label=s.label,
                    play_url=s.play_url,
                    identity_trust="candidate",
                    attribution=(
                        "unconfirmed video face candidate (not MB-confirmed identity)"
                    ),
                )
            )
        status["ok"] = True
        status["detail"] = f"candidate_video_hits={len(hits)} unmapped={unmapped}"
        if unmapped:
            status["disclosure"] = (
                "Resolvable MB Person(s) exist without video provider mapping; "
                "results are unconfirmed candidates only."
            )
        return hits[:limit], status
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

    Queries stories/story_versions (+ person relationships) directly ? no silo,
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
            excerpt = body[:200] + ("?" if len(body) > 200 else "")
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


@dataclass
class JournalHit:
    journal_id: str
    version: int
    title: str | None
    excerpt: str
    author_person_id: str | None
    author_display_name: str | None
    captured_at: str | None
    described_start_date: str | None
    described_end_date: str | None
    described_precision: str
    provenance_kind: str
    attribution: str
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def search_journals(plan: QueryPlan, *, limit: int = 12) -> list[JournalHit]:
    """Retrieve current Journal versions via direct PG ? no journal_passage required."""
    if not getattr(plan, "want_journal", False):
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
                "journal",
                "journals",
                "entry",
                "entries",
            }
        ]
    loose = not tokens
    # Listing asks ("show my journals") must not truncate owner entries under
    # synthetic prove noise ? pull a wider recent window when unconstrained.
    fetch_n = max(limit * 8, 80) if loose else limit * 8
    result_n = max(limit, 50) if loose else limit

    hits: list[JournalHit] = []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                j.id AS journal_id,
                j.title,
                j.author_person_id,
                j.current_version,
                j.captured_at,
                j.described_start_date,
                j.described_end_date,
                j.described_precision,
                jv.body_text,
                jv.version,
                p.display_name AS author_name
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id AND jv.version = j.current_version
            LEFT JOIN people p ON p.id = j.author_person_id
            WHERE j.status = 'active'
            ORDER BY j.updated_at DESC
            LIMIT %s
            """,
            (fetch_n,),
        ).fetchall()

        rel_people: dict[str, list[str]] = {}
        if rows:
            ids = [r["journal_id"] for r in rows]
            rrows = conn.execute(
                """
                SELECT r.from_id, p.display_name
                FROM relationships r
                JOIN people p ON p.id = r.to_id
                WHERE r.from_type = 'journal'
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
            jid = str(r["journal_id"])
            blob = " ".join(
                [
                    r["title"] or "",
                    r["body_text"] or "",
                    r["author_name"] or "",
                    " ".join(rel_people.get(jid, [])),
                    str(r.get("described_start_date") or ""),
                    str(r.get("described_end_date") or ""),
                ]
            ).lower()
            if loose:
                match_n = 1
            else:
                match_n = sum(1 for t in tokens if t.lower() in blob)
                if match_n == 0:
                    continue
            if plan.time_start or plan.time_end:
                ds = str(r.get("described_start_date") or "")
                de = str(r.get("described_end_date") or "")
                if plan.time_start and de and de < plan.time_start[:10]:
                    continue
                if plan.time_end and ds and ds > plan.time_end[:10]:
                    continue
            author = r["author_name"] or "owner"
            body = r["body_text"] or ""
            excerpt = body[:200] + ("?" if len(body) > 200 else "")
            prec = r.get("described_precision") or "unknown"
            hits.append(
                JournalHit(
                    journal_id=jid,
                    version=int(r["version"]),
                    title=r["title"],
                    excerpt=excerpt,
                    author_person_id=str(r["author_person_id"])
                    if r["author_person_id"]
                    else None,
                    author_display_name=r["author_name"],
                    captured_at=str(r["captured_at"]) if r.get("captured_at") else None,
                    described_start_date=str(r["described_start_date"])
                    if r.get("described_start_date")
                    else None,
                    described_end_date=str(r["described_end_date"])
                    if r.get("described_end_date")
                    else None,
                    described_precision=prec,
                    provenance_kind="owner_journal",
                    attribution=f"{author} journaled (Journal v{int(r['version'])})",
                    score=float(match_n),
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:result_n]

def search_artifacts(plan: QueryPlan, *, limit: int = 12) -> list[dict[str, Any]]:
    """Thin I9 Ask earn-in: Artifact identity/metadata, not filename-as-meaning."""
    if not getattr(plan, "want_artifact", False):
        return []
    from memorybox.artifact import search_artifacts_for_ask

    q = (plan.original_ask or "").strip()
    # Prefer constraint tokens / entity slots when present
    bits = list(plan.retrieval_constraints or ())
    bits.extend(plan.person_names or ())
    bits.extend(getattr(plan, "place_names", ()) or ())
    if bits:
        q = " ".join([q] + [str(b) for b in bits if b])
    return search_artifacts_for_ask(q, limit=limit)
