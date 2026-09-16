"""Read-only census of HTML recovery beyond v2's eight-letter body preference.

Never writes comms_* or evidence. FlightSim requires audit allow flags.
"""
from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_prepared_display import (
    DISPOSITION_AUTHORED,
    decide_prepared_row,
    html_recovery_beyond_v2_eight_letter,
)
from memorybox.ops.i14_prepared_loader import COMMERCIAL_MAP, _quote_quality
from memorybox.ops.i14_prepared_text import html_to_plain, prepare_message_text, select_authored_source
from memorybox.ops.i14_thread_review import classify_commercial

BATCH = 250
PACKET_CAP = 14
EXCERPT = 900
V3_ALGO = "i14-prepared-email-v3"


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _excerpt(text: str) -> str:
    blob = str(text or "").replace("\r\n", "\n")
    if len(blob) <= EXCERPT:
        return blob
    return blob[:EXCERPT] + "\n…[truncated]"


def _person_bucket(name: str) -> str:
    first = str(name or "").split()[0] if str(name or "").strip() else ""
    if first in {"Tom", "Peggy", "Sue"}:
        return first
    if first:
        return "other_authenticated" if first else "unknown"
    return "unknown"


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _sample_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("disposition") or ""),
            "voice" if row.get("would_voice") else "novoice",
            str(row.get("person_bucket") or ""),
            str(row.get("commercial_class") or ""),
            str(row.get("quote_quality") or ""),
        ]
    )


def select_v2_generation(conn: Any) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT id, algo_version, status, published, is_active, checksum
          FROM comms_prepared_generations
         WHERE algo_version = 'i14-prepared-email-v2'
         ORDER BY is_active DESC, published DESC, created_at DESC
         LIMIT 1
        """
    ).fetchone()
    if not row:
        raise RuntimeError("v2_generation_missing")
    return dict(row)


def run_census(conn: Any, *, out_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    tracemalloc.start()
    gen = select_v2_generation(conn)
    gid = gen["id"]
    total = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
            (gid,),
        ).fetchone()["n"]
    )
    scanned = 0
    candidates = 0
    n_html = 0
    disp: dict[str, int] = defaultdict(int)
    voice_by: dict[str, int] = defaultdict(int)
    commercial: dict[str, int] = defaultdict(int)
    quote_counts: dict[str, int] = defaultdict(int)
    v2_commercial: dict[str, int] = defaultdict(int)
    v2_quote: dict[str, int] = defaultdict(int)
    authored = 0
    would_voice = 0
    last_id = UUID("00000000-0000-0000-0000-000000000000")
    samples: dict[str, dict[str, Any]] = {}
    unusual_by: dict[str, dict[str, Any]] = {}

    while True:
        rows = conn.execute(
            """
            SELECT m.id, m.evidence_id::text AS evidence_id, m.ordinal,
                   t.display_id, m.subject, m.cleaned_authored_text,
                   m.voice_corpus, m.quote_quality, m.commercial_class,
                   m.authorship,
                   p.identity_confidence,
                   split_part(coalesce(pe.display_name, p.display_name, ''), ' ', 1) AS who,
                   (
                     SELECT COUNT(*)::int FROM comms_prepared_attachments a
                      WHERE a.message_id = m.id
                   ) AS att_n,
                   e.payload_json
              FROM comms_prepared_messages m
              JOIN comms_prepared_threads t ON t.id = m.thread_id
              JOIN evidence e ON e.id = m.evidence_id
              LEFT JOIN comms_prepared_participants p
                ON p.message_id = m.id AND p.role = 'from'
              LEFT JOIN people pe ON pe.id = p.person_id
             WHERE m.generation_id = %s AND m.id > %s
             ORDER BY m.id
             LIMIT %s
            """,
            (gid, last_id, BATCH),
        ).fetchall()
        if not rows:
            break
        for rec in rows:
            scanned += 1
            last_id = rec["id"]
            payload = _payload(rec.get("payload_json"))
            body = str(payload.get("body_text") or payload.get("body") or "")
            html_raw = str(payload.get("body_html") or "")
            if len(body.strip()) < 8 or not html_raw.strip():
                continue
            candidates += 1
            if not html_recovery_beyond_v2_eight_letter(payload):
                continue
            src = select_authored_source(payload)
            prep = prepare_message_text(src.text, subject=str(rec.get("subject") or ""))
            from_auth = str(rec.get("identity_confidence") or "") == "authenticated_focal"
            quote_quality = _quote_quality(
                {
                    "cleaned_body": str(prep.authored or ""),
                    "residue_class": prep.method if prep.quote_history_removed else None,
                }
            )
            v3_comm = COMMERCIAL_MAP.get(
                str(
                    classify_commercial(
                        {
                            "cleaned_body": str(prep.authored or ""),
                            "subject": str(rec.get("subject") or ""),
                            "raw_body": html_raw[:4000],
                        }
                    ).get("commercial_class")
                    or "not_commercial"
                ),
                "not_commercial",
            )
            decision = decide_prepared_row(
                str(prep.authored or ""),
                from_authenticated=from_auth,
                quote_quality=quote_quality,
                from_person=str(rec.get("who") or ""),
                has_attachments=int(rec.get("att_n") or 0) > 0,
            )
            who = str(rec.get("who") or "")
            bucket = _person_bucket(who)
            if from_auth and bucket == "unknown":
                bucket = "other_authenticated"
            elif not from_auth:
                bucket = "unauthenticated"
            item = {
                "display_id": rec["display_id"],
                "ordinal": rec["ordinal"],
                "evidence_id": rec["evidence_id"],
                "disposition": decision["prepared_text_disposition"],
                "would_voice": bool(decision["voice_corpus"]),
                "person_bucket": bucket,
                "commercial_class": v3_comm,
                "v2_commercial_class": str(rec.get("commercial_class") or ""),
                "quote_quality": quote_quality,
                "v2_quote_quality": str(rec.get("quote_quality") or ""),
                "authorship": str(rec.get("authorship") or ""),
                "v2_voice": bool(rec.get("voice_corpus")),
                "v2_cleaned_chars": len(str(rec.get("cleaned_authored_text") or "").strip()),
                "new_cleaned": str(decision["stored_cleaned"] or ""),
                "source_kind": src.kind,
                "plain_excerpt": _excerpt(body),
                "html_excerpt": _excerpt(html_raw),
                "html_plain_excerpt": _excerpt(html_to_plain(html_raw)),
                "prepared_excerpt": _excerpt(str(prep.authored or "")),
                "subject": str(rec.get("subject") or ""),
            }
            n_html += 1
            disp[str(item["disposition"])] += 1
            if item["disposition"] == DISPOSITION_AUTHORED:
                authored += 1
            if item["would_voice"]:
                would_voice += 1
                voice_by[str(item["person_bucket"])] += 1
            commercial[str(item["commercial_class"])] += 1
            quote_counts[str(item["quote_quality"])] += 1
            v2_commercial[str(item["v2_commercial_class"])] += 1
            v2_quote[str(item["v2_quote_quality"])] += 1
            key = _sample_key(item)
            if key not in samples and len(samples) < PACKET_CAP:
                samples[key] = item
            unusual_reason = None
            if item["disposition"] != DISPOSITION_AUTHORED:
                unusual_reason = f"disposition:{item['disposition']}"
            elif item["quote_quality"] != "clean":
                unusual_reason = f"quote:{item['quote_quality']}"
            elif item["commercial_class"] not in {"not_commercial", "retain_life_evidence"}:
                unusual_reason = f"commercial:{item['commercial_class']}"
            elif item["person_bucket"] == "other_authenticated":
                unusual_reason = "other_authenticated"
            elif item["person_bucket"] == "unauthenticated":
                unusual_reason = "unauthenticated"
            elif any(ord(ch) > 127 for ch in item["new_cleaned"]):
                unusual_reason = "non_ascii"
            if unusual_reason and unusual_reason not in unusual_by:
                unusual_by[unusual_reason] = {**item, "unusual": unusual_reason}
        del rows
        if scanned % 5000 == 0:
            print(f"html_census_scanned={scanned}/{total}", file=sys.stderr, flush=True)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    unexplained = n_html - sum(disp.values())
    if unexplained != 0:
        raise RuntimeError("html_recovery_unexplained")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    public = {
        "ok": True,
        "kind": "html_recovery_beyond_v2_eight_letter",
        "v2_generation_id_present": True,
        "v2_checksum_present": bool(gen.get("checksum")),
        "v2_algo_version": gen["algo_version"],
        "v2_status": gen["status"],
        "v2_published": bool(gen["published"]),
        "v2_is_active": bool(gen["is_active"]),
        "prepared_messages_scanned": scanned,
        "prepared_messages_total": total,
        "html_present_and_plain_len_ge_8": candidates,
        "n_html": n_html,
        "authored_displayable": authored,
        "would_voice": would_voice,
        "voice_by_from": {
            k: int(voice_by.get(k, 0))
            for k in ("Tom", "Peggy", "Sue", "other_authenticated", "unauthenticated", "unknown")
            if voice_by.get(k)
        },
        "remain_unavailable_non_substantive_uncertain": {
            "prepared_text_unavailable": int(disp.get("prepared_text_unavailable", 0)),
            "non_substantive": int(disp.get("non_substantive", 0)),
            "uncertain": int(disp.get("uncertain", 0)),
            "attachment_only": int(disp.get("attachment_only", 0)),
            "correctly_empty": int(disp.get("correctly_empty", 0)),
        },
        "disposition": dict(disp),
        "commercial_class": dict(commercial),
        "quote_quality": dict(quote_counts),
        "v2_commercial_class": dict(v2_commercial),
        "v2_quote_quality": dict(v2_quote),
        "unexplained": unexplained,
        "scan_complete": scanned == total,
        "elapsed_ms": elapsed_ms,
        "tracemalloc_current_bytes": int(current),
        "tracemalloc_peak_bytes": int(peak),
        "v3_algo": V3_ALGO,
    }
    if scanned != total:
        public["ok"] = False
        public["error"] = "scan_incomplete"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "COUNTS.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
    lines = [
        "I14 HTML recovery beyond v2 eight-letter preference (private).",
        "Do not commit. Originals are excerpts only. Not a corpus dump.",
        f"n_html={n_html} authored_displayable={authored} would_voice={would_voice}",
        "",
    ]
    packed: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in unusual_by.values():
        if item["evidence_id"] not in seen_ids:
            packed.append(item)
            seen_ids.add(item["evidence_id"])
    for item in samples.values():
        if item["evidence_id"] not in seen_ids:
            packed.append(item)
            seen_ids.add(item["evidence_id"])
    for i, item in enumerate(packed, start=1):
        lines.append(f"===== sample {i} {item.get('unusual') or _sample_key(item)} =====")
        lines.append(
            f"{item['display_id']}-M-{int(item['ordinal']):02d} "
            f"disp={item['disposition']} would_voice={item['would_voice']} "
            f"from={item['person_bucket']} quote={item['quote_quality']} "
            f"commercial={item['commercial_class']} v2_commercial={item.get('v2_commercial_class')} "
            f"quote={item['quote_quality']} v2_quote={item.get('v2_quote_quality')}"
        )
        lines.append("SUBJECT: " + item["subject"])
        lines.append("-- plain --")
        lines.append(item["plain_excerpt"])
        lines.append("-- html --")
        lines.append(item["html_excerpt"])
        lines.append("-- html_plain --")
        lines.append(item["html_plain_excerpt"])
        lines.append("-- prepared --")
        lines.append(item["prepared_excerpt"])
        lines.append("")
    (out_dir / "PACKET.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "INDEX.txt").write_text(
        "\n".join(
            f"{it['display_id']}-M-{int(it['ordinal']):02d}\t{it['disposition']}\t"
            f"voice={it['would_voice']}\t{it['person_bucket']}\t{it['commercial_class']}\t"
            f"{it['quote_quality']}"
            for it in packed
        )
        + "\n",
        encoding="utf-8",
    )
    public["packet_samples"] = len(packed)
    public["packet_dir"] = str(out_dir)
    return public


def main(argv: list[str] | None = None) -> int:
    del argv
    from memorybox.db import connect

    allow_db = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB")
    allow_fs = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_FLIGHTSIM")
    out_dir = Path(os.environ.get("MEMORYBOX_I14_HTML_CENSUS_OUT") or "working/i14-html-recovery-review")
    conn = connect()
    try:
        conn.autocommit = True
        conn.execute("SET default_transaction_read_only = on")
        conn.autocommit = False
        conn.execute("SET TRANSACTION READ ONLY")
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
        payload = run_census(conn, out_dir=out_dir)
        conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(json.dumps({k: v for k, v in payload.items() if k != "packet_dir"}))
    return 0 if payload.get("ok") else 2
