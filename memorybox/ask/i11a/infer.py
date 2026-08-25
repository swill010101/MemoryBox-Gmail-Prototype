"""Provider-neutral I11A inference: batch, retry, merge, validate."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from memorybox.ask.i11a import needs_semantic_inference, resolve_request_context
from memorybox.ask.i11a.person_context import build_person_context, slim_person_context_for_model
from memorybox.ask.i11a.units import ask_kind_for_plan, compact_units_for_model, units_from_pack
from memorybox.ask.i11a.support import rank_episodes_for_narrator
from memorybox.ask.i11a.validate import parse_inference_json, validate_inference
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage

INFERENCE_SYSTEM = """EVIDENCE_INFERENCE
You are MemoryBox's structured inference engine. Return JSON only. Do not write family prose.
Interpret the evidence for the current Ask using Person context as interpretation aid, not as proof of period events.
This leaf sees only one batch. Emit grounded observations, not a competing final trip narrative.
A later reduce/correlation stage merges all leaf observations into one trip episode.
Rules:
- Ground every material claim in supporting_evidence_ids copied exactly from unit evidence_id or unit_id fields. Never invent IDs.
- Do not invent people, places, dates, motives, emotions, photographer identity, trip purpose, or that a calendar event occurred.
- Date proximity is not enough to merge records. Subject lines are not episode labels unless they name the real topic.
- Do not apply hard-coded topic importance (commerce is noise, health is important, family messages matter).
- Relationship labels may only reuse labels supplied in PersonContext. Unknown contacts stay unknown. Warmth or frequency is not family.
- candidate_visual_ids may only be asset/evidence ids from supplied media units.
- Media units may include captured_at, reliable EXIF/GPS, observed people, and location provenance. Infer candidate episodes from those fields; do not infer photographer, purpose, emotion, or companions beyond the evidence.
- A GPS or reverse-geocode city is presence at capture time, not residence or a month-long stay. Correlate nearby calendar/travel/media (for example Paradise, NV with Las Vegas) instead of inventing an independent period episode.
- Video assets (file + capture time + optional GPS) are evidence even without a face-appearance moment. Video moments (a span on a video) are a separate concept.
- A calendar 'Flight to Las Vegas' supports scheduled travel, not that the flight occurred. A generic flight without a destination cannot support 'flew to Las Vegas'. A Person+GPS photo supports physical presence at capture time.
- Return unresolved items rather than guessing.
- Do not include coverage, counts, provider status, eligible/processed totals, or incomplete flags in the JSON.
- Schema keys: schema_version, ask_semantics, focal_subjects, episodes, themes, unresolved.
- ask_semantics.kind must be period|trip|person|event|communications|other.
- Each episode needs label, date_span, people[].role, claims[].text, claims[].supporting_evidence_ids copied from unit evidence_id or unit_id, claim_type observed|recorded|recollection|derived|inferred.
- unresolved is short strings only. Do not copy whole units into unresolved.
Episode people.role: participant|mentioned|unknown.
"""

MERGE_SYSTEM = """INFERENCE_MERGE
Correlate leaf observation JSON objects into one schema_version 2 document for the Ask.
Leaves are observations, not competing final trip truth. Produce one normalized trip episode when they describe the same travel cluster.
Preserve original evidence IDs. Do not invent claims. JSON only. No coverage or counts.
"""

_DEFAULT_BATCH_CHARS = 12_000
_DEFAULT_RETRIES = 1


def _batch_chars() -> int:
    raw = (os.environ.get("MEMORYBOX_I11A_BATCH_CHARS") or "").strip()
    if raw.isdigit() and int(raw) > 500:
        return int(raw)
    return _DEFAULT_BATCH_CHARS


def _retries() -> int:
    raw = (os.environ.get("MEMORYBOX_I11A_BATCH_RETRIES") or "").strip()
    if raw.isdigit():
        return max(0, min(5, int(raw)))
    return _DEFAULT_RETRIES


def _chunk_units(units: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split by character budget only. Every unit is assigned to a chunk."""
    budget = _batch_chars()
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    size = 0
    for u in units:
        piece = len(json.dumps(u, default=str))
        if cur and size + piece > budget:
            chunks.append(cur)
            cur = []
            size = 0
        cur.append(u)
        size += piece
    if cur:
        chunks.append(cur)
    return chunks


def _trace_span(**kwargs: Any) -> None:
    try:
        from memorybox.ai_trace import context as ai_ctx
        from memorybox.ai_trace import store

        tid = ai_ctx.current_trace_id()
        if not tid:
            return
        store.insert_span(trace_id=tid, **kwargs)
    except Exception:  # noqa: BLE001
        return


def _chat_json(llm: Any, system: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if llm is None:
        raise ProviderUnavailable("No language model is configured.")
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=json.dumps(payload, default=str)),
    ]
    result = llm.chat(messages, json_mode=True)
    return str(getattr(result, "content", "") or ""), {
        "model": getattr(result, "model", None),
        "provider_key": getattr(llm, "provider_key", None),
    }


def _call_with_retry(llm: Any, system: str, payload: dict[str, Any]) -> str:
    last: Exception | None = None
    attempts = 1 + _retries()
    for i in range(attempts):
        try:
            text, _meta = _chat_json(llm, system, payload)
            if text.strip():
                return text
            last = ProviderError("empty inference response")
        except ProviderUnavailable:
            raise
        except (ProviderError, Exception) as exc:  # noqa: BLE001
            last = exc
            if i + 1 < attempts:
                time.sleep(0.05 * (i + 1))
                continue
            raise last
    raise last or ProviderError("inference failed")


def _deterministic_merge(
    leaf_docs: list[dict[str, Any]],
    *,
    keep_ids: set[str] | None = None,
) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    themes: list[Any] = []
    unresolved: list[Any] = []
    focals: list[Any] = []
    kind = "other"
    for doc in leaf_docs:
        if not isinstance(doc, dict):
            continue
        sem = doc.get("ask_semantics") if isinstance(doc.get("ask_semantics"), dict) else {}
        if sem.get("kind"):
            kind = str(sem.get("kind"))
        episodes.extend([e for e in (doc.get("episodes") or []) if isinstance(e, dict)])
        themes.extend(list(doc.get("themes") or []))
        unresolved.extend(list(doc.get("unresolved") or []))
        focals.extend(list(doc.get("focal_subjects") or []))

    def _ep_key(ep: dict[str, Any]) -> str:
        ds = ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {}
        return str(ds.get("start") or "") + "|" + str(ep.get("label") or "")

    episodes.sort(key=_ep_key)

    def _ep_keep_priority(ep: dict[str, Any]) -> int:
        blob = " ".join(
            str(x or "")
            for x in (
                ep.get("label"),
                ep.get("content"),
                " ".join(str(p) for p in (ep.get("places") or [])),
            )
        ).lower()
        kinds = " ".join(str(x) for x in (ep.get("source_kinds") or []))
        if any(tok in blob for tok in ("calendar", "flight", "sphere", "eagles", "cruise", "itinerary")):
            return 0
        if "calendar" in kinds or "travel" in kinds:
            return 0
        return 1

    ranked = sorted(episodes, key=lambda e: (_ep_keep_priority(e), _ep_key(e)))
    keep_ids = keep_ids or set()

    def _cites_keep(ep: dict[str, Any]) -> bool:
        ids: list[str] = []
        for raw in ep.get("supporting_evidence_ids") or []:
            ids.append(str(raw))
        for cl in ep.get("claims") or []:
            if isinstance(cl, dict):
                ids.extend(str(x) for x in (cl.get("supporting_evidence_ids") or []))
        return any(i in keep_ids for i in ids)

    pinned = [e for e in ranked if _cites_keep(e)]
    rest = [e for e in ranked if e not in pinned]
    room = max(0, 80 - len(pinned))
    return {
        "schema_version": 2,
        "ask_semantics": {"kind": kind, "constraints": {}},
        "focal_subjects": focals[:12],
        "episodes": (pinned + rest[:room])[: max(80, len(pinned))],
        "themes": themes[:24],
        "unresolved": unresolved[:24],
    }


def _llm_merge_enabled() -> bool:
    raw = (os.environ.get("MEMORYBOX_I11A_LLM_MERGE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _leaf_payload(
    *,
    plan: Any,
    person_context: dict[str, Any],
    chunk: list[dict[str, Any]],
    kind: str,
    modality_state: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "original_ask": getattr(plan, "original_ask", ""),
        "ask_kind": kind,
        "person_context": slim_person_context_for_model(person_context),
        "units": [_unit_for_model(u) for u in chunk],
        "modality_state": modality_state or {},
        "note": (
            "modality_state is operational. Do not restate counts or coverage in JSON."
        ),
    }


def _unit_for_model(unit: dict[str, Any]) -> dict[str, Any]:
    row = {
        "unit_id": unit.get("unit_id"),
        "evidence_id": unit.get("evidence_id"),
        "kind": unit.get("kind"),
        "source_type": unit.get("source_type"),
        "time": str(unit.get("time") or "")[:10],
        "people": unit.get("people") or [],
        "place": unit.get("place"),
        "content": str(unit.get("content") or "")[:120],
        "asset_ref": unit.get("asset_ref"),
    }
    if unit.get("media"):
        row["media"] = unit.get("media")
    elif unit.get("captured_at") or unit.get("exif_gps"):
        row["captured_at"] = unit.get("captured_at")
    return row


def run_inference(
    plan: Any,
    pack: dict[str, Any],
    llm: Any,
    *,
    modality_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run inference+validate. Never returns heuristic episodes as product truth."""
    t0 = time.perf_counter()
    person_context = build_person_context(plan)
    req = resolve_request_context(plan)
    kind = ask_kind_for_plan(plan)
    units = units_from_pack(pack)
    model_units = compact_units_for_model(units)
    chunks = _chunk_units(model_units)
    chunk_map: dict[str, int] = {}
    for i, ch in enumerate(chunks):
        for u in ch:
            for key in (u.get("unit_id"), u.get("evidence_id"), u.get("asset_ref")):
                s = str(key or "").strip()
                if s:
                    chunk_map[s] = i
            for extra in u.get("extra_ids") or []:
                s = str(extra or "").strip()
                if s:
                    chunk_map[s] = i
    keep_ids = {
        str(u.get("evidence_id") or u.get("unit_id") or "")
        for u in model_units
        if str(u.get("kind") or "") in {"calendar", "travel", "video_asset"}
    }
    keep_ids = {x for x in keep_ids if x}
    accounting = {
        "eligible_units": len(units),
        "chunk_n": len(chunks),
        "attempted_units": 0,
        "successful_units": 0,
        "failed_units": 0,
        "retries": _retries(),
        "merge_depth": 0,
        "units_generated": len(units),
        "units_passed_to_inference": len(model_units),
        "dropped_before_inference": max(0, len(units) - len(model_units)),
    }
    if not units:
        result = {
            "ok": False,
            "fail_closed": True,
            "reason": "no evidence units",
            "document": None,
            "rejected": [],
            "person_context": slim_person_context_for_model(person_context),
            "request_context": req,
            "accounting": accounting,
            "partial": False,
        }
        _trace_span(
            stage="i11a_validate",
            component="i11a",
            operation="fail_closed",
            status="error",
            error_class="PARSE_SCHEMA",
            assembled_context={
                "ok": False,
                "reason": result["reason"],
                "partial": False,
                "document": None,
                "rejected": [],
                "accounting": accounting,
                "fail_closed": True,
                "person_context": slim_person_context_for_model(person_context),
                "request_context": req,
            },
        )
        return result
    leaf_docs: list[dict[str, Any]] = []
    failed_chunks = 0
    raw_leaves: list[str] = []
    for idx, chunk in enumerate(chunks):
        accounting["attempted_units"] += len(chunk)
        payload = _leaf_payload(
            plan=plan,
            person_context=person_context,
            chunk=chunk,
            kind=kind,
            modality_state=modality_state,
        )
        try:
            raw = _call_with_retry(llm, INFERENCE_SYSTEM, payload)
            raw_leaves.append(raw)
            parsed = parse_inference_json(raw)
            if not parsed:
                raise ProviderError("inference JSON parse failed")
            leaf_docs.append(parsed)
            accounting["successful_units"] += len(chunk)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="leaf",
                status="ok",
                assembled_context={"chunk": idx, "unit_n": len(chunk)},
                provider_payload={"system": INFERENCE_SYSTEM, "user": payload},
                raw_response={"content": raw},
                parsed=parsed,
            )
        except Exception as exc:  # noqa: BLE001
            failed_chunks += 1
            accounting["failed_units"] += len(chunk)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="leaf",
                status="error",
                error_class="MODEL_OUTPUT",
                assembled_context={"chunk": idx, "unit_n": len(chunk)},
                error={"message": str(exc)},
            )
    merged_raw = None
    if not leaf_docs:
        result = {
            "ok": False,
            "fail_closed": True,
            "reason": "inference unavailable or unparsable",
            "document": None,
            "rejected": [],
            "person_context": slim_person_context_for_model(person_context),
            "request_context": req,
            "accounting": accounting,
            "partial": False,
        }
        _trace_span(
            stage="i11a_validate",
            component="i11a",
            operation="fail_closed",
            status="error",
            error_class="PARSE_SCHEMA",
            assembled_context={
                "ok": False,
                "reason": result["reason"],
                "partial": False,
                "document": None,
                "rejected": [],
                "accounting": accounting,
                "fail_closed": True,
                "person_context": slim_person_context_for_model(person_context),
                "request_context": req,
            },
        )
        return result
    parsed_merge = leaf_docs[0]
    if len(leaf_docs) > 1:
        accounting["merge_depth"] = 1
        if _llm_merge_enabled():
            merge_payload = {
                "original_ask": getattr(plan, "original_ask", ""),
                "leaf_results": leaf_docs,
            }
            try:
                merged_raw = _call_with_retry(llm, MERGE_SYSTEM, merge_payload)
                parsed_merge = parse_inference_json(merged_raw) or parsed_merge
                _trace_span(
                    stage="i11a_inference",
                    component="i11a",
                    operation="merge",
                    status="ok",
                    provider_payload={"system": MERGE_SYSTEM, "user": merge_payload},
                    raw_response={"content": merged_raw},
                    parsed=parsed_merge,
                )
            except Exception as exc:  # noqa: BLE001
                result = {
                    "ok": False,
                    "fail_closed": True,
                    "reason": "inference merge failed",
                    "document": None,
                    "rejected": [{"reason": str(exc)}],
                    "person_context": person_context,
                    "request_context": req,
                    "accounting": accounting,
                    "partial": False,
                }
                _trace_span(
                    stage="i11a_validate",
                    component="i11a",
                    operation="merge_fail",
                    status="error",
                    error_class="PARSE_SCHEMA",
                    error={"message": str(exc)},
                )
                return result
        else:
            parsed_merge = _deterministic_merge(leaf_docs, keep_ids=keep_ids)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="merge_deterministic",
                status="ok",
                parsed=parsed_merge,
            )
    from memorybox.ask.i11a.reduce import reduce_leaf_observations

    parsed_merge = reduce_leaf_observations(parsed_merge)
    _trace_span(
        stage="i11a_inference",
        component="i11a",
        operation="reduce_correlate",
        status="ok",
        parsed=parsed_merge,
    )
    validated = validate_inference(
        parsed_merge, pack=pack, person_context=person_context
    )
    incomplete = failed_chunks > 0
    fail_closed = not validated.get("ok")
    if incomplete and accounting["successful_units"] == 0:
        fail_closed = True
    if incomplete and accounting["attempted_units"] and (
        accounting["successful_units"] < max(1, accounting["attempted_units"] // 2)
    ):
        fail_closed = True
        incomplete = False
    result = {
        "ok": bool(validated.get("ok")) and not fail_closed,
        "fail_closed": fail_closed,
        "partial": incomplete and not fail_closed,
        "reason": None if validated.get("ok") and not fail_closed else "validation failed",
        "document": validated.get("document") if not fail_closed else None,
        "rejected": validated.get("rejected") or [],
        "person_context": person_context,
        "request_context": req,
        "accounting": accounting,
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "raw_leaf_n": len(raw_leaves),
        "chunk_map": chunk_map,
    }
    if fail_closed and not leaf_docs:
        result["reason"] = "inference unavailable or unparsable"
    _trace_span(
        stage="i11a_validate",
        component="i11a",
        operation="validate",
        status="ok" if result["ok"] else "error",
        parsed=validated.get("document"),
        validation={"rejected": result["rejected"], "ok": result["ok"]},
        assembled_context={
            "request_context": req,
            "accounting": accounting,
            "partial": result["partial"],
            "person_context": slim_person_context_for_model(person_context),
        },
        disposition={"validated_semantic_pack": validated.get("document") if result["ok"] else None},
    )
    return result


def outline_from_inference(document: dict[str, Any], plan: Any) -> dict[str, Any]:
    episodes = []
    for ep in document.get("episodes") or []:
        claims = [c.get("text") for c in (ep.get("claims") or []) if isinstance(c, dict) and c.get("text")]
        people = []
        for p in ep.get("people") or []:
            if isinstance(p, dict):
                people.append(str(p.get("name") or p.get("person_id") or "").strip())
            else:
                people.append(str(p))
        people = [x for x in people if x]
        eids = list(ep.get("supporting_evidence_ids") or [])
        for c in ep.get("claims") or []:
            if isinstance(c, dict):
                eids.extend(str(x) for x in (c.get("supporting_evidence_ids") or []))
        eids = list(dict.fromkeys(eids))
        uncertainty: dict[str, Any] = {}
        for c in ep.get("claims") or []:
            if not isinstance(c, dict):
                continue
            if c.get("claim_type") == "recorded":
                uncertainty["occurrence_not_established_by_calendar_alone"] = True
            if c.get("claim_type") == "derived":
                uncertainty["travel_derived_from_communication"] = True
        row = {
            "theme_or_episode": ep.get("label") or "Untitled",
            "claims": claims,
            "evidence_ids": eids[:40],
            "date_span": ep.get("date_span") or {},
            "scheduled_window": ep.get("scheduled_window") or {"start": None, "end": None, "evidence_ids": []},
            "observed_window": ep.get("observed_window") or {"start": None, "end": None, "evidence_ids": []},
            "derived_window": ep.get("derived_window") or {"start": None, "end": None, "evidence_ids": []},
            "people": people[:12],
            "places": ep.get("places") or [],
            "significance": str(ep.get("why_relevant_to_ask") or "characterizes the period"),
            "exemplars": [],
            "provenance": {"grounded_in_evidence_ids": True, "not_family_truth": True},
            "candidate_visual_ids": ep.get("candidate_visual_ids") or [],
            "support_profile": ep.get("support_profile") or {},
            "support_score": ep.get("support_score"),
        }
        if uncertainty:
            row["uncertainty"] = uncertainty
        episodes.append(row)
    episodes = rank_episodes_for_narrator(episodes, budget=24)
    windows_raw = [tuple(w) for w in (getattr(plan, "temporal_windows", ()) or ()) if w]
    if not windows_raw:
        t0 = getattr(plan, "time_start", None)
        t1 = getattr(plan, "time_end", None)
        if t0 and t1:
            windows_raw = [(t0, t1)]
    from memorybox.ask.i11a.windows import pack_level_windows

    return {
        "period": str(getattr(plan, "temporal_label", None) or "this period"),
        "windows": [{"start": str(a)[:10], "end": str(b)[:10]} for a, b in windows_raw],
        "episodes": episodes,
        **pack_level_windows(episodes),
    }


def apply_inference_to_pack(
    plan: Any,
    pack: dict[str, Any],
    llm: Any,
    *,
    modality_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not needs_semantic_inference(plan):
        pack["inference"] = {"ok": False, "bypassed": True}
        return pack
    inf = run_inference(plan, pack, llm, modality_state=modality_state)
    pack["inference"] = {
        "ok": inf.get("ok"),
        "fail_closed": inf.get("fail_closed"),
        "partial": inf.get("partial"),
        "reason": inf.get("reason"),
        "accounting": inf.get("accounting"),
        "rejected": inf.get("rejected"),
        "request_context": inf.get("request_context"),
        "heuristic_not_product_truth": True,
    }
    pack["person_context"] = inf.get("person_context")
    pack["request_context"] = inf.get("request_context")
    if inf.get("partial"):
        cov = pack.get("coverage") if isinstance(pack.get("coverage"), dict) else {}
        cov["incomplete"] = True
        cov["truncated"] = True
        cov["truncation_disclosure"] = (
            cov.get("truncation_disclosure")
            or "Some evidence batches could not be inferred."
        )
        pack["coverage"] = cov
    if inf.get("ok") and inf.get("document"):
        pack["validated_inference"] = inf["document"]
        outline = outline_from_inference(inf["document"], plan)
        pack["life_period_outline"] = outline
        vol = pack.get("volume") if isinstance(pack.get("volume"), dict) else {}
        vol["narrator_input_n"] = len(outline.get("episodes") or [])
        vol["supplied_to_model_n"] = vol["narrator_input_n"]
        vol["reduction"] = "i11a_inference"
        pack["volume"] = vol
        vis: list[str] = []
        for ep in inf["document"].get("episodes") or []:
            vis.extend(ep.get("candidate_visual_ids") or [])
        pack["candidate_visual_ids"] = list(dict.fromkeys(vis))
    from memorybox.ask.i11a.consideration import finish_consideration

    finish_consideration(
        pack,
        chunk_map=inf.get("chunk_map") or {},
        document=inf.get("document"),
        accounting=inf.get("accounting"),
    )
    return pack


def rank_photos_by_candidates(photos: list[Any], candidate_ids: list[str]) -> list[Any]:
    """Reorder only. Never drop in-scope photos."""
    if not candidate_ids or not photos:
        return list(photos)
    wanted = {str(x) for x in candidate_ids}
    head: list[Any] = []
    tail: list[Any] = []
    for p in photos:
        d = p.to_dict() if hasattr(p, "to_dict") else p
        eid = str((d or {}).get("external_id") or "")
        if eid in wanted:
            head.append(p)
        else:
            tail.append(p)
    return head + tail
