"""Read-only prepared-text recovery census. Never writes comms_* or evidence."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_peggy_preview import _compact_thread_messages
from memorybox.ops.i14_prepared_loader import _schema_message_fields
from memorybox.ops.i14_prepared_text import (
    HOTMAIL_DATE_FROM_TO_SUBJECT,
    select_authored_source,
    source_is_meaningful,
)
from memorybox.ops.i14_thread_review import annotate_messages
from memorybox.ops.i14_voice_delta import _ledger

DISPOSITIONS = (
    "authored_prepared",
    "correctly_empty",
    "attachment_only",
    "prepared_text_unavailable",
    "cleanup_removed_meaningful",
)

VOICE_DROP_REASONS = (
    "blank_prepared_text",
    "correctly_empty",
    "attachment_only",
    "prepared_text_unavailable",
    "quote_contamination",
    "commercial_suppression",
    "identity_authorship_change",
    "other",
)

PACKET_CAP = 14


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def disposition_for(
    *,
    cleaned: str,
    source_text: str,
    has_attachments: bool,
    quote_history_removed: bool,
    method: str,
) -> str:
    if source_is_meaningful(cleaned):
        return "authored_prepared"
    if has_attachments and not source_is_meaningful(source_text):
        return "attachment_only"
    if source_is_meaningful(source_text) and not source_is_meaningful(cleaned):
        method_l = str(method or "")
        if quote_history_removed or "hotmail" in method_l:
            return "cleanup_removed_meaningful"
        return "prepared_text_unavailable"
    if quote_history_removed or str(method or "").startswith("explicit_forward"):
        return "correctly_empty"
    if not (source_text or "").strip():
        return "correctly_empty"
    return "prepared_text_unavailable"


def classify_voice_drop(
    *,
    stored_voice: bool,
    after_voice: bool,
    cleaned: str,
    disposition: str,
    quote_after: str,
    from_authenticated: bool,
    commercial_after: str,
) -> str | None:
    """Mutually exclusive reason a stored voice row is no longer voice.

    Voice never uses commercial class. commercial_suppression is therefore 0
    unless a future rule ties voice to suppress_default.
    """
    del commercial_after
    if not stored_voice or after_voice:
        return None
    if not from_authenticated:
        return "identity_authorship_change"
    if str(quote_after or "") != "clean":
        return "quote_contamination"
    if not str(cleaned or "").strip():
        if disposition == "attachment_only":
            return "attachment_only"
        if disposition == "correctly_empty":
            return "correctly_empty"
        if disposition in {"prepared_text_unavailable", "cleanup_removed_meaningful"}:
            return disposition
        return "blank_prepared_text"
    return "other"


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def run_census(conn: Any) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*)::int FROM comms_prepared_threads t
             JOIN comms_prepared_active_generations g ON g.id = t.generation_id) AS threads,
          (SELECT COUNT(*)::int FROM comms_prepared_messages m
             JOIN comms_prepared_threads t ON t.id = m.thread_id
             JOIN comms_prepared_active_generations g ON g.id = t.generation_id) AS messages,
          (SELECT COUNT(*)::int FROM comms_prepared_participants p
             JOIN comms_prepared_messages m ON m.id = p.message_id
             JOIN comms_prepared_threads t ON t.id = m.thread_id
             JOIN comms_prepared_active_generations g ON g.id = t.generation_id) AS participants,
          (SELECT COUNT(*)::int FROM comms_prepared_attachments a
             JOIN comms_prepared_messages m ON m.id = a.message_id
             JOIN comms_prepared_threads t ON t.id = m.thread_id
             JOIN comms_prepared_active_generations g ON g.id = t.generation_id) AS attachments
        """
    ).fetchone()
    voice_before = {
        str(r["who"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT split_part(pe.display_name, ' ', 1) AS who, COUNT(*)::int AS n
              FROM comms_prepared_messages m
              JOIN comms_prepared_threads t ON t.id = m.thread_id
              JOIN comms_prepared_active_generations g ON g.id = t.generation_id
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE m.voice_corpus
             GROUP BY 1
            """
        ).fetchall()
    }
    commercial_before = {
        str(r["c"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT m.commercial_class AS c, COUNT(*)::int AS n
              FROM comms_prepared_messages m
              JOIN comms_prepared_threads t ON t.id = m.thread_id
              JOIN comms_prepared_active_generations g ON g.id = t.generation_id
             GROUP BY 1
            """
        ).fetchall()
    }
    quote_before = {
        str(r["q"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT m.quote_quality AS q, COUNT(*)::int AS n
              FROM comms_prepared_messages m
              JOIN comms_prepared_threads t ON t.id = m.thread_id
              JOIN comms_prepared_active_generations g ON g.id = t.generation_id
             GROUP BY 1
            """
        ).fetchall()
    }
    rows = conn.execute(
        """
        SELECT t.display_id, m.ordinal, m.evidence_id::text AS evidence_id,
               m.subject, m.commercial_class, m.authorship, m.quote_quality,
               m.voice_corpus, m.cleaned_authored_text, m.forward_status,
               (
                 SELECT COUNT(*)::int FROM comms_prepared_attachments a
                  WHERE a.message_id = m.id
               ) AS att_n,
               e.payload_json
          FROM comms_prepared_threads t
          JOIN comms_prepared_messages m ON m.thread_id = t.id
          JOIN comms_prepared_active_generations g ON g.id = t.generation_id
          JOIN evidence e ON e.id = m.evidence_id
         ORDER BY t.display_id, m.ordinal
        """
    ).fetchall()
    ledger = _ledger(conn)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in rows:
        groups[str(rec["display_id"])].append(dict(rec))

    recovered_html = 0
    recovered_alt = 0
    hotmail_glue = 0
    disp = {k: 0 for k in DISPOSITIONS}
    commercial_after: dict[str, int] = defaultdict(int)
    quote_after: dict[str, int] = defaultdict(int)
    voice_after: dict[str, int] = defaultdict(int)
    voice_true_blank = 0
    processed = 0
    samples: dict[str, dict[str, Any]] = {}
    voice_drop = {
        who: {k: 0 for k in VOICE_DROP_REASONS} for who in ("Tom", "Peggy", "Sue")
    }
    voice_drop["other_people"] = {k: 0 for k in VOICE_DROP_REASONS}
    html_personal_not_suppressed = 0
    html_personal_suppressed = 0
    unavailable_from_meaningful_source = 0

    for display_id, members in groups.items():
        msgs = []
        for rec in members:
            payload = _payload(rec.get("payload_json"))
            src = select_authored_source(payload)
            msgs.append(
                {
                    "payload": payload,
                    "raw_body": src.text,
                    "body": src.text,
                    "source_kind": src.kind,
                    "hotmail_glued": src.hotmail_glued,
                    "subject": rec.get("subject") or payload.get("subject") or "",
                    "timestamp": payload.get("sent_at"),
                    "from": payload.get("from"),
                    "to": payload.get("to"),
                    "cc": payload.get("cc"),
                    "from_parsed": payload.get("from_parsed"),
                    "to_parsed": payload.get("to_parsed"),
                    "cc_parsed": payload.get("cc_parsed"),
                    "evidence_id": rec["evidence_id"],
                    "_stored": rec,
                }
            )
        compacted = _compact_thread_messages(msgs)
        annotated = annotate_messages(compacted, ledger)
        for row, rec in zip(annotated, members):
            processed += 1
            fields = _schema_message_fields(row)
            src_kind = str(row.get("source_kind") or "")
            hotmail = bool(row.get("hotmail_glued")) or bool(
                HOTMAIL_DATE_FROM_TO_SUBJECT.search(str(row.get("raw_body") or ""))
            )
            stored_empty = not str(rec.get("cleaned_authored_text") or "").strip()
            cleaned = str(fields.get("cleaned") or row.get("cleaned_body") or "")
            authored_ok = source_is_meaningful(cleaned)
            if stored_empty and authored_ok:
                if src_kind == "html":
                    recovered_html += 1
                elif src_kind == "alt_part":
                    recovered_alt += 1
                if hotmail:
                    hotmail_glue += 1
            d = disposition_for(
                cleaned=cleaned,
                source_text=str(row.get("raw_body") or ""),
                has_attachments=int(rec.get("att_n") or 0) > 0,
                quote_history_removed=bool(row.get("quoted_removed")),
                method=str(row.get("clean_method") or ""),
            )
            if d == "prepared_text_unavailable" and source_is_meaningful(
                str(row.get("raw_body") or "")
            ):
                unavailable_from_meaningful_source += 1
            disp[d] = disp.get(d, 0) + 1
            commercial_after[str(fields["commercial_class"])] += 1
            quote_after[str(fields["quote_quality"])] += 1
            if src_kind == "html" and authored_ok:
                cls = str(fields["commercial_class"] or "")
                if cls in {"not_commercial", "retain_life_evidence"}:
                    html_personal_not_suppressed += 1
                elif cls == "suppress_default":
                    html_personal_suppressed += 1
            label = "unknown"
            from_auth = str(fields.get("authorship") or "") == "authenticated_focal"
            for party in row.get("from_parties") or []:
                label = str(party.get("label") or "").split()[0] or "unknown"
                break
            if fields["voice_corpus"]:
                if not cleaned.strip():
                    voice_true_blank += 1
                voice_after[label] += 1
            drop = classify_voice_drop(
                stored_voice=bool(rec.get("voice_corpus")),
                after_voice=bool(fields["voice_corpus"]),
                cleaned=cleaned,
                disposition=d,
                quote_after=str(fields.get("quote_quality") or ""),
                from_authenticated=from_auth,
                commercial_after=str(fields.get("commercial_class") or ""),
            )
            if drop:
                bucket = voice_drop[label] if label in voice_drop else voice_drop["other_people"]
                bucket[drop] += 1
            _maybe_sample(
                samples,
                display_id,
                rec,
                row,
                fields,
                d,
                src_kind,
                hotmail,
                stored_empty,
                authored_ok,
                person_label=label,
            )

    unexplained = 0
    return {
        "ok": True,
        "processed_messages": processed,
        "lineage_totals": dict(totals),
        "recovered_from_html": recovered_html,
        "recovered_from_alt_mime": recovered_alt,
        "hotmail_glue_recoveries": hotmail_glue,
        "dispositions": disp,
        "correctly_empty": disp["correctly_empty"],
        "attachment_only": disp["attachment_only"],
        "prepared_text_unavailable": disp["prepared_text_unavailable"],
        "remaining_defects_unavailable": disp["prepared_text_unavailable"],
        "unavailable_from_meaningful_source": unavailable_from_meaningful_source,
        "unexplained": unexplained,
        "commercial_before": commercial_before,
        "commercial_after": dict(commercial_after),
        "html_personal_not_suppressed": html_personal_not_suppressed,
        "html_personal_suppressed": html_personal_suppressed,
        "quote_before": quote_before,
        "quote_after": dict(quote_after),
        "voice_before": voice_before,
        "voice_after": dict(voice_after),
        "voice_true_blank_after": voice_true_blank,
        "voice_drop_by_person": voice_drop,
        "samples": {k: _public_sample(v) for k, v in samples.items()},
        "sample_rows": samples,
    }


def _public_sample(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": row.get("slot"),
        "display_id": row.get("display_id"),
        "ordinal": row.get("ordinal"),
        "evidence_id": row.get("evidence_id"),
        "source_kind": row.get("source_kind"),
        "disposition": row.get("disposition"),
        "hotmail_glued": row.get("hotmail_glued"),
        "stored_empty": row.get("stored_empty"),
        "recovered": row.get("recovered"),
    }


def _maybe_sample(
    samples: dict[str, dict[str, Any]],
    display_id: str,
    rec: dict[str, Any],
    row: dict[str, Any],
    fields: dict[str, Any],
    disp: str,
    src_kind: str,
    hotmail: bool,
    stored_empty: bool,
    authored_ok: bool,
    person_label: str = "",
) -> None:
    cleaned = str(fields.get("cleaned") or "")
    commercial = str(fields.get("commercial_class") or rec.get("commercial_class") or "")
    slot = None
    if display_id == "T-39987" and int(rec.get("ordinal") or 0) == 2:
        slot = "john_t39987"
    elif (
        person_label == "Sue"
        and rec.get("voice_corpus")
        and fields.get("voice_corpus")
        and "sue_voice_retained" not in samples
    ):
        slot = "sue_voice_retained"
    elif (
        person_label == "Sue"
        and rec.get("voice_corpus")
        and not fields.get("voice_corpus")
        and "sue_voice_removed" not in samples
    ):
        slot = "sue_voice_removed"
    elif src_kind == "html" and authored_ok and commercial in {"not_commercial", "retain_life_evidence"}:
        slot = "personal_html"
    elif src_kind == "html" and authored_ok and commercial not in {"not_commercial", "retain_life_evidence"}:
        slot = "commercial_html"
    elif src_kind == "body_text" and authored_ok:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        html_raw = str(payload.get("body_html") or "")
        if html_raw.strip() and source_is_meaningful(str(payload.get("body_text") or "")):
            slot = "multipart_plain_html"
    elif disp == "attachment_only":
        slot = "attachment_only"
    elif disp == "correctly_empty" and row.get("quoted_removed"):
        slot = "quoted_reply"
    elif str(row.get("clean_method") or "").startswith("explicit_forward"):
        slot = "forward"
    elif hotmail and authored_ok:
        slot = "hotmail_glue"
    elif "&" in str(row.get("raw_body") or "")[:400] or "&#" in str(row.get("raw_body") or ""):
        slot = "encoding_entity"
    elif disp == "correctly_empty" and not row.get("quoted_removed"):
        slot = "correctly_empty"
    elif disp == "prepared_text_unavailable":
        slot = "prepared_text_unavailable"
    if not slot:
        return
    if slot in samples and slot != "john_t39987":
        return
    samples[slot] = {
        "slot": slot,
        "display_id": display_id,
        "ordinal": rec.get("ordinal"),
        "evidence_id": rec.get("evidence_id"),
        "source_kind": src_kind,
        "disposition": disp,
        "hotmail_glued": hotmail,
        "stored_empty": stored_empty,
        "recovered": authored_ok and stored_empty,
        "prepared_text": cleaned,
        "subject": rec.get("subject") or "",
    }


def write_founder_packet(census: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = census.get("sample_rows") or {}
    if isinstance(raw, dict):
        rows = [v for v in raw.values() if isinstance(v, dict)]
    else:
        rows = [v for v in raw if isinstance(v, dict)]
    preferred = [
        "john_t39987",
        "sue_voice_retained",
        "sue_voice_removed",
        "personal_html",
        "commercial_html",
        "multipart_plain_html",
        "attachment_only",
        "quoted_reply",
        "forward",
        "hotmail_glue",
        "encoding_entity",
        "correctly_empty",
        "prepared_text_unavailable",
    ]
    ordered = []
    seen = set()
    by_slot = {r["slot"]: r for r in rows}
    for key in preferred:
        if key in by_slot:
            ordered.append(by_slot[key])
            seen.add(key)
    for row in rows:
        if row["slot"] not in seen:
            ordered.append(row)
            seen.add(row["slot"])
        if len(ordered) >= PACKET_CAP:
            break
    lines = [
        "I14 prepared-text recovery founder packet (private).",
        "Do not commit this file. Immutable originals are Evidence-ref only.",
        "No corpus dump. No raw HTML.",
        "",
    ]
    for i, row in enumerate(ordered[:PACKET_CAP], 1):
        lines.append(f"## {i}. {row['slot']}  {row['display_id']} ordinal={row['ordinal']}")
        lines.append(f"Evidence-ref: {row['evidence_id']}")
        lines.append(f"source_kind={row['source_kind']} disposition={row['disposition']} stored_empty={row['stored_empty']}")
        lines.append("Recovered prepared text:")
        body = str(row.get("prepared_text") or "").strip() or "(none)"
        lines.append(body)
        lines.append("")
    path = out_dir / "FOUNDER-PACKET.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    del argv
    from memorybox.db import connection

    allow_db = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB")
    allow_fs = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_FLIGHTSIM") or _env_on(
        "MEMORYBOX_I14_GALLERY_TIMING_ALLOW_FLIGHTSIM"
    )
    out_dir = Path("working/i14-prepared-text-recovery")
    out_dir.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        row = conn.execute("SELECT current_database() AS d").fetchone()
        name = str(row["d"])
        info = getattr(conn, "info", None)
        host = str(getattr(info, "host", "") or "") if info is not None else ""
        try:
            refuse_live_dsn(host, None if allow_db else name, allow_flightsim=allow_fs)
        except ProductionDSNError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
        if name.lower() == "memorybox" and not allow_db:
            print(json.dumps({"ok": False, "error": "refused_memorybox_dbname"}))
            return 2
        census = run_census(conn)
    public = {k: v for k, v in census.items() if k != "sample_rows"}
    counts_path = out_dir / "COUNTS.json"
    counts_path.write_text(json.dumps(public, indent=2), encoding="utf-8")
    (out_dir / "SAMPLES.json").write_text(json.dumps(census.get("sample_rows") or {}, indent=2), encoding="utf-8")
    packet = write_founder_packet(census, out_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "counts": str(counts_path),
                "packet": str(packet),
                "recovered_from_html": census["recovered_from_html"],
                "recovered_from_alt_mime": census["recovered_from_alt_mime"],
                "hotmail_glue_recoveries": census["hotmail_glue_recoveries"],
                "unexplained": census["unexplained"],
                "dispositions": census["dispositions"],
                "voice_drop_by_person": census.get("voice_drop_by_person"),
                "voice_before": census.get("voice_before"),
                "voice_after": census.get("voice_after"),
                "voice_true_blank_after": census.get("voice_true_blank_after"),
                "unavailable_from_meaningful_source": census.get(
                    "unavailable_from_meaningful_source"
                ),
            }
        )
    )
    return 0
