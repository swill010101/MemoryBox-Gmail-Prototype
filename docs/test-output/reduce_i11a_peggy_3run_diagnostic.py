#!/usr/bin/env python3
"""Reduce a full I11A regression JSON to I11A_Peggy_3Run_Diagnostic_Summary.json.

Does not call MemoryBox, Ollama, or the regression harness. Trace analysis only.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUT_NAME = "I11A_Peggy_3Run_Diagnostic_Summary.json"
ID_SAMPLE = 25
ROLLUP_SAMPLE = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _as_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _day(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _day(raw.get("start") or raw.get("time") or raw.get("date"))
    s = str(raw).strip()
    if not s:
        return None
    if "T" in s:
        s = s.split("T", 1)[0]
    return s[:10] if len(s) >= 10 else s


def _span_days(start: Any, end: Any) -> int | None:
    a, b = _day(start), _day(end)
    if not a or not b:
        return None
    try:
        da = datetime.fromisoformat(a).date()
        db = datetime.fromisoformat(b).date()
    except ValueError:
        return None
    return abs((db - da).days)


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)


def _dist(values: list[float | int]) -> dict[str, Any]:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return {"min": None, "median": None, "p95": None, "max": None, "n": 0}
    return {
        "min": min(nums),
        "median": statistics.median(nums),
        "p95": _pct(nums, 95),
        "max": max(nums),
        "n": len(nums),
    }


def _first(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x).strip()]


def _set_diff(base: list[str], other: list[str]) -> dict[str, Any]:
    sa, sb = set(base), set(other)
    added = sorted(sb - sa)
    missing = sorted(sa - sb)
    match = len(sa & sb)
    return {
        "same": not added and not missing,
        "match_count": match,
        "added_count": len(added),
        "missing_count": len(missing),
        "added_ids": added[:ID_SAMPLE] if added else [],
        "missing_ids": missing[:ID_SAMPLE] if missing else [],
    }


def _fp_compare(base: list[str], other: list[str]) -> dict[str, Any]:
    d = _set_diff(base, other)
    # Fingerprints are identity strings: a given fingerprint either matches,
    # is added, or is missing. There is no in-place rewrite to count as mismatch.
    out = {
        "same": d["same"],
        "match_count": d["match_count"],
        "mismatch_count": 0,
        "added_count": d["added_count"],
        "missing_count": d["missing_count"],
    }
    if not d["same"]:
        out["added_ids"] = d["added_ids"]
        out["missing_ids"] = d["missing_ids"]
    return out


def _id_compare(base: list[str], other: list[str]) -> dict[str, Any]:
    d = _set_diff(base, other)
    out = {
        "same": d["same"],
        "added_count": d["added_count"],
        "missing_count": d["missing_count"],
    }
    if not d["same"]:
        out["added_ids"] = d["added_ids"]
        out["missing_ids"] = d["missing_ids"]
    return out


def _spans(test: dict[str, Any]) -> list[dict[str, Any]]:
    tr = test.get("trace") if isinstance(test.get("trace"), dict) else {}
    spans = tr.get("spans") if isinstance(tr, dict) else None
    return [s for s in (spans or []) if isinstance(s, dict)]


def _span_op(spans: list[dict[str, Any]], *ops: str) -> list[dict[str, Any]]:
    want = set(ops)
    return [s for s in spans if str(s.get("operation") or "") in want]


def _wall_ms(spans: list[dict[str, Any]]) -> int:
    starts = [_dt(s.get("started_at")) for s in spans]
    ends = [_dt(s.get("ended_at")) for s in spans]
    starts_n = [x for x in starts if x]
    ends_n = [x for x in ends if x]
    if not starts_n:
        return sum(_as_int(s.get("duration_ms")) for s in spans)
    last = max(ends_n) if ends_n else max(starts_n)
    return max(0, int((last - min(starts_n)).total_seconds() * 1000))


def _chat_system(span: dict[str, Any]) -> str:
    pp = span.get("provider_payload")
    if not isinstance(pp, dict):
        return ""
    msgs = pp.get("messages")
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and str(m.get("role") or "") == "system":
                return str(m.get("content") or "")
    if isinstance(pp.get("system"), str):
        return pp["system"]
    return ""


def _classify_chat(span: dict[str, Any]) -> str:
    sysmsg = _chat_system(span)
    if sysmsg.startswith("OBSERVATION_EXTRACT") or "OBSERVATION_EXTRACT" in sysmsg[:80]:
        return "observation_extract"
    if sysmsg.startswith("ASK_RELATIVE") or "ASK_RELATIVE" in sysmsg[:80]:
        return "ask_relative"
    return "narrator"


def _is_timeout(span: dict[str, Any]) -> bool:
    cls = str(span.get("error_class") or "")
    if cls == "PROVIDER_TIMEOUT" or "TIMEOUT" in cls:
        return True
    err = span.get("error")
    if isinstance(err, dict) and "TIMEOUT" in str(err.get("class") or err.get("error_class") or ""):
        return True
    return False


def _timeout_events(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One event per timed-out extract chunk or Ask-relative call (no chat+named double count)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in spans:
        if not _is_timeout(s):
            continue
        op = str(s.get("operation") or "")
        if op == "chat" and _classify_chat(s) == "observation_extract":
            continue
        ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
        chunk = ac.get("chunk")
        key = f"{op}:{chunk}:{s.get('span_id')}"
        if key in seen:
            continue
        seen.add(key)
        err = s.get("error") if isinstance(s.get("error"), dict) else {}
        out.append(
            {
                "operation": op,
                "chunk": chunk,
                "duration_ms": s.get("duration_ms"),
                "error_class": s.get("error_class") or err.get("class") or err.get("error_class"),
                "message": (str(err.get("message") or err.get("exception_message") or "")[:240] or None),
            }
        )
    return out


def _timeout_count(test: dict[str, Any], spans: list[dict[str, Any]]) -> int:
    m = test.get("metrics") if isinstance(test.get("metrics"), dict) else {}
    inf = test.get("inference_accounting") if isinstance(test.get("inference_accounting"), dict) else {}
    events = _timeout_events(spans)
    return max(
        _as_int(m.get("extract_timeouts")),
        _as_int(inf.get("extract_timeouts")),
        len(events),
    )


def _error_classes(test: dict[str, Any], spans: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    top = test.get("error_class")
    if top:
        found.append(str(top))
    tr = test.get("trace") if isinstance(test.get("trace"), dict) else {}
    if tr.get("error_class"):
        found.append(str(tr.get("error_class")))
    for s in spans:
        cls = s.get("error_class")
        if cls:
            found.append(str(cls))
        err = s.get("error")
        if isinstance(err, dict):
            c = err.get("class") or err.get("error_class")
            if c:
                found.append(str(c))
    # Preserve order, unique.
    out: list[str] = []
    for c in found:
        if c and c not in out:
            out.append(c)
    return out


def _preagg(test: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    for s in _span_op(spans, "preaggregation"):
        for key in ("assembled_context", "parsed"):
            blob = s.get(key)
            if isinstance(blob, dict) and ("raw_eligible" in blob or "sms_raw" in blob):
                return blob
    m = test.get("metrics") if isinstance(test.get("metrics"), dict) else {}
    return {
        k: m.get(k)
        for k in (
            "raw_eligible_evidence",
            "sms_raw",
            "raw_comm_items",
            "email_thread_units",
            "sms_segment_units",
            "eligible_evidence_ids",
            "sms_evidence_ids",
            "semantic_unit_fingerprints",
        )
        if k in m
    }


def _request_context(test: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    rc = test.get("request_context")
    if isinstance(rc, dict) and rc:
        return rc
    for s in spans:
        ac = s.get("assembled_context")
        if not isinstance(ac, dict):
            continue
        if isinstance(ac.get("request_context"), dict):
            return ac["request_context"]
        if "focal_subject_person_ids" in ac or "requestor_person_id" in ac:
            return ac
    return {}


def _person_name(rc: dict[str, Any], spans: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    focals = rc.get("focal_subject_person_ids") or rc.get("focal_person_ids") or []
    pid = str(focals[0]) if focals else None
    name = rc.get("focal_subject_name") or rc.get("focal_person_name")
    if not name:
        names = rc.get("focal_subject_names") or rc.get("person_names") or []
        if isinstance(names, list) and names:
            name = str(names[0])
    if not name:
        for s in _span_op(spans, "plan_ask", "plan_ask_resolved"):
            ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
            plan = ac.get("plan") if isinstance(ac.get("plan"), dict) else ac
            pn = (plan.get("person_names") if isinstance(plan, dict) else None) or []
            if pn:
                name = str(pn[0])
            pids = (plan.get("person_ids") if isinstance(plan, dict) else None) or []
            if pids and not pid:
                pid = str(pids[0])
            disp = s.get("disposition") if isinstance(s.get("disposition"), dict) else {}
            if not name and disp.get("person_names"):
                name = str(disp["person_names"][0])
            if not pid and disp.get("person_ids"):
                pid = str(disp["person_ids"][0])
    return (str(name) if name else None, pid)


def _json_load_maybe(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip()[:1] in "{[":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _units_from_extract_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for s in spans:
        op = str(s.get("operation") or "")
        if op not in {"observation_extract", "chat"}:
            continue
        payloads: list[Any] = []
        pp = s.get("provider_payload")
        if isinstance(pp, dict):
            payloads.append(pp.get("user"))
            msgs = pp.get("messages")
            if isinstance(msgs, list):
                for m in msgs:
                    if isinstance(m, dict) and str(m.get("role") or "") == "user":
                        payloads.append(_json_load_maybe(m.get("content")))
        ac = s.get("assembled_context")
        if isinstance(ac, dict) and isinstance(ac.get("units"), list):
            payloads.append(ac)
        for blob in payloads:
            body = _json_load_maybe(blob)
            if not isinstance(body, dict):
                continue
            rows = body.get("units")
            if not isinstance(rows, list):
                continue
            for u in rows:
                if isinstance(u, dict):
                    units.append(u)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for u in units:
        key = str(u.get("unit_id") or u.get("evidence_id") or json.dumps(u.get("date_span"), default=str))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(u)
    return deduped


def _slim_unit_stats(units: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    msg_counts: list[int] = []
    spans_days: list[int] = []
    longest: list[dict[str, Any]] = []
    buckets = Counter()
    for u in units:
        if not isinstance(u, dict):
            continue
        kind = str(u.get("kind") or u.get("source_type") or "")
        if kind not in {
            "sms_segment",
            "communication_thread",
            "communication",
            "sms",
            "email",
        } and u.get("source_type") not in {"sms", "email"}:
            # Still count semantic extract units that carry messages.
            if not (u.get("messages") or u.get("message_n") or u.get("date_span")):
                continue
        msgs = u.get("messages") if isinstance(u.get("messages"), list) else []
        n = _as_int(u.get("message_n"), default=len(msgs) if msgs else _as_int(u.get("occurrence_count")))
        if n:
            msg_counts.append(n)
        ds = u.get("date_span") if isinstance(u.get("date_span"), dict) else {}
        start = ds.get("start") or u.get("time")
        end = ds.get("end") or start
        days = _span_days(start, end)
        if days is None:
            days = 0 if start else None
        if days is not None:
            spans_days.append(days)
            if days <= 1:
                buckets["leq_1_day"] += 1
            elif days <= 7:
                buckets["days_2_to_7"] += 1
            elif days <= 30:
                buckets["days_8_to_30"] += 1
            elif days <= 90:
                buckets["days_31_to_90"] += 1
            elif days <= 365:
                buckets["days_91_to_365"] += 1
            else:
                buckets["days_over_365"] += 1
        conv = (
            u.get("thread_id")
            or u.get("conversation")
            or u.get("subject")
            or (msgs[0].get("conversation") if msgs and isinstance(msgs[0], dict) else None)
            or u.get("unit_id")
        )
        longest.append(
            {
                "conversation_or_thread_name": str(conv) if conv else None,
                "start_date": _day(start),
                "end_date": _day(end),
                "span_days": days,
                "message_count": n,
                "kind": kind or u.get("source_type"),
            }
        )
    uniq: list[dict[str, Any]] = []
    seen_l: set[tuple[Any, ...]] = set()
    for row in longest:
        key = (
            row.get("conversation_or_thread_name"),
            row.get("start_date"),
            row.get("end_date"),
            row.get("span_days"),
            row.get("message_count"),
        )
        if key in seen_l:
            continue
        seen_l.add(key)
        uniq.append(row)
    uniq.sort(key=lambda r: (_as_int(r.get("span_days")), _as_int(r.get("message_count"))), reverse=True)
    longest = uniq
    stats = {
        "messages_per_semantic_unit": _dist(msg_counts),
        "span_day_buckets": {
            "leq_1_day": int(buckets.get("leq_1_day") or 0),
            "days_2_to_7": int(buckets.get("days_2_to_7") or 0),
            "days_8_to_30": int(buckets.get("days_8_to_30") or 0),
            "days_31_to_90": int(buckets.get("days_31_to_90") or 0),
            "days_91_to_365": int(buckets.get("days_91_to_365") or 0),
            "days_over_365": int(buckets.get("days_over_365") or 0),
            "units_with_span": len(spans_days),
        },
        "longest_span_semantic_units": longest[:10],
    }
    return stats, longest[:10]


def _extract_call_stats(test: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    payloads = []
    m = test.get("metrics") if isinstance(test.get("metrics"), dict) else {}
    pd = test.get("peggy_diagnostics") if isinstance(test.get("peggy_diagnostics"), dict) else {}
    inf = test.get("inference_accounting") if isinstance(test.get("inference_accounting"), dict) else {}
    raw = _first(m.get("extract_payloads"), pd.get("extract_payloads"), inf.get("extract_payloads"))
    if isinstance(raw, list):
        payloads = [p for p in raw if isinstance(p, dict)]
    bytes_l = [_as_float(p.get("payload_bytes")) for p in payloads]
    tok_l = [_as_float(p.get("approx_tokens")) for p in payloads]
    durs: list[float] = []
    for s in spans:
        op = str(s.get("operation") or "")
        if op == "observation_extract":
            ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
            if ac.get("cache_hit") or ac.get("deferred"):
                continue
            d = _as_float(s.get("duration_ms"))
            if d:
                durs.append(d)
        elif op == "chat" and _classify_chat(s) == "observation_extract":
            d = _as_float(s.get("duration_ms"))
            if d is not None:
                durs.append(d)
    return {
        "payload_bytes": _dist([x for x in bytes_l if x is not None]),
        "approx_tokens": _dist([x for x in tok_l if x is not None]),
        "model_call_duration_ms": _dist(durs),
        "extract_payload_records": len(payloads),
    }


def _rollups_from_test(test: dict[str, Any], spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for s in spans:
        op = str(s.get("operation") or "")
        parsed = s.get("parsed")
        ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
        pp = s.get("provider_payload") if isinstance(s.get("provider_payload"), dict) else {}
        user = _json_load_maybe(pp.get("user"))
        if op in {"ask_relative", "ask_relative_payload"} and isinstance(user, dict):
            rus = user.get("rollups")
            if isinstance(rus, list):
                found.extend(r for r in rus if isinstance(r, dict))
        if op == "chat" and _classify_chat(s) == "ask_relative":
            for m in pp.get("messages") or []:
                if isinstance(m, dict) and m.get("role") == "user":
                    body = _json_load_maybe(m.get("content"))
                    if isinstance(body, dict) and isinstance(body.get("rollups"), list):
                        found.extend(r for r in body["rollups"] if isinstance(r, dict))
        if isinstance(parsed, dict) and isinstance(parsed.get("rollups"), list):
            found.extend(r for r in parsed["rollups"] if isinstance(r, dict))
        if isinstance(ac.get("semantic_rollups"), dict):
            rus = ac["semantic_rollups"].get("rollups")
            if isinstance(rus, list):
                found.extend(r for r in rus if isinstance(r, dict))
        elif isinstance(ac.get("semantic_rollups"), list):
            found.extend(r for r in ac["semantic_rollups"] if isinstance(r, dict))
        if isinstance(ac.get("rollups"), list):
            found.extend(r for r in ac["rollups"] if isinstance(r, dict))
    # Dedupe by rollup_id / label.
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in found:
        key = str(r.get("rollup_id") or r.get("label") or json.dumps(r, sort_keys=True, default=str)[:120])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _compact_rollup(r: dict[str, Any]) -> dict[str, Any]:
    ds = r.get("date_span") if isinstance(r.get("date_span"), dict) else {}
    eids = r.get("supporting_evidence_ids") if isinstance(r.get("supporting_evidence_ids"), list) else []
    oids = r.get("observation_ids") if isinstance(r.get("observation_ids"), list) else []
    return {
        "text": r.get("label") or r.get("text") or r.get("gist"),
        "kind": r.get("kind") or r.get("category") or r.get("bucket"),
        "start_date": _day(ds.get("start") or r.get("start")),
        "end_date": _day(ds.get("end") or r.get("end")),
        "participant_names": list(r.get("people") or [])[:16],
        "underlying_observation_count": _as_int(r.get("observation_n"), default=len(oids)),
        "underlying_evidence_count": _as_int(r.get("evidence_n"), default=len(eids)),
    }


def _ask_relative_output(spans: list[dict[str, Any]]) -> Any:
    """Complete model output only (small). Do not substitute the Python-expanded view."""
    for s in _span_op(spans, "ask_relative"):
        raw = s.get("raw_response")
        if isinstance(raw, dict) and raw.get("content"):
            return _json_load_maybe(raw.get("content"))
        if isinstance(raw, str) and raw.strip():
            return _json_load_maybe(raw)
        if s.get("parsed") not in (None, {}, []):
            return s.get("parsed")
    for s in spans:
        if str(s.get("operation") or "") == "chat" and _classify_chat(s) == "ask_relative":
            raw = s.get("raw_response")
            if isinstance(raw, dict) and raw.get("content"):
                return _json_load_maybe(raw.get("content"))
    return None


def _ask_relative_view_counts(spans: list[dict[str, Any]]) -> dict[str, Any]:
    for s in _span_op(spans, "ask_relative_view"):
        parsed = s.get("parsed")
        if not isinstance(parsed, dict):
            continue
        ep_n, th_n, cl_n = _count_view(parsed)
        return {
            "answer_focus": parsed.get("answer_focus"),
            "output_episode_count": ep_n,
            "output_theme_count": th_n,
            "output_claim_count": cl_n,
            "unresolved": parsed.get("unresolved") if isinstance(parsed.get("unresolved"), list) else [],
            "note": "Python-expanded view after model JSON; observation bodies omitted",
        }
    return {}


def _count_view(obj: Any) -> tuple[int, int, int]:
    if not isinstance(obj, dict):
        return 0, 0, 0
    view = obj.get("view") if isinstance(obj.get("view"), dict) else obj
    episodes = view.get("episodes") if isinstance(view.get("episodes"), list) else []
    themes = view.get("themes") if isinstance(view.get("themes"), list) else []
    claims = 0
    for ep in episodes:
        if isinstance(ep, dict) and isinstance(ep.get("claims"), list):
            claims += len(ep["claims"])
    if not claims and isinstance(view.get("claims"), list):
        claims = len(view["claims"])
    return len(episodes), len(themes), claims


def _rejected_ask_relative(spans: list[dict[str, Any]], test: dict[str, Any]) -> int:
    n = 0
    for s in _span_op(spans, "validate"):
        val = s.get("validation") if isinstance(s.get("validation"), dict) else {}
        rej = val.get("rejected")
        if isinstance(rej, list):
            n = max(n, len(rej))
    inf = test.get("inference_accounting") if isinstance(test.get("inference_accounting"), dict) else {}
    if isinstance(inf.get("rejected"), list):
        n = max(n, len(inf["rejected"]))
    return n


def _stage_timing(test: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, int]:
    total = _as_int(test.get("duration_ms") or test.get("wall_duration_ms"))
    retrieve_spans = [
        s
        for s in spans
        if str(s.get("operation") or "") in {"retrieve_progress", "retrieval_resolution", "retrieve", "retrieve_complete"}
        or (str(s.get("stage") or "") == "retrieve" and str(s.get("operation") or "") != "plan_ask")
    ]
    # Heartbeats are snapshots; use wall clock of the retrieve phase, not the sum.
    retrieval_ms = _wall_ms(retrieve_spans) if retrieve_spans else 0

    pre = _span_op(spans, "preaggregation")
    preaggregation_ms = sum(_as_int(s.get("duration_ms")) for s in pre) or _wall_ms(pre)

    assim = [
        s
        for s in spans
        if str(s.get("operation") or "") in {"consideration", "evidence_prep", "assimilation"}
        or str(s.get("stage") or "") in {"i11a_consideration", "assimilation"}
    ]
    assimilation_ms = sum(_as_int(s.get("duration_ms")) for s in assim) or _wall_ms(assim)

    extract_chat = [
        s
        for s in spans
        if str(s.get("operation") or "") == "chat" and _classify_chat(s) == "observation_extract"
    ]
    extract_named = _span_op(spans, "observation_extract")
    observation_extract_ms = sum(_as_int(s.get("duration_ms")) for s in extract_chat)
    if not observation_extract_ms:
        observation_extract_ms = sum(
            _as_int(s.get("duration_ms"))
            for s in extract_named
            if not (
                isinstance(s.get("assembled_context"), dict)
                and (s["assembled_context"].get("cache_hit") or s["assembled_context"].get("deferred"))
            )
        )

    ru = _span_op(spans, "semantic_rollup")
    rollup_ms = sum(_as_int(s.get("duration_ms")) for s in ru) or _wall_ms(ru)

    ask_named = _span_op(spans, "ask_relative")
    ask_chat = [
        s for s in spans if str(s.get("operation") or "") == "chat" and _classify_chat(s) == "ask_relative"
    ]
    ask_relative_ms = max(
        sum(_as_int(s.get("duration_ms")) for s in ask_named),
        sum(_as_int(s.get("duration_ms")) for s in ask_chat),
    )

    nar_chat = [
        s for s in spans if str(s.get("operation") or "") == "chat" and _classify_chat(s) == "narrator"
    ]
    narrator_ms = sum(_as_int(s.get("duration_ms")) for s in nar_chat)

    accounted = (
        retrieval_ms
        + assimilation_ms
        + preaggregation_ms
        + observation_extract_ms
        + rollup_ms
        + ask_relative_ms
        + narrator_ms
    )
    other_ms = total - accounted
    if other_ms < 0:
        # Overlap between named ask_relative span and chat span already handled via max().
        # Remaining negative usually means retrieve wall-clock overlaps later stages.
        other_ms = 0
    return {
        "retrieval_ms": retrieval_ms,
        "assimilation_ms": assimilation_ms,
        "preaggregation_ms": preaggregation_ms,
        "observation_extract_ms": observation_extract_ms,
        "rollup_ms": rollup_ms,
        "ask_relative_ms": ask_relative_ms,
        "narrator_ms": narrator_ms,
        "other_ms": other_ms,
        "total_ms": total,
        "accounted_ms": accounted,
    }


def _retrieval_block(test: dict[str, Any], spans: list[dict[str, Any]], pre: dict[str, Any]) -> dict[str, Any]:
    rc = _request_context(test, spans)
    name, pid = _person_name(rc, spans)
    ev = test.get("evidence_considered") if isinstance(test.get("evidence_considered"), dict) else {}
    cov = ev.get("coverage") if isinstance(ev.get("coverage"), dict) else {}
    vol = ev.get("narrative_pack_volume") if isinstance(ev.get("narrative_pack_volume"), dict) else {}
    m = test.get("metrics") if isinstance(test.get("metrics"), dict) else {}
    pages = len(_span_op(spans, "retrieve_progress"))
    retrieve_spans = [
        s
        for s in spans
        if str(s.get("stage") or "") == "retrieve"
        or str(s.get("operation") or "") in {"retrieval_resolution", "retrieve_progress"}
    ]
    incomplete = cov.get("incomplete")
    if incomplete is None:
        incomplete = bool(cov.get("truncated"))
    scope = rc.get("retrieval_scope") or rc.get("scope")
    if not scope:
        plan_names = []
        for s in _span_op(spans, "plan_ask", "plan_ask_resolved"):
            ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
            plan = ac.get("plan") if isinstance(ac.get("plan"), dict) else {}
            if plan:
                scope = {
                    "person_ids": plan.get("person_ids"),
                    "person_names": plan.get("person_names"),
                    "time_start": plan.get("time_start"),
                    "time_end": plan.get("time_end"),
                    "want_communication": plan.get("want_communication"),
                    "modalities": plan.get("modalities"),
                }
                plan_names = plan.get("person_names") or []
                break
        if not name and plan_names:
            name = str(plan_names[0])
    return {
        "focal_person_name": name,
        "canonical_person_id": pid,
        "requestor_person_id": rc.get("requestor_person_id"),
        "retrieval_scope": scope,
        "raw_eligible_evidence_count": _first(
            pre.get("raw_eligible"), m.get("raw_eligible_evidence"), vol.get("eligible_n"), m.get("eligible_evidence_id_n")
        ),
        "counts_by_modality": {
            "photo": _first(pre.get("photos_raw"), ev.get("photo")),
            "video_asset": _first(pre.get("video_assets_raw"), ev.get("video")),
            "video_moment": pre.get("video_moments_raw"),
            "sms": _first(pre.get("sms_raw"), m.get("sms_raw")),
            "email": pre.get("email_raw"),
            "calendar": pre.get("calendar_event_count"),
            "travel": pre.get("travel_units"),
            "artifact": _first(pre.get("artifacts"), ev.get("artifact")),
            "audio": _first(pre.get("spoken_moments_raw"), pre.get("audio_raw")),
        },
        "total_raw_communication_items": _first(pre.get("raw_comm_items"), m.get("raw_comm_items")),
        "retrieval_pages_or_calls": pages,
        "retrieval_duration_ms": _wall_ms(retrieve_spans) if retrieve_spans else None,
        "retrieval_completeness_flag": {
            "incomplete": incomplete,
            "truncated": cov.get("truncated"),
            "missing": cov.get("missing"),
        },
    }


def _build_run(test: dict[str, Any], cold: dict[str, Any] | None) -> dict[str, Any]:
    spans = _spans(test)
    m = test.get("metrics") if isinstance(test.get("metrics"), dict) else {}
    pd = test.get("peggy_diagnostics") if isinstance(test.get("peggy_diagnostics"), dict) else {}
    inf = test.get("inference_accounting") if isinstance(test.get("inference_accounting"), dict) else {}
    pre = _preagg(test, spans)
    errors = _error_classes(test, spans)
    extract_calls = _as_int(
        _first(m.get("observation_extract_calls"), inf.get("extract_calls"), pd.get("extract_calls"))
    )
    # Count actual model extract chats even if metrics say 0.
    extract_chats = [
        s for s in spans if str(s.get("operation") or "") == "chat" and _classify_chat(s) == "observation_extract"
    ]
    named_extract_llm = []
    for s in _span_op(spans, "observation_extract"):
        ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
        if ac.get("cache_hit") or ac.get("deferred"):
            continue
        if s.get("provider_payload") or _as_int(s.get("duration_ms")) > 5:
            named_extract_llm.append(s)
    extract_model_calls = max(extract_calls, len(extract_chats), len(named_extract_llm))
    span_hits = span_miss = span_defer = 0
    for s in _span_op(spans, "observation_extract"):
        ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
        if ac.get("cache_hit"):
            span_hits += 1
        if ac.get("deferred"):
            span_defer += 1
        if ac.get("cache_hit") is False or (not ac.get("cache_hit") and not ac.get("deferred") and s.get("provider_payload")):
            span_miss += 1
    cons_acc = {}
    for s in _span_op(spans, "consideration"):
        ac = s.get("assembled_context") if isinstance(s.get("assembled_context"), dict) else {}
        if isinstance(ac.get("accounting"), dict):
            cons_acc = ac["accounting"]
            break

    units = _units_from_extract_spans(spans)
    unit_stats, _ = _slim_unit_stats(units)
    extract_stats = _extract_call_stats(test, spans)
    rollups = _rollups_from_test(test, spans)
    kinds = Counter(str(r.get("kind") or r.get("category") or "unknown") for r in rollups)
    obs_represented = 0
    for r in rollups:
        oids = r.get("observation_ids") if isinstance(r.get("observation_ids"), list) else []
        obs_represented += _as_int(r.get("observation_n"), default=len(oids))

    ask_invoked = bool(
        _span_op(spans, "ask_relative")
        or _as_int(_first(m.get("ask_relative_calls"), inf.get("ask_relative_calls")))
    )
    ask_out = _ask_relative_output(spans) if ask_invoked else None
    view_counts = _ask_relative_view_counts(spans)
    ep_n = view_counts.get("output_episode_count") or 0
    th_n = view_counts.get("output_theme_count") or 0
    cl_n = view_counts.get("output_claim_count") or 0
    if not (ep_n or th_n or cl_n):
        ep_n, th_n, cl_n = _count_view(ask_out)
    ask_payload = _first(m.get("ask_relative_payload"), inf.get("ask_relative_payload"), pd.get("ask_relative_payload"))
    if not isinstance(ask_payload, dict):
        ask_payload = {}
        for s in _span_op(spans, "ask_relative_payload", "ask_relative"):
            ac = s.get("assembled_context")
            if isinstance(ac, dict) and ("payload_bytes" in ac or "approx_tokens" in ac):
                ask_payload = ac
                break

    ask_spans = _span_op(spans, "ask_relative")
    ask_status = None
    ask_err = None
    if ask_spans:
        ask_status = ask_spans[-1].get("status")
        ask_err = ask_spans[-1].get("error_class")
        if not ask_err:
            err = ask_spans[-1].get("error")
            if isinstance(err, dict):
                ask_err = err.get("error_class") or err.get("class")

    nar_chats = [
        s for s in spans if str(s.get("operation") or "") == "chat" and _classify_chat(s) == "narrator"
    ]
    nar_invoked = bool(nar_chats) or _as_int(m.get("narrator_calls")) > 0
    nar_status = nar_chats[-1].get("status") if nar_chats else None
    nar_err = nar_chats[-1].get("error_class") if nar_chats else None
    nar_bytes = None
    nar_tokens = None
    if nar_chats:
        pp = nar_chats[-1].get("provider_payload") if isinstance(nar_chats[-1].get("provider_payload"), dict) else {}
        try:
            raw = json.dumps(pp, default=str)
            nar_bytes = len(raw.encode("utf-8"))
            nar_tokens = max(1, nar_bytes // 4)
        except Exception:
            pass

    stages = _stage_timing(test, spans)
    eligible_ids = _ids(_first(m.get("eligible_evidence_ids"), pre.get("eligible_evidence_ids")))
    sms_ids = _ids(_first(m.get("sms_evidence_ids"), pre.get("sms_evidence_ids")))
    fps = _ids(_first(m.get("semantic_unit_fingerprints"), pre.get("semantic_unit_fingerprints")))

    det: dict[str, Any] | None = None
    if cold is not None:
        det = {
            "compared_to_run_index": cold.get("index"),
            "same_raw_eligible_evidence_ids": None,
            "same_sms_evidence_ids": None,
        }
        c_el = cold.get("_eligible_ids") or []
        c_sms = cold.get("_sms_ids") or []
        c_fp = cold.get("_fps") or []
        el = _id_compare(c_el, eligible_ids)
        sm = _id_compare(c_sms, sms_ids)
        fp = _fp_compare(c_fp, fps)
        det.update(
            {
                "same_raw_eligible_evidence_ids": el["same"] if (c_el or eligible_ids) else None,
                "same_sms_evidence_ids": sm["same"] if (c_sms or sms_ids) else None,
                "raw_eligible_added_count": el["added_count"],
                "raw_eligible_missing_count": el["missing_count"],
                "sms_added_count": sm["added_count"],
                "sms_missing_count": sm["missing_count"],
                "semantic_unit_fingerprint_match_count": fp["match_count"],
                "semantic_unit_fingerprint_mismatch_count": fp["mismatch_count"],
                "semantic_unit_fingerprint_added_count": fp["added_count"],
                "semantic_unit_fingerprint_missing_count": fp["missing_count"],
            }
        )
        if not el["same"]:
            det["raw_eligible_added_ids"] = el.get("added_ids") or []
            det["raw_eligible_missing_ids"] = el.get("missing_ids") or []
        if not sm["same"]:
            det["sms_added_ids"] = sm.get("added_ids") or []
            det["sms_missing_ids"] = sm.get("missing_ids") or []
        if not fp["same"]:
            det["semantic_unit_fingerprint_added_ids"] = fp.get("added_ids") or []
            det["semantic_unit_fingerprint_missing_ids"] = fp.get("missing_ids") or []

    persisted = _first(
        m.get("persisted_observations"),
        inf.get("persisted_observations"),
        pd.get("persisted_observations"),
        m.get("validated_observations"),
        inf.get("validated_observations"),
    )
    return {
        "index": test.get("index"),
        "pass_kind": test.get("pass_kind") or test.get("inference_stage"),
        "inference_stage": test.get("inference_stage"),
        "ask_text": test.get("ask"),
        "trace_id": test.get("trace_id"),
        "started_at": test.get("started_at"),
        "ended_at": test.get("ended_at"),
        "total_duration_ms": _as_int(test.get("duration_ms") or test.get("wall_duration_ms")),
        "status": test.get("status"),
        "error_class": test.get("error_class"),
        "error_classes_including_spans": errors,
        "total_model_calls": _as_int(_first(test.get("model_call_count"), m.get("total_model_calls"))),
        "timeout_count": _timeout_count(test, spans),
        "timeout_events": _timeout_events(spans),
        "retrieval": _retrieval_block(test, spans, pre),
        "determinism_vs_cold": det,
        "preaggregation_enrichment": {
            "preaggregation_duration_ms": stages["preaggregation_ms"],
            "normalized_eligible_evidence_count": _first(pre.get("normalized"), m.get("raw_eligible_evidence")),
            "deterministic_unit_count": _first(
                pre.get("deterministic_units"), m.get("a_deterministic_units")
            ),
            "semantic_unit_count": _first(pre.get("extract_units"), m.get("b_semantic_units")),
            "sms_semantic_unit_count": _first(
                pre.get("sms_segment_units"), m.get("sms_segment_units"), pd.get("sms_segment_units")
            ),
            "email_thread_unit_count": _first(pre.get("email_thread_units"), m.get("email_thread_units")),
            "observation_extract_calls": extract_model_calls,
            "extraction_cache_hits": max(
                _as_int(m.get("extract_cache_hits")),
                _as_int(inf.get("extract_cache_hits")),
                _as_int(pd.get("extract_cache_hits")),
                _as_int(cons_acc.get("extract_cache_hits")),
                span_hits,
            ),
            "extraction_cache_misses": max(
                _as_int(m.get("extract_cache_misses")),
                _as_int(inf.get("extract_cache_misses")),
                _as_int(pd.get("extract_cache_misses")),
                _as_int(cons_acc.get("extract_cache_misses")),
                span_miss,
            ),
            "enrichment_deferred_units": max(
                _as_int(m.get("enrichment_deferred")),
                _as_int(inf.get("enrichment_deferred")),
                _as_int(cons_acc.get("enrichment_deferred")),
                span_defer,
            ),
            "extract_timeout_count": _first(m.get("extract_timeouts"), inf.get("extract_timeouts"), pd.get("extract_timeouts"), cons_acc.get("extract_timeouts")),
            "persisted_observation_count": persisted,
            "accepted_model_derived_observation_count": _first(
                m.get("model_derived_observations"), inf.get("observations_b")
            ),
            "rejected_observation_count": _first(
                m.get("extract_observations_rejected"), inf.get("extract_observations_rejected")
            ),
            "provenance_coverage": _first(pre.get("provenance_coverage"), m.get("provenance_coverage")),
            "extraction_aggregates": {**unit_stats, **extract_stats},
        },
        "persisted_semantic_representation": {
            "total_persisted_observations_available_to_warm_ask": persisted,
            "deterministic_observations_available": _first(
                m.get("deterministic_observations"), inf.get("observations_a")
            ),
            "model_derived_observations_available": _first(
                m.get("model_derived_observations"), inf.get("observations_b")
            ),
            "rollup_count": _first(m.get("rollup_units"), inf.get("rollup_units"), len(rollups)),
            "rollup_generation_duration_ms": stages["rollup_ms"],
            "rollups_by_kind": dict(kinds),
            "lower_level_observations_represented_by_rollups": obs_represented or None,
            "provenance_coverage_rollup_to_observation_to_raw": _first(
                m.get("rollup_provenance_coverage"), inf.get("rollup_provenance_coverage")
            ),
            "representative_rollups": [_compact_rollup(r) for r in rollups[:ROLLUP_SAMPLE]],
        },
        "ask_relative": {
            "invoked": ask_invoked,
            "call_count": _as_int(_first(m.get("ask_relative_calls"), inf.get("ask_relative_calls"), 1 if ask_invoked else 0)),
            "payload_bytes": ask_payload.get("payload_bytes"),
            "approximate_input_tokens": _first(ask_payload.get("approx_tokens"), ask_payload.get("prompt_tokens")),
            "observation_count_in_payload": ask_payload.get("observation_n"),
            "rollup_count_in_payload": ask_payload.get("rollup_n"),
            "duration_ms": stages["ask_relative_ms"],
            "timeout_seconds": ask_payload.get("timeout_seconds"),
            "status": ask_status,
            "error_class": ask_err,
            "output_episode_count": ep_n,
            "output_theme_count": th_n,
            "output_claim_count": cl_n,
            "rejected_ask_relative_claims_count": _rejected_ask_relative(spans, test),
            "python_expanded_view": view_counts or None,
            "model_output": ask_out,
            "provider_eval": ask_payload.get("provider_eval"),
        },
        "narrator": {
            "invoked": nar_invoked,
            "duration_ms": stages["narrator_ms"],
            "input_bytes": nar_bytes,
            "approximate_input_tokens": nar_tokens,
            "status": nar_status,
            "error_class": nar_err,
            "final_answer_text": test.get("curator_response"),
        },
        "stage_timing": {
            "retrieval_ms": stages["retrieval_ms"],
            "assimilation_ms": stages["assimilation_ms"],
            "preaggregation_ms": stages["preaggregation_ms"],
            "observation_extract_ms": stages["observation_extract_ms"],
            "rollup_ms": stages["rollup_ms"],
            "ask_relative_ms": stages["ask_relative_ms"],
            "narrator_ms": stages["narrator_ms"],
            "other_ms": stages["other_ms"],
            "total_ms": stages["total_ms"],
        },
        "_eligible_ids": eligible_ids,
        "_sms_ids": sms_ids,
        "_fps": fps,
        "_extract_calls": extract_model_calls,
        "_obs_digest": m.get("validated_observation_digest"),
        "_el_digest": m.get("eligible_evidence_id_digest"),
        "_fp_digest": m.get("semantic_unit_fingerprint_digest"),
        "_ask_payload_bytes": ask_payload.get("payload_bytes"),
        "_ask_tokens": ask_payload.get("approx_tokens"),
    }


DROP_SUMMARY_KEYS = {
    "eligible_evidence_ids",
    "sms_evidence_ids",
    "email_evidence_ids",
    "semantic_unit_fingerprints",
    "extract_payloads",
    "sms_windows",
}


def _slim_summary(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in DROP_SUMMARY_KEYS:
                if isinstance(v, list):
                    out[f"{k}_n"] = len(v)
                continue
            out[k] = _slim_summary(v)
        return out
    if isinstance(obj, list):
        if obj and all(isinstance(i, str) for i in obj) and len(obj) > 40:
            return {"_omitted_id_list_n": len(obj)}
        return [_slim_summary(i) for i in obj]
    return obj


def _peggy_tests(data: dict[str, Any]) -> list[dict[str, Any]]:
    tests = [t for t in (data.get("tests") or []) if isinstance(t, dict)]
    peggy = [t for t in tests if "peggy" in str(t.get("ask") or "").lower()]
    return peggy or tests


def build_summary(data: dict[str, Any], *, source_path: Path, source_bytes: int) -> dict[str, Any]:
    tests = _peggy_tests(data)
    built: list[dict[str, Any]] = []
    cold_ref: dict[str, Any] | None = None
    for t in tests:
        kind = str(t.get("pass_kind") or t.get("inference_stage") or "")
        run = _build_run(t, cold_ref)
        built.append(run)
        if cold_ref is None and kind in {"cold_enrichment", "enrich"}:
            cold_ref = run
        elif cold_ref is None and len(built) == 1:
            cold_ref = run

    # Strip private comparison arrays from emitted runs.
    public_runs = []
    for r in built:
        pub = {k: v for k, v in r.items() if not k.startswith("_")}
        public_runs.append(pub)

    cold = next((r for r in built if str(r.get("pass_kind") or "") in {"cold_enrichment", "enrich"}), built[0] if built else None)
    warms = [r for r in built if str(r.get("pass_kind") or "") in {"warm_ask", "ask"}]
    if not warms and len(built) > 1:
        warms = built[1:]

    retrieval_stable = True
    fp_stable = True
    zero_extract = True
    obs_stable = True
    ask_payload_stable = True
    for w in warms:
        det = w.get("determinism_vs_cold") or {}
        if det.get("same_raw_eligible_evidence_ids") is False:
            retrieval_stable = False
        if (det.get("semantic_unit_fingerprint_added_count") or 0) or (
            det.get("semantic_unit_fingerprint_missing_count") or 0
        ):
            fp_stable = False
        if _as_int(w.get("_extract_calls")) != 0:
            zero_extract = False
        if cold and w.get("_obs_digest") and cold.get("_obs_digest") and w.get("_obs_digest") != cold.get("_obs_digest"):
            obs_stable = False
        if len(warms) >= 2:
            if w.get("_ask_payload_bytes") != warms[0].get("_ask_payload_bytes"):
                ask_payload_stable = False
            if w.get("_ask_tokens") != warms[0].get("_ask_tokens"):
                ask_payload_stable = False

    if len(warms) >= 2:
        if warms[0].get("_el_digest") and warms[1].get("_el_digest"):
            if warms[0]["_el_digest"] != warms[1]["_el_digest"]:
                retrieval_stable = False
        if warms[0].get("_fp_digest") and warms[1].get("_fp_digest"):
            if warms[0]["_fp_digest"] != warms[1]["_fp_digest"]:
                fp_stable = False

    runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    comparison = {
        "retrieval_stable": retrieval_stable,
        "semantic_unit_fingerprints_stable": fp_stable,
        "warm_runs_used_zero_observation_extract_calls": zero_extract and all(
            _as_int(w.get("_extract_calls")) == 0 for w in warms
        ),
        "persisted_observation_set_stable": obs_stable,
        "ask_relative_payload_stable": ask_payload_stable,
        "warm_run_2_completed": bool(len(warms) >= 1 and warms[0].get("status")),
        "warm_run_3_completed": bool(len(warms) >= 2 and warms[1].get("status")),
        "warm_run_duration_ms": [r.get("total_duration_ms") for r in warms],
        "ask_relative_duration_ms": [
            ((r.get("ask_relative") or {}).get("duration_ms")) for r in warms
        ],
        "narrator_duration_ms": [((r.get("narrator") or {}).get("duration_ms")) for r in warms],
        "final_answers": [((r.get("narrator") or {}).get("final_answer_text")) for r in warms],
        "warm_run_statuses": [r.get("status") for r in warms],
        "warm_run_error_classes": [r.get("error_class") for r in warms],
        "warm_extract_calls": [r.get("_extract_calls") for r in warms],
    }
    # warm_run_2/3 naming: enrich-first Peggy is tests [cold, warm1, warm2]
    if len(warms) >= 2:
        comparison["warm_run_2_completed"] = str(warms[0].get("status") or "") in {"ok", "error"}
        comparison["warm_run_3_completed"] = str(warms[1].get("status") or "") in {"ok", "error"}
        comparison["warm_run_2_status"] = warms[0].get("status")
        comparison["warm_run_3_status"] = warms[1].get("status")

    return {
        "generated_at": _now_iso(),
        "source": {
            "path": str(source_path),
            "bytes": source_bytes,
        },
        "model": data.get("model"),
        "runtime": {
            "provider": runtime.get("provider_key") or runtime.get("provider"),
            "model": runtime.get("chat_model") or data.get("model"),
            "base_url": runtime.get("base_url"),
            "health": runtime.get("health"),
        },
        "overall_regression_summary": _slim_summary(data.get("summary")),
        "peggy_runs": public_runs,
        "three_run_comparison": comparison,
    }


def find_source(explicit: Path | None) -> Path:
    if explicit:
        p = explicit.expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"Source not found: {p}")
        return p
    env = (Path.cwd() / "docs/test-output")
    search = [
        Path("/workspace/docs/test-output"),
        env,
        Path(r"C:\memorybox\docs\test-output"),
        Path(r"C:\memorybox"),
        Path("/home/ubuntu/.cursor/projects/workspace/uploads"),
        Path("/tmp"),
        Path.cwd(),
    ]
    # Also search the current directory tree one level for a ~141 MB capture.
    if Path.cwd().is_dir():
        search.append(Path.cwd() / "docs" / "test-output")
    found: list[Path] = []
    for root in search:
        if not root.is_dir():
            continue
        found.extend(root.glob("I11A_regression_*.json"))
        found.extend(root.glob("*i11a*regression*.json"))
        found.extend(root.glob("*Peggy*3Run*.json"))
    # Prefer the largest file (the 141 MB FlightSim capture), skip our own output.
    cands = [p for p in found if p.is_file() and p.name != OUT_NAME]
    if not cands:
        raise FileNotFoundError(
            "No I11A regression JSON found. Pass the 141 MB file path as argv[1]."
        )
    cands.sort(key=lambda p: p.stat().st_size, reverse=True)
    return cands[0]


def console_summary(source: Path, out: Path, payload: dict[str, Any]) -> str:
    runs = payload.get("peggy_runs") or []
    cmp_ = payload.get("three_run_comparison") or {}
    lines = [
        f"source_file_bytes={source.stat().st_size}",
        f"diagnostic_file_bytes={out.stat().st_size}",
    ]
    for i, r in enumerate(runs):
        kind = r.get("pass_kind")
        lines.append(
            f"run[{r.get('index')}] kind={kind} duration_ms={r.get('total_duration_ms')} "
            f"model_calls={r.get('total_model_calls')} extract_calls="
            f"{(r.get('preaggregation_enrichment') or {}).get('observation_extract_calls')} "
            f"status={r.get('status')} error_class={r.get('error_class')} "
            f"timeouts={r.get('timeout_count')}"
        )
    lines.append(f"retrieval_ids_matched={cmp_.get('retrieval_stable')}")
    lines.append(f"semantic_fingerprints_matched={cmp_.get('semantic_unit_fingerprints_stable')}")
    lines.append(
        f"warm_runs_zero_extraction_calls={cmp_.get('warm_runs_used_zero_observation_extract_calls')}"
    )
    lines.append(f"ask_relative_duration_ms={cmp_.get('ask_relative_duration_ms')}")
    lines.append(f"narrator_duration_ms={cmp_.get('narrator_duration_ms')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", nargs="?", type=Path, help="Full I11A regression JSON (≈141 MB)")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=f"Output path (default: next to source as {OUT_NAME})",
    )
    args = ap.parse_args(argv)
    source = find_source(args.source)
    source_bytes = source.stat().st_size
    if source_bytes < 1_000_000:
        print(
            f"WARNING: source {source} is {source_bytes} bytes; expected ~141 MB FlightSim capture.",
            file=sys.stderr,
        )
    print(f"Loading {source} ({source_bytes} bytes)…", flush=True)
    with source.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    payload = build_summary(data, source_path=source, source_bytes=source_bytes)
    out = args.output or source.parent / OUT_NAME
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    # Drop private keys if any leaked.
    parsed = json.loads(text)
    out.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    json.loads(out.read_text(encoding="utf-8"))
    size = out.stat().st_size
    if size > 1_000_000:
        print(f"ERROR: diagnostic {size} bytes exceeds 1 MB cap", flush=True)
        return 1
    print(console_summary(source, out, parsed), flush=True)
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
