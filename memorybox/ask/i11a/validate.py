"""Deterministic validation of I11A model inference."""
from __future__ import annotations

import json
import re
from typing import Any

from memorybox.ask.i11a.person_context import allowed_relationship_labels
from memorybox.ask.i11a.units import (
    ASK_KINDS,
    CLAIM_TYPES,
    PEOPLE_ROLES,
    SCHEMA_VERSION,
    in_scope_ids,
    in_scope_visual_ids,
)

_REL_EMIT = re.compile(
    r"\b(spouse|partner|sibling|brother|sister|child|son|daughter|"
    r"parent|father|mother|family|friend|colleague|uncle|aunt|"
    r"niece|nephew|grandparent|grandchild)\b",
    re.I,
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
    kind = str(ask_sem.get("kind") or "other")
    if kind not in ASK_KINDS:
        ask_sem = {**ask_sem, "kind": "other"}
        doc["ask_semantics"] = ask_sem
    focals = []
    for row in doc.get("focal_subjects") or []:
        if isinstance(row, dict) and row.get("person_id"):
            focals.append({"person_id": str(row.get("person_id"))})
        elif isinstance(row, str) and row.strip():
            focals.append({"person_id": row.strip()})
    doc["focal_subjects"] = focals
    episodes_out: list[dict[str, Any]] = []
    for ep in doc.get("episodes") or []:
        if not isinstance(ep, dict):
            rejected.append({"reason": "episode_not_object"})
            continue
        claims_out = []
        for cl in ep.get("claims") or []:
            if isinstance(cl, str) and cl.strip():
                cl = {"text": cl.strip(), "supporting_evidence_ids": [], "claim_type": "inferred"}
            if not isinstance(cl, dict):
                rejected.append({"reason": "claim_not_object"})
                continue
            ids = [
                str(x)
                for x in (cl.get("supporting_evidence_ids") or [])
                if str(x).strip()
            ]
            bad = [i for i in ids if i not in scope]
            if not ids or bad:
                rejected.append(
                    {
                        "reason": "claim_ids_out_of_scope" if bad else "claim_missing_ids",
                        "text": cl.get("text"),
                        "bad_ids": bad,
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
                continue
            role = str(p.get("role") or "participant")
            if role not in PEOPLE_ROLES:
                role = "participant"
            people_out.append(
                {
                    "person_id": p.get("person_id"),
                    "role": role,
                    "name": p.get("name"),
                }
            )
        vis = [
            str(x)
            for x in (ep.get("candidate_visual_ids") or [])
            if str(x).strip() and str(x) in visuals
        ]
        dropped_vis = [
            str(x)
            for x in (ep.get("candidate_visual_ids") or [])
            if str(x).strip() and str(x) not in visuals
        ]
        if dropped_vis:
            rejected.append({"reason": "visual_id_out_of_scope", "ids": dropped_vis})
        eids = [
            str(x)
            for x in (ep.get("supporting_evidence_ids") or [])
            if str(x).strip() and str(x) in scope
        ]
        if not claims_out and not eids:
            rejected.append({"reason": "episode_no_grounded_claims", "label": ep.get("label")})
            continue
        label = str(ep.get("label") or "Untitled")[:160]
        episodes_out.append(
            {
                "label": label,
                "date_span": ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {},
                "people": people_out[:24],
                "places": [str(x) for x in (ep.get("places") or []) if str(x).strip()][:12],
                "claims": claims_out,
                "why_relevant_to_ask": str(ep.get("why_relevant_to_ask") or "")[:400],
                "supporting_evidence_ids": eids[:40],
                "candidate_visual_ids": vis[:24],
            }
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
    for u in doc.get("unresolved") or []:
        if isinstance(u, str) and u.strip():
            unresolved.append(u.strip()[:300])
        elif isinstance(u, dict) and u.get("text"):
            unresolved.append(str(u.get("text"))[:300])
    document = {
        "schema_version": SCHEMA_VERSION,
        "ask_semantics": doc.get("ask_semantics") or {"kind": "other", "constraints": {}},
        "focal_subjects": focals,
        "episodes": episodes_out,
        "themes": themes,
        "unresolved": unresolved,
    }
    ok = bool(episodes_out or unresolved or themes)
    return {
        "ok": ok,
        "document": document,
        "rejected": rejected,
        "unresolved": unresolved,
    }
