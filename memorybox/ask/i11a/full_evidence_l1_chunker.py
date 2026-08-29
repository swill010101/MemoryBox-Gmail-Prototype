"""Level-1 complete-coverage evidence chunker (diagnostic only).

Governing rule: every eligible evidence item appears in the chunk hierarchy.
Chunking may organize and safely compact; it may not semantically select, rank,
sample, or discard evidence. No LLM. No production I11A behavior changes.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from memorybox.ask.authored import authored_email_text
from memorybox.ask.i11a.full_evidence_diagnostic import (
    estimate_tokens,
    format_item_block,
    slim_person_context_for_model,
)

# Model-chunk sizing (estimated tokens via bytes/4).
L1_CHUNK_TARGET_MIN = 75_000
L1_CHUNK_TARGET_MAX = 125_000
# Modest overshoot allowed to keep coherent source units intact.
L1_CHUNK_OVERSHOOT_MAX = 150_000

# SMS episode segmentation (deterministic; no LLM topic boundaries).
SMS_GAP_HOURS = 4.0
# Day boundary alone is a weak signal — only reinforce an existing large gap.
SMS_DAY_BOUNDARY_MIN_GAP_HOURS = 2.0

_SIG_LINE = re.compile(
    r"(?m)^(--)[ \t]*$|^Sent from my iPhone.*$|^Get Outlook for.*$|"
    r"^Sent from my (?:Galaxy|Android).*|^Get.*for iOS.*$",
    re.I,
)
_QUOTE_MARKERS = re.compile(
    r"(?is)"
    r"(?:\n|^)\s*On .{8,400}?\bwrote:\s*"
    r"|-----Original Message-----"
    r"|(?:\n|^)_{8,}\s*\nFrom:"
    r"|(?:\n|^)Begin forwarded message:"
    r"|(?:\n|^)From:\s+.+\nSent:"
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_ts(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        if len(s) >= 10:
            try:
                return datetime.fromisoformat(s[:10]).replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None


def _participant_set(item: dict[str, Any]) -> frozenset[str]:
    people = item.get("participants") or item.get("people") or []
    return frozenset(str(p).strip().lower() for p in people if str(p).strip())


def _size_of_items(items: list[dict[str, Any]]) -> dict[str, int]:
    text = "\n".join(format_item_block(it) for it in items)
    b = text.encode("utf-8")
    return {
        "bytes": len(b),
        "characters": len(text),
        "estimated_tokens": estimate_tokens(text) if text else 0,
    }


# ---------------------------------------------------------------------------
# Safe compaction (auditable only)
# ---------------------------------------------------------------------------


def compact_email_item(item: dict[str, Any], *, prior_bodies: list[str]) -> tuple[dict[str, Any], dict[str, int]]:
    """Strip repeated quoted history + separable signatures. Preserve authored content."""
    counts = {
        "quoted_email_history_chars_removed": 0,
        "signature_boilerplate_chars_removed": 0,
        "empty_malformed_skipped": 0,
    }
    out = dict(item)
    raw = str(item.get("body") or "")
    if not raw.strip():
        # Keep empty bodies represented — do not discard short/empty meaning.
        return out, counts

    authored, _flags = authored_email_text(raw)
    # Prefer uncapped authored when production path truncated.
    if len(raw) > 8000 and len(authored) >= 8000:
        cut_m = _QUOTE_MARKERS.search("\n" + raw)
        authored = raw[: cut_m.start() - 1].strip() if cut_m and cut_m.start() > 1 else raw

    # Remove verbatim copies of earlier messages in the same thread when present.
    body = authored
    for prior in prior_bodies:
        prior = (prior or "").strip()
        if len(prior) < 40:
            continue
        if prior in body and prior != body:
            before = len(body)
            body = body.replace(prior, "").strip()
            counts["quoted_email_history_chars_removed"] += max(0, before - len(body))

    # Signature / transport boilerplate when separable.
    stripped = _SIG_LINE.sub("", body).strip()
    if stripped != body.strip():
        counts["signature_boilerplate_chars_removed"] += max(0, len(body) - len(stripped))
        body = stripped

    if len(raw) > len(body):
        counts["quoted_email_history_chars_removed"] += max(
            0, len(raw) - len(body) - counts["signature_boilerplate_chars_removed"]
        )

    out["body"] = body
    out["raw_body_chars"] = len(raw)
    out["compaction"] = {
        "quoted_removed": counts["quoted_email_history_chars_removed"] > 0,
        "signature_removed": counts["signature_boilerplate_chars_removed"] > 0,
    }
    return out, counts


def apply_safe_compaction(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Exact-dupe already handled upstream; here: email quote/signature compaction only.

    Short messages (love you / OK / emoji) are NEVER deleted.
    """
    tallies = {
        "exact_duplicates_removed": 0,  # reported by caller if already done
        "quoted_email_history_chars_removed": 0,
        "quoted_email_messages_compacted": 0,
        "signature_boilerplate_chars_removed": 0,
        "empty_malformed_skipped": 0,
        "short_messages_preserved": 0,
    }
    # Group emails by thread for prior-body context.
    by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    others: list[dict[str, Any]] = []
    for it in items:
        if it.get("source") == "email":
            by_thread[str(it.get("thread_id") or it.get("item_id") or "")].append(it)
        else:
            others.append(it)
            body = str(it.get("body") or "")
            if it.get("source") == "sms" and 0 < len(body.strip()) <= 40:
                tallies["short_messages_preserved"] += 1

    compacted: list[dict[str, Any]] = []
    for _tid, msgs in by_thread.items():
        msgs_sorted = sorted(
            msgs,
            key=lambda m: (str(m.get("timestamp") or ""), str(m.get("item_id") or "")),
        )
        prior_bodies: list[str] = []
        for m in msgs_sorted:
            c_item, counts = compact_email_item(m, prior_bodies=prior_bodies)
            for k, v in counts.items():
                if k in tallies:
                    tallies[k] += int(v)
            if counts.get("quoted_email_history_chars_removed") or counts.get(
                "signature_boilerplate_chars_removed"
            ):
                tallies["quoted_email_messages_compacted"] += 1
            prior_bodies.append(str(c_item.get("body") or ""))
            compacted.append(c_item)

    # Preserve original chronological order of non-email + compacted email by timestamp.
    all_items = others + compacted
    all_items.sort(
        key=lambda it: (
            str(it.get("timestamp") or "9999"),
            str(it.get("source") or ""),
            str(it.get("item_id") or ""),
        )
    )
    return all_items, tallies


# ---------------------------------------------------------------------------
# Source-specific Level-1 units
# ---------------------------------------------------------------------------


def segment_sms_episodes(
    sms_items: list[dict[str, Any]],
    *,
    gap_hours: float = SMS_GAP_HOURS,
) -> list[dict[str, Any]]:
    """Deterministic SMS conversation episodes within each channel/thread.

    Split signals (no LLM):
    - timestamp gap >= gap_hours (primary)
    - participant-set change
    - day boundary only when gap also >= SMS_DAY_BOUNDARY_MIN_GAP_HOURS (weak)

    Every message remains represented.
    """
    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in sms_items:
        ch = str(it.get("thread_id") or "sms-unknown")
        by_channel[ch].append(it)

    episodes: list[dict[str, Any]] = []
    for channel_id, msgs in sorted(by_channel.items(), key=lambda kv: kv[0]):
        msgs_sorted = sorted(
            msgs,
            key=lambda m: (str(m.get("timestamp") or ""), str(m.get("item_id") or "")),
        )
        current: list[dict[str, Any]] = []
        prev_ts: datetime | None = None
        prev_parts: frozenset[str] | None = None
        ep_idx = 0
        split_reasons: list[str] = []

        def _flush(reason: str | None = None) -> None:
            nonlocal current, ep_idx, split_reasons
            if not current:
                return
            earliest = str(current[0].get("timestamp") or "") or None
            latest = str(current[-1].get("timestamp") or "") or None
            episodes.append(
                {
                    "unit_id": f"sms-episode:{channel_id}:{ep_idx:04d}",
                    "unit_kind": "sms_episode",
                    "channel_id": channel_id,
                    "episode_index": ep_idx,
                    "split_reason_into": reason,
                    "item_ids": [str(m.get("item_id")) for m in current],
                    "items": list(current),
                    "message_count": len(current),
                    "earliest_date": earliest,
                    "latest_date": latest,
                    "participants": sorted(_participant_set(current[0])) if current else [],
                }
            )
            ep_idx += 1
            current = []
            split_reasons = []

        for m in msgs_sorted:
            ts = _parse_ts(m.get("timestamp"))
            parts = _participant_set(m)
            reason = None
            if current:
                if prev_parts is not None and parts and prev_parts and parts != prev_parts:
                    reason = "participant_set_change"
                elif prev_ts and ts:
                    gap_h = (ts - prev_ts).total_seconds() / 3600.0
                    if gap_h >= gap_hours:
                        reason = f"time_gap>={gap_hours}h"
                    elif gap_h >= SMS_DAY_BOUNDARY_MIN_GAP_HOURS and prev_ts.date() != ts.date():
                        reason = "day_boundary_with_gap"
                if reason:
                    _flush(reason)
            current.append(m)
            prev_ts = ts or prev_ts
            if parts:
                prev_parts = parts
        _flush(None)
    return episodes


_REPLY_SUBJ = re.compile(r"^(?:(?:re|fw|fwd)\s*:\s*)+", re.I)


def _norm_email_subject(raw: Any) -> str:
    s = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    while True:
        nxt = _REPLY_SUBJ.sub("", s).strip()
        if nxt == s:
            return s
        s = nxt


def _thread_structured_addresses(item: dict[str, Any]) -> list[str]:
    """From/To/CC/BCC + parsed addresses. Never people[]."""
    found: set[str] = set()
    for raw in item.get("addresses") or []:
        s = str(raw).strip().lower()
        if s and "@" in s:
            found.add(s)
    for rec in (
        list(item.get("from_parsed") or [])
        + list(item.get("to_parsed") or [])
        + list(item.get("cc_parsed") or [])
        + list(item.get("bcc_parsed") or [])
    ):
        if not isinstance(rec, dict):
            continue
        s = str(rec.get("normalized") or rec.get("address") or "").strip().lower()
        if s and "@" in s:
            found.add(s)
    blob = " ".join(
        str(item.get(k) or "")
        for k in ("from", "to", "cc", "bcc", "from_header", "to_header")
    )
    for m in re.finditer(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob
    ):
        found.add(m.group(0).strip().lower())
    return sorted(found)


def _email_thread_key(item: dict[str, Any]) -> str:
    """Prefer RFC thread_id; else same normalized subject + structured addresses.

    Takeout often omits thread_id. people[] is never part of the key.
    """
    tid = str(item.get("thread_id") or "").strip()
    iid = str(item.get("item_id") or "")
    if tid and tid != iid:
        return f"tid:{tid}"
    subj = _norm_email_subject(item.get("subject") or item.get("title"))
    addrs = _thread_structured_addresses(item)
    if subj and addrs:
        return f"subj:{subj}|{','.join(addrs)}"
    return f"item:{iid or id(item)}"


def group_email_threads(email_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in email_items:
        by_thread[_email_thread_key(it)].append(it)
    units: list[dict[str, Any]] = []
    for tid, msgs in sorted(by_thread.items(), key=lambda kv: kv[0]):
        msgs_sorted = sorted(
            msgs,
            key=lambda m: (str(m.get("timestamp") or ""), str(m.get("item_id") or "")),
        )
        units.append(
            {
                "unit_id": f"email-thread:{tid}",
                "unit_kind": "email_thread",
                "thread_id": tid,
                "item_ids": [str(m.get("item_id")) for m in msgs_sorted],
                "items": msgs_sorted,
                "message_count": len(msgs_sorted),
                "earliest_date": str(msgs_sorted[0].get("timestamp") or "") or None,
                "latest_date": str(msgs_sorted[-1].get("timestamp") or "") or None,
            }
        )
    return units


def _singleton_units(items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    out = []
    for it in items:
        out.append(
            {
                "unit_id": f"{kind}:{it.get('item_id')}",
                "unit_kind": kind,
                "item_ids": [str(it.get("item_id"))],
                "items": [it],
                "message_count": 1,
                "earliest_date": it.get("timestamp"),
                "latest_date": it.get("timestamp"),
            }
        )
    return out


def build_l1_units(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build source-physics Level-1 units covering every item exactly once."""
    by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        by_src[str(it.get("source") or "other")].append(it)

    units: list[dict[str, Any]] = []
    units.extend(_singleton_units(by_src.get("person") or [], "person_facts"))
    units.extend(segment_sms_episodes(by_src.get("sms") or []))
    units.extend(group_email_threads(by_src.get("email") or []))
    units.extend(_singleton_units(by_src.get("calendar") or [], "calendar_event"))
    units.extend(_singleton_units(by_src.get("story") or [], "story"))
    units.extend(_singleton_units(by_src.get("journal") or [], "journal"))
    units.extend(_singleton_units(by_src.get("travel") or [], "travel"))
    units.extend(_singleton_units(by_src.get("photo") or [], "media_observation"))
    units.extend(_singleton_units(by_src.get("video") or [], "media_observation"))
    units.extend(_singleton_units(by_src.get("artifact") or [], "artifact"))
    units.extend(_singleton_units(by_src.get("guided_capture") or [], "guided_capture"))
    for src, members in by_src.items():
        if src in {
            "person",
            "sms",
            "email",
            "calendar",
            "story",
            "journal",
            "travel",
            "photo",
            "video",
            "artifact",
            "guided_capture",
        }:
            continue
        units.extend(_singleton_units(members, "other"))

    # Chronological by unit earliest date.
    units.sort(
        key=lambda u: (
            str(u.get("earliest_date") or "9999"),
            str(u.get("unit_kind") or ""),
            str(u.get("unit_id") or ""),
        )
    )
    return units


def _unit_text(unit: dict[str, Any]) -> str:
    kind = str(unit.get("unit_kind") or "").upper().replace("_", " ")
    lines = [f"===== {kind} ====="]
    if unit.get("channel_id"):
        lines.append(f"sms_channel_id: {unit.get('channel_id')}")
        lines.append(f"episode_index: {unit.get('episode_index')}")
    if unit.get("thread_id"):
        lines.append(f"email_thread_id: {unit.get('thread_id')}")
    if unit.get("earliest_date") or unit.get("latest_date"):
        lines.append(
            f"date_span: {unit.get('earliest_date') or '?'} .. {unit.get('latest_date') or '?'}"
        )
    lines.append(f"evidence_ids: {', '.join(unit.get('item_ids') or [])}")
    lines.append("")
    for it in unit.get("items") or []:
        lines.append(format_item_block(it))
    return "\n".join(lines)


def _subdivide_oversized_unit(unit: dict[str, Any], max_tokens: int) -> list[dict[str, Any]]:
    """Split only at message boundaries when a thread/episode exceeds overshoot max."""
    items = list(unit.get("items") or [])
    text = _unit_text(unit)
    if estimate_tokens(text) <= max_tokens or len(items) <= 1:
        return [unit]

    kind = str(unit.get("unit_kind") or "")
    if kind not in {"email_thread", "sms_episode"}:
        return [unit]

    parts: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    part_i = 0

    def _flush() -> None:
        nonlocal cur, part_i
        if not cur:
            return
        sub = {
            **{k: v for k, v in unit.items() if k not in {"items", "item_ids", "message_count"}},
            "unit_id": f"{unit.get('unit_id')}#part{part_i:02d}",
            "parent_unit_id": unit.get("unit_id"),
            "subdivision": "message_boundary",
            "items": list(cur),
            "item_ids": [str(m.get("item_id")) for m in cur],
            "message_count": len(cur),
            "earliest_date": cur[0].get("timestamp"),
            "latest_date": cur[-1].get("timestamp"),
        }
        parts.append(sub)
        part_i += 1
        cur = []

    for it in items:
        trial = cur + [it]
        trial_unit = {
            **unit,
            "items": trial,
            "item_ids": [str(m.get("item_id")) for m in trial],
        }
        if cur and estimate_tokens(_unit_text(trial_unit)) > max_tokens:
            _flush()
        cur.append(it)
    _flush()
    return parts or [unit]


def pack_model_chunks(
    units: list[dict[str, Any]],
    *,
    target_min: int = L1_CHUNK_TARGET_MIN,
    target_max: int = L1_CHUNK_TARGET_MAX,
    overshoot_max: int = L1_CHUNK_OVERSHOOT_MAX,
) -> list[dict[str, Any]]:
    """Pack L1 units into bounded model chunks. Never split normal-sized threads/episodes."""
    expanded: list[dict[str, Any]] = []
    for u in units:
        expanded.extend(_subdivide_oversized_unit(u, overshoot_max))

    chunks: list[dict[str, Any]] = []
    cur_units: list[dict[str, Any]] = []
    cur_tokens = 0

    def _flush() -> None:
        nonlocal cur_units, cur_tokens
        if not cur_units:
            return
        items: list[dict[str, Any]] = []
        item_ids: list[str] = []
        for u in cur_units:
            items.extend(u.get("items") or [])
            item_ids.extend(str(i) for i in (u.get("item_ids") or []))
        body = "\n".join(_unit_text(u) for u in cur_units)
        earliest, latest = None, None
        dates = [str(u.get("earliest_date") or "") for u in cur_units if u.get("earliest_date")]
        dates += [str(u.get("latest_date") or "") for u in cur_units if u.get("latest_date")]
        dates = [d for d in dates if d]
        if dates:
            earliest, latest = min(dates), max(dates)
        fam: dict[str, int] = defaultdict(int)
        for it in items:
            fam[str(it.get("source") or "other")] += 1
        chunk_id = f"PEGGY_CHUNK_{len(chunks) + 1:03d}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": len(chunks),
                "unit_ids": [str(u.get("unit_id")) for u in cur_units],
                "units": list(cur_units),
                "item_ids": item_ids,
                "items": items,
                "item_count": len(item_ids),
                "source_family_counts": dict(fam),
                "earliest_date": earliest,
                "latest_date": latest,
                "date_span": {"earliest": earliest, "latest": latest},
                "bytes": len(body.encode("utf-8")),
                "estimated_tokens": estimate_tokens(body),
                "body_text": body,
            }
        )
        cur_units = []
        cur_tokens = 0

    for u in expanded:
        utok = estimate_tokens(_unit_text(u))
        if not cur_units:
            cur_units.append(u)
            cur_tokens = utok
            if cur_tokens >= overshoot_max:
                _flush()
            continue
        # Prefer not to exceed target_max; allow overshoot to keep unit intact.
        if cur_tokens >= target_min and cur_tokens + utok > target_max:
            _flush()
            cur_units.append(u)
            cur_tokens = utok
            if cur_tokens >= overshoot_max:
                _flush()
            continue
        if cur_tokens + utok > overshoot_max and cur_tokens > 0:
            _flush()
            cur_units.append(u)
            cur_tokens = utok
            continue
        cur_units.append(u)
        cur_tokens += utok
        if cur_tokens >= overshoot_max:
            _flush()
    _flush()
    return chunks


def format_chunk_file(
    chunk: dict[str, Any],
    *,
    person_context: dict[str, Any] | None,
    ask: str,
    chunk_n: int,
    chunk_total: int,
    person_as_reference: bool,
) -> str:
    slim = slim_person_context_for_model(person_context) if person_context else {}
    lines = [
        f"{chunk.get('chunk_id')}  ({chunk_n}/{chunk_total})",
        f"ask: {ask}",
        f"date_span: {chunk.get('earliest_date') or '?'} .. {chunk.get('latest_date') or '?'}",
        f"estimated_tokens: {chunk.get('estimated_tokens')}",
        f"evidence_item_count: {chunk.get('item_count')}",
        f"source_family_counts: {json.dumps(chunk.get('source_family_counts') or {}, sort_keys=True)}",
        "",
        "===== PERSON CONTEXT"
        + (" (REFERENCE)" if person_as_reference else "")
        + " =====",
        "",
        json.dumps(slim, indent=2, default=str, ensure_ascii=False),
        "",
    ]
    # Body already has unit headings; skip re-embedding person_facts units in reference mode
    # when they were already placed in chunk 1 as evidence — body still includes them once.
    lines.append(chunk.get("body_text") or "")
    return "\n".join(lines).rstrip() + "\n"


def prove_chunk_completeness(
    items: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    all_ids = [str(it.get("item_id")) for it in items if it.get("item_id")]
    chunk_ids: list[str] = []
    for ch in chunks:
        chunk_ids.extend(str(i) for i in (ch.get("item_ids") or []))
    c_all = Counter(all_ids)
    c_chunk = Counter(chunk_ids)
    missing = sorted(set(c_all) - set(c_chunk))
    extra = sorted(set(c_chunk) - set(c_all))
    dup_across = sorted(iid for iid, n in c_chunk.items() if n > 1)
    multiset_ok = c_all == c_chunk
    ok = (
        not missing
        and not extra
        and multiset_ok
        and not dup_across
        and len(all_ids) == len(chunk_ids)
    )
    return {
        "ok": ok,
        "eligible_item_count": len(all_ids),
        "chunked_item_count": len(chunk_ids),
        "unique_eligible": len(set(all_ids)),
        "unique_chunked": len(set(chunk_ids)),
        "union_equals_normalized": sorted(set(all_ids)) == sorted(set(chunk_ids)) and multiset_ok,
        "multiset_equal": multiset_ok,
        "missing_item_ids": missing,
        "extra_item_ids": extra,
        "duplicated_across_chunks": dup_across,
        "no_cross_chunk_duplicates": not dup_across,
        "llm_invoked": False,
        "production_semantics_changed": False,
    }


def build_chunk_manifest(
    items: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    compaction: dict[str, Any] | None = None,
    sms_rules: dict[str, Any] | None = None,
    proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proof = proof or prove_chunk_completeness(items, chunks)
    return {
        "manifest_version": 1,
        "layer": "level1_complete_coverage",
        "chunk_count": len(chunks),
        "eligible_item_count": len(items),
        "sms_segmentation_rules": sms_rules
        or {
            "gap_hours": SMS_GAP_HOURS,
            "day_boundary_min_gap_hours": SMS_DAY_BOUNDARY_MIN_GAP_HOURS,
            "participant_set_change": True,
            "llm_topic_boundaries": False,
        },
        "compaction": compaction or {},
        "completeness_proof": proof,
        "chunk_sizing": {
            "target_min_tokens": L1_CHUNK_TARGET_MIN,
            "target_max_tokens": L1_CHUNK_TARGET_MAX,
            "overshoot_max_tokens": L1_CHUNK_OVERSHOOT_MAX,
        },
        "normalized_item_ids_sha256": _sha256_text(json.dumps(sorted(str(i.get("item_id")) for i in items))),
        "chunks": [
            {
                "chunk_id": ch.get("chunk_id"),
                "chunk_index": ch.get("chunk_index"),
                "filename": ch.get("filename"),
                "date_span": ch.get("date_span"),
                "source_family_counts": ch.get("source_family_counts"),
                "evidence_ids": ch.get("item_ids"),
                "bytes": ch.get("bytes"),
                "estimated_tokens": ch.get("estimated_tokens"),
                "unit_ids": ch.get("unit_ids"),
            }
            for ch in chunks
        ],
    }


def run_l1_chunker(
    items: list[dict[str, Any]],
    *,
    person_context: dict[str, Any] | None = None,
    ask: str = "",
) -> dict[str, Any]:
    """Compact → L1 units → model chunks → completeness proof."""
    compacted, compaction = apply_safe_compaction(items)
    # Exact-dupe already applied upstream; keep key for report symmetry.
    units = build_l1_units(compacted)
    chunks = pack_model_chunks(units)
    proof = prove_chunk_completeness(compacted, chunks)
    if not proof.get("ok"):
        raise RuntimeError(
            "L1 completeness proof failed: "
            f"missing={proof.get('missing_item_ids')} "
            f"extra={proof.get('extra_item_ids')} "
            f"dupes={proof.get('duplicated_across_chunks')}"
        )

    sms_rules = {
        "gap_hours": SMS_GAP_HOURS,
        "day_boundary_min_gap_hours": SMS_DAY_BOUNDARY_MIN_GAP_HOURS,
        "participant_set_change": True,
        "llm_topic_boundaries": False,
        "episode_count": sum(1 for u in units if u.get("unit_kind") == "sms_episode"),
        "email_thread_count": sum(1 for u in units if u.get("unit_kind") == "email_thread"),
        "l1_unit_count": len(units),
    }
    # Attach human-readable filenames / text
    total = len(chunks)
    for i, ch in enumerate(chunks):
        fname = f"{ch['chunk_id']}.txt"
        ch["filename"] = fname
        ch["file_text"] = format_chunk_file(
            ch,
            person_context=person_context,
            ask=ask,
            chunk_n=i + 1,
            chunk_total=total,
            person_as_reference=i > 0,
        )
        # Person context header is reference-only after chunk 1 — not an evidence ID.
        ch["person_context_mode"] = "reference" if i > 0 else "primary"

    manifest = build_chunk_manifest(
        compacted,
        chunks,
        compaction=compaction,
        sms_rules=sms_rules,
        proof=proof,
    )
    return {
        "items": compacted,
        "units": units,
        "chunks": chunks,
        "manifest": manifest,
        "compaction": compaction,
        "proof": proof,
        "sms_rules": sms_rules,
    }
