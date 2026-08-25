"""Fake LLM for offline acceptance — token-hash embeddings so retrieval works."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from memorybox.providers.base import ProviderHealth
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto

_DIM = 32
_VOLUME_NOISE = re.compile(
    r"(?i)evidence item\(s\)|\d{4}-W\d{2}:|\b\d+ email\b|\b\d+ sms\b|member_n"
)
_TXN_NOISE = re.compile(
    r"(?i)\b(tracking|shipment|shipped|order confirmation|survey invitation|"
    r"your receipt|invoice|fedex|usps)\b"
)


def _fake_observations(user_json: str) -> str:
    try:
        data = json.loads(user_json)
    except Exception:
        return json.dumps({"observations": []})
    units = [u for u in (data.get("units") or []) if isinstance(u, dict)]
    try:
        from memorybox.ask.i11a.observations import observation_from_unit
    except Exception:
        observation_from_unit = None  # type: ignore[assignment]
    rows = []
    for u in units:
        obs = observation_from_unit(u) if observation_from_unit else None
        if obs:
            rows.append(obs)
    return json.dumps({"observations": rows})


def _fake_ask_relative(user_json: str) -> str:
    try:
        data = json.loads(user_json)
    except Exception:
        return json.dumps({"schema_version": 2, "episodes": [], "themes": [], "unresolved": []})
    observations = [o for o in (data.get("observations") or []) if isinstance(o, dict)]
    ask = str(data.get("ask") or "")
    hint = str(data.get("ask_kind_hint") or "other")
    try:
        from memorybox.ask.i11a.reason import fallback_view

        view = fallback_view(observations, ask=ask, ask_kind_hint=hint)
        eps = []
        for ep in view.get("episodes") or []:
            blob = json.dumps(ep, default=str)
            if _TXN_NOISE.search(blob) and not re.search(
                r"(?i)\b(trip|visit|dinner|family|journal|surgery|harbor|alaska)\b",
                blob,
            ):
                continue
            eps.append(ep)
        view["episodes"] = eps
        return json.dumps(view, default=str)
    except Exception:
        return json.dumps(
            {
                "schema_version": 2,
                "ask_semantics": {"kind": hint, "constraints": {}},
                "episodes": [],
                "themes": [],
                "unresolved": [],
                "selected_observation_ids": [o.get("observation_id") for o in observations],
            }
        )


def _fake_inference(user_json: str) -> str:
    try:
        data = json.loads(user_json)
    except Exception:
        return json.dumps({"schema_version": 2, "episodes": [], "themes": [], "unresolved": ["unreadable input"]})
    if isinstance(data.get("leaf_results"), list):
        episodes: list[dict] = []
        for leaf in data["leaf_results"]:
            if isinstance(leaf, dict):
                episodes.extend([e for e in (leaf.get("episodes") or []) if isinstance(e, dict)])
        return json.dumps(
            {
                "schema_version": 2,
                "ask_semantics": {"kind": "period", "constraints": {}},
                "focal_subjects": [],
                "episodes": episodes[:48],
                "themes": [],
                "unresolved": [],
            }
        )
    units = [u for u in (data.get("units") or []) if isinstance(u, dict)]
    groups: dict[tuple[str, str], list[dict]] = {}
    for u in units:
        day = str(u.get("time") or "")[:10] or "undated"
        kind = str(u.get("kind") or "other")
        groups.setdefault((day, kind), []).append(u)
    episodes = []
    for (day, kind), rows in groups.items():
        claims = []
        vis = []
        people = []
        eids = []
        places: list[str] = []
        for u in rows[:12]:
            pl = str(u.get("place") or "").strip()
            if pl and pl not in places:
                places.append(pl)
            eid = str(u.get("evidence_id") or u.get("unit_id") or "").strip()
            text = re.sub(r"\s+", " ", str(u.get("content") or kind)).strip()[:220]
            if eid and text:
                if _TXN_NOISE.search(text) and not re.search(
                    r"(?i)\b(trip|visit|dinner|family|journal|surgery|harbor|alaska)\b",
                    text,
                ):
                    continue
                ctype = "recorded" if kind == "calendar" else (
                    "derived" if kind == "travel" else "observed"
                )
                claims.append(
                    {
                        "text": text,
                        "supporting_evidence_ids": [eid],
                        "claim_type": ctype,
                        "uncertainty": [],
                    }
                )
                eids.append(eid)
            if kind in {"media_observation", "spoken_moment", "video_asset", "video_moment"}:
                vid = str(u.get("asset_ref") or eid).strip()
                if vid:
                    vis.append(vid)
            for p in u.get("people") or []:
                if isinstance(p, dict) and (p.get("name") or p.get("person_id")):
                    people.append(
                        {
                            "person_id": p.get("person_id"),
                            "role": "participant",
                            "name": p.get("name"),
                        }
                    )
        if not claims:
            continue
        label = claims[0]["text"][:80]
        episodes.append(
            {
                "label": label,
                "date_span": {"start": None if day == "undated" else day, "end": None if day == "undated" else day},
                "people": people[:8],
                "places": places[:8],
                "claims": claims,
                "why_relevant_to_ask": "grounded in the supplied evidence",
                "supporting_evidence_ids": list(dict.fromkeys(eids))[:24],
                "candidate_visual_ids": list(dict.fromkeys(vis))[:12],
            }
        )
    episodes.sort(key=lambda e: str((e.get("date_span") or {}).get("start") or "9999"))
    return json.dumps(
        {
            "schema_version": 2,
            "ask_semantics": {"kind": str((data.get("ask_kind") or "other")), "constraints": {}},
            "focal_subjects": [],
            "episodes": episodes[:48],
            "themes": [],
            "unresolved": [],
        }
    )


def _claim_line(claim: Any) -> str:
    if isinstance(claim, dict):
        return str(claim.get("text") or "").strip()
    return str(claim or "").strip()


def _fake_narrative(pack_json: str) -> str:
    try:
        pack = json.loads(pack_json)
    except Exception:
        return "The prepared pack could not be read. MemoryBox will not invent family facts."
    label = pack.get("period") or pack.get("temporal_label") or "this period"
    episodes = [x for x in (pack.get("episodes") or []) if isinstance(x, dict)]

    paras: list[str] = [
        f"This is a chronological account of {label} from family records, "
        "without pasting the original messages."
    ]
    story_lines: list[str] = []
    for ep in episodes:
        claims = [_claim_line(c) for c in (ep.get("claims") or []) if _claim_line(c)]
        theme = str(ep.get("theme_or_episode") or "").strip()
        text = claims[0] if claims else theme
        t = re.sub(r"\s+", " ", text).strip()
        t = re.split(
            r"(?i)\nOn .+ wrote:|-----Original Message-----|Begin forwarded message:",
            t,
            maxsplit=1,
        )[0].strip()
        if not t or _VOLUME_NOISE.search(t):
            continue
        if _TXN_NOISE.search(t) and not re.search(r"(?i)\b(trip|visit|dinner|family|journal)\b", t):
            continue
        span = ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {}
        when = str((span or {}).get("start") or "").strip()
        people = []
        for p in ep.get("people") or []:
            if isinstance(p, dict):
                name = str(p.get("name") or p.get("person_id") or "").strip()
            else:
                name = str(p).strip()
            if name:
                people.append(name)
        if people:
            t = f"{t} — {', '.join(people[:3])}"
        unc = ep.get("uncertainty") if isinstance(ep.get("uncertainty"), dict) else {}
        kinds = {str(k).lower() for k in (ep.get("source_kinds") or {})}
        if unc.get("occurrence_not_established_by_calendar_alone") or unc.get(
            "calendar_scheduled_not_occurred"
        ) or "calendar" in kinds:
            if len(when) >= 10:
                story_lines.append(f"The calendar showed {when[:10]}: {t.rstrip('.')}.")
            else:
                story_lines.append(f"The calendar showed {t.rstrip('.')}.")
        elif unc.get("travel_derived_from_communication"):
            story_lines.append(f"Travel records indicate {t.rstrip('.')}.")
        elif any(k in {"photo", "photos", "media_observation"} for k in kinds):
            story_lines.append(f"Photos place {t.rstrip('.')}.")
        elif len(when) >= 10:
            story_lines.append(f"On {when[:10]}, {t.rstrip('.')}.")
        else:
            story_lines.append(t if t.endswith(".") else f"{t}.")
    if story_lines:
        chunk = max(1, (len(story_lines) + 1) // 2)
        paras.append(" ".join(story_lines[:chunk]))
        if story_lines[chunk:]:
            paras.append(" ".join(story_lines[chunk:]))
    else:
        paras.append(
            f"Nothing in the prepared outline rose above ordinary correspondence for {label}."
        )
    return "\n\n".join(p for p in paras if p)


def _token_vector(text: str) -> tuple[float, ...]:
    vec = [0.0] * _DIM
    tokens = re.findall(r"[a-z0-9_]+", (text or "").lower())
    if not tokens:
        tokens = ["empty"]
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % _DIM] += 1.0
    # L2 normalize
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return tuple(x / norm for x in vec)


class FakeLlmProvider:
    provider_key = "fake_llm"
    embed_model = "fake-embed"

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider_key=self.provider_key, ok=True, detail="fake")

    def embed(
        self, text: str, *, purpose: Literal["query", "document"] = "document"
    ) -> EmbeddingDto:
        return EmbeddingDto(
            model=self.embed_model,
            vector=_token_vector(text),
            purpose=purpose,
        )

    def chat(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> ChatResultDto:
        last = messages[-1].content if messages else ""
        system = next((m.content for m in messages if m.role == "system"), "")
        if json_mode:
            if "ASK_RELATIVE_REASONING" in (system or ""):
                content = _fake_ask_relative(last)
            elif "OBSERVATION_EXTRACT" in (system or ""):
                content = _fake_observations(last)
            elif "EVIDENCE_INFERENCE" in (system or "") or "INFERENCE_MERGE" in (system or ""):
                content = _fake_inference(last)
            else:
                content = '{"ok":true}'
        elif "NARRATIVE_SYNTHESIS" in (system or ""):
            content = _fake_narrative(last)
        else:
            content = f"echo:{last[:200]}"
        return ChatResultDto(model="fake-chat", content=content)
