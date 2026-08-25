"""Deterministic pre-aggregation of evidence units before I11A model calls.

Pre-aggregation is not sampling. Every underlying evidence/asset ID is retained.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from memorybox.ask.i11a.comm_patterns import communication_pattern_units
from memorybox.ask.i11a.observation_cache import load_observation, save_observation, source_hash
from memorybox.ask.i11a.windows import _day

_BURST_HOURS = 6

METHOD = "media_place_observation"
_GENERIC_PLACES = frozenset(
    {"unplaced", "unspecified", "unknown", "none", "n/a", "unspecified roadside"}
)


def _generic_place(place: str) -> bool:
    p = (place or "").strip().lower()
    if not p or p in _GENERIC_PLACES:
        return True
    return "unspecified" in p
_SMS_GAP_DAYS = 3
_MEDIA_KINDS = frozenset(
    {"media_observation", "video_asset", "video_moment", "spoken_moment"}
)


def _parse_dt(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s[:32])
    except ValueError:
        day = _day(s)
        if day:
            return datetime.fromisoformat(day)
        return None


def _ids(unit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in (
        unit.get("evidence_id"),
        unit.get("asset_ref"),
        unit.get("unit_id"),
        unit.get("source_id"),
    ):
        s = str(key or "").strip()
        if s and s not in out:
            out.append(s)
    prov = unit.get("provenance") if isinstance(unit.get("provenance"), dict) else {}
    for k in ("evidence_id", "external_id", "journal_id", "story_id", "artifact_id"):
        s = str(prov.get(k) or "").strip()
        if s and s not in out:
            out.append(s)
    for extra in unit.get("extra_ids") or []:
        s = str(extra or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _people_key(unit: dict[str, Any]) -> str:
    names: list[str] = []
    for p in unit.get("people") or []:
        if isinstance(p, dict):
            n = str(p.get("person_id") or p.get("name") or "").strip()
        else:
            n = str(p).strip()
        if n:
            names.append(n.lower())
    return "|".join(sorted(set(names))[:8])


def _place_key(unit: dict[str, Any]) -> str:
    place = str(unit.get("place") or unit.get("city") or unit.get("location") or "").strip()
    if place:
        return place.lower()
    lat, lon = unit.get("latitude"), unit.get("longitude")
    media = unit.get("media") if isinstance(unit.get("media"), dict) else {}
    gps = media.get("exif_gps") if isinstance(media.get("exif_gps"), dict) else {}
    try:
        lat_f = float(lat if lat is not None else (gps or {}).get("latitude"))
        lon_f = float(lon if lon is not None else (gps or {}).get("longitude"))
        return f"{lat_f:.2f},{lon_f:.2f}"
    except (TypeError, ValueError):
        return "unplaced"


def _dedupe_media(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    dup = 0
    for u in rows:
        asset = str(u.get("asset_ref") or u.get("evidence_id") or u.get("unit_id") or "")
        if asset and asset in seen:
            dup += 1
            continue
        if asset:
            seen.add(asset)
        out.append(u)
    return out, dup


def _cluster_media(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: list[tuple[datetime | None, dict[str, Any]]] = []
    for u in rows:
        indexed.append((_parse_dt(u.get("time") or u.get("captured_at") or u.get("capture_time")), u))
    indexed.sort(key=lambda x: x[0] or datetime.min)
    used: set[int] = set()
    clusters: list[dict[str, Any]] = []
    for i, (dt, u) in enumerate(indexed):
        if i in used:
            continue
        group = [u]
        used.add(i)
        place = _place_key(u)
        people = _people_key(u)
        for j in range(i + 1, len(indexed)):
            if j in used:
                continue
            dt2, u2 = indexed[j]
            if _place_key(u2) != place:
                continue
            if people and _people_key(u2) and _people_key(u2) != people:
                continue
            if dt and dt2 and abs((dt2 - dt).total_seconds()) > _BURST_HOURS * 3600:
                if dt2.date() != dt.date():
                    continue
            group.append(u2)
            used.add(j)
        days = sorted(
            d
            for d in (
                _day(x.get("time") or x.get("captured_at") or x.get("capture_time"))
                for x in group
            )
            if d
        )
        eids: list[str] = []
        for x in group:
            for i in _ids(x):
                if i not in eids:
                    eids.append(i)
        first = group[0]
        place_label = str(first.get("place") or first.get("city") or place)
        clusters.append(
            {
                "unit_id": f"mcl-{eids[0] if eids else 'x'}",
                "evidence_id": eids[0] if eids else first.get("unit_id"),
                "kind": "media_cluster",
                "source_type": first.get("source_type") or "photo",
                "time": days[0] if days else first.get("time"),
                "people": first.get("people") or [],
                "place": place_label if place_label != "unplaced" else None,
                "content": (
                    f"{len(group)} media observation(s)"
                    + (f" at {place_label}" if place_label != "unplaced" else "")
                    + (f" from {days[0]} through {days[-1]}" if len(days) > 1 else (f" on {days[0]}" if days else ""))
                )[:240],
                "extra_ids": eids,
                "source_evidence_ids": eids,
                "cluster_n": len(group),
                "asset_ref": first.get("asset_ref") or eids[0] if eids else None,
                "latitude": first.get("latitude"),
                "longitude": first.get("longitude"),
                "captured_at": first.get("captured_at") or first.get("time"),
                "media": first.get("media"),
            }
        )
    return clusters


def _place_history_units(
    clusters: list[dict[str, Any]],
    *,
    person_id: str | None,
) -> list[dict[str, Any]]:
    by_place: dict[str, list[dict[str, Any]]] = {}
    for c in clusters:
        place = str(c.get("place") or "unplaced").strip() or "unplaced"
        if place == "unplaced" or _generic_place(place):
            continue
        by_place.setdefault(place.lower(), []).append(c)
    out: list[dict[str, Any]] = []
    for place, rows in by_place.items():
        eids: list[str] = []
        days: list[str] = []
        for c in rows:
            for i in c.get("source_evidence_ids") or c.get("extra_ids") or []:
                s = str(i)
                if s not in eids:
                    eids.append(s)
            d = _day(c.get("time"))
            if d:
                days.append(d)
        days = sorted(set(days))
        cached = load_observation(
            person_id=person_id, method=METHOD, evidence_ids=eids
        )
        if cached:
            out.append(cached)
            continue
        label = rows[0].get("place") or place
        unit = {
            "unit_id": f"place-{source_hash(eids)[:12]}",
            "evidence_id": eids[0] if eids else f"place-{place}",
            "kind": "place_observation",
            "source_type": "media",
            "time": days[0] if days else None,
            "place": label,
            "people": rows[0].get("people") or [],
            "content": (
                f"Observed at {label} on {len(days)} date(s)"
                + (f" ({days[0]}–{days[-1]})" if days else "")
            )[:400],
            "extra_ids": eids,
            "source_evidence_ids": eids,
            "occurrence_count": len(days),
            "asset_ref": None,
        }
        save_observation(
            person_id=person_id,
            method=METHOD,
            evidence_ids=eids,
            payload=dict(unit),
            uncertainty="gps_or_labeled_place_is_presence_not_residence",
        )
        out.append(unit)
    return out


def _thread_email(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    unthreaded: list[dict[str, Any]] = []
    for u in rows:
        tid = str(u.get("thread_id") or "").strip()
        subj = re_norm_subject(str(u.get("subject") or u.get("content") or ""))
        key = tid or (f"subj:{subj}" if subj else "")
        if not key:
            unthreaded.append(u)
            continue
        buckets.setdefault(key, []).append(u)
    out: list[dict[str, Any]] = []
    for key, group in buckets.items():
        if len(group) == 1:
            row = dict(group[0])
            row.setdefault("extra_ids", _ids(group[0]))
            out.append(row)
            continue
        days = sorted(d for d in (_day(x.get("time")) for x in group) if d)
        eids: list[str] = []
        snippets: list[str] = []
        people: list[Any] = []
        seen_p: set[str] = set()
        for x in group:
            for i in _ids(x):
                if i not in eids:
                    eids.append(i)
            t = str(x.get("content") or x.get("authored_text") or "").strip()
            if t:
                snippets.append(t[:80])
            for p in x.get("people") or []:
                k = str((p.get("name") if isinstance(p, dict) else p) or "")
                if k and k not in seen_p:
                    seen_p.add(k)
                    people.append(p)
        first = group[0]
        subj = str(first.get("subject") or first.get("content") or "thread")[:80]
        out.append(
            {
                "unit_id": f"eth-{eids[0] if eids else key}"[:80],
                "evidence_id": eids[0] if eids else first.get("evidence_id"),
                "kind": "communication_thread",
                "source_type": "email",
                "time": days[0] if days else first.get("time"),
                "people": people[:12],
                "place": first.get("place"),
                "content": (
                    f"Email thread “{subj}” ({len(group)} messages"
                    + (f", {days[0]}–{days[-1]}" if len(days) > 1 else "")
                    + "). "
                    + " · ".join(snippets[:3])
                )[:400],
                "subject": subj,
                "thread_id": first.get("thread_id") or key,
                "extra_ids": eids,
                "source_evidence_ids": eids,
                "occurrence_count": len(group),
                "asset_ref": None,
            }
        )
    out.extend(unthreaded)
    return out


def re_norm_subject(raw: str) -> str:
    s = raw.lower().strip()
    for pfx in ("re:", "fw:", "fwd:"):
        while s.startswith(pfx):
            s = s[len(pfx) :].strip()
    return s[:80]


def _sms_segments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for u in rows:
        tid = str(u.get("thread_id") or "") or "|".join(
            sorted(_people_key(u).split("|"))
        ) or str(u.get("unit_id") or "sms")
        buckets.setdefault(tid, []).append(u)
    out: list[dict[str, Any]] = []
    for tid, group in buckets.items():
        group = sorted(group, key=lambda x: str(x.get("time") or ""))
        current: list[dict[str, Any]] = []
        last_d: datetime | None = None
        segs: list[list[dict[str, Any]]] = []
        for u in group:
            dt = _parse_dt(u.get("time"))
            if current and last_d and dt and (dt - last_d) > timedelta(days=_SMS_GAP_DAYS):
                segs.append(current)
                current = []
            current.append(u)
            last_d = dt or last_d
        if current:
            segs.append(current)
        for seg in segs:
            if len(seg) == 1:
                row = dict(seg[0])
                row.setdefault("extra_ids", _ids(seg[0]))
                out.append(row)
                continue
            days = sorted(d for d in (_day(x.get("time")) for x in seg) if d)
            eids: list[str] = []
            snippets: list[str] = []
            for x in seg:
                for i in _ids(x):
                    if i not in eids:
                        eids.append(i)
                t = str(x.get("content") or x.get("authored_text") or "").strip()
                if t:
                    snippets.append(t[:72])
            first = seg[0]
            out.append(
                {
                    "unit_id": f"sms-{eids[0] if eids else tid}"[:80],
                    "evidence_id": eids[0] if eids else first.get("evidence_id"),
                    "kind": "sms_segment",
                    "source_type": "sms",
                    "time": days[0] if days else first.get("time"),
                    "people": first.get("people") or [],
                    "place": first.get("place"),
                    "content": (
                        f"Text conversation ({len(seg)} messages"
                        + (f", {days[0]}–{days[-1]}" if days else "")
                        + "). "
                        + " · ".join(snippets[:3])
                    )[:400],
                    "thread_id": first.get("thread_id") or tid,
                    "extra_ids": eids,
                    "source_evidence_ids": eids,
                    "occurrence_count": len(seg),
                    "asset_ref": None,
                }
            )
    return out


def _calendar_units(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_title: dict[str, list[dict[str, Any]]] = {}
    for u in rows:
        title = re_norm_subject(str(u.get("title") or u.get("content") or "event"))
        by_title.setdefault(title, []).append(u)
    out: list[dict[str, Any]] = []
    for title, group in by_title.items():
        if len(group) < 3:
            for u in group:
                row = dict(u)
                row.setdefault("extra_ids", _ids(u))
                out.append(row)
            continue
        days = sorted(d for d in (_day(x.get("time")) for x in group) if d)
        eids: list[str] = []
        for x in group:
            for i in _ids(x):
                if i not in eids:
                    eids.append(i)
        first = group[0]
        out.append(
            {
                "unit_id": f"calr-{eids[0] if eids else title}"[:80],
                "evidence_id": eids[0] if eids else first.get("evidence_id"),
                "kind": "calendar_series",
                "source_type": "calendar",
                "time": days[0] if days else first.get("time"),
                "people": first.get("people") or [],
                "place": first.get("place"),
                "content": (
                    f"Recurring calendar item “{title}” ({len(group)} scheduled dates"
                    + (f", {days[0]}–{days[-1]}" if days else "")
                    + ")"
                )[:400],
                "extra_ids": eids,
                "source_evidence_ids": eids,
                "occurrence_count": len(group),
                "title": title,
                "asset_ref": None,
            }
        )
    return out


def _correlate_dinners(
    *,
    calendar: list[dict[str, Any]],
    comms: list[dict[str, Any]],
    media: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    dinner_re = __import__("re").compile(r"(?i)\b(dinner|supper|get[- ]together)\b")
    out: list[dict[str, Any]] = []
    for cal in calendar:
        blob = str(cal.get("content") or cal.get("title") or "")
        if not dinner_re.search(blob):
            continue
        day = _day(cal.get("time"))
        if not day:
            continue
        eids = list(_ids(cal))
        parts = ["calendar"]
        for c in comms:
            cd = _day(c.get("time"))
            if not cd:
                continue
            try:
                delta = abs((datetime.fromisoformat(cd) - datetime.fromisoformat(day)).days)
            except ValueError:
                continue
            if delta > 2:
                continue
            text = str(c.get("content") or "")
            cal_people = set(_people_key(cal).split("|")) - {""}
            comm_people = set(_people_key(c).split("|")) - {""}
            overlap = bool(cal_people & comm_people) if cal_people and comm_people else False
            if dinner_re.search(text) or (cd == day and (overlap or not cal_people)):
                for i in _ids(c):
                    if i not in eids:
                        eids.append(i)
                if "communication" not in parts:
                    parts.append("communication")
        for m in media:
            md = _day(m.get("time") or m.get("captured_at"))
            if md == day:
                for i in m.get("source_evidence_ids") or _ids(m):
                    s = str(i)
                    if s not in eids:
                        eids.append(s)
                if "media" not in parts:
                    parts.append("media")
        if len(parts) < 2:
            continue
        out.append(
            {
                "unit_id": f"corr-dinner-{day}",
                "evidence_id": eids[0] if eids else f"corr-{day}",
                "kind": "correlated_event",
                "source_type": "cross_source",
                "time": day,
                "people": cal.get("people") or [],
                "place": cal.get("place"),
                "content": (
                    f"Shared dinner/get-together candidate on {day} from "
                    + " + ".join(parts)
                    + ". Supporting items need not each name every participant."
                )[:400],
                "extra_ids": eids,
                "source_evidence_ids": eids,
                "correlation_parts": parts,
                "asset_ref": None,
            }
        )
    return out


def preaggregate_pack(
    pack: dict[str, Any] | None,
    *,
    person_id: str | None = None,
) -> dict[str, Any]:
    units = [u for u in (pack or {}).get("units") or [] if isinstance(u, dict)]
    raw_n = len(units)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for u in units:
        by_kind.setdefault(str(u.get("kind") or "other"), []).append(u)

    media_raw = []
    for k in _MEDIA_KINDS:
        media_raw.extend(by_kind.get(k) or [])
    media_deduped, dup_n = _dedupe_media(media_raw)
    media_clusters = _cluster_media(media_deduped)
    place_hist = _place_history_units(media_clusters, person_id=person_id)

    emails = [
        u
        for u in (by_kind.get("communication") or [])
        if str(u.get("source_type") or "") == "email"
    ]
    sms = [
        u
        for u in (by_kind.get("communication") or [])
        if str(u.get("source_type") or "") in {"sms", "imessage", "text", "mms"}
    ]
    other_comm = [
        u
        for u in (by_kind.get("communication") or [])
        if u not in emails and u not in sms
    ]
    email_units = _thread_email(emails)
    sms_units = _sms_segments(sms)
    cal_units = _calendar_units(by_kind.get("calendar") or [])
    travel = list(by_kind.get("travel") or [])
    rest_kinds = [
        k
        for k in by_kind
        if k not in _MEDIA_KINDS and k not in {"communication", "calendar", "travel"}
    ]
    rest: list[dict[str, Any]] = []
    for k in rest_kinds:
        rest.extend(by_kind[k])

    patterns = communication_pattern_units(by_kind.get("communication") or [])
    correlated = _correlate_dinners(
        calendar=cal_units + list(by_kind.get("calendar") or []),
        comms=sms_units + email_units + other_comm,
        media=media_clusters,
    )

    generic_clusters = [
        c
        for c in media_clusters
        if not c.get("place") or _generic_place(str(c.get("place") or ""))
    ]
    inference = (
        list(cal_units)
        + list(travel)
        + list(email_units)
        + list(sms_units)
        + list(other_comm)
        + list(patterns)
        + list(correlated)
        + list(place_hist)
        + list(generic_clusters)
        + list(rest)
    )
    trace = {
        "raw_eligible": raw_n,
        "normalized": raw_n,
        "deduplicated_media": len(media_deduped),
        "duplicate_media_dropped": dup_n,
        "photos_raw": sum(
            1
            for u in media_raw
            if str(u.get("kind") or "") == "media_observation"
            and str(u.get("source_type") or "") != "video"
        ),
        "video_assets_raw": sum(1 for u in media_raw if str(u.get("kind") or "") == "video_asset"),
        "video_moments_raw": sum(1 for u in media_raw if str(u.get("kind") or "") == "video_moment"),
        "spoken_moments_raw": sum(1 for u in media_raw if str(u.get("kind") or "") == "spoken_moment"),
        "email_raw": len(emails),
        "email_thread_units": sum(
            1 for u in email_units if str(u.get("kind") or "") == "communication_thread"
        ),
        "sms_raw": len(sms),
        "sms_segment_units": sum(1 for u in sms_units if str(u.get("kind") or "") == "sms_segment"),
        "calendar_event_count": len(by_kind.get("calendar") or []),
        "calendar_series_units": sum(
            1 for u in cal_units if str(u.get("kind") or "") == "calendar_series"
        ),
        "travel_units": len(travel),
        "media_clusters": len(media_clusters),
        "place_observations": len(place_hist),
        "comm_pattern_units": len(patterns),
        "correlated_event_units": len(correlated),
        "stories": len(by_kind.get("story") or []),
        "journals": len(by_kind.get("journal") or []),
        "artifacts": len(by_kind.get("artifact") or []),
        "inference_units": len(inference),
        "note": "Pre-aggregation retains all source evidence IDs. Not a first-N cap.",
    }
    return {"units": inference, "trace": trace, "patterns": patterns}
