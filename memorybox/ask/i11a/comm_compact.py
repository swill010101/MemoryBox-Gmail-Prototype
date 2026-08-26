"""Prefer richer communication units; coherent extract batches; reject bad model rows.

Not sampling: every source evidence ID stays on a retained unit.
"""
from __future__ import annotations

import json
import re
from typing import Any

from memorybox.ask.i11a.observations import OBSERVATION_KINDS, canonicalize_observation
from memorybox.ask.i11a.windows import _day

_EMPTY_TEXT = frozenset({"", "none", "null", "n/a", "undefined"})
_GENERIC_PLACES = frozenset(
    {"unplaced", "unspecified", "unknown", "none", "n/a", "null", "unspecified roadside"}
)
_REL_STATED = re.compile(
    r"\b(spouse|partner|sibling|brother|sister|child|son|daughter|"
    r"parent|father|mother|family|friend|colleague|uncle|aunt|"
    r"niece|nephew|grandparent|grandchild|husband|wife|married|"
    r"related|kin|cousin)\b",
    re.I,
)

_PRESENCE_STATED = re.compile(
    r"(?i)\b("
    r"i(?:'m| am)\s+(?:in|at|near)|"
    r"we(?:'re| are)\s+(?:in|at|near)|"
    r"arrived\s+(?:in|at)|"
    r"staying\s+(?:in|at)|"
    r"here\s+(?:in|at)|"
    r"currently\s+(?:in|at)|"
    r"visiting\s+"
    r")\b"
)
_TRANSPORT_ONLY = re.compile(
    r"(?i)^\s*("
    r"(?:tom|the user|owner|i)?\s*(?:sent|received|got|has)\s+"
    r"(?:an?\s+)?(?:email|text|sms|imessage|message)s?"
    r"|(?:an?\s+)?email thread (?:exists|was found|is present)"
    r"|(?:there )?(?:is|was) (?:an?\s+)?(?:email|sms|text) "
    r"(?:thread|conversation|message)"
    r"|(?:email|sms|text|message)s? (?:from|to) [\w .'-]+"
    r"|communications? (?:occurred|existed|were exchanged)"
    r")\s*[.!]?\s*$"
)
_PERSONALITY = re.compile(
    r"(?i)\b("
    r"personality|character trait|narciss|"
    r"always there for|tends to|is a (?:kind|loving|generous|anxious|warm|cold) person|"
    r"kind[- ]hearted|warm[- ]hearted"
    r")\b"
)
_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_OBS_STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "were",
        "they",
        "them",
        "their",
        "about",
        "after",
        "before",
        "into",
        "over",
        "also",
        "just",
        "then",
        "when",
        "what",
        "discussed",
        "stated",
        "expressed",
        "mentioned",
        "referenced",
        "planned",
        "said",
        "told",
        "wrote",
        "sent",
        "received",
        "asked",
        "replied",
        "noted",
        "shared",
        "message",
        "messages",
        "email",
        "emails",
        "text",
        "texts",
        "sms",
        "thread",
        "conversation",
        "communication",
        "communications",
        "people",
        "person",
        "someone",
        "together",
        "well",
        "very",
        "some",
        "more",
        "than",
        "only",
        "other",
        "there",
        "here",
        "would",
        "could",
        "should",
        "will",
        "being",
        "doing",
        "made",
        "make",
        "named",
        "called",
        "using",
        "used",
        "appears",
        "appeared",
        "observed",
        "records",
        "recorded",
        "calendar",
        "listing",
        "presence",
        "capture",
        "affectionate",
        "affection",
    }
)
_COMM_KINDS = frozenset(
    {"communication", "communication_thread", "sms_segment"}
)
_HIGHER_KINDS = frozenset(
    {"communication_thread", "sms_segment"}
)
_PATTERN_KIND = "comm_pattern"


def unit_evidence_ids(unit: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    if not isinstance(unit, dict):
        return out
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
    for extra in list(unit.get("extra_ids") or []) + list(unit.get("source_evidence_ids") or []):
        s = str(extra or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _id_set(units: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for u in units:
        ids.update(unit_evidence_ids(u))
    return ids


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


def _blob(unit: dict[str, Any]) -> str:
    parts = [
        unit.get("content"),
        unit.get("authored_text"),
        unit.get("subject"),
        unit.get("title"),
        unit.get("excerpt"),
        unit.get("place"),
        unit.get("time"),
        unit.get("sender_name"),
        unit.get("thread_id"),
    ]
    for m in unit.get("messages") or []:
        if not isinstance(m, dict):
            continue
        parts.extend(
            [
                m.get("sender"),
                m.get("text"),
                m.get("time"),
                m.get("evidence_id"),
                " ".join(str(x) for x in (m.get("recipients") or [])),
            ]
        )
    return " ".join(str(x or "") for x in parts)


def omit_covered_communication_units(
    units: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Drop raw communication rows fully represented by a richer unit.

    Preference: thread > SMS segment > pattern fragments. Correlated events
    stay as A units; they do not swallow a whole thread's remaining meaning.
    """
    higher_ids: set[str] = set()
    pattern_ids: set[str] = set()
    for u in units:
        kind = str(u.get("kind") or "")
        ids = unit_evidence_ids(u)
        if kind in _HIGHER_KINDS:
            higher_ids.update(ids)
        if kind == _PATTERN_KIND:
            pattern_ids.update(ids)
    kept: list[dict[str, Any]] = []
    omitted = 0
    omitted_ids: list[str] = []
    for u in units:
        kind = str(u.get("kind") or "")
        ids = set(unit_evidence_ids(u))
        if kind == "communication" and ids and ids <= higher_ids:
            omitted += 1
            omitted_ids.extend(sorted(ids))
            continue
        if (
            kind == "communication"
            and ids
            and ids <= pattern_ids
            and len(_blob(u).strip()) < 80
        ):
            omitted += 1
            omitted_ids.extend(sorted(ids))
            continue
        kept.append(u)
    retained = _id_set(kept)
    raw_comm = [
        u
        for u in units
        if str(u.get("kind") or "") in _COMM_KINDS
        or str(u.get("source_type") or "") in {"email", "sms", "imessage", "text", "mms"}
    ]
    raw_ids = _id_set(raw_comm)
    covered = raw_ids & retained if raw_ids else set()
    # IDs only on omitted rows must still live on a higher unit in `units`.
    higher_and_pattern = higher_ids | pattern_ids | retained
    return kept, {
        "duplicate_comm_units_omitted_from_extract": omitted,
        "semantic_comm_units_after_dedupe": sum(
            1 for u in kept if str(u.get("kind") or "") in _COMM_KINDS
        ),
        "provenance_ids_raw_comm": len(raw_ids),
        "provenance_ids_retained": len(raw_ids & higher_and_pattern),
        "provenance_coverage": (
            round(len(raw_ids & higher_and_pattern) / len(raw_ids), 4) if raw_ids else 1.0
        ),
        "provenance_gap_ids": sorted(raw_ids - higher_and_pattern)[:40],
        "omitted_but_covered": omitted_ids[:80],
        "covered_n": len(covered),
    }


def _real_thread_id(unit: dict[str, Any]) -> str:
    tid = str(unit.get("thread_id") or "").strip()
    if not tid:
        return ""
    uid = str(unit.get("unit_id") or "").strip()
    eid = str(unit.get("evidence_id") or "").strip()
    if tid in {uid, eid, "email", "sms"}:
        return ""
    return tid


def semantic_group_key(unit: dict[str, Any]) -> str:
    """Batch key: shared thread, else same people+day, else same calendar day.

    Unique per-row keys are forbidden — they create one OBSERVATION_EXTRACT
    call per email.
    """
    tid = _real_thread_id(unit)
    occ = unit.get("occurrence_count")
    try:
        n = int(occ) if occ is not None else 1
    except (TypeError, ValueError):
        n = 1
    msgs = unit.get("messages") if isinstance(unit.get("messages"), list) else []
    if msgs:
        # Already a bounded semantic window — do not regroup by thread into a mega extract.
        return f"window:{unit.get('unit_id') or unit.get('evidence_id') or tid or 'comm'}"
    if tid and n > 1:
        return f"thread:{tid}"
    people = _people_key(unit)
    day = _day(unit.get("time")) or ""
    kind = str(unit.get("kind") or "other")
    src = str(unit.get("source_type") or kind)
    if people and day:
        return f"people-day:{people}:{day}"
    cluster = str(unit.get("pattern_type") or unit.get("topic") or "").strip()
    if cluster and day:
        return f"topic:{cluster}:{day}"
    if day:
        return f"day-src:{src}:{day}"
    if people:
        return f"people:{people}"
    return f"kind:{kind}"


def unit_for_extract_model(unit: dict[str, Any]) -> dict[str, Any]:
    """The OBSERVATION_EXTRACT row. Must match payload_piece_bytes sizing."""
    msgs = unit.get("messages") if isinstance(unit.get("messages"), list) else []
    header = str(unit.get("content") or "").split("\n", 1)[0][:240]
    if msgs:
        header = header or (
            f"{unit.get('kind') or 'communication'} ({len(msgs)} attributed messages)"
        )
    row = {
        "unit_id": unit.get("unit_id"),
        "evidence_id": unit.get("evidence_id"),
        "kind": unit.get("kind"),
        "source_type": unit.get("source_type"),
        "time": _day(unit.get("time")) or str(unit.get("time") or "")[:10],
        "people": unit.get("people") or [],
        "place": unit.get("place"),
        "content": header if msgs else str(unit.get("content") or "")[:1200],
        "asset_ref": unit.get("asset_ref"),
        "extra_ids": list(unit.get("extra_ids") or unit.get("source_evidence_ids") or []),
        "source_evidence_ids": list(unit.get("source_evidence_ids") or unit.get("extra_ids") or []),
        "occurrence_count": unit.get("occurrence_count"),
        "pattern_type": unit.get("pattern_type"),
        "thread_id": unit.get("thread_id"),
        "title": unit.get("title"),
        "authored_text": "" if msgs else str(unit.get("authored_text") or "")[:800],
    }
    if msgs:
        row["messages"] = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            row["messages"].append(
                {
                    "sender": m.get("sender"),
                    "sender_person_id": m.get("sender_person_id"),
                    "from_owner": m.get("from_owner"),
                    "recipients": list(m.get("recipients") or [])[:12],
                    "conversation": m.get("conversation") or unit.get("thread_id"),
                    "time": m.get("time"),
                    "text": str(m.get("text") or "")[:400],
                    "evidence_id": m.get("evidence_id"),
                }
            )
        row["message_n"] = len(row["messages"])
        span = unit.get("date_span") if isinstance(unit.get("date_span"), dict) else {}
        row["date_span"] = span or None
    if unit.get("media"):
        row["media"] = unit.get("media")
    return row


def payload_piece_bytes(unit: dict[str, Any]) -> int:
    """Size the extract payload row, including attributed messages[]."""
    return len(json.dumps(unit_for_extract_model(unit), default=str))


def _split_group(group: list[dict[str, Any]], budget: int) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    size = 0
    for u in group:
        piece = payload_piece_bytes(u)
        if cur and size + piece > budget:
            chunks.append(cur)
            cur = []
            size = 0
        cur.append(u)
        size += piece
    if cur:
        chunks.append(cur)
    return chunks


def chunk_units_semantically(
    units: list[dict[str, Any]],
    *,
    budget: int,
) -> list[list[dict[str, Any]]]:
    """Keep a real multi-message thread together; pack same-day/same-people units.

    Do not emit one chunk per unique thread id. That is how January exploded
    past 200 extract calls.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for u in units:
        key = semantic_group_key(u)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(u)
    # Pack leftover singleton groups that share a calendar day (narrow time band).
    packed: list[list[dict[str, Any]]] = []
    day_bins: dict[str, list[dict[str, Any]]] = {}
    day_order: list[str] = []
    for key in order:
        group = groups[key]
        if key.startswith("thread:"):
            packed.extend(_split_group(group, budget))
            continue
        day = ""
        if ":20" in key:
            day = key.rsplit(":", 1)[-1]
        if len(day) == 10 and day[4] == "-":
            if day not in day_bins:
                day_bins[day] = []
                day_order.append(day)
            day_bins[day].extend(group)
        else:
            packed.extend(_split_group(group, budget))
    for day in day_order:
        packed.extend(_split_group(day_bins[day], budget))
    return packed


def chunk_provenance_ids(chunk: list[dict[str, Any]]) -> set[str]:
    return _id_set(chunk)


def _evidence_blob(chunk: list[dict[str, Any]]) -> str:
    return " ".join(_blob(u) for u in chunk).lower()


def _names_in_chunk(chunk: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()

    def _add(raw: Any) -> None:
        n = str(raw or "").strip().lower()
        if not n:
            return
        names.add(n)
        names.update(part for part in n.split() if len(part) > 1)

    for u in chunk:
        for p in u.get("people") or []:
            if isinstance(p, dict):
                _add(p.get("name"))
            else:
                _add(p)
        _add(u.get("sender_name"))
        for m in u.get("messages") or []:
            if not isinstance(m, dict):
                continue
            _add(m.get("sender"))
            for r in m.get("recipients") or []:
                _add(r)
    return names


def _authored_names_for_ids(chunk: list[dict[str, Any]], ids: list[str]) -> set[str] | None:
    """Names that appear as sender/recipient on supporting messages, if any."""
    wanted = {str(i) for i in ids if str(i).strip()}
    names: set[str] = set()
    saw_messages = False

    def _add(raw: Any) -> None:
        n = str(raw or "").strip().lower()
        if not n:
            return
        names.add(n)
        names.update(part for part in n.split() if len(part) > 1)

    for u in chunk:
        msgs = u.get("messages") if isinstance(u.get("messages"), list) else []
        if not msgs:
            continue
        for m in msgs:
            if not isinstance(m, dict):
                continue
            eid = str(m.get("evidence_id") or "").strip()
            if wanted and eid and eid not in wanted:
                continue
            saw_messages = True
            _add(m.get("sender"))
            for r in m.get("recipients") or []:
                _add(r)
    return names if saw_messages else None


def _authored_blob_for_ids(chunk: list[dict[str, Any]], ids: list[str]) -> str:
    wanted = {str(i) for i in ids if str(i).strip()}
    parts: list[str] = []
    for u in chunk:
        msgs = u.get("messages") if isinstance(u.get("messages"), list) else []
        if msgs:
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                eid = str(m.get("evidence_id") or "").strip()
                if wanted and eid and eid not in wanted:
                    continue
                parts.append(str(m.get("text") or ""))
                parts.append(str(m.get("sender") or ""))
                parts.extend(str(x) for x in (m.get("recipients") or []))
            continue
        eids = set(unit_evidence_ids(u))
        if wanted and eids and not (wanted & eids):
            continue
        parts.append(_blob(u))
    return " ".join(parts).lower()


def missing_entailment_tokens(text: str, support_blob: str, names: set[str]) -> list[str]:
    """Content tokens in the observation that the supporting messages do not contain."""
    blob = support_blob or ""
    missing: list[str] = []
    for tok in re.findall(r"[a-z]{4,}", (text or "").lower()):
        if tok in _OBS_STOP or tok in names:
            continue
        if tok in blob:
            continue
        missing.append(tok)
    return missing


def _places_in_chunk(chunk: list[dict[str, Any]]) -> set[str]:
    places: set[str] = set()
    for u in chunk:
        lab = str(u.get("place") or "").strip().lower()
        if lab:
            places.add(lab)
    return places


def _dates_in_chunk(chunk: list[dict[str, Any]]) -> set[str]:
    days: set[str] = set()
    blob = _evidence_blob(chunk)
    days.update(_DATE.findall(blob))
    for u in chunk:
        d = _day(u.get("time"))
        if d:
            days.add(d)
        span = u.get("date_span") if isinstance(u.get("date_span"), dict) else {}
        for k in ("start", "end"):
            d2 = _day(span.get(k))
            if d2:
                days.add(d2)
    return days


def _is_comm_chunk(chunk: list[dict[str, Any]]) -> bool:
    for u in chunk:
        kind = str(u.get("kind") or "")
        src = str(u.get("source_type") or "").lower()
        if kind in _COMM_KINDS or src in {"email", "sms", "imessage", "text", "mms"}:
            return True
    return False


def filter_extract_observations(
    rows: list[Any],
    chunk: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop invalid / transport-only model observations immediately."""
    scope = chunk_provenance_ids(chunk)
    blob = _evidence_blob(chunk)
    names = _names_in_chunk(chunk)
    places = _places_in_chunk(chunk)
    dates = _dates_in_chunk(chunk)
    comm = _is_comm_chunk(chunk)
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            rejected.append({"reason": "observation_not_object"})
            continue
        kind_raw = str(raw.get("kind") or "").strip().lower().replace(" ", "_")
        from memorybox.ask.i11a.observations import KIND_ALIASES

        kind = KIND_ALIASES.get(kind_raw, kind_raw)
        if kind not in OBSERVATION_KINDS:
            rejected.append({"reason": "kind_not_canonical", "kind": raw.get("kind")})
            continue
        oid = str(raw.get("observation_id") or "").strip()
        if oid and oid not in scope and not oid.startswith("obs"):
            rejected.append({"reason": "invented_observation_id", "observation_id": oid[:80]})
            continue
        ids: list[str] = []
        invented_eid = False
        for i in raw.get("supporting_evidence_ids") or raw.get("evidence_ids") or []:
            s = str(i).strip()
            if not s:
                continue
            if s not in scope:
                rejected.append({"reason": "evidence_id_not_in_unit_provenance", "id": s[:80]})
                invented_eid = True
                break
            if s not in ids:
                ids.append(s)
        if invented_eid:
            continue
        raw_text = raw.get("text")
        if raw_text is None or str(raw_text).strip().lower() in _EMPTY_TEXT:
            rejected.append({"reason": "empty_observation", "text": None if raw_text is None else str(raw_text)[:80]})
            continue
        if not ids:
            rejected.append({"reason": "observation_ids_not_from_chunk", "text": str(raw.get("text") or "")[:160]})
            continue
        row = dict(raw)
        row["kind"] = kind
        row["supporting_evidence_ids"] = ids
        canon = canonicalize_observation(row, strict_kind=True)
        if not canon:
            rejected.append({"reason": "observation_schema_invalid", "kind": kind})
            continue
        text = str(canon.get("text") or "").strip()
        if not text or text.lower() in _EMPTY_TEXT:
            rejected.append({"reason": "empty_observation"})
            continue
        if str(canon.get("kind") or "") == "place_referenced":
            places_ok = [
                str(p).strip()
                for p in (canon.get("places") or [])
                if str(p).strip() and str(p).strip().lower() not in _GENERIC_PLACES
            ]
            if not places_ok:
                rejected.append({"reason": "place_referenced_without_place", "text": text[:160]})
                continue
        if str(canon.get("kind") or "") == "person_at_place_time":
            places_ok = [
                str(p).strip()
                for p in (canon.get("places") or [])
                if str(p).strip()
                and str(p).strip().lower() not in _GENERIC_PLACES
                and "unspecified" not in str(p).strip().lower()
            ]
            if not places_ok:
                rejected.append({"reason": "person_at_place_time_without_place", "text": text[:160]})
                continue
        if str(canon.get("kind") or "") == "relationship_stated" and not _REL_STATED.search(text):
            rejected.append({"reason": "relationship_stated_without_relationship", "text": text[:160]})
            continue
        if _TRANSPORT_ONLY.match(text):
            rejected.append({"reason": "transport_metadata_only", "text": text[:160]})
            continue
        if _PERSONALITY.search(text) and not _PERSONALITY.search(blob):
            rejected.append({"reason": "unsupported_personality_inference", "text": text[:160]})
            continue
        if comm and str(canon.get("kind") or "") == "person_at_place_time":
            if not _PRESENCE_STATED.search(blob) and not _PRESENCE_STATED.search(text):
                rejected.append(
                    {
                        "reason": "person_at_place_time_without_stated_presence",
                        "text": text[:160],
                    }
                )
                continue
        invented_place = False
        for p in canon.get("places") or []:
            lab = str(p or "").strip().lower()
            if not lab:
                continue
            if lab in places or lab in blob:
                continue
            tokens = [t for t in re.split(r"[^a-z0-9]+", lab) if len(t) > 2]
            if tokens and all(t in blob for t in tokens):
                continue
            invented_place = True
            break
        if invented_place:
            rejected.append({"reason": "invented_place", "text": text[:160], "places": canon.get("places")})
            continue
        invented_person = False
        for p in canon.get("people") or []:
            n = str((p.get("name") if isinstance(p, dict) else p) or "").strip().lower()
            if not n:
                continue
            if n in names or n in blob:
                continue
            tokens = [t for t in n.split() if len(t) > 1]
            if tokens and all(t in blob or t in names for t in tokens):
                continue
            invented_person = True
            break
        if invented_person:
            rejected.append({"reason": "invented_person", "text": text[:160]})
            continue
        authored = _authored_names_for_ids(chunk, ids)
        if authored is not None:
            unsupported = False
            for p in canon.get("people") or []:
                n = str((p.get("name") if isinstance(p, dict) else p) or "").strip().lower()
                if not n:
                    continue
                tokens = [t for t in n.split() if len(t) > 1]
                if n in authored or (tokens and all(t in authored for t in tokens)):
                    continue
                unsupported = True
                break
            if unsupported:
                rejected.append({"reason": "people_not_in_authored_message", "text": text[:160]})
                continue
        support_blob = _authored_blob_for_ids(chunk, ids)
        missing = missing_entailment_tokens(text, support_blob, names)
        if missing:
            rejected.append(
                {
                    "reason": "observation_not_entailed_by_supporting_messages",
                    "text": text[:160],
                    "missing": missing[:12],
                }
            )
            continue
        t = str(canon.get("time") or "")[:10]
        if t and _DATE.match(t) and t not in dates and t not in blob:
            rejected.append({"reason": "invented_date", "time": t, "text": text[:160]})
            continue
        kept.append(canon)
    return kept, rejected
