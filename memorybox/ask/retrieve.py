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
    # Structured place (I4 location filter / map) — optional; never invent coords
    place: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    original_filename: str | None = None
    # Camera EXIF for Source rail — dict keys are human labels
    exif: dict[str, str] | None = None
    # Immich-named faces on the asset (+ optional boxes)
    faces: list[dict[str, Any]] | None = None
    # IMAGE | VIDEO — Immich library videos ride this channel then map to Explore video
    asset_kind: str = "IMAGE"

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
    plan: QueryPlan, photo: PhotoProvider, *, limit: int = 5000
) -> tuple[list[PhotoHit], dict[str, Any]]:
    """Search photos via PhotoProvider with I6/I7 identity authority rules.

    Confirmed and trusted-provider-seeded MB Persons retrieve via provider_identities.
    Unconfirmed Immich name matches remain candidates and never become confirmed.
    Empty mapped Immich results fall through to Immich **person-id** name
    lookup (stale mapping safe). Never pad a successful personIds result with
    bare Immich text/metadata search — that returns newest library pages and
    over-counts person asks (e.g. 661 → 912 with unrelated 2026 photos).
    Limit defaults high so person asks can return the full Immich person library
    (hundreds–thousands), not only the newest page (~48–120).
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

    def _filter_photo_hits(hits: list[PhotoHit]) -> list[PhotoHit]:
        """Apply shared plan time windows + place tokens to photo hits."""
        from memorybox.planner.temporal import date_in_windows

        windows = tuple(getattr(plan, "temporal_windows", ()) or ())
        if not windows and plan.time_start and plan.time_end:
            windows = ((plan.time_start, plan.time_end),)
        places = [str(p).lower() for p in (plan.place_names or ()) if p]
        if not windows and not places:
            scoped = _scope_asset_kind(hits)
            return scoped
        out: list[PhotoHit] = []
        for h in hits:
            if windows and not date_in_windows(h.taken_at, windows):
                continue
            if places:
                blob = " ".join(
                    str(x)
                    for x in (
                        h.location,
                        getattr(h, "place", None),
                        h.city,
                        h.state,
                        h.country,
                    )
                    if x
                ).lower()
                if not any(p in blob for p in places):
                    continue
            out.append(h)
        if windows:
            status["temporal_windows"] = [list(w) for w in windows]
            status["temporal_label"] = getattr(plan, "temporal_label", None)
            status["before_temporal_filter"] = len(hits)
            status["after_temporal_filter"] = len(out)
        if places:
            status["place_filter"] = list(plan.place_names)
            status["after_place_filter"] = len(out)
        return _scope_asset_kind(out)

    def _scope_asset_kind(hits: list[PhotoHit]) -> list[PhotoHit]:
        scope = str(getattr(plan, "visual_scope", "") or "").lower()
        want_still = bool(getattr(plan, "want_still", False) or getattr(plan, "want_photo", False))
        want_video = bool(getattr(plan, "want_video", False))
        if scope == "still_only" or (want_still and not want_video):
            return [h for h in hits if str(h.asset_kind or "IMAGE").upper() != "VIDEO"]
        if scope == "video_only" or (want_video and not want_still):
            return [h for h in hits if str(h.asset_kind or "").upper() == "VIDEO"]
        return hits

    def _finish(hits: list[PhotoHit]) -> tuple[list[PhotoHit], dict[str, Any]]:
        filtered = _filter_photo_hits(hits)
        return filtered[:limit], status

    # Immich VIDEO lives on the photo provider. Video-only asks must still search here.
    if not plan.want_still and not plan.want_photo and not getattr(plan, "want_video", False):
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
        ambiguous_candidates: list[dict[str, Any]] = []
        clarify_message: str | None = None

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
                ambiguous_candidates.extend(list(exc.candidates or []))
                clarify_message = str(exc) or clarify_message
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

        if ambiguous_names and not mapped_ext:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            status["candidates"] = ambiguous_candidates
            status["clarify_message"] = clarify_message or (
                f"Please specify which {ambiguous_names[0].split()[0]} you would like."
            )
            status["ambiguous_person_names"] = list(ambiguous_names)
            return [], status

        # Named person ask with zero MB+Immich matches → ask who (do not dump library).
        if (
            plan.person_names
            and not mapped_ext
            and not unmapped_resolvable_names
            and not ambiguous_names
            and not (getattr(plan, "person_ids", None) or ())
        ):
            from memorybox.person import (
                _ask_named_photo_people,
                list_people_by_exact_name,
                list_people_by_first_token,
            )

            unknown: list[str] = []
            for name in plan.person_names:
                mb_hits = (
                    list_people_by_first_token(name)
                    if " " not in name.strip()
                    else list_people_by_exact_name(name)
                )
                photo_hits = _ask_named_photo_people(photo, name)
                if not mb_hits and not photo_hits:
                    unknown.append(name)
            if unknown and len(unknown) == len(list(plan.person_names)):
                who = unknown[0]
                status["identity_mode"] = "unknown_person"
                status["ok"] = True
                status["detail"] = f"unknown={unknown}"
                status["unknown_person_names"] = list(unknown)
                status["clarify_message"] = f"Who is {who}?"
                return [], status

        hits: list[PhotoHit] = []

        def _people_for_hit(a: PhotoAssetDto, person_name: str | None) -> list[str]:
            """Immich personId search often omits per-asset people[]; keep ask person."""
            out: list[str] = []
            for pref in a.people or ():
                n = (pref.display_name or "").strip()
                if n and n.lower() != "unknown" and n not in out:
                    out.append(n)
            for face in getattr(a, "faces", ()) or ():
                n = (getattr(face, "display_name", None) or "").strip()
                if n and n.lower() != "unknown" and n not in out:
                    out.append(n)
            pn = (person_name or "").strip()
            if pn and pn.lower() != "unknown" and pn not in out:
                out.insert(0, pn)
            return out

        def _faces_for_hit(a: PhotoAssetDto) -> list[dict[str, Any]] | None:
            rows: list[dict[str, Any]] = []
            for face in getattr(a, "faces", ()) or ():
                name = (getattr(face, "display_name", None) or "").strip()
                box = getattr(face, "face_box", None)
                if not name and not box:
                    continue
                row: dict[str, Any] = {
                    "name": name or "Unknown",
                    "person_external_id": getattr(face, "external_person_id", None),
                }
                if box and len(box) == 4:
                    row["face_box"] = {
                        "x": float(box[0]),
                        "y": float(box[1]),
                        "w": float(box[2]),
                        "h": float(box[3]),
                    }
                rows.append(row)
            return rows or None

        def _asset_to_hit(
            a: PhotoAssetDto,
            *,
            trust: str,
            person_id: str | None = None,
            person_name: str | None = None,
        ) -> PhotoHit:
            loc = None
            city = state = country = None
            lat = lon = None
            place = None
            if a.location:
                city = a.location.city
                state = a.location.state
                country = a.location.country
                lat = a.location.latitude
                lon = a.location.longitude
                parts = [city, state, country]
                loc = ", ".join(p for p in parts if p)
                place = city or state or country or loc
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
                people=_people_for_hit(a, person_name),
                location=loc,
                # Browser-safe MB proxy (Immich URLs are not cookie-auth'd for Ask UI)
                thumb_url=(
                    f"/library/media/photo/{a.external_id}" if a.external_id else a.thumb_url
                ),
                web_url=a.web_url,
                identity_trust=trust,
                mb_person_id=person_id,
                mb_person_name=person_name,
                attribution=attrib,
                place=place,
                city=city,
                state=state,
                country=country,
                latitude=lat,
                longitude=lon,
                original_filename=getattr(a, "original_filename", None),
                exif=dict(getattr(a, "exif", ()) or ()) or None,
                faces=_faces_for_hit(a),
                asset_kind=str(getattr(a, "asset_kind", None) or "IMAGE").upper(),
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
            status["mapped_person_names"] = list(mapped_names)
            status["unmapped_person_names"] = list(unmapped_resolvable_names)
            if unmapped_resolvable_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + f" No Immich/photo provider mapping for: {unmapped_resolvable_names}."
                ).strip()
            if ambiguous_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + f" Ambiguous identity for: {ambiguous_names}."
                ).strip()
            # PersonIds hits are the Immich person library. Do **not** "fill"
            # remaining slots with Immich text/metadata search — that path
            # often ignores `query` and returns the newest ~page of the whole
            # library (FlightSim: Eugene 661 + ~250 recent 2026 → 912).
            # Only fall through when the mapped id returned zero (stale mapping).
            if hits:
                return _finish(hits)
            status["detail"] = (
                f"mapped_hits=0 mapped_names={mapped_names}; "
                "fallback_via_name_person_ids"
            )

        status["identity_mode"] = (
            "candidate_unmapped_person"
            if unmapped_resolvable_names and not hits
            else (
                "mixed_mapping_plus_name"
                if hits and mapped_ext
                else (
                    "candidate_after_empty_mapping"
                    if mapped_ext and not hits
                    else (
                        "candidate_unmapped_person"
                        if unmapped_resolvable_names
                        else "candidate_provider_name"
                    )
                )
            )
        )
        if ambiguous_names and not hits:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            status["candidates"] = ambiguous_candidates
            status["clarify_message"] = clarify_message or (
                f"Please specify which {ambiguous_names[0].split()[0]} you would like."
            )
            status["ambiguous_person_names"] = list(ambiguous_names)
            return [], status

        person_ext: list[str] = []
        # Prefer resolved MB display names (Peggy → Peggy George) for Immich lookup
        name_queries: list[str] = []
        for name in plan.person_names:
            if name and name not in name_queries:
                name_queries.append(name)
        for meta in mapped_meta:
            n = meta.get("name")
            if n and n not in name_queries:
                name_queries.append(n)
        for name in unmapped_resolvable_names:
            if name and name not in name_queries:
                name_queries.append(name)
        for name in name_queries:
            confirmed = find_confirmed_person_by_name(name)
            from memorybox.person import _ask_named_photo_people

            # Strict Immich name resolution only (exact / unique first-token).
            try:
                refs = _ask_named_photo_people(photo, name)
            except Exception:  # noqa: BLE001
                refs = []
            if len(refs) > 1:
                first = name.split()[0] if name.split() else name
                labels = [
                    str(getattr(r, "display_name", "") or "").strip()
                    for r in refs
                    if str(getattr(r, "display_name", "") or "").strip()
                ]
                status["identity_mode"] = "ambiguous_identity"
                status["ok"] = True
                status["detail"] = f"ambiguous={name}"
                status["clarify_message"] = (
                    f"Please specify which {first} you would like"
                    + (f": {', '.join(labels)}." if labels else ".")
                )
                status["ambiguous_person_names"] = [name]
                status["candidates"] = [
                    {
                        "external_id": str(getattr(r, "external_id", "") or ""),
                        "display_name": getattr(r, "display_name", name),
                    }
                    for r in refs
                ]
                return [], status
            for r in refs or []:
                if confirmed and is_negative(
                    provider_key=photo_pk,
                    external_id=r.external_id,
                    person_id=confirmed.id,
                ):
                    continue
                if r.external_id in mapped_ext and hits:
                    continue
                person_ext.append(r.external_id)

        person_ext = list(dict.fromkeys(person_ext))
        if not person_ext:
            status["ok"] = True
            locked = bool(getattr(plan, "person_ids", None) or ())
            if plan.person_names and not hits and not locked:
                who = list(plan.person_names)[0]
                status["identity_mode"] = "unknown_person"
                status["detail"] = f"unknown={list(plan.person_names)}"
                status["unknown_person_names"] = list(plan.person_names)
                status["clarify_message"] = f"Who is {who}?"
                return _finish(hits)
            status["detail"] = (
                f"no_immich_person_ids names={name_queries} "
                f"unmapped_resolvable={unmapped_resolvable_names or []}"
            )
            if unmapped_resolvable_names:
                status["disclosure"] = (
                    "Resolvable MB Person(s) exist without Immich mapping; "
                    "no Immich person id resolved for name search."
                )
            return _finish(hits)

        # Person asks must stay on personIds only — never bare Immich text search
        # (unfiltered newest-library page).
        query = PhotoSearchQuery(
            person_external_ids=tuple(person_ext),
            limit=limit,
        )
        assets = photo.search_assets(query)
        seen_ext = {h.external_id for h in hits}
        for a in assets:
            if a.external_id in seen_ext:
                continue
            hits.append(_asset_to_hit(a, trust="candidate"))
            seen_ext.add(a.external_id)
        status["ok"] = True
        status["detail"] = (
            f"candidate_hits={len(hits)} person_ids={len(person_ext)} "
            f"unmapped_resolvable={unmapped_resolvable_names or []}"
        )
        if unmapped_resolvable_names:
            status["disclosure"] = (
                "Resolvable MB Person(s) exist without Immich mapping; "
                "Immich name matches are unconfirmed candidates only."
            )
        return _finish(hits)
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


def _dedupe_video_hits(
    hits: list[VideoHit], *, window_sec: float = 2.5, limit: int = 48
) -> list[VideoHit]:
    """Collapse near-duplicate moments (HVRT segment + appearance merge).

    Prefer labeled / named / confirmed hits over generic face-appearance copies.
    """

    def _score(h: VideoHit) -> tuple[int, int, int]:
        named = 1 if (h.mb_person_name or (h.label and h.label != "face-appearance-moment")) else 0
        trust = {"confirmed": 3, "trusted_provider": 2, "candidate": 1}.get(
            h.identity_trust or "", 0
        )
        has_face = 1 if h.face_external_id else 0
        return (named, trust, has_face)

    buckets: dict[tuple[str, int], VideoHit] = {}
    order: list[tuple[str, int]] = []
    for h in hits:
        vid = str(h.video_external_id or h.external_id or "")
        slot = int(float(h.start_sec or 0) // window_sec)
        key = (vid, slot)
        prev = buckets.get(key)
        if prev is None:
            buckets[key] = h
            order.append(key)
            continue
        if _score(h) > _score(prev):
            buckets[key] = h
    return [buckets[k] for k in order][:limit]


def search_videos(
    plan: QueryPlan,
    video: Any,
    *,
    limit: int = 48,
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
            status["unmapped_person_names"] = list(unmapped)
            # Merge durable face_appearance_moments (P2-I1) with seek URLs
            try:
                from memorybox.recognition.process import (
                    ensure_timeslot_play_url,
                    list_appearance_moments,
                )

                person_ids = {
                    str(m.get("person_id"))
                    for m in mapped_meta
                    if m.get("person_id")
                }
                name_by_pid = {
                    str(m.get("person_id")): str(m.get("name") or "")
                    for m in mapped_meta
                    if m.get("person_id")
                }
                existing_keys = {
                    (
                        str(h.video_external_id or ""),
                        int(float(h.start_sec or 0) // 2.5),
                    )
                    for h in hits
                }
                for pid in person_ids:
                    for mom in list_appearance_moments(pid, limit=limit):
                        vid = str(mom["video_external_id"])
                        t0 = float(mom["start_sec"])
                        slot_key = (vid, int(t0 // 2.5))
                        if slot_key in existing_keys:
                            continue
                        play = ensure_timeslot_play_url(
                            video_external_id=vid,
                            start_sec=t0,
                            play_url=mom.get("play_url"),
                        )
                        pname = name_by_pid.get(pid) or None
                        hits.append(
                            VideoHit(
                                provider_key=mom["video_provider_key"],
                                external_id=mom["id"],
                                video_external_id=vid,
                                start_sec=t0,
                                end_sec=float(mom["end_sec"]),
                                face_external_id=mom.get("face_external_id"),
                                label=pname or "Video moment",
                                play_url=play,
                                identity_trust=(
                                    "confirmed"
                                    if mom.get("authority") == "owner_confirmed"
                                    else "trusted_provider"
                                    if mom.get("authority") == "trusted_provider"
                                    else "candidate"
                                ),
                                mb_person_id=pid,
                                mb_person_name=pname,
                                attribution=(
                                    f"face-appearance moment "
                                    f"({mom.get('method')}, {mom.get('confirmation_state')})"
                                ),
                            )
                        )
                        existing_keys.add(slot_key)
            except Exception:  # noqa: BLE001
                pass
            if unmapped:
                status["disclosure"] = (
                    f"No HVRT/video provider mapping for: {unmapped}. "
                    "Teach/confirm the video face onto the same MB Person in Review "
                    "(do not recreate the human in each provider)."
                )
            return _dedupe_video_hits(hits, limit=limit), status

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


def search_guided_capture(plan: QueryPlan, *, limit: int = 12) -> list[dict[str, Any]]:
    """I11: cite Guided Capture Responses directly (no Story promotion required)."""
    if not getattr(plan, "want_guided_capture", False):
        return []
    from memorybox.guided_capture import search_responses_for_ask

    return search_responses_for_ask(
        query=plan.original_ask or "",
        person_names=tuple(plan.person_names or ()),
        limit=limit,
    )
