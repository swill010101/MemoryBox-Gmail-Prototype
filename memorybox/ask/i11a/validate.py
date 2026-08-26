"""Deterministic validation of I11A model inference."""
from __future__ import annotations

import json
import re
from typing import Any

from memorybox.ask.i11a.person_context import allowed_relationship_labels
from memorybox.ask.i11a.support import attach_support_profile
from memorybox.ask.i11a.units import (
    ASK_KINDS,
    CLAIM_TYPES,
    PEOPLE_ROLES,
    SCHEMA_VERSION,
    in_scope_ids,
    in_scope_visual_ids,
)
from memorybox.ask.i11a.windows import (
    attach_windows,
    leaf_unit_index,
    pack_level_windows,
    union_windows,
    windows_from_episode,
    _index_pack_units,
)

_REL_EMIT = re.compile(
    r"\b(spouse|partner|sibling|brother|sister|child|son|daughter|"
    r"parent|father|mother|family|friend|colleague|uncle|aunt|"
    r"niece|nephew|grandparent|grandchild|husband|wife|married|"
    r"related|kin|cousin)\b",
    re.I,
)
_GENERIC_PLACES = frozenset(
    {"unplaced", "unspecified", "unknown", "none", "n/a", "null", "unspecified roadside"}
)


def parse_inference_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _resolve_id(raw: str, scope: set[str]) -> str | None:
    token = str(raw or "").strip()
    if not token:
        return None
    if token in scope:
        return token
    low = token.lower()
    for sid in scope:
        if sid.lower() == low:
            return sid
    if len(token) >= 8:
        hits = [sid for sid in scope if sid.lower().endswith(low) or low.endswith(sid.lower())]
        if len(hits) == 1:
            return hits[0]
        hits = [sid for sid in scope if low in sid.lower() or sid.lower() in low]
        if len(hits) == 1:
            return hits[0]
    return None


def _collect_ids(raw: Any, scope: set[str]) -> list[str]:
    values: list[Any]
    if isinstance(raw, (list, tuple)):
        values = list(raw)
    elif raw:
        values = [raw]
    else:
        values = []
    out: list[str] = []
    for item in values:
        resolved = _resolve_id(str(item), scope)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


def _strip_operational(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out.pop("coverage", None)
    out.pop("volume", None)
    out.pop("evidence_considered", None)
    out.pop("eligible_n", None)
    out.pop("processed_n", None)
    out.pop("incomplete", None)
    out.pop("provider", None)
    out["schema_version"] = SCHEMA_VERSION
    return out


def _coerce_ask_semantics(ask_sem: dict[str, Any]) -> dict[str, Any]:
    kind = str(ask_sem.get("kind") or "")
    if kind not in ASK_KINDS:
        kind = "other"
        for candidate in ("trip", "period", "person", "event", "communications"):
            if ask_sem.get(candidate) is True:
                kind = candidate
                break
    constraints = ask_sem.get("constraints")
    if not isinstance(constraints, dict):
        constraints = {}
    return {"kind": kind, "constraints": constraints}


def _claim_type_for(raw: Any, *, kind: str = "") -> str:
    ctype = str(raw or "").strip().lower()
    if ctype in CLAIM_TYPES:
        return ctype
    if kind == "travel":
        return "derived"
    if kind == "calendar":
        return "recorded"
    if kind in {"journal", "story"}:
        return "recollection"
    return "observed"


def _ids_from_mapping(obj: dict[str, Any], scope: set[str]) -> list[str]:
    ids: list[str] = []
    for key in (
        "supporting_evidence_ids",
        "evidence_ids",
        "ids",
        "evidence_id",
        "unit_id",
        "asset_ref",
    ):
        for token in _collect_ids(obj.get(key), scope):
            if token not in ids:
                ids.append(token)
    for extra in obj.get("extra_ids") or []:
        for token in _collect_ids(extra, scope):
            if token not in ids:
                ids.append(token)
    return ids


def _looks_like_unit(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if not (obj.get("evidence_id") or obj.get("unit_id")):
        return False
    return bool(obj.get("kind") or obj.get("content") or obj.get("time"))


def _episode_from_unit(unit: dict[str, Any], scope: set[str]) -> dict[str, Any] | None:
    ids = _ids_from_mapping(unit, scope)
    text = str(unit.get("content") or unit.get("label") or unit.get("kind") or "").strip()
    if not ids or not text:
        return None
    kind = str(unit.get("kind") or "")
    day = str(unit.get("time") or "")[:10]
    date_span = {"start": day, "end": day} if day else {}
    place = str(unit.get("place") or "").strip()
    people = []
    for p in unit.get("people") or []:
        if isinstance(p, dict):
            people.append(p)
        elif str(p).strip():
            people.append({"name": str(p).strip()})
    return {
        "label": text[:160],
        "date_span": date_span,
        "people": people,
        "places": [place] if place else [],
        "claims": [
            {
                "text": text[:500],
                "supporting_evidence_ids": ids[:24],
                "claim_type": _claim_type_for(unit.get("claim_type") or unit.get("episode_type"), kind=kind),
                "uncertainty": [],
            }
        ],
        "why_relevant_to_ask": "",
        "supporting_evidence_ids": ids[:40],
        "candidate_visual_ids": [],
    }


def validate_observations(
    observations: list[dict[str, Any]] | None,
    *,
    pack: dict[str, Any],
    person_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask-independent claim/evidence compatibility. Same rules for every Ask."""
    rejected: list[dict[str, Any]] = []
    scope = in_scope_ids(pack)
    allowed = allowed_relationship_labels(person_context)
    index = _index_pack_units(pack)
    leaves = leaf_unit_index(pack)
    out: list[dict[str, Any]] = []
    for obs in observations or []:
        if not isinstance(obs, dict):
            rejected.append({"reason": "observation_not_object"})
            continue
        from memorybox.ask.i11a.observations import canonicalize_observation
        from memorybox.ask.i11a.comm_compact import _TRANSPORT_ONLY

        canon = canonicalize_observation(obs)
        if not canon:
            rejected.append({"reason": "observation_schema_invalid", "kind": obs.get("kind")})
            continue
        obs = canon
        raw_text = obs.get("text")
        text = str(raw_text or "").strip()
        if raw_text is None or text.lower() in {"none", "null", "n/a", "undefined"}:
            rejected.append({"reason": "empty_observation", "text": None if raw_text is None else text[:80]})
            continue
        if _TRANSPORT_ONLY.match(text):
            rejected.append({"reason": "transport_metadata_only", "text": text[:160]})
            continue
        ids = _collect_ids(obs.get("supporting_evidence_ids") or obs.get("evidence_ids"), scope)
        if not ids:
            ids = [str(x) for x in (obs.get("supporting_evidence_ids") or []) if str(x) in scope]
        if not text:
            rejected.append({"reason": "empty_observation"})
            continue
        if str(obs.get("kind") or "") == "place_referenced":
            places_ok = [
                str(p).strip()
                for p in (obs.get("places") or [])
                if str(p).strip() and str(p).strip().lower() not in _GENERIC_PLACES
            ]
            if not places_ok:
                rejected.append({"reason": "place_referenced_without_place", "text": text[:160]})
                continue
        if str(obs.get("kind") or "") == "person_at_place_time":
            places_ok = [
                str(p).strip()
                for p in (obs.get("places") or [])
                if str(p).strip()
                and str(p).strip().lower() not in _GENERIC_PLACES
                and "unspecified" not in str(p).strip().lower()
            ]
            if not places_ok:
                rejected.append({"reason": "person_at_place_time_without_place", "text": text[:160]})
                continue
        if str(obs.get("kind") or "") == "relationship_stated" and not _REL_EMIT.search(text):
            rejected.append({"reason": "relationship_stated_without_relationship", "text": text[:160]})
            continue
        if not ids:
            rejected.append({"reason": "observation_missing_ids", "text": text[:160]})
            continue
        from memorybox.ask.i11a.claim_support import filter_claim_ids

        kept, support_rej = filter_claim_ids(text, ids, index, leaf_index=leaves)
        for row in support_rej:
            rejected.append({"reason": "evidence_cannot_support_claim", "text": text[:160], **row})
        if not kept:
            rejected.append({"reason": "observation_unsupportable", "text": text[:160]})
            continue
        people_out = []
        for p in obs.get("people") or []:
            if isinstance(p, str):
                people_out.append({"name": p, "person_id": None, "role": "mentioned"})
                continue
            if not isinstance(p, dict):
                continue
            extra_rel = str(p.get("relationship") or p.get("kin") or p.get("family_role") or "").lower()
            if extra_rel and extra_rel not in allowed and extra_rel not in PEOPLE_ROLES:
                rejected.append({"reason": "relationship_not_in_graph", "label": extra_rel})
                extra_rel = ""
            role = str(p.get("role") or "participant")
            if role not in PEOPLE_ROLES:
                role = "participant"
            people_out.append(
                {"person_id": p.get("person_id"), "role": role, "name": p.get("name")}
            )
        ctype = str(obs.get("claim_type") or "observed")
        if ctype not in CLAIM_TYPES:
            ctype = "inferred"
        row = dict(obs)
        row["text"] = text[:500]
        row["supporting_evidence_ids"] = kept
        row["claim_type"] = ctype
        row["people"] = people_out
        out.append(row)
    return {"ok": bool(out), "observations": out, "rejected": rejected}


def validate_inference(
    doc: dict[str, Any] | None,
    *,
    pack: dict[str, Any],
    person_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return {ok, document, rejected, unresolved} after stripping system-truth."""
    rejected: list[dict[str, Any]] = []
    if not isinstance(doc, dict):
        return {
            "ok": False,
            "document": None,
            "rejected": [{"reason": "not_an_object"}],
            "unresolved": [],
        }
    doc = _strip_operational(doc)
    scope = in_scope_ids(pack)
    visuals = in_scope_visual_ids(pack)
    allowed = allowed_relationship_labels(person_context)
    ask_sem = doc.get("ask_semantics") if isinstance(doc.get("ask_semantics"), dict) else {}
    doc["ask_semantics"] = _coerce_ask_semantics(ask_sem)
    focals = []
    seen_focal: set[str] = set()
    for row in doc.get("focal_subjects") or []:
        pid = ""
        if isinstance(row, dict) and row.get("person_id"):
            pid = str(row.get("person_id"))
        elif isinstance(row, str) and row.strip():
            pid = row.strip()
        if pid and pid not in seen_focal:
            seen_focal.add(pid)
            focals.append({"person_id": pid})
    doc["focal_subjects"] = focals
    raw_episodes = list(doc.get("episodes") or [])
    leftover_unresolved: list[Any] = []
    for u in doc.get("unresolved") or []:
        if _looks_like_unit(u):
            raw_episodes.append(u)
        else:
            leftover_unresolved.append(u)
    episodes_out: list[dict[str, Any]] = []
    for ep in raw_episodes:
        if not isinstance(ep, dict):
            rejected.append({"reason": "episode_not_object"})
            continue
        if _looks_like_unit(ep) and not ep.get("claims") and not ep.get("label"):
            promoted = _episode_from_unit(ep, scope)
            if promoted:
                ep = promoted
            else:
                rejected.append({"reason": "episode_no_grounded_claims"})
                continue
        ep_ids = _ids_from_mapping(ep, scope)
        claims_src = list(ep.get("claims") or [])
        if not claims_src:
            text = str(ep.get("content") or ep.get("label") or "").strip()
            if text and ep_ids:
                claims_src = [
                    {
                        "text": text,
                        "supporting_evidence_ids": ep_ids,
                        "claim_type": _claim_type_for(
                            ep.get("claim_type") or ep.get("episode_type"),
                            kind=str(ep.get("kind") or ""),
                        ),
                    }
                ]
        claims_out = []
        for cl in claims_src:
            if isinstance(cl, str) and cl.strip():
                cl = {"text": cl.strip(), "supporting_evidence_ids": [], "claim_type": "inferred"}
            if not isinstance(cl, dict):
                rejected.append({"reason": "claim_not_object"})
                continue
            ids = _collect_ids(
                cl.get("supporting_evidence_ids") or cl.get("evidence_ids") or cl.get("ids"),
                scope,
            )
            if not ids:
                ids = list(ep_ids)
            if not ids:
                rejected.append(
                    {
                        "reason": "claim_missing_ids",
                        "text": cl.get("text"),
                    }
                )
                continue
            ctype = str(cl.get("claim_type") or "inferred")
            if ctype not in CLAIM_TYPES:
                ctype = "inferred"
            text = str(cl.get("text") or "").strip()
            if not text:
                rejected.append({"reason": "empty_claim"})
                continue
            from memorybox.ask.i11a.claim_support import filter_claim_ids
            from memorybox.ask.i11a.windows import leaf_unit_index as _leaf_idx

            kept_ids, support_rej = filter_claim_ids(
                text, ids, _index_pack_units(pack), leaf_index=_leaf_idx(pack)
            )
            for row in support_rej:
                rejected.append(
                    {
                        "reason": "evidence_cannot_support_claim",
                        "text": text[:160],
                        **row,
                    }
                )
            if not kept_ids:
                rejected.append({"reason": "claim_unsupportable", "text": text[:160]})
                continue
            ids = kept_ids
            unc = cl.get("uncertainty") if isinstance(cl.get("uncertainty"), list) else []
            claims_out.append(
                {
                    "text": text[:500],
                    "supporting_evidence_ids": ids[:24],
                    "claim_type": ctype,
                    "uncertainty": [str(u) for u in unc[:12]],
                }
            )
        people_out = []
        for p in ep.get("people") or []:
            if isinstance(p, str):
                people_out.append({"person_id": None, "role": "mentioned", "name": p})
                continue
            if not isinstance(p, dict):
                continue
            extra_rel = str(
                p.get("relationship") or p.get("kin") or p.get("family_role") or ""
            ).lower()
            if extra_rel and extra_rel not in allowed and extra_rel not in PEOPLE_ROLES:
                rejected.append(
                    {
                        "reason": "relationship_not_in_graph",
                        "label": extra_rel,
                    }
                )
                extra_rel = ""
            role = str(p.get("role") or p.get("role_kind") or "participant")
            if role not in PEOPLE_ROLES:
                role = "participant"
            people_out.append(
                {
                    "person_id": p.get("person_id"),
                    "role": role,
                    "name": p.get("name"),
                }
            )
        vis = _collect_ids(ep.get("candidate_visual_ids"), visuals)
        eids = list(ep_ids)
        for c in claims_out:
            for i in c.get("supporting_evidence_ids") or []:
                if i not in eids:
                    eids.append(i)
        label = str(ep.get("label") or ep.get("content") or "Untitled")[:160]
        date_span = ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {}
        if not date_span:
            day = str(ep.get("time") or "")[:10]
            if day:
                date_span = {"start": day, "end": day}
        places = [str(x) for x in (ep.get("places") or []) if str(x).strip()][:12]
        if ep.get("place") and str(ep.get("place")).strip() not in places:
            places.append(str(ep.get("place")).strip())
        if not claims_out and eids:
            claims_out.append(
                {
                    "text": label,
                    "supporting_evidence_ids": eids[:8],
                    "claim_type": "inferred",
                    "uncertainty": ["repaired_from_episode_ids"],
                }
            )
        if not claims_out and not eids:
            rejected.append({"reason": "episode_no_grounded_claims", "label": ep.get("label")})
            continue
        row = {
            "label": label,
            "date_span": date_span,
            "people": people_out[:24],
            "places": places[:12],
            "claims": claims_out,
            "why_relevant_to_ask": str(ep.get("why_relevant_to_ask") or "")[:400],
            "supporting_evidence_ids": eids[:40],
            "candidate_visual_ids": vis[:24],
        }
        attach_windows(
            row,
            windows_from_episode(
                claims=claims_out,
                evidence_ids=eids,
                date_span=date_span,
                pack=pack,
            ),
            fallback_span=date_span,
        )
        for key in ("observed_window", "scheduled_window", "derived_window"):
            prev = ep.get(key) if isinstance(ep.get(key), dict) else {}
            cur = row.get(key) if isinstance(row.get(key), dict) else {}
            if prev.get("start") and not (cur or {}).get("start"):
                row[key] = union_windows([cur, prev])
        attach_support_profile(row, pack=pack)
        episodes_out.append(row)
    episodes_out.sort(
        key=lambda e: (
            -float(e.get("support_score") or 0),
            str(((e.get("date_span") or {}) if isinstance(e.get("date_span"), dict) else {}).get("start") or "9999")[:10],
        )
    )
    themes = []
    for th in doc.get("themes") or []:
        if isinstance(th, str) and th.strip():
            themes.append({"label": th.strip()[:160], "supporting_evidence_ids": []})
        elif isinstance(th, dict) and th.get("label"):
            ids = [
                str(x)
                for x in (th.get("supporting_evidence_ids") or [])
                if str(x).strip() and str(x) in scope
            ]
            themes.append({"label": str(th.get("label"))[:160], "supporting_evidence_ids": ids[:24]})
    unresolved = []
    for u in leftover_unresolved:
        if isinstance(u, str) and u.strip():
            unresolved.append(u.strip()[:300])
        elif isinstance(u, dict) and (u.get("text") or u.get("content")):
            unresolved.append(str(u.get("text") or u.get("content"))[:300])
    document = {
        "schema_version": SCHEMA_VERSION,
        "ask_semantics": doc.get("ask_semantics") or {"kind": "other", "constraints": {}},
        "focal_subjects": focals,
        "episodes": episodes_out,
        "themes": themes,
        "unresolved": unresolved,
        "person_understanding": doc.get("person_understanding"),
        **pack_level_windows(episodes_out),
    }
    ok = bool(episodes_out or unresolved or themes)
    return {
        "ok": ok,
        "document": document,
        "rejected": rejected,
        "unresolved": unresolved,
    }
