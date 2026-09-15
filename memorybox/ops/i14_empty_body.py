"""Read-only empty prepared-body classification. Never writes comms_* or evidence."""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from memorybox.explore.gallery_scope import empty_prepared_body_notice
from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_prepared_text import (
    TRACKING_HINT,
    _cut_reply_history,
    html_to_plain,
    prepare_message_text,
    source_is_meaningful,
)

CATEGORIES = (
    "original_genuinely_empty",
    "attachment_only",
    "quoted_history_only",
    "forward_history_only",
    "commercial_or_automated_shell",
    "html_only_or_alt_part",
    "encoding_or_parser_failure",
    "cleanup_removed_meaningful",
    "other_known",
    "unexplained",
)
DISPOSITIONS = ("correct_empty", "safe_nondisplayable", "defect")
PERSONAL = frozenset({"not_commercial", "retain_life_evidence"})


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def meaningful(text: str) -> bool:
    return source_is_meaningful(text)


def html_to_text(raw: str) -> str:
    return html_to_plain(raw)


def classify_empty_prepared(
    *,
    body_text: str = "",
    body_html: str = "",
    html_only: bool = False,
    has_attachments: bool = False,
    commercial_class: str = "",
    subject: str = "",
    forward_status: str = "",
) -> dict[str, str]:
    orig = str(body_text or "").strip()
    html_text = html_to_text(body_html)
    orig_m = meaningful(orig)
    html_m = meaningful(html_text)
    commercial = str(commercial_class or "")

    if not orig_m and not html_m:
        if has_attachments:
            return {
                "category": "attachment_only",
                "disposition": "correct_empty",
            }
        return {
            "category": "original_genuinely_empty",
            "disposition": "correct_empty",
        }

    if html_only or (html_m and not orig_m):
        html_prep = prepare_message_text(html_text, subject=subject)
        if meaningful(html_prep.authored):
            return {
                "category": "html_only_or_alt_part",
                "disposition": "defect",
            }
        if html_prep.quote_history_removed:
            return {
                "category": "quoted_history_only",
                "disposition": "correct_empty",
            }
        return {
            "category": "html_only_or_alt_part",
            "disposition": "safe_nondisplayable",
        }

    source = orig if orig_m else html_text
    prepared = prepare_message_text(source, subject=subject)
    authored = str(prepared.authored or "").strip()
    if meaningful(authored):
        return {
            "category": "cleanup_removed_meaningful",
            "disposition": "defect",
        }

    if "\ufffd" in orig or re.search(r"(?i)^=\?utf-8\?", orig[:120]):
        if not meaningful(authored):
            return {
                "category": "encoding_or_parser_failure",
                "disposition": "safe_nondisplayable",
            }

    if str(forward_status or "").startswith("relay") or (
        prepared.method.startswith("explicit_forward") and not meaningful(authored)
    ):
        return {
            "category": "forward_history_only",
            "disposition": "correct_empty",
        }

    if prepared.quote_history_removed and not meaningful(authored):
        before, _, _ = _cut_reply_history(source)
        if meaningful(before):
            return {
                "category": "cleanup_removed_meaningful",
                "disposition": "defect",
            }
        return {
            "category": "quoted_history_only",
            "disposition": "correct_empty",
        }

    if TRACKING_HINT.search(source) and commercial in {"suppress_default", "uncertain"}:
        return {
            "category": "commercial_or_automated_shell",
            "disposition": "correct_empty",
        }

    if prepared.urls_stripped and orig_m and not meaningful(authored):
        return {
            "category": "commercial_or_automated_shell",
            "disposition": "correct_empty",
        }

    if orig_m and not meaningful(authored):
        return {
            "category": "cleanup_removed_meaningful",
            "disposition": "defect",
        }

    if prepared.signature_removed or prepared.list_footer_removed:
        return {
            "category": "other_known",
            "disposition": "correct_empty",
        }

    return {
        "category": "unexplained",
        "disposition": "safe_nondisplayable",
    }


def notice_for(category: str, *, has_attachments: bool = False) -> str:
    if category == "attachment_only" or (has_attachments and category == "original_genuinely_empty"):
        return "This message contains attachments and no prepared text."
    if category in {"original_genuinely_empty"}:
        return "This message has no authored text."
    if category == "quoted_history_only":
        return "This message has no new authored text after removing quoted history."
    if category == "forward_history_only":
        return "This message is forwarded or quoted history only. There is no new authored text."
    if category == "commercial_or_automated_shell":
        return "This message has no family authored text."
    return empty_prepared_body_notice()


def _blank() -> dict[str, Any]:
    return {
        "messages": 0,
        "threads": set(),
        "auth_from": 0,
        "unverified_from": 0,
        "commercial": defaultdict(int),
        "with_attachments": 0,
        "voice_true": 0,
        "original_meaningful": 0,
        "personal_messages": 0,
        "suppress_messages": 0,
        "disposition": defaultdict(int),
    }


def run_audit(conn: Any) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT t.display_id, m.ordinal, m.evidence_id::text AS evidence_id,
               m.subject, m.commercial_class, m.authorship, m.identity_quality,
               m.quote_quality, m.voice_corpus, m.forward_status,
               (
                 SELECT COUNT(*)::int FROM comms_prepared_attachments a
                  WHERE a.message_id = m.id
               ) AS att_n,
               e.payload_json
          FROM comms_prepared_threads t
          JOIN comms_prepared_messages m ON m.thread_id = t.id
          JOIN comms_prepared_active_generations g ON g.id = t.generation_id
          JOIN evidence e ON e.id = m.evidence_id
         WHERE length(trim(coalesce(m.cleaned_authored_text, ''))) = 0
        """
    ).fetchall()
    buckets: dict[str, dict[str, Any]] = {k: _blank() for k in CATEGORIES}
    john = None
    samples: dict[str, list[dict[str, Any]]] = {k: [] for k in CATEGORIES}
    for rec in rows:
        payload = rec["payload_json"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        payload = payload or {}
        body_text = str(payload.get("body_text") or "")
        body_html = str(payload.get("body_html") or "")
        html_only = bool(payload.get("html_only"))
        has_att = int(rec["att_n"] or 0) > 0 or bool(payload.get("attachments"))
        cls = classify_empty_prepared(
            body_text=body_text,
            body_html=body_html,
            html_only=html_only,
            has_attachments=has_att,
            commercial_class=str(rec["commercial_class"] or ""),
            subject=str(rec["subject"] or ""),
            forward_status=str(rec["forward_status"] or ""),
        )
        cat = cls["category"]
        b = buckets[cat]
        b["messages"] += 1
        b["threads"].add(str(rec["display_id"]))
        if str(rec["authorship"] or "").startswith("authenticated"):
            b["auth_from"] += 1
        else:
            b["unverified_from"] += 1
        cc = str(rec["commercial_class"] or "")
        b["commercial"][cc] += 1
        if has_att:
            b["with_attachments"] += 1
        if rec["voice_corpus"]:
            b["voice_true"] += 1
        if meaningful(body_text) or meaningful(html_to_text(body_html)):
            b["original_meaningful"] += 1
        if cc in PERSONAL:
            b["personal_messages"] += 1
        else:
            b["suppress_messages"] += 1
        b["disposition"][cls["disposition"]] += 1
        if len(samples[cat]) < 2:
            samples[cat].append(
                {
                    "display_id": rec["display_id"],
                    "ordinal": rec["ordinal"],
                    "evidence_id": rec["evidence_id"],
                    "commercial_class": cc,
                    "authorship": rec["authorship"],
                    "disposition": cls["disposition"],
                    "original_href": "/explore/api/email/" + str(rec["evidence_id"]),
                }
            )
        if str(rec["display_id"]) == "T-39987" and int(rec["ordinal"] or 0) == 2:
            john = {
                "display_id": "T-39987",
                "ordinal": 2,
                "evidence_id": rec["evidence_id"],
                "category": cat,
                "disposition": cls["disposition"],
                "commercial_class": cc,
                "quote_quality": rec["quote_quality"],
                "voice_corpus": bool(rec["voice_corpus"]),
                "original_meaningful": meaningful(body_text) or meaningful(html_to_text(body_html)),
                "prepared_empty": True,
            }

    out_cats = []
    defect_n = 0
    for cat in CATEGORIES:
        b = buckets[cat]
        threads = sorted(b["threads"])
        disp = dict(b["disposition"])
        defect_n += int(disp.get("defect") or 0)
        out_cats.append(
            {
                "category": cat,
                "messages": b["messages"],
                "threads": len(threads),
                "authenticated_from": b["auth_from"],
                "unverified_from": b["unverified_from"],
                "commercial_class": dict(b["commercial"]),
                "with_attachments": b["with_attachments"],
                "voice_corpus_true": b["voice_true"],
                "original_has_meaningful_text": b["original_meaningful"],
                "personal_or_retain": b["personal_messages"],
                "commercial_or_uncertain": b["suppress_messages"],
                "disposition": disp,
            }
        )
    return {
        "ok": True,
        "empty_messages": len(rows),
        "defect_messages": defect_n,
        "categories": out_cats,
        "john_t39987_m02": john,
        "sample_index": samples,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    from memorybox.db import connection

    allow_db = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB")
    allow_fs = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_FLIGHTSIM") or _env_on(
        "MEMORYBOX_I14_GALLERY_TIMING_ALLOW_FLIGHTSIM"
    )
    out_dir = Path("working/i14-empty-body-audit")
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
        payload = run_audit(conn)
    counts_path = out_dir / "COUNTS.json"
    counts_path.write_text(json.dumps({k: payload[k] for k in ("ok", "empty_messages", "defect_messages", "categories", "john_t39987_m02") if k in payload}, indent=2), encoding="utf-8")
    sample_lines = [
        "I14 empty-body sample index (private). Open originals via the listed hrefs.",
        "Do not commit this file.",
        "",
    ]
    n = 0
    forced = []
    john = payload.get("john_t39987_m02")
    if john:
        forced.append(
            f"html_only_or_alt_part\tT-39987\tordinal=2\t{john['disposition']}\t/explore/api/email/{john['evidence_id']}\tJOHN"
        )
        n += 1
    for cat, items in payload["sample_index"].items():
        if cat == "other_known" or cat == "unexplained":
            continue
        for it in items[:1]:
            if n >= 12:
                break
            if john and str(it.get("display_id")) == "T-39987":
                continue
            sample_lines.append(
                f"{cat}\t{it['display_id']}\tordinal={it['ordinal']}\t{it['disposition']}\t{it['original_href']}"
            )
            n += 1
        if n >= 12:
            break
    sample_lines[3:3] = forced
    (out_dir / "SAMPLE-INDEX.txt").write_text("\n".join(sample_lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "counts": str(counts_path), "samples": str(out_dir / "SAMPLE-INDEX.txt"), "empty_messages": payload["empty_messages"], "defect_messages": payload["defect_messages"]}))
    return 0
