"""Household-email prepared generation loader.

Never activates or publishes. Never updates evidence. Disposable runs refuse
FlightSim and dbname memorybox and roll back the whole generation. Production
loads require explicit allow flags, persist building batches, and mark the
generation failed (unpublished, inactive) if a batch cannot finish.

One household-email generation stores each message once. Authored voice is any
authenticated From Person with clean quote quality, not one focal Person.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from memorybox.ingest.comms_lineage import normalize_rfc_message_id
from memorybox.ops.i14_consolidation import RULE_ID, consolidate_messages
from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_peggy_preview import cluster_threads, _compact_thread_messages
from memorybox.ops.i14_thread_review import (
    AUTH_OTHER,
    AUTH_PEGGY,
    UNVERIFIED,
    IdentityLedger,
    annotate_messages,
    evidence_ref,
    format_display_id,
    gallery_attachment_action,
    message_sort_key,
    parse_sent_at,
)

ALGO_VERSION = "i14-prepared-email-v1"
MISSING_TS = datetime(1970, 1, 1, tzinfo=timezone.utc)
HTTP_SUBSTRING = re.compile(r"(?i)https?://\S*")

AUTH_MAP = {
    AUTH_PEGGY: "authenticated_focal",
    AUTH_OTHER: "authenticated_other",
    UNVERIFIED: "unverified",
}
DIR_MAP = {
    "sent_by_authenticated_peggy": "sent_by_focal",
    "sent_to_peggy_authored_other": "sent_to_focal_other_author",
    "no_authenticated_peggy_participation": "no_focal",
    "peggy_unresolved_direction": "unresolved",
}
COMMERCIAL_MAP = {
    "commercial_retain": "retain_life_evidence",
    "commercial_suppress": "suppress_default",
    "commercial_uncertain": "uncertain",
    "not_commercial": "not_commercial",
    "retain_life_evidence": "retain_life_evidence",
    "suppress_default": "suppress_default",
    "uncertain": "uncertain",
}


class LoaderError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _dbname(conn: Any, dsn: str | None = None, *, allow_live: bool = False) -> str:
    row = conn.execute("SELECT current_database() AS d").fetchone()
    name = str(row["d"] if isinstance(row, dict) else row[0])
    info = getattr(conn, "info", None)
    host = str(getattr(info, "host", "") or "") if info is not None else ""
    blob = dsn or host
    try:
        refuse_live_dsn(blob, None if allow_live else name, allow_flightsim=allow_live)
    except ProductionDSNError as exc:
        raise LoaderError(str(exc)) from None
    if str(name).lower() == "memorybox" and not allow_live:
        raise LoaderError("refused_memorybox_dbname")
    return name


def _deadline_guard(deadline_mono: float | None) -> None:
    if deadline_mono is not None and time.monotonic() >= deadline_mono:
        raise LoaderError("run_deadline")


def mark_generation_failed(conn: Any, gid: Any) -> None:
    """Unusable failed generation. Never published or active."""
    conn.execute(
        """
        UPDATE comms_prepared_generations
           SET status = 'failed', published = FALSE, is_active = FALSE, updated_at = now()
         WHERE id = %s AND NOT published AND NOT is_active
        """,
        (gid,),
    )


def _quote_quality(msg: dict[str, Any]) -> str:
    residue = msg.get("residue_class") or msg.get("clean_method")
    authored = str(msg.get("cleaned_body") or "")
    from memorybox.ops.i14_prepared_text import classify_residue

    if classify_residue(authored):
        return "suspected_contamination"
    if residue in {"hotmail_date_subject_from_to", "on_wrote", "original_message"}:
        return "suspected_contamination"
    return "clean"


def _forward_fields(msg: dict[str, Any]) -> tuple[str, str, str]:
    omitted = str(msg.get("forward_omitted") or "")
    block = str(msg.get("forward_block") or "")
    if omitted == "commercial_suppress" or omitted == "commercial_body_omitted":
        return "omitted_duplicate", "commercial_body_omitted", ""
    if omitted == "duplicate_of_thread_message" or omitted == "relay_history_omitted":
        reason = "duplicate_of_thread_message" if "duplicate" in omitted else "relay_history_omitted"
        status = "relay" if reason == "relay_history_omitted" else "omitted_duplicate"
        return status, reason, ""
    if block.strip():
        return "new_forward", "", block
    return "none", "", ""


def _thread_gallery(msgs: list[dict[str, Any]]) -> tuple[str, str]:
    classes = [str(m.get("commercial_class") or "not_commercial") for m in msgs]
    if classes and all(c == "suppress_default" for c in classes):
        return "suppress_default", "commercial_suppress_default"
    if any(c == "uncertain" for c in classes) and not any(c == "retain_life_evidence" for c in classes):
        return "hold_uncertain", ""
    return "show_by_default", ""


def _thread_identity(msgs: list[dict[str, Any]]) -> str:
    auths = [str(m.get("authorship") or UNVERIFIED) for m in msgs]
    mapped = [AUTH_MAP.get(a, a) for a in auths]
    if mapped and all(a != "unverified" for a in mapped):
        return "all_authenticated"
    if mapped and all(a == "unverified" for a in mapped):
        return "unverified_present"
    return "mixed"


def _threading_confidence(msgs: list[dict[str, Any]]) -> str:
    has_rfc = any(m.get("rfc_message_id") for m in msgs)
    has_vendor = any(m.get("vendor_thread_id") or m.get("stored_thread_id") for m in msgs)
    unthreaded = any(m.get("thread_status") == "unthreaded" or not m.get("rfc_message_id") for m in msgs)
    if has_rfc and has_vendor:
        return "vendor+rfc"
    if has_rfc:
        return "rfc"
    if has_vendor:
        return "vendor"
    if unthreaded:
        return "mixed_unthreaded"
    return "unknown"


def _checksum(ids: list[Any]) -> str:
    blob = "\n".join(sorted(str(i) for i in ids)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _ensure_logical(conn: Any) -> UUID:
    row = conn.execute(
        """
        INSERT INTO comms_logical_sources (logical_key, source_kind, label)
        VALUES ('household_email', 'email', 'Household email')
        ON CONFLICT (source_kind, logical_key) DO UPDATE
           SET label = EXCLUDED.label
        RETURNING id
        """
    ).fetchone()
    return row["id"] if isinstance(row, dict) else row[0]


def _ensure_memberships(conn: Any, logical_id: UUID, source_ids: set[Any]) -> None:
    for sid in source_ids:
        conn.execute(
            """
            INSERT INTO comms_source_memberships (source_id, logical_source_id)
            VALUES (%s, %s)
            ON CONFLICT (source_id) DO NOTHING
            """,
            (sid, logical_id),
        )


def _ensure_extract(conn: Any, logical_id: UUID, source_id: Any) -> UUID:
    fingerprint = hashlib.sha256(f"{ALGO_VERSION}:{logical_id}:{source_id}".encode()).hexdigest()
    row = conn.execute(
        """
        INSERT INTO comms_extract_instances (
          logical_source_id, source_id, fingerprint, landing_alias, landing_basename,
          validation_status, ingest_status
        ) VALUES (%s, %s, %s, 'household_email', 'synthetic.mbox', 'valid', 'ingested')
        ON CONFLICT (logical_source_id, fingerprint) DO UPDATE
           SET ingest_status = comms_extract_instances.ingest_status
        RETURNING id
        """,
        (logical_id, source_id, fingerprint),
    ).fetchone()
    return row["id"] if isinstance(row, dict) else row[0]


def _ensure_canonical(
    conn: Any, *, logical_id: UUID, extract_id: UUID, evidence_id: Any, rfc: str | None, digest: str
) -> UUID:
    existing = conn.execute(
        "SELECT id FROM comms_record_identities WHERE evidence_id = %s",
        (evidence_id,),
    ).fetchone()
    if existing:
        cid = existing["id"] if isinstance(existing, dict) else existing[0]
    else:
        rec = conn.execute(
            """
            INSERT INTO comms_record_identities (
              logical_source_id, evidence_id, source_kind, first_extract_instance_id
            ) VALUES (%s, %s, 'email', %s)
            RETURNING id
            """,
            (logical_id, evidence_id, extract_id),
        ).fetchone()
        cid = rec["id"] if isinstance(rec, dict) else rec[0]
    aliases: list[tuple[str, str, str]] = []
    if digest and len(digest) == 64:
        aliases.append(("email_full_sha256", digest, "fallback_hash"))
    if rfc and len(rfc) >= 3:
        aliases.append(("email_rfc_message_id", rfc[:700], "rfc_message_id"))
    for method, key, native in aliases:
        conn.execute(
            """
            INSERT INTO comms_record_identity_aliases (
              canonical_record_id, logical_source_id, identity_method, record_key, native_id_class
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (logical_source_id, identity_method, record_key) DO NOTHING
            """,
            (cid, logical_id, method, key, native),
        )
    return cid


def _from_is_authenticated_person(msg: dict[str, Any]) -> bool:
    """Authored voice is household-wide: any confirmed From Person, not one focal."""
    for party in msg.get("from_parties") or []:
        pid = str(party.get("person_id") or "").strip()
        status = str(party.get("status") or UNVERIFIED)
        if pid and status != UNVERIFIED:
            return True
    return False


def _schema_message_fields(msg: dict[str, Any]) -> dict[str, Any]:
    from_auth = _from_is_authenticated_person(msg)
    authorship_raw = str(msg.get("authorship") or UNVERIFIED)
    if from_auth:
        authorship = "authenticated_focal"
    else:
        authorship = AUTH_MAP.get(authorship_raw, "unverified")
        if authorship == "authenticated_other":
            authorship = "unverified"
    identity_quality = "resolved" if authorship != "unverified" else "unverified"
    if msg.get("ambiguous_participant") and authorship != "unverified":
        identity_quality = "uncertain"
    quote = _quote_quality(msg)
    commercial = COMMERCIAL_MAP.get(str(msg.get("commercial_class") or "not_commercial"), "not_commercial")
    direction = DIR_MAP.get(str(msg.get("direction") or ""), "unresolved")
    # Household authored voice is authenticated From + clean quote.
    # Unverified To/Cc keep identity_quality uncertain (thread mix) but must not
    # strip the From Person's voice. Census counted that way (12071/1342/307).
    voice = from_auth and quote == "clean"
    fwd_status, fwd_omitted, fwd_block = _forward_fields(msg)
    sent = parse_sent_at(str(msg.get("timestamp") or msg.get("sent_at") or "")) or MISSING_TS
    from memorybox.ops.i14_prepared_text import sanitize_prepared

    cleaned, url_a = sanitize_prepared(str(msg.get("cleaned_body") or ""))
    fwd_block, url_f = sanitize_prepared(fwd_block)
    cleaned2 = HTTP_SUBSTRING.sub("", cleaned)
    fwd2 = HTTP_SUBSTRING.sub("", fwd_block)
    if fwd_status == "none":
        fwd2 = ""
        fwd_omitted = ""
    urls = bool(msg.get("urls_stripped")) or url_a or url_f or cleaned2 != cleaned or fwd2 != fwd_block
    return {
        "authorship": authorship,
        "identity_quality": identity_quality,
        "quote_quality": quote,
        "commercial_class": commercial,
        "direction": direction,
        "voice_corpus": voice,
        "forward_status": fwd_status,
        "forward_omitted": fwd_omitted,
        "forward_block": fwd2,
        "sent_at": sent,
        "cleaned": cleaned2,
        "urls_stripped": urls,
        "subject": str(msg.get("subject") or ""),
    }


def forecast_prepared_counts(
    messages: list[dict[str, Any]],
    ledger: IdentityLedger,
    *,
    deadline_mono: float | None = None,
    on_progress: Any = None,
    sequential_quote_prior: bool = True,
) -> dict[str, Any]:
    """Counts-only reconstruction. Never writes. Evidence rows are not mutated."""
    import time

    from memorybox.ops.i14_thread_review import extract_parties

    def _guard() -> None:
        _deadline_guard(deadline_mono)

    _guard()
    partition = consolidate_messages(messages)
    omitted_lineage = 0
    omitted_missing_survivor = 0
    for dup in partition["duplicates"]:
        if dup.get("duplicate_of"):
            omitted_lineage += 1
        else:
            omitted_missing_survivor += 1
    prepared_in: list[dict[str, Any]] = []
    missing_from = 0
    for msg in partition["displayed"]:
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        from_rows = extract_parties(payload, msg)["from"]
        if not from_rows:
            missing_from += 1
            continue
        prepared_in.append(msg)
    clustered = cluster_threads(prepared_in) if prepared_in else {}
    threads: dict[str, list[dict[str, Any]]] = {}
    for msg in prepared_in:
        threads.setdefault(clustered[str(msg["evidence_id"])], []).append(msg)
    commercial_counts = {
        "retain_life_evidence": 0,
        "suppress_default": 0,
        "uncertain": 0,
        "not_commercial": 0,
    }
    participants = 0
    authenticated_participants = 0
    unverified_participants = 0
    attachments = 0
    voice_n = 0
    quote_flags = 0
    voice_by_label: dict[str, int] = {}
    sizes = [len(members) for members in threads.values()]
    annotated_rows: list[dict[str, Any]] = []
    if sequential_quote_prior:
        done = 0
        for members in threads.values():
            _guard()
            compacted = _compact_thread_messages(members)
            annotated_rows.extend(annotate_messages(compacted, ledger))
            done += 1
            if on_progress and done % 50 == 0:
                on_progress({"stage": "forecast_threads", "threads_done": done})
    else:
        from memorybox.ops.i14_prepared_text import prepare_message_text

        prepared_text: list[dict[str, Any]] = []
        for i, msg in enumerate(prepared_in):
            _guard()
            raw = str(msg.get("raw_body") or msg.get("body") or "")
            prep = prepare_message_text(
                raw,
                subject=str(msg.get("subject") or ""),
                prior_authored=[],
            )
            row = dict(msg)
            row["cleaned_body"] = prep.authored
            row["forward_block"] = prep.forward_block
            row["quoted_removed"] = prep.quote_history_removed
            row["clean_method"] = prep.method
            row["forward_omitted"] = prep.forward_omitted
            prepared_text.append(row)
            if on_progress and i and i % 2000 == 0:
                on_progress({"stage": "forecast_clean", "cleaned": i})
        annotated_rows = annotate_messages(prepared_text, ledger)
    for row in annotated_rows:
        fields = _schema_message_fields(row)
        commercial_counts[fields["commercial_class"]] = (
            commercial_counts.get(fields["commercial_class"], 0) + 1
        )
        if fields["voice_corpus"]:
            voice_n += 1
        if fields["quote_quality"] != "clean":
            quote_flags += 1
        from_ok = False
        for role, rows in (
            ("from", row.get("from_parties") or []),
            ("to", row.get("to_parties") or []),
            ("cc", row.get("cc_parties") or []),
        ):
            for party in rows or []:
                addr = str(party.get("address") or "").strip()
                if not addr:
                    continue
                if role == "from" and from_ok:
                    continue
                if role == "from":
                    from_ok = True
                participants += 1
                status = AUTH_MAP.get(str(party.get("status") or UNVERIFIED), "unverified")
                if status == "unverified":
                    unverified_participants += 1
                else:
                    authenticated_participants += 1
                if role == "from" and fields["voice_corpus"]:
                    label = str(party.get("label") or "confirmed_person").split()[0]
                    if not label or "@" in label:
                        label = "confirmed_person"
                    voice_by_label[label] = voice_by_label.get(label, 0) + 1
        attachments += len(row.get("attachment_meta") or [])
        row.pop("raw_body", None)
        row.pop("body", None)
        row.pop("cleaned_body", None)
        row.pop("forward_block", None)
        if isinstance(row.get("payload"), dict):
            row["payload"] = {}
    sizes_sorted = sorted(sizes)
    over_99 = sum(1 for n in sizes if n > 99)
    excluded_reasons = {
        "spam_or_trash": sum(
            1 for m in partition["excluded"] if m.get("exclude_reason") == "spam_or_trash"
        ),
        "malformed": sum(
            1 for m in partition["excluded"] if m.get("exclude_reason") == "malformed"
        ),
        "missing_from": missing_from,
    }
    eligible = len(partition["eligible"])
    prepared = len(prepared_in)
    omitted = len(partition["duplicates"])
    excluded_n = len(partition["excluded"]) + missing_from
    unexplained = eligible - prepared - omitted - missing_from
    if unexplained != 0:
        raise LoaderError("unexplained_loss")
    return {
        "ok": True,
        "rule_id": RULE_ID,
        "eligible": eligible,
        "prepared_messages": prepared,
        "identity_duplicates_omitted": omitted,
        "omitted_with_survivor_lineage": omitted_lineage,
        "omitted_missing_survivor": omitted_missing_survivor,
        "excluded_in_assigned_stream": excluded_n,
        "excluded_reasons": excluded_reasons,
        "unexplained": 0,
        "threads": len(threads),
        "max_thread_size": max(sizes) if sizes else 0,
        "threads_over_99": over_99,
        "thread_size_p50": sizes_sorted[len(sizes_sorted) // 2] if sizes_sorted else 0,
        "participants": participants,
        "authenticated_participants": authenticated_participants,
        "unverified_participants": unverified_participants,
        "attachments": attachments,
        "commercial_classes": commercial_counts,
        "voice_corpus_messages": voice_n,
        "authenticated_from_clean_quote_by_person_label": [
            {"person_label": k, "messages": voice_by_label[k]}
            for k in sorted(voice_by_label, key=lambda x: (-voice_by_label[x], x))
        ],
        "quote_quality_exceptions": quote_flags,
        "evidence_never_deleted_or_updated": True,
        "completeness_ok": eligible == prepared + omitted + missing_from,
    }


def _insert_participants(conn: Any, message_id: Any, msg: dict[str, Any]) -> None:
    seen_from = False
    for role, rows in (("from", msg.get("from_parties") or []), ("to", msg.get("to_parties") or []), ("cc", msg.get("cc_parties") or [])):
        for row in rows or []:
            addr = str(row.get("address") or "").strip()
            if not addr:
                continue
            status = AUTH_MAP.get(str(row.get("status") or UNVERIFIED), "unverified")
            pid = row.get("person_id") or None
            if status == "unverified":
                pid = None
            elif not pid:
                status = "unverified"
                pid = None
            if role == "from":
                if seen_from:
                    continue
                seen_from = True
                if pid:
                    status = "authenticated_focal"
            elif status == "authenticated_focal":
                status = "authenticated_other"
            conn.execute(
                """
                INSERT INTO comms_prepared_participants (
                  message_id, role, display_name, address_normalized, identity_confidence, person_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (message_id, role, str(row.get("display") or "")[:200], addr, status, pid or None),
            )
    if not seen_from:
        raise LoaderError("missing_from")


def _insert_attachments(conn: Any, message_id: Any, evidence_id: Any, msg: dict[str, Any]) -> int:
    atts = msg.get("attachment_meta") or []
    n = 0
    for i, att in enumerate(atts, start=1):
        filename = str(att.get("filename") or "")
        mime = str(att.get("mime_type") or "")
        locator = str(att.get("source_locator") or msg.get("source_locator") or filename)
        if "\\" in locator or locator.lower().startswith("p:") or "://" in locator:
            locator = filename or "archive-ref"
        conn.execute(
            """
            INSERT INTO comms_prepared_attachments (
              message_id, parent_evidence_id, attachment_ordinal, filename, mime_type,
              disposition, byte_size, source_locator, gallery_action
            ) VALUES (%s, %s, %s, %s, %s, 'attachment', %s, %s, %s)
            """,
            (
                message_id,
                evidence_id,
                i,
                filename,
                mime,
                att.get("byte_size"),
                locator[:500],
                gallery_attachment_action(filename, mime),
            ),
        )
        n += 1
    return n


def read_source_messages(
    conn: Any, source_ids: list[Any], *, dsn: str | None = None, allow_live: bool = False
) -> list[dict[str, Any]]:
    _dbname(conn, dsn, allow_live=allow_live)
    if not source_ids:
        return []
    rows = conn.execute(
        """
        SELECT e.id, e.source_id, e.payload_json
          FROM evidence e
         WHERE e.source_id = ANY(%s)
           AND e.evidence_kind = 'communication'
        """,
        (list(source_ids),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(row)
        payload = rec.get("payload_json") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        rfc = payload.get("rfc_message_id") or payload.get("message_id")
        if rfc:
            rfc = normalize_rfc_message_id(str(rfc)) or str(rfc)
        skip = str(payload.get("mailbox_skip") or "").lower()
        out.append(
            {
                "evidence_id": rec["id"],
                "source_id": rec["source_id"],
                "payload": payload,
                "content_hash": str(payload.get("content_hash") or "").strip().lower(),
                "rfc_message_id": rfc,
                "timestamp": payload.get("sent_at"),
                "subject": payload.get("subject") or "",
                "raw_body": payload.get("body_text") or payload.get("body") or "",
                "body": payload.get("body_text") or payload.get("body") or "",
                "from": payload.get("from"),
                "to": payload.get("to"),
                "cc": payload.get("cc"),
                "from_parsed": payload.get("from_parsed"),
                "to_parsed": payload.get("to_parsed"),
                "cc_parsed": payload.get("cc_parsed"),
                "in_reply_to_ids": payload.get("in_reply_to_ids") or [],
                "reference_ids": payload.get("reference_ids") or [],
                "vendor_thread_id": payload.get("vendor_thread_id") or payload.get("thread_id"),
                "spam_or_trash": skip in {"spam", "trash"},
                "source_locator": payload.get("source_locator") or "",
            }
        )
    return out


def load_household_email_generation(
    conn: Any,
    messages: list[dict[str, Any]],
    ledger: IdentityLedger,
    *,
    dsn: str | None = None,
    fail_after: str | None = None,
    allow_live: bool = False,
    persist_batches: bool = False,
    batch_threads: int = 200,
    deadline_mono: float | None = None,
    on_progress: Any = None,
) -> dict[str, Any]:
    _dbname(conn, dsn, allow_live=allow_live)
    _deadline_guard(deadline_mono)
    evidence_before = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
    ).fetchone()
    partition = consolidate_messages(messages)
    if partition["unexplained"] != 0:
        raise LoaderError("unexplained_loss")
    prepared_in: list[dict[str, Any]] = []
    for msg in partition["displayed"]:
        parties_ok = True
        from memorybox.ops.i14_thread_review import extract_parties

        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        from_rows = extract_parties(payload, msg)["from"]
        if not from_rows:
            partition["excluded"].append({**msg, "exclude_reason": "missing_from"})
            continue
        prepared_in.append(msg)
    if fail_after == "before_write":
        raise LoaderError("injected_failure")

    _deadline_guard(deadline_mono)
    clustered = cluster_threads(prepared_in) if prepared_in else {}
    threads: dict[str, list[dict[str, Any]]] = {}
    for msg in prepared_in:
        threads.setdefault(clustered[str(msg["evidence_id"])], []).append(msg)

    logical_id = _ensure_logical(conn)
    source_ids = {m.get("source_id") for m in prepared_in if m.get("source_id")}
    _ensure_memberships(conn, logical_id, source_ids)
    extract_by_source = {
        sid: _ensure_extract(conn, logical_id, sid) for sid in source_ids
    }

    checksum = _checksum([m["evidence_id"] for m in prepared_in])
    reuse = conn.execute(
        """
        SELECT id FROM comms_prepared_generations
         WHERE logical_source_id = %s AND checksum = %s AND status = 'validated'
           AND NOT published AND NOT is_active
         ORDER BY created_at DESC LIMIT 1
        """,
        (logical_id, checksum),
    ).fetchone()
    if reuse and not fail_after:
        gid = reuse["id"] if isinstance(reuse, dict) else reuse[0]
        return _counts_report(conn, gid, partition, evidence_before, reused=True)

    gen = conn.execute(
        """
        INSERT INTO comms_prepared_generations (
          algo_version, logical_source_id, status, checksum
        ) VALUES (%s, %s, 'building', %s)
        RETURNING id
        """,
        (ALGO_VERSION, logical_id, checksum),
    ).fetchone()
    gid = gen["id"] if isinstance(gen, dict) else gen[0]
    if persist_batches:
        conn.commit()
        if on_progress:
            on_progress({"stage": "generation_building", "threads": len(threads)})
    if fail_after == "after_generation":
        raise LoaderError("injected_failure")

    thread_items = []
    for done, (cluster_key, members) in enumerate(threads.items(), start=1):
        _deadline_guard(deadline_mono)
        compacted = _compact_thread_messages(members)
        annotated = annotate_messages(compacted, ledger)
        for row in annotated:
            fields = _schema_message_fields(row)
            row.update(fields)
        ordered = sorted(annotated, key=message_sort_key)
        thread_items.append((cluster_key, ordered))
        if on_progress and done % 50 == 0:
            on_progress({"stage": "annotate_threads", "threads_done": done})
    thread_items.sort(key=lambda item: (item[1][0]["sent_at"], str(item[1][0]["evidence_id"])))

    omitted_by_cluster: dict[str, int] = {}
    displayed_ids = {str(m["evidence_id"]) for m in prepared_in}
    for dup in partition["duplicates"]:
        # attribute omitted rows to the survivor's cluster when possible
        survivor = str(dup.get("duplicate_of") or "")
        omitted_by_cluster[survivor] = omitted_by_cluster.get(survivor, 0) + 1

    msg_n = 0
    part_n = 0
    att_n = 0
    voice_n = 0
    commercial_counts: dict[str, int] = {}
    unresolved_identities = 0
    quote_flags = 0
    for idx, (cluster_key, ordered) in enumerate(thread_items, start=1):
        _deadline_guard(deadline_mono)
        display_id = format_display_id(idx)
        gallery, suppress_reason = _thread_gallery(ordered)
        earliest = ordered[0]["sent_at"]
        latest = ordered[-1]["sent_at"]
        omitted = sum(omitted_by_cluster.get(str(m["evidence_id"]), 0) for m in ordered)
        thread = conn.execute(
            """
            INSERT INTO comms_prepared_threads (
              generation_id, thread_key, display_id, earliest_at, latest_at,
              message_count, evidence_count, duplicate_omitted_count,
              threading_confidence, identity_confidence, gallery_eligibility,
              suppression_reason, provenance
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            RETURNING id
            """,
            (
                gid,
                cluster_key[:700],
                display_id,
                earliest,
                latest,
                len(ordered),
                len(ordered) + omitted,
                omitted,
                _threading_confidence(ordered),
                _thread_identity(ordered),
                gallery,
                suppress_reason,
                json.dumps(
                    {
                        "rule_id": RULE_ID,
                        "duplicate_omitted_count": omitted,
                        "excluded_from_this_thread": 0,
                    }
                ),
            ),
        ).fetchone()
        tid = thread["id"] if isinstance(thread, dict) else thread[0]
        for ordinal, msg in enumerate(ordered, start=1):
            rfc = str(msg.get("rfc_message_id") or "").strip()
            if rfc:
                rfc = normalize_rfc_message_id(rfc) or rfc
            digest = str(msg.get("content_hash") or "").strip().lower()
            sid = msg.get("source_id")
            extract_id = extract_by_source.get(sid) or next(iter(extract_by_source.values()))
            canonical_id = _ensure_canonical(
                conn,
                logical_id=logical_id,
                extract_id=extract_id,
                evidence_id=msg["evidence_id"],
                rfc=rfc or None,
                digest=digest,
            )
            fields = _schema_message_fields(msg)
            row = conn.execute(
                """
                INSERT INTO comms_prepared_messages (
                  thread_id, generation_id, ordinal, evidence_id, canonical_record_id,
                  evidence_ref, sent_at, subject, cleaned_authored_text, forward_block,
                  forward_status, forward_omitted, urls_stripped, quote_quality,
                  identity_quality, authorship, voice_corpus, commercial_class, direction
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    tid,
                    gid,
                    ordinal,
                    msg["evidence_id"],
                    canonical_id,
                    evidence_ref(display_id, ordinal),
                    fields["sent_at"],
                    fields["subject"],
                    fields["cleaned"],
                    fields["forward_block"],
                    fields["forward_status"],
                    fields["forward_omitted"],
                    fields["urls_stripped"],
                    fields["quote_quality"],
                    fields["identity_quality"],
                    fields["authorship"],
                    fields["voice_corpus"],
                    fields["commercial_class"],
                    fields["direction"],
                ),
            ).fetchone()
            mid = row["id"] if isinstance(row, dict) else row[0]
            _insert_participants(conn, mid, msg)
            part_n += 1 + len(msg.get("to_parties") or []) + len(msg.get("cc_parties") or [])
            att_n += _insert_attachments(conn, mid, msg["evidence_id"], msg)
            msg_n += 1
            if fields["voice_corpus"]:
                voice_n += 1
            commercial_counts[fields["commercial_class"]] = commercial_counts.get(fields["commercial_class"], 0) + 1
            if fields["identity_quality"] != "resolved":
                unresolved_identities += 1
            if fields["quote_quality"] != "clean":
                quote_flags += 1
            displayed_ids.add(str(msg["evidence_id"]))
        if persist_batches and idx % max(1, int(batch_threads)) == 0:
            conn.commit()
            if on_progress:
                on_progress(
                    {
                        "stage": "insert_threads",
                        "threads_done": idx,
                        "messages_done": msg_n,
                    }
                )

    conn.execute(
        """
        UPDATE comms_prepared_generations
           SET status = 'validated', item_count = %s, updated_at = now()
         WHERE id = %s AND NOT published AND NOT is_active
        """,
        (msg_n, gid),
    )
    if fail_after == "before_commit":
        raise LoaderError("injected_failure")

    evidence_after = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
    ).fetchone()
    if dict(evidence_before) != dict(evidence_after):
        raise LoaderError("evidence_mutated")
    return {
        "ok": True,
        "generation_id": str(gid),
        "reused": False,
        "published": False,
        "is_active": False,
        "status": "validated",
        "algo_version": ALGO_VERSION,
        "threads": len(thread_items),
        "messages": msg_n,
        "participants_inserted": part_n,
        "attachments": att_n,
        "voice_rows": voice_n,
        "commercial_classes": commercial_counts,
        "unresolved_identities": unresolved_identities,
        "quote_quality_exceptions": quote_flags,
        "duplicates": len(partition["duplicates"]),
        "excluded": len(partition["excluded"]) + max(0, len(partition["displayed"]) - len(prepared_in)),
        "eligible": len(partition["eligible"]),
        "displayed": len(prepared_in),
        "unexplained": 0,
        "activation_called": False,
        "evidence_unchanged": True,
        "rule_id": RULE_ID,
        "class_extra_rows": partition["class_extra_rows"],
    }


def run_load(conn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    persist = bool(kwargs.get("persist_batches"))
    try:
        result = load_household_email_generation(conn, *args, **kwargs)
        conn.commit()
        return result
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        if persist:
            try:
                rows = conn.execute(
                    """
                    SELECT id FROM comms_prepared_generations
                     WHERE status = 'building' AND NOT published AND NOT is_active
                    """
                ).fetchall()
                for row in rows:
                    ident = row["id"] if isinstance(row, dict) else row[0]
                    mark_generation_failed(conn, ident)
                conn.commit()
            except Exception:
                conn.rollback()
        raise


def _counts_report(conn: Any, gid: Any, partition: dict[str, Any], evidence_before: Any, *, reused: bool) -> dict[str, Any]:
    msg_n = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
        (gid,),
    ).fetchone()["n"]
    thread_n = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_prepared_threads WHERE generation_id = %s",
        (gid,),
    ).fetchone()["n"]
    return {
        "ok": True,
        "generation_id": str(gid),
        "reused": reused,
        "published": False,
        "is_active": False,
        "status": "validated",
        "threads": int(thread_n),
        "messages": int(msg_n),
        "duplicates": len(partition["duplicates"]),
        "excluded": len(partition["excluded"]),
        "unexplained": 0,
        "activation_called": False,
        "evidence_unchanged": True,
        "rule_id": RULE_ID,
    }
