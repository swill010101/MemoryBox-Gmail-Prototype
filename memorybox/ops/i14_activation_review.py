"""Bounded founder activation-review packet. Read-only. Never activates."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import assert_counts_only, failure_json
from memorybox.ops.i14_prepared_text import HOTMAIL_DATE_FROM_TO_SUBJECT
from memorybox.ops.i14_thread_review import format_review_date

NAMED_REFS = ("T-2312-M-02", "T-2345-M-02")
MAX_THREADS = 12
FOCUS_OTHER = 10


class ActivationReviewError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _allow() -> None:
    if os.environ.get("MEMORYBOX_I14_REVIEW_EMIT_PRIVATE", "").strip() != "1":
        raise ActivationReviewError("private_review_emit_not_authorized")
    if os.environ.get("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", "").strip() != "1":
        raise ActivationReviewError("memorybox_db_not_allowed")
    if os.environ.get("MEMORYBOX_I14_VOICE_DELTA_ALLOW_FLIGHTSIM", "").strip() != "1":
        raise ActivationReviewError("flightsim_not_allowed")


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def _voice_reason(msg: dict[str, Any], *, focus: bool, glued: bool) -> str:
    if msg.get("voice_corpus"):
        bits = [
            "VOICE ACCEPTED",
            "authenticated From Person",
            f"quote_quality={msg.get('quote_quality')}",
            f"identity_quality={msg.get('identity_quality')}",
        ]
        if glued:
            bits.append("glued Hotmail Date/From/To/Subject cut; Peggy authored text preserved")
        return " | ".join(bits)
    return (
        "VOICE REJECTED | "
        f"quote_quality={msg.get('quote_quality')} | "
        f"identity_quality={msg.get('identity_quality')} | "
        f"authorship={msg.get('authorship')}"
    )


def select_activation_threads(conn: Any, gid: Any) -> dict[str, Any]:
    named_threads = []
    for ref in NAMED_REFS:
        row = conn.execute(
            """
            SELECT t.display_id, m.evidence_ref
              FROM comms_prepared_messages m
              JOIN comms_prepared_threads t ON t.id = m.thread_id
             WHERE t.generation_id = %s AND m.evidence_ref = %s
            """,
            (gid, ref),
        ).fetchone()
        if not row:
            raise ActivationReviewError(f"named_ref_missing:{ref}")
        named_threads.append(str(row["display_id"]))
    glued_rows = conn.execute(
        """
        SELECT t.display_id, m.evidence_ref, m.ordinal, e.payload_json
          FROM comms_prepared_messages m
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
          JOIN people pe ON pe.id = p.person_id
          JOIN evidence e ON e.id = m.evidence_id
         WHERE t.generation_id = %s
           AND m.voice_corpus
           AND split_part(pe.display_name, ' ', 1) = 'Peggy'
         ORDER BY t.display_id, m.ordinal
        """,
        (gid,),
    ).fetchall()
    other_pairs: list[tuple[str, str]] = []
    other_total = 0
    thread_counts: dict[str, int] = {}
    for rec in glued_rows:
        payload = _payload(rec.get("payload_json"))
        raw = str(payload.get("body_text") or payload.get("body") or "")
        if not HOTMAIL_DATE_FROM_TO_SUBJECT.search(raw.replace("\r\n", "\n")):
            continue
        ref = str(rec["evidence_ref"])
        if ref in NAMED_REFS:
            continue
        other_total += 1
        tid = str(rec["display_id"])
        other_pairs.append((tid, ref))
        thread_counts[tid] = thread_counts.get(tid, 0) + 1
    ranked_other = [
        tid
        for tid, _n in sorted(thread_counts.items(), key=lambda item: (-item[1], item[0]))
        if tid not in named_threads
    ]
    other_refs: list[str] = []

    def _take(tid: str) -> int:
        added = 0
        for t, ref in other_pairs:
            if t != tid or ref in other_refs or len(other_refs) >= 24:
                continue
            other_refs.append(ref)
            added += 1
        return added

    for tid in named_threads:
        _take(tid)
    other_threads: list[str] = []
    for tid in ranked_other:
        if len(other_refs) >= 24 or len(other_threads) >= FOCUS_OTHER:
            break
        if _take(tid):
            other_threads.append(tid)
    selected = []
    for tid in named_threads + other_threads:
        if tid not in selected:
            selected.append(tid)
        if len(selected) >= MAX_THREADS:
            break
    return {
        "selected": selected,
        "named_refs": list(NAMED_REFS),
        "other_glued_voice_refs": other_refs,
        "other_glued_voice_count_total": other_total,
    }


def _pack_thread(conn: Any, gid: Any, display_id: str, focus_refs: set[str]) -> dict[str, Any]:
    trow = conn.execute(
        """
        SELECT * FROM comms_prepared_threads
         WHERE generation_id = %s AND display_id = %s
        """,
        (gid, display_id),
    ).fetchone()
    msgs = conn.execute(
        """
        SELECT m.*, e.payload_json
          FROM comms_prepared_messages m
          JOIN evidence e ON e.id = m.evidence_id
         WHERE m.thread_id = %s
         ORDER BY m.ordinal
        """,
        (trow["id"],),
    ).fetchall()
    packed = []
    for msg in msgs:
        payload = _payload(msg.get("payload_json"))
        raw = str(payload.get("body_text") or payload.get("body") or "")
        glued = bool(HOTMAIL_DATE_FROM_TO_SUBJECT.search(raw.replace("\r\n", "\n")))
        parties = conn.execute(
            """
            SELECT role, display_name, address_normalized, identity_confidence, person_id
              FROM comms_prepared_participants
             WHERE message_id = %s
             ORDER BY role, address_normalized
            """,
            (msg["id"],),
        ).fetchall()
        from_p, to_p, cc_p = [], [], []
        for party in parties:
            item = {
                "display": party["display_name"],
                "address": party["address_normalized"],
                "status": party["identity_confidence"],
            }
            if party["role"] == "from":
                from_p.append(item)
            elif party["role"] == "to":
                to_p.append(item)
            else:
                cc_p.append(item)
        rec = {
            "evidence_ref": msg["evidence_ref"],
            "ordinal": msg["ordinal"],
            "timestamp": msg["sent_at"].isoformat() if hasattr(msg["sent_at"], "isoformat") else str(msg["sent_at"]),
            "subject": msg["subject"],
            "from_parties": from_p,
            "to_parties": to_p,
            "cc_parties": cc_p,
            "cleaned_body": msg["cleaned_authored_text"],
            "raw_body": raw,
            "voice_corpus": msg["voice_corpus"],
            "quote_quality": msg["quote_quality"],
            "identity_quality": msg["identity_quality"],
            "authorship": msg["authorship"],
            "commercial_class": msg["commercial_class"],
            "forward_block": msg["forward_block"],
            "forward_omitted": msg["forward_omitted"],
            "focus": msg["evidence_ref"] in focus_refs,
            "glued_hotmail": glued,
        }
        rec["voice_reason"] = _voice_reason(rec, focus=rec["focus"], glued=glued)
        packed.append(rec)
    return {
        "preview_thread_id": display_id,
        "messages": packed,
        "threading_confidence": trow["threading_confidence"],
        "identity_confidence": trow["identity_confidence"],
        "duplicate_omitted": trow["duplicate_omitted_count"],
        "source_evidence_count": trow["evidence_count"],
        "commercial_summary": trow["gallery_eligibility"],
        "cases": [],
        "warnings": [],
        "message_count": trow["message_count"],
    }


def _party(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(none)"
    out = []
    for row in rows:
        name = str(row.get("display") or "").strip() or "unknown"
        status = str(row.get("status") or "")
        out.append(f"{name} [{status}]")
    return "; ".join(out)


def format_activation_thread(thread: dict[str, Any]) -> str:
    tid = thread["preview_thread_id"]
    msgs = thread["messages"]
    lines = [
        "=" * 78,
        f"BEGIN THREAD  {tid}",
        f"messages: {len(msgs)} | threading: {thread.get('threading_confidence')} | "
        f"identity: {thread.get('identity_confidence')}",
        f"duplicates_omitted: {thread.get('duplicate_omitted')}",
        "-" * 78,
    ]
    for msg in msgs:
        ref = msg["evidence_ref"]
        mark = "FOCUS" if msg.get("focus") else "context"
        lines.extend(
            [
                f"MESSAGE {msg['ordinal']} of {len(msgs)}  [{mark}]",
                f"Evidence-ref: {ref}",
                f"From: {_party(msg.get('from_parties') or [])}",
                f"To: {_party(msg.get('to_parties') or [])}",
                f"Cc: {_party(msg.get('cc_parties') or [])}",
                f"Date: {format_review_date(msg.get('timestamp'))}",
                f"Subject: {msg.get('subject') or '(none)'}",
                f"Voice decision: {msg.get('voice_reason')}",
                "Cleaned authored text:",
                str(msg.get("cleaned_body") or "(empty)"),
                f"Immutable original: originals/{ref}.txt",
                "-" * 78,
            ]
        )
    lines.append(f"END THREAD  {tid}")
    lines.append("=" * 78)
    return "\n".join(lines) + "\n"


def write_activation_packet(conn: Any, out_dir: Path) -> dict[str, Any]:
    gid = conn.execute(
        """
        SELECT id FROM comms_prepared_generations
         WHERE status = 'validated' AND NOT published AND NOT is_active
         ORDER BY created_at DESC
         LIMIT 1
        """
    ).fetchone()
    if not gid:
        raise ActivationReviewError("no_eligible_unpublished_generation")
    gid = gid["id"]
    choice = select_activation_threads(conn, gid)
    selected = choice["selected"]
    if len(selected) > MAX_THREADS:
        raise ActivationReviewError("packet_thread_limit")
    focus_refs = set(choice["named_refs"]) | set(choice["other_glued_voice_refs"])
    threads = [_pack_thread(conn, gid, tid, focus_refs) for tid in selected]
    out_dir.mkdir(parents=True, exist_ok=True)
    originals = out_dir / "originals"
    originals.mkdir(exist_ok=True)
    index = []
    bodies = []
    original_n = 0
    for thread in threads:
        tid = thread["preview_thread_id"]
        focus = [m["evidence_ref"] for m in thread["messages"] if m.get("focus")]
        index.append(
            f"{tid} | msgs {len(thread['messages'])} | focus {','.join(focus) or 'none'}"
        )
        bodies.append(format_activation_thread(thread))
        for msg in thread["messages"]:
            ref = msg["evidence_ref"]
            header = [f"Evidence-ref: {ref}", f"Subject: {msg.get('subject') or ''}", ""]
            (originals / f"{ref}.txt").write_text(
                "\n".join(header) + str(msg.get("raw_body") or "") + "\n", encoding="utf-8"
            )
            original_n += 1
    (out_dir / "INDEX.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    (out_dir / "packet-001.txt").write_text("\n".join(bodies), encoding="utf-8")
    (out_dir / "README.txt").write_text(
        "Founder activation-review packet (private, gitignored).\n"
        "Open INDEX.txt, then packet-001.txt, then one originals/Evidence-ref.txt at a time.\n"
        "Required cases: T-2312-M-02 and T-2345-M-02 (glued Hotmail cut; Peggy authored preserved).\n"
        "Other FOCUS rows are representative Peggy glued-Hotmail voice admissions.\n"
        "At most 12 threads. TXT only. Do not commit this folder.\n"
        "Do not activate or publish from this packet.\n",
        encoding="utf-8",
    )
    return {
        "thread_count_written": len(threads),
        "original_files": original_n,
        "named_refs": choice["named_refs"],
        "other_focus_refs": choice["other_glued_voice_refs"],
        "other_glued_voice_count_total": choice["other_glued_voice_count_total"],
        "threads": selected,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        _allow()
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise ActivationReviewError("MEMORYBOX_DATABASE_URL_missing")
        try:
            refuse_live_dsn(dsn, None, allow_flightsim=True)
        except ProductionDSNError as exc:
            raise ActivationReviewError(str(exc)) from None
        out = os.environ.get("MEMORYBOX_I14_REVIEW_OUT", "").strip()
        if not out:
            raise ActivationReviewError("MEMORYBOX_I14_REVIEW_OUT_missing")
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=10) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            meta = write_activation_packet(conn, Path(out))
            conn.rollback()
        public = {
            "ok": True,
            "kind": "activation_review_packet",
            "thread_count_written": meta["thread_count_written"],
            "original_files": meta["original_files"],
            "named_refs_included": 2,
            "other_glued_voice_examples": len(meta["other_focus_refs"]),
            "other_glued_voice_count_total": meta["other_glued_voice_count_total"],
            "activation_called": False,
        }
        assert_counts_only(public)
        print(json.dumps(public, indent=2, sort_keys=True))
        return 0
    except ActivationReviewError as exc:
        print(json.dumps(failure_json(str(exc))))
        return 2
