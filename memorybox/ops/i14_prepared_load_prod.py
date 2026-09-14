"""Guarded unpublished household-email production load.

Requires explicit env flags. Never activates or publishes. Never mutates evidence.
Private generation id and review bodies stay out of Git.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from memorybox.migrate import applied_versions, pending
from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import assert_counts_only, emit_progress, failure_json
from memorybox.ops.i14_peggy_preview import load_identity_ledger
from memorybox.ops.i14_preload_census import (
    assigned_source_ids,
    classify_mbox_sources,
    load_messages_keyset,
    run_census,
)
from memorybox.ops.i14_prepared_loader import LoaderError, run_load
from memorybox.ops.i14_thread_review import (
    evidence_ref,
    format_thread_txt,
    index_line,
)

CONFIRM = "household-email-unpublished-v1"
REQUIRED_LEDGER = 37
ACCEPTED = {
    "mbox_rows": 91281,
    "assigned_rows": 91275,
    "prepared_messages": 91247,
    "identity_duplicates_omitted": 26,
    "excluded_missing_from": 2,
    "held_rows": 6,
    "unexplained": 0,
    "threads": 40996,
    "max_thread_size": 89,
}
HOUSEHOLD_PACKET_CASES = (
    "peggy_from_voice",
    "sue_from_voice",
    "tom_from_voice",
    "unknown_from",
    "commercial_retain",
    "commercial_suppress",
    "commercial_uncertain",
    "attachment",
    "forward",
    "quote_cleanup",
    "high_quote_risk",
    "multiple_participants",
)
MAX_PACKET_THREADS = 12


class LoadProdError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _require_flags() -> None:
    if not _env_on("MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM"):
        raise LoadProdError("load_flightsim_not_allowed")
    if not _env_on("MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB"):
        raise LoadProdError("load_memorybox_db_not_allowed")
    if os.environ.get("MEMORYBOX_I14_LOAD_CONFIRM", "").strip() != CONFIRM:
        raise LoadProdError("load_confirm_mismatch")


def _empty_counts(conn: Any) -> dict[str, int]:
    names = [
        "comms_logical_sources",
        "comms_source_memberships",
        "comms_extract_instances",
        "comms_source_checkpoint",
        "comms_record_identities",
        "comms_record_identity_aliases",
        "comms_prepared_generations",
        "comms_prepared_threads",
        "comms_prepared_messages",
        "comms_prepared_participants",
        "comms_prepared_attachments",
    ]
    out: dict[str, int] = {}
    for name in names:
        out[name] = int(conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"])
    out["active_generations"] = int(
        conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_active_generations").fetchone()["n"]
    )
    return out


def _assert_pre_empty(counts: dict[str, int]) -> None:
    if any(int(v) != 0 for v in counts.values()):
        raise LoadProdError("lineage_or_prepared_not_empty")


def _structural_from_census(census: dict[str, Any]) -> dict[str, int]:
    forecast = census.get("forecast") or {}
    complete = census.get("completeness") or {}
    mbox = census.get("mbox_inventory") or {}
    excluded = forecast.get("excluded_reasons") or {}
    return {
        "mbox_rows": int(complete.get("mbox_rows") or mbox.get("mbox_rows") or 0),
        "assigned_rows": int(forecast.get("eligible_assigned_rows") or mbox.get("assigned_rows") or 0),
        "prepared_messages": int(forecast.get("prepared_messages") or 0),
        "identity_duplicates_omitted": int(forecast.get("identity_duplicates_omitted") or 0),
        "excluded_missing_from": int(excluded.get("missing_from") or 0),
        "held_rows": int(complete.get("held_rows") or mbox.get("held_rows") or 0),
        "unexplained": int(complete.get("unexplained") or 0),
        "threads": int(forecast.get("threads") or 0),
        "max_thread_size": int(forecast.get("max_thread_size") or 0),
    }


def _agree(actual: dict[str, int], expected: dict[str, int]) -> list[str]:
    diffs = []
    for key, want in expected.items():
        got = int(actual.get(key) or 0)
        if got != want:
            diffs.append(f"{key}:{got}!={want}")
    return diffs


def _ledger(conn: Any) -> Any:
    row = conn.execute(
        """
        SELECT p.id::text AS pid, COALESCE(p.display_name, '') AS n
          FROM people p
         WHERE p.status <> 'merged_away'
         ORDER BY p.display_name
         LIMIT 1
        """
    ).fetchone()
    if not row:
        raise LoadProdError("no_people_for_ledger")
    return load_identity_ledger(
        conn, focal_person_id=str(row["pid"]), focal_label=str(row["n"] or "Person")
    )


def post_load_validation(conn: Any, gid: Any, *, held_rows: int) -> dict[str, Any]:
    def n(sql: str, params: tuple | None = None) -> int:
        row = conn.execute(sql, params) if params else conn.execute(sql)
        return int(row.fetchone()["n"])

    lineage = {
        "comms_logical_sources": n("SELECT COUNT(*) AS n FROM comms_logical_sources"),
        "comms_extract_instances": n("SELECT COUNT(*) AS n FROM comms_extract_instances"),
        "comms_record_identities": n("SELECT COUNT(*) AS n FROM comms_record_identities"),
        "comms_record_identity_aliases": n(
            "SELECT COUNT(*) AS n FROM comms_record_identity_aliases"
        ),
        "comms_source_memberships": n("SELECT COUNT(*) AS n FROM comms_source_memberships"),
        "comms_source_checkpoint": n("SELECT COUNT(*) AS n FROM comms_source_checkpoint"),
    }
    prepared = {
        "generations": n("SELECT COUNT(*) AS n FROM comms_prepared_generations"),
        "threads": n(
            "SELECT COUNT(*) AS n FROM comms_prepared_threads WHERE generation_id = %s",
            (gid,),
        ),
        "messages": n(
            "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
            (gid,),
        ),
        "participants": n(
            """
            SELECT COUNT(*) AS n FROM comms_prepared_participants p
              JOIN comms_prepared_messages m ON m.id = p.message_id
             WHERE m.generation_id = %s
            """,
            (gid,),
        ),
        "attachments": n(
            """
            SELECT COUNT(*) AS n FROM comms_prepared_attachments a
              JOIN comms_prepared_messages m ON m.id = a.message_id
             WHERE m.generation_id = %s
            """,
            (gid,),
        ),
    }
    identity = {
        r["identity_confidence"]: int(r["n"])
        for r in conn.execute(
            """
            SELECT p.identity_confidence, COUNT(*)::int AS n
              FROM comms_prepared_participants p
              JOIN comms_prepared_messages m ON m.id = p.message_id
             WHERE m.generation_id = %s
             GROUP BY p.identity_confidence
            """,
            (gid,),
        ).fetchall()
    }
    commercial = {
        r["commercial_class"]: int(r["n"])
        for r in conn.execute(
            """
            SELECT commercial_class, COUNT(*)::int AS n
              FROM comms_prepared_messages
             WHERE generation_id = %s
             GROUP BY commercial_class
            """,
            (gid,),
        ).fetchall()
    }
    quote = {
        r["quote_quality"]: int(r["n"])
        for r in conn.execute(
            """
            SELECT quote_quality, COUNT(*)::int AS n
              FROM comms_prepared_messages
             WHERE generation_id = %s
             GROUP BY quote_quality
            """,
            (gid,),
        ).fetchall()
    }
    voice = []
    for r in conn.execute(
        """
        SELECT COALESCE(pe.display_name, 'unknown') AS person_label, COUNT(*)::int AS n
          FROM comms_prepared_messages m
          JOIN comms_prepared_participants p
            ON p.message_id = m.id AND p.role = 'from'
          LEFT JOIN people pe ON pe.id = p.person_id
         WHERE m.generation_id = %s AND m.voice_corpus
         GROUP BY COALESCE(pe.display_name, 'unknown')
         ORDER BY COUNT(*) DESC, 1
        """,
        (gid,),
    ).fetchall():
        label = str(r["person_label"] or "unknown").split()[0]
        voice.append({"person_label": label, "messages": int(r["n"])})
    omitted = n(
        """
        SELECT COALESCE(SUM(duplicate_omitted_count),0)::int AS n
          FROM comms_prepared_threads WHERE generation_id = %s
        """,
        (gid,),
    )
    omitted_with_lineage = n(
        """
        SELECT COUNT(*) AS n
          FROM comms_record_identity_aliases
         WHERE identity_method IN ('content_hash', 'rfc_message_id')
        """
    )
    published = n(
        "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE published"
    )
    active = n("SELECT COUNT(*) AS n FROM comms_prepared_active_generations")
    gen = conn.execute(
        """
        SELECT status, published, is_active FROM comms_prepared_generations WHERE id = %s
        """,
        (gid,),
    ).fetchone()
    unexplained = 0
    prepared_n = prepared["messages"]
    completeness = {
        "equation": (
            "mbox_rows = prepared + identity_duplicates_omitted + "
            "excluded_in_assigned_stream + held_rows + unexplained"
        ),
        "mbox_rows": ACCEPTED["mbox_rows"],
        "prepared": prepared_n,
        "identity_duplicates_omitted": omitted,
        "excluded_in_assigned_stream": ACCEPTED["excluded_missing_from"],
        "held_rows": held_rows,
        "unexplained": unexplained,
        "check": (
            ACCEPTED["mbox_rows"]
            == prepared_n + omitted + ACCEPTED["excluded_missing_from"] + held_rows + unexplained
        ),
    }
    return {
        "lineage": lineage,
        "prepared": prepared,
        "participant_identity": identity,
        "commercial_classes": commercial,
        "quote_quality": quote,
        "authored_voice_by_from_person": voice,
        "duplicate_omitted_count": omitted,
        "identity_alias_rows": omitted_with_lineage,
        "published_generations": published,
        "active_generations": active,
        "generation_status": str(gen["status"] if gen else ""),
        "generation_published": bool(gen["published"]) if gen else True,
        "generation_active": bool(gen["is_active"]) if gen else True,
        "completeness": completeness,
    }


def _pick_thread_id(conn: Any, gid: Any, sql: str, params: tuple) -> str | None:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    return str(row["display_id"])


def select_loaded_packet_ids(conn: Any, gid: Any) -> dict[str, str]:
    coverage: dict[str, str] = {}
    queries = {
        "peggy_from_voice": (
            """
            SELECT t.display_id
              FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE t.generation_id = %s AND m.voice_corpus
               AND lower(pe.display_name) LIKE 'peggy%%'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "sue_from_voice": (
            """
            SELECT t.display_id
              FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE t.generation_id = %s AND m.voice_corpus
               AND lower(pe.display_name) LIKE 'sue%%'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "tom_from_voice": (
            """
            SELECT t.display_id
              FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE t.generation_id = %s AND m.voice_corpus
               AND lower(pe.display_name) LIKE 'tom%%'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "unknown_from": (
            """
            SELECT t.display_id
              FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
             WHERE t.generation_id = %s AND p.person_id IS NULL
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "commercial_retain": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
             WHERE t.generation_id = %s AND m.commercial_class = 'retain_life_evidence'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "commercial_suppress": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
             WHERE t.generation_id = %s AND m.commercial_class = 'suppress_default'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "commercial_uncertain": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
             WHERE t.generation_id = %s AND m.commercial_class = 'uncertain'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "attachment": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
              JOIN comms_prepared_attachments a ON a.message_id = m.id
             WHERE t.generation_id = %s
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "forward": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
             WHERE t.generation_id = %s AND m.forward_status <> 'none'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "quote_cleanup": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
             WHERE t.generation_id = %s AND m.urls_stripped AND m.quote_quality = 'clean'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "high_quote_risk": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
             WHERE t.generation_id = %s AND m.quote_quality = 'suspected_contamination'
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
        "multiple_participants": (
            """
            SELECT t.display_id FROM comms_prepared_threads t
              JOIN comms_prepared_messages m ON m.thread_id = t.id
              JOIN comms_prepared_participants p ON p.message_id = m.id
             WHERE t.generation_id = %s
             GROUP BY t.display_id, t.message_count
            HAVING COUNT(DISTINCT p.address_normalized) >= 3
             ORDER BY t.message_count, t.display_id LIMIT 1
            """,
            (gid,),
        ),
    }
    seen: list[str] = []
    for case in HOUSEHOLD_PACKET_CASES:
        sql, params = queries[case]
        tid = _pick_thread_id(conn, gid, sql, params)
        if not tid:
            coverage[case] = "not_present_in_corpus"
            continue
        coverage[case] = tid
        if tid not in seen and len(seen) < MAX_PACKET_THREADS:
            seen.append(tid)
        elif tid not in seen:
            coverage[case] = "omitted_packet_thread_limit"
    coverage["_selected"] = ",".join(seen)
    return coverage


def write_loaded_review_packet(conn: Any, gid: Any, out_dir: Path) -> dict[str, Any]:
    from memorybox.ops.i14_thread_review import ReviewError

    coverage = select_loaded_packet_ids(conn, gid)
    selected = [x for x in str(coverage.pop("_selected", "")).split(",") if x]
    if len(selected) > MAX_PACKET_THREADS:
        raise ReviewError("packet_thread_limit")
    threads = []
    for display_id in selected:
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
        packed_msgs = []
        for msg in msgs:
            payload = msg.get("payload_json") or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
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
                    "person_id": party["person_id"],
                }
                if party["role"] == "from":
                    from_p.append(item)
                elif party["role"] == "to":
                    to_p.append(item)
                else:
                    cc_p.append(item)
            atts = conn.execute(
                """
                SELECT filename, mime_type, gallery_action
                  FROM comms_prepared_attachments WHERE message_id = %s
                 ORDER BY attachment_ordinal
                """,
                (msg["id"],),
            ).fetchall()
            packed_msgs.append(
                {
                    "timestamp": msg["sent_at"].isoformat() if hasattr(msg["sent_at"], "isoformat") else str(msg["sent_at"]),
                    "subject": msg["subject"],
                    "from_parties": from_p,
                    "to_parties": to_p,
                    "cc_parties": cc_p,
                    "cleaned_body": msg["cleaned_authored_text"],
                    "raw_body": payload.get("body_text") or payload.get("body") or "",
                    "body": payload.get("body_text") or payload.get("body") or "",
                    "authorship_label": msg["authorship"],
                    "voice_corpus": msg["voice_corpus"],
                    "commercial_class": msg["commercial_class"],
                    "attachment_meta": [dict(a) for a in atts],
                    "forward_block": msg["forward_block"],
                    "forward_omitted": msg["forward_omitted"],
                }
            )
        threads.append(
            {
                "preview_thread_id": display_id,
                "person_pilot": 0,
                "messages": packed_msgs,
                "threading_confidence": trow["threading_confidence"],
                "identity_confidence": trow["identity_confidence"],
                "duplicate_omitted": trow["duplicate_omitted_count"],
                "source_evidence_count": trow["evidence_count"],
                "cases": [k for k, v in coverage.items() if v == display_id],
                "commercial_summary": trow["gallery_eligibility"],
                "warnings": [],
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    originals = out_dir / "originals"
    originals.mkdir(exist_ok=True)
    packet = "\n".join(format_thread_txt(t) for t in threads)
    (out_dir / "INDEX.txt").write_text(
        "\n".join(index_line(t) for t in threads) + ("\n" if threads else ""),
        encoding="utf-8",
    )
    (out_dir / "packet-001.txt").write_text(packet, encoding="utf-8")
    (out_dir / "README.txt").write_text(
        "Household-email unpublished load review (private, gitignored).\n"
        "Open INDEX.txt, then packet-001.txt, then one originals/Evidence-ref.txt at a time.\n"
        "At most 12 threads. Do not commit this folder.\n",
        encoding="utf-8",
    )
    original_n = 0
    for thread in threads:
        tid = str(thread["preview_thread_id"])
        for i, msg in enumerate(thread["messages"], start=1):
            header = [
                f"Evidence-ref: {evidence_ref(tid, i)}",
                f"Subject: {msg.get('subject') or ''}",
                "",
            ]
            text = "\n".join(header) + str(msg.get("raw_body") or "") + "\n"
            (originals / f"{evidence_ref(tid, i)}.txt").write_text(text, encoding="utf-8")
            original_n += 1
    return {
        "thread_count_written": len(threads),
        "original_files": original_n,
        "representative_coverage": coverage,
        "packet_bytes": (out_dir / "packet-001.txt").stat().st_size,
    }


def run_production_load(conn: Any, dsn: str, *, deadline_s: int) -> dict[str, Any]:
    started = time.monotonic()
    deadline_mono = started + max(1, int(deadline_s))
    applied = applied_versions()
    pending_files = pending()
    if pending_files:
        raise LoadProdError("pending_not_empty")
    if len(applied) != REQUIRED_LEDGER:
        raise LoadProdError("ledger_not_001_037")
    last = applied[-1]["filename"] if applied else ""
    if last != "037_p2_i14_prepared_evidence_ref_scale.sql":
        raise LoadProdError("ledger_last_not_037")
    empty = _empty_counts(conn)
    _assert_pre_empty(empty)
    evidence_before = int(conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"])
    sources_before = int(conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"])
    rfc_before = int(conn.execute("SELECT COUNT(*) AS n FROM communication_rfc_ids").fetchone()["n"])
    emit_progress({"stage": "preflight_census"})
    remaining = max(1, int(deadline_mono - time.monotonic()))
    threshold = int(os.environ.get("MEMORYBOX_I14_ASSIGN_THRESHOLD", "1000"))
    census = run_census(
        conn,
        run_deadline_s=min(900, remaining),
        include_duplicate_audit=False,
        assign_threshold=threshold,
    )
    conn.rollback()
    structural = _structural_from_census(census)
    diffs = _agree(structural, ACCEPTED)
    if diffs:
        raise LoadProdError("preflight_forecast_mismatch:" + ",".join(diffs))
    source_ids = assigned_source_ids(conn, assign_threshold=threshold)
    messages = load_messages_keyset(
        conn,
        source_ids,
        batch_size=2000,
        statement_timeout="30s",
        deadline_mono=deadline_mono,
        started=started,
    )
    ledger = _ledger(conn)
    emit_progress({"stage": "load_start", "loaded": len(messages)})
    result = run_load(
        conn,
        messages,
        ledger,
        dsn=dsn,
        allow_live=True,
        persist_batches=True,
        batch_threads=200,
        deadline_mono=deadline_mono,
        on_progress=lambda ev: emit_progress(ev),
    )
    if result.get("activation_called") or result.get("published") or result.get("is_active"):
        raise LoadProdError("activation_or_publish_refused")
    gid = result["generation_id"]
    held = int(structural["held_rows"])
    validation = post_load_validation(conn, gid, held_rows=held)
    if validation["published_generations"] != 0 or validation["active_generations"] != 0:
        raise LoadProdError("generation_not_unpublished")
    if validation["generation_status"] != "validated":
        raise LoadProdError("generation_not_validated")
    if not validation["completeness"]["check"]:
        raise LoadProdError("completeness_failed")
    evidence_after = int(conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"])
    sources_after = int(conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"])
    rfc_after = int(conn.execute("SELECT COUNT(*) AS n FROM communication_rfc_ids").fetchone()["n"])
    if (evidence_after, sources_after, rfc_after) != (evidence_before, sources_before, rfc_before):
        raise LoadProdError("evidence_or_sources_changed")
    actual = {
        "mbox_rows": ACCEPTED["mbox_rows"],
        "assigned_rows": ACCEPTED["assigned_rows"],
        "prepared_messages": validation["prepared"]["messages"],
        "identity_duplicates_omitted": validation["duplicate_omitted_count"],
        "excluded_missing_from": ACCEPTED["excluded_missing_from"],
        "held_rows": held,
        "unexplained": 0,
        "threads": validation["prepared"]["threads"],
        "max_thread_size": int(
            conn.execute(
                """
                SELECT COALESCE(MAX(message_count),0) AS n
                  FROM comms_prepared_threads WHERE generation_id = %s
                """,
                (gid,),
            ).fetchone()["n"]
        ),
    }
    recon_diffs = _agree(actual, ACCEPTED)
    private: dict[str, Any] = {"generation_id": gid}
    review_meta = None
    review_out = os.environ.get("MEMORYBOX_I14_REVIEW_OUT", "").strip()
    if review_out:
        if os.environ.get("MEMORYBOX_I14_REVIEW_EMIT_PRIVATE", "").strip() != "1":
            raise LoadProdError("private_review_emit_not_authorized")
        review_meta = write_loaded_review_packet(conn, gid, Path(review_out))
        private["review_out"] = review_out
        private["review_threads"] = review_meta["thread_count_written"]
        private["review_coverage"] = {
            k: ("present" if str(v).startswith("T-") else v)
            for k, v in (review_meta.get("representative_coverage") or {}).items()
        }
    public = {
        "ok": True,
        "kind": "household_email_unpublished_load",
        "activation_called": False,
        "published_generations": 0,
        "active_generations": 0,
        "ledger_n": REQUIRED_LEDGER,
        "pending": [],
        "preflight": structural,
        "accepted_forecast": ACCEPTED,
        "actual": actual,
        "reconciliation_diffs": recon_diffs,
        "lineage": validation["lineage"],
        "prepared": validation["prepared"],
        "participant_identity": validation["participant_identity"],
        "commercial_classes": validation["commercial_classes"],
        "quote_quality": validation["quote_quality"],
        "authored_voice_by_from_person": validation["authored_voice_by_from_person"],
        "duplicate_omitted_count": validation["duplicate_omitted_count"],
        "completeness": validation["completeness"],
        "baseline": {
            "evidence": evidence_after,
            "sources": sources_after,
            "communication_rfc_ids": rfc_after,
        },
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "review_thread_count": None if not review_meta else review_meta["thread_count_written"],
        "review_coverage_present": None
        if not review_meta
        else sorted(
            k
            for k, v in (private.get("review_coverage") or {}).items()
            if str(v) == "present" or str(v).startswith("T-")
        ),
    }
    assert_counts_only(public)
    return {"public": public, "private": private}


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        _require_flags()
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise LoadProdError("MEMORYBOX_DATABASE_URL_missing")
        try:
            refuse_live_dsn(dsn, None, allow_flightsim=True)
        except ProductionDSNError as exc:
            raise LoadProdError(str(exc)) from None
        deadline_s = int(os.environ.get("MEMORYBOX_I14_LOAD_DEADLINE_S", "7200"))
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=10) as conn:
            packed = run_production_load(conn, dsn, deadline_s=deadline_s)
        public = packed["public"]
        private = packed["private"]
        private_out = os.environ.get("MEMORYBOX_I14_LOAD_PRIVATE_OUT", "").strip()
        if private_out:
            Path(private_out).parent.mkdir(parents=True, exist_ok=True)
            Path(private_out).write_text(
                json.dumps(private, indent=2, sort_keys=True), encoding="utf-8"
            )
        public_out = os.environ.get("MEMORYBOX_I14_LOAD_PUBLIC_OUT", "").strip()
        blob = json.dumps(public, indent=2, sort_keys=True)
        if public_out:
            Path(public_out).write_text(blob, encoding="utf-8")
        else:
            print(blob)
        return 0
    except (LoadProdError, LoaderError) as exc:
        print(json.dumps(failure_json(str(exc))))
        return 2
