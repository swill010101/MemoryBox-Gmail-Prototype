"""Read-only I14 Peggy email-thread reconstruction preview.

Reuses I11A compaction and mbox RFC/vendor thread_fields. Never writes comms_*
or other persistent tables. Private HTML is gitignored. Git report is counts only
(no bodies, addresses, Message-IDs, hashes, paths, or UUIDs).

Refuse dbname memorybox unless MEMORYBOX_I14_PREVIEW_ALLOW_MEMORYBOX_DB=1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.full_evidence_l1_chunker import compact_email_item
from memorybox.ingest.comms_lineage import normalize_rfc_message_id
from memorybox.ops.i14_duplicate_audit import (
    EMAIL_RE,
    HEX64,
    HEX_PREFIX,
    UUID_RE,
    WRITE_HEAD,
)
from memorybox.ops import i14_thread_review as review
from memorybox.person.phone_map import normalize_handle
from memorybox.providers.email_read.mbox_parse import parse_message_ids, thread_fields

CASE_IDS = (
    "normal_two_person",
    "long_thread",
    "forwarded_message",
    "quoted_reply_stripping",
    "changed_subject",
    "missing_or_malformed_message_id",
    "duplicate_across_extracts",
    "attachment_indicators",
    "ambiguous_participant_identity",
    "threader_split_or_combine",
    "likely_incorrect_split",
    "likely_incorrect_merge",
)

MARK_IDS = (
    "accept_thread",
    "split_here",
    "merge_with_another",
    "incorrect_participant",
    "incorrect_ordering",
    "quoted_text_removed_incorrectly",
    "missing_message",
    "needs_investigation",
)

MIN_ASSIGNED_MBOX_ROWS = 1000
LONG_THREAD_MESSAGES = 8
WRITE_HEAD_RE = WRITE_HEAD
FWD_SUBJ = re.compile(r"^\s*(fwd?|fw)\s*:", re.I)
RE_SUBJ = re.compile(r"^\s*((re|fwd?|fw)\s*:)+\s*", re.I)
HTML_TAG = re.compile(r"<[^>]+>")


class PreviewError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def catalog_execute(conn: Any, sql: str, params: tuple | list | None = None) -> Any:
    _refuse_persistent_write(sql)
    if not params:
        return conn.execute(sql)
    return conn.execute(sql, params)


def _refuse_persistent_write(sql: str) -> None:
    stripped = sql.strip()
    if stripped.startswith("--"):
        return
    if WRITE_HEAD_RE.match(stripped) or re.search(
        r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b", stripped, re.I
    ):
        raise PreviewError("persistent_write_refused")


def require_dbname(conn: Any) -> str:
    row = catalog_execute(conn, "SELECT current_database() AS d").fetchone()
    name = str(row["d"] if isinstance(row, dict) else row[0]).lower()
    allow = os.environ.get("MEMORYBOX_I14_PREVIEW_ALLOW_MEMORYBOX_DB", "").strip() == "1"
    if name == "memorybox" and not allow:
        raise PreviewError("refused_memorybox_dbname")
    return name


def _norm_rfc(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    strict = normalize_rfc_message_id(text)
    if strict:
        return strict
    if not (text.startswith("<") and text.endswith(">")):
        text = f"<{text.strip('<>')}>"
    return text.lower() if "@" in text else None


def _subject_stem(subject: str) -> str:
    return RE_SUBJ.sub("", (subject or "").strip().lower())


def _body_text(payload: dict[str, Any]) -> str:
    text = str(payload.get("body_text") or "")
    if text.strip():
        return text
    raw_html = str(payload.get("body_html") or "")
    if raw_html.strip():
        return HTML_TAG.sub(" ", raw_html)
    return ""


def _attachment_flag(payload: dict[str, Any]) -> bool:
    atts = payload.get("attachments") or []
    if isinstance(atts, list) and atts:
        return True
    return bool(payload.get("has_attachments"))


def message_from_payload(
    *,
    evidence_id: str,
    source_id: str,
    payload: dict[str, Any],
    content_hash: str | None = None,
) -> dict[str, Any]:
    rfc = _norm_rfc(payload.get("rfc_message_id") or payload.get("message_id"))
    irt = tuple(
        x
        for x in (
            _norm_rfc(v)
            for v in (payload.get("in_reply_to_ids") or parse_message_ids(payload.get("in_reply_to")))
        )
        if x
    )
    refs = tuple(
        x
        for x in (
            _norm_rfc(v)
            for v in (payload.get("reference_ids") or parse_message_ids(payload.get("references")))
        )
        if x
    )
    vendor = str(payload.get("vendor_thread_id") or "").strip() or None
    stored_thread = str(payload.get("thread_id") or "").strip() or None
    computed, status = thread_fields(
        rfc_message_id=rfc,
        in_reply_to_ids=irt,
        reference_ids=refs,
        vendor=vendor,
    )
    skip = str(payload.get("mailbox_skip") or "").strip().lower()
    raw = _body_text(payload)
    from_h = str(payload.get("from") or "")
    to_h = payload.get("to")
    if isinstance(to_h, list):
        to_h = ", ".join(str(x) for x in to_h if str(x).strip())
    else:
        to_h = str(to_h or "")
    from_n = normalize_handle(from_h)
    people_ids = [str(x) for x in (payload.get("person_ids") or []) if str(x).strip()]
    return {
        "evidence_id": str(evidence_id),
        "source_id": str(source_id),
        "item_id": str(evidence_id),
        "source": "email",
        "timestamp": str(payload.get("sent_at") or ""),
        "from": from_h,
        "from_handle": from_n,
        "from_parsed": payload.get("from_parsed") or [],
        "to": to_h,
        "to_parsed": payload.get("to_parsed") or [],
        "cc": payload.get("cc"),
        "cc_parsed": payload.get("cc_parsed") or [],
        "bcc": payload.get("bcc"),
        "bcc_parsed": payload.get("bcc_parsed") or [],
        "payload": payload,
        "subject": str(payload.get("subject") or ""),
        "body": raw,
        "raw_body": raw,
        "rfc_message_id": rfc,
        "in_reply_to_ids": irt,
        "reference_ids": refs,
        "vendor_thread_id": vendor,
        "stored_thread_id": stored_thread,
        "computed_thread_id": computed,
        "thread_status": status,
        "mailbox_skip": skip,
        "content_hash": (content_hash or str(payload.get("content_hash") or "")).strip().lower(),
        "attachments": bool(_attachment_flag(payload)),
        "attachment_meta": review.attachment_meta(payload, None),
        "person_ids": people_ids,
        "spam_or_trash": skip in {"spam", "trash"},
    }


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self.parent.setdefault(key, key)

    def find(self, key: str) -> str:
        self.add(key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _token_keys(msg: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    if msg.get("vendor_thread_id"):
        keys.append(f"vendor:{msg['vendor_thread_id']}")
    if msg.get("stored_thread_id"):
        keys.append(f"stored:{msg['stored_thread_id']}")
    if msg.get("computed_thread_id"):
        keys.append(f"computed:{msg['computed_thread_id']}")
    if msg.get("rfc_message_id"):
        keys.append(f"rfc:{msg['rfc_message_id']}")
    for token in list(msg.get("in_reply_to_ids") or []) + list(msg.get("reference_ids") or []):
        if token:
            keys.append(f"rfc:{token}")
    return keys


def cluster_threads(messages: list[dict[str, Any]]) -> dict[str, str]:
    uf = _UnionFind()
    msg_ids = [str(m["evidence_id"]) for m in messages]
    for mid in msg_ids:
        uf.add(f"msg:{mid}")
    for msg in messages:
        keys = _token_keys(msg)
        mid = f"msg:{msg['evidence_id']}"
        if not keys:
            continue
        uf.union(mid, keys[0])
        for k in keys[1:]:
            uf.union(keys[0], k)
    return {str(m["evidence_id"]): uf.find(f"msg:{m['evidence_id']}") for m in messages}


def _dupe_key(msg: dict[str, Any]) -> str:
    digest = str(msg.get("content_hash") or "").strip()
    if digest and HEX64.fullmatch(digest):
        return f"hash:{digest}"
    rfc = msg.get("rfc_message_id")
    if rfc:
        return f"rfc:{rfc}"
    return f"row:{msg['evidence_id']}"


def partition_population(messages: list[dict[str, Any]]) -> dict[str, Any]:
    excluded: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("spam_or_trash"):
            excluded.append({**msg, "exclude_reason": "spam_or_trash"})
        elif not msg.get("evidence_id"):
            excluded.append({**msg, "exclude_reason": "malformed"})
        else:
            eligible.append(msg)

    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for msg in eligible:
        by_key[_dupe_key(msg)].append(msg)
    displayed: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for key, group in by_key.items():
        group_sorted = sorted(
            group,
            key=lambda m: (str(m.get("timestamp") or ""), str(m.get("evidence_id") or "")),
        )
        displayed.append(group_sorted[0])
        for extra in group_sorted[1:]:
            duplicates.append({**extra, "duplicate_of": group_sorted[0]["evidence_id"], "dupe_key_class": key.split(":", 1)[0]})
    unexplained = len(eligible) - len(displayed) - len(duplicates)
    return {
        "excluded": excluded,
        "eligible": eligible,
        "displayed": displayed,
        "duplicates": duplicates,
        "unexplained": unexplained,
    }


def _compact_thread_messages(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(msgs, key=lambda m: (str(m.get("timestamp") or ""), str(m.get("evidence_id") or "")))
    prior: list[str] = []
    out: list[dict[str, Any]] = []
    for msg in ordered:
        item = {
            "item_id": msg["evidence_id"],
            "source": "email",
            "timestamp": msg.get("timestamp"),
            "body": msg.get("raw_body") or msg.get("body") or "",
        }
        compacted, counts = compact_email_item(item, prior_bodies=prior)
        row = dict(msg)
        row["cleaned_body"] = compacted.get("body") or ""
        row["raw_body_chars"] = len(str(msg.get("raw_body") or ""))
        row["quoted_removed"] = bool((compacted.get("compaction") or {}).get("quoted_removed"))
        row["compaction_counts"] = counts
        prior.append(str(compacted.get("body") or ""))
        out.append(row)
    return out


def _handles(msg: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for raw in (msg.get("from"), msg.get("to"), msg.get("cc")):
        if raw is None:
            continue
        if isinstance(raw, list):
            texts = [str(x) for x in raw]
        else:
            texts = [str(raw)]
        for text in texts:
            handle = normalize_handle(text)
            if handle and "@" in handle:
                found.add(handle)
            for match in EMAIL_RE.findall(text):
                found.add(match.lower())
    if msg.get("from_handle") and "@" in str(msg["from_handle"]):
        found.add(str(msg["from_handle"]).lower())
    return found


def classify_thread(thread: dict[str, Any], *, all_stems: dict[str, list[str]]) -> list[str]:
    msgs = thread["messages"]
    cases: list[str] = []
    froms = {str(m.get("from_handle") or "") for m in msgs if m.get("from_handle")}
    if len(msgs) >= 2 and len(froms) == 2:
        cases.append("normal_two_person")
    if len(msgs) >= LONG_THREAD_MESSAGES:
        cases.append("long_thread")
    if any(FWD_SUBJ.match(str(m.get("subject") or "")) or "begin forwarded message" in str(m.get("raw_body") or "").lower() for m in msgs):
        cases.append("forwarded_message")
    if any(m.get("quoted_removed") for m in msgs):
        cases.append("quoted_reply_stripping")
    stems = {_subject_stem(str(m.get("subject") or "")) for m in msgs}
    stems.discard("")
    raw_subjects = {str(m.get("subject") or "").strip() for m in msgs}
    if len(raw_subjects) > 1:
        cases.append("changed_subject")
    if any((not m.get("rfc_message_id")) or m.get("thread_status") == "unthreaded" for m in msgs):
        cases.append("missing_or_malformed_message_id")
    if thread.get("duplicate_omitted", 0) > 0:
        cases.append("duplicate_across_extracts")
    if any(m.get("attachments") or m.get("attachment_meta") for m in msgs):
        cases.append("attachment_indicators")
    if any(m.get("ambiguous_participant") for m in msgs):
        cases.append("ambiguous_participant_identity")
    vendor_ids = {m.get("vendor_thread_id") for m in msgs if m.get("vendor_thread_id")}
    if len(vendor_ids) > 1:
        cases.append("likely_incorrect_merge")
        cases.append("threader_split_or_combine")
    stem = next(iter(stems), "")
    if stem and len(all_stems.get(stem) or []) > 1 and any(not m.get("rfc_message_id") for m in msgs):
        cases.append("likely_incorrect_split")
        if "threader_split_or_combine" not in cases:
            cases.append("threader_split_or_combine")
    return cases


def reconstruct(
    messages: list[dict[str, Any]],
    *,
    focal_person_id: str | None = None,
    ledger: review.IdentityLedger | None = None,
) -> dict[str, Any]:
    parts = partition_population(messages)
    displayed = parts["displayed"]
    clusters = cluster_threads(displayed)
    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for msg in displayed:
        by_cluster[clusters[str(msg["evidence_id"])]].append(msg)
    dupes_by_displayed: dict[str, int] = defaultdict(int)
    for dupe in parts["duplicates"]:
        dupes_by_displayed[str(dupe.get("duplicate_of") or "")] += 1

    stems: dict[str, list[str]] = defaultdict(list)
    for cid, msgs in by_cluster.items():
        stem = _subject_stem(str((msgs[0].get("subject") if msgs else "") or ""))
        if stem:
            stems[stem].append(cid)

    ident = ledger or review.IdentityLedger(focal_person_id=str(focal_person_id or ""))
    threads: list[dict[str, Any]] = []
    for index, (cid, msgs) in enumerate(sorted(by_cluster.items(), key=lambda kv: kv[0])):
        compacted = review.annotate_messages(_compact_thread_messages(msgs), ident)
        omitted = sum(dupes_by_displayed[str(m["evidence_id"])] for m in compacted)
        warnings: list[str] = []
        if any(not m.get("rfc_message_id") for m in compacted):
            warnings.append("missing_or_malformed_message_id")
        if omitted:
            warnings.append("duplicate_omitted")
        if any(m.get("ambiguous_participant") for m in compacted):
            warnings.append("unverified_participant")
        if any(m.get("quoted_removed") for m in compacted):
            warnings.append("quoted_text_removed")
        thread = {
            "preview_thread_id": f"T-{index + 1:04d}",
            "cluster_key": cid,
            "focal_person_id": ident.focal_person_id,
            "messages": compacted,
            "message_count": len(compacted),
            "source_evidence_count": len(compacted) + omitted,
            "duplicate_omitted": omitted,
            "warnings": warnings,
        }
        thread["cases"] = classify_thread(thread, all_stems=stems)
        if "likely_incorrect_split" in thread["cases"]:
            warnings.append("likely_incorrect_split")
        if "likely_incorrect_merge" in thread["cases"]:
            warnings.append("likely_incorrect_merge")
        thread["warnings"] = list(dict.fromkeys(warnings))
        review.thread_confidence(thread)
        threads.append(thread)

    coverage = {cid: 0 for cid in CASE_IDS}
    for thread in threads:
        for cid in thread["cases"]:
            if cid in coverage:
                coverage[cid] += 1
    eligible_n = len(parts["eligible"])
    displayed_n = len(displayed)
    dupe_n = len(parts["duplicates"])
    excl_n = len(parts["excluded"])
    unexplained = eligible_n - displayed_n - dupe_n
    all_displayed_msgs = [m for t in threads for m in t["messages"]]
    census = review.authorship_census(all_displayed_msgs)
    return {
        "threads": threads,
        "eligible": eligible_n,
        "displayed": displayed_n,
        "deliberate_duplicates": dupe_n,
        "excluded": excl_n,
        "unexplained": unexplained,
        "excluded_reasons": _count_reason(parts["excluded"], "exclude_reason"),
        "duplicate_classes": _count_reason(parts["duplicates"], "dupe_key_class"),
        "case_coverage": coverage,
        "case_missing": [cid for cid, n in coverage.items() if n == 0],
        "completeness_ok": unexplained == 0,
        "thread_count": len(threads),
        "authorship": census,
        "detector_note": (
            "ambiguous_participant_identity means an unverified From/To/Cc address "
            "on the thread after confirmed-contact authentication; it is not a "
            "display-name miss."
        ),
    }


def _count_reason(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for row in rows:
        out[str(row.get(field) or "unknown")] += 1
    return dict(out)


def counts_report(pack: dict[str, Any], *, marks: dict[str, str] | None = None) -> dict[str, Any]:
    mark_counts = {mid: 0 for mid in MARK_IDS}
    for value in (marks or {}).values():
        if value in mark_counts:
            mark_counts[value] += 1
    report = {
        "ok": True,
        "read_only": True,
        "production_i14_writes": False,
        "person_gate": "peggy",
        "eligible": int(pack["eligible"]),
        "displayed": int(pack["displayed"]),
        "deliberate_duplicates": int(pack["deliberate_duplicates"]),
        "excluded": int(pack["excluded"]),
        "unexplained": int(pack["unexplained"]),
        "completeness_ok": bool(pack["completeness_ok"]),
        "thread_count": int(pack["thread_count"]),
        "case_coverage": dict(pack["case_coverage"]),
        "case_missing": list(pack["case_missing"]),
        "excluded_reasons": dict(pack.get("excluded_reasons") or {}),
        "duplicate_classes": dict(pack.get("duplicate_classes") or {}),
        "authorship": {k: int(v) for k, v in dict(pack.get("authorship") or {}).items()},
        "ambiguity_detector": "unverified_header_address",
        "focal_confirmed_addresses": int(pack.get("confirmed_address_count") or 0),
        "ledger_unique_addresses": int(pack.get("ledger_address_count") or 0),
        "ledger_unique_people": int(pack.get("ledger_person_count") or 0),
        "mark_counts": mark_counts,
        "founder_accept_recorded": False,
        "second_person_required": True,
        "load_authorization": False,
        "private_review_emitted": False,
    }
    assert_counts_only(report)
    return report


def assert_counts_only(payload: dict[str, Any]) -> None:
    blob = json.dumps(payload, default=str)
    if HEX64.search(blob):
        raise PreviewError("preview_output_contains_hash")
    if UUID_RE.search(blob):
        raise PreviewError("preview_output_contains_uuid")
    if EMAIL_RE.search(blob):
        raise PreviewError("preview_output_contains_address")
    if HEX_PREFIX.search(blob):
        raise PreviewError("preview_output_contains_hash_prefix")
    lowered = blob.lower()
    for marker in (".mbox", "message-id", "://", "\\\\"):
        if marker in lowered:
            raise PreviewError("preview_output_contains_uri_or_token")


def render_html(*_args: Any, **_kwargs: Any) -> str:
    raise PreviewError("html_review_retired")


def _addr_sql(addrs: list[str]) -> tuple[str, list[Any]]:
    norms = sorted({a.strip().lower() for a in addrs if a.strip() and "@" in a})
    if not norms:
        raise PreviewError("no_confirmed_addresses")
    patterns = [f"%{a}%" for a in norms]
    sql = (
        "("
        " lower(coalesce(payload_json->>'from', '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'to')::text, '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'cc')::text, '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'bcc')::text, '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'from_parsed')::text, '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'to_parsed')::text, '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'cc_parsed')::text, '')) LIKE ANY(%s)"
        " OR lower(coalesce((payload_json->'bcc_parsed')::text, '')) LIKE ANY(%s)"
        ")"
    )
    return sql, [patterns] * 8


def load_confirmed_addresses(conn: Any, person_id: str) -> list[str]:
    addrs: set[str] = set()
    rows = catalog_execute(
        conn,
        """
        SELECT value_text AS v
        FROM person_contact_points
        WHERE contact_kind = 'email' AND status = 'confirmed' AND person_id::text = %s
        """,
        (person_id,),
    ).fetchall()
    for row in rows:
        n = normalize_handle(str(row.get("v") or ""))
        if n and "@" in n:
            addrs.add(n)
    ident = catalog_execute(
        conn,
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'communication_identities'
        """,
    ).fetchone()
    if ident:
        rows = catalog_execute(
            conn,
            """
            SELECT address_normalized AS v
            FROM communication_identities
            WHERE identity_kind = 'email'
              AND resolution_status = 'confirmed'
              AND resolved_person_id::text = %s
            """,
            (person_id,),
        ).fetchall()
        for row in rows:
            n = normalize_handle(str(row.get("v") or ""))
            if n and "@" in n:
                addrs.add(n)
    if not addrs:
        raise PreviewError("no_confirmed_addresses")
    return sorted(addrs)


def load_identity_ledger(conn: Any, *, focal_person_id: str, focal_label: str) -> review.IdentityLedger:
    ledger = review.IdentityLedger(focal_person_id=str(focal_person_id))
    rows = catalog_execute(
        conn,
        """
        SELECT p.id::text AS pid, p.display_name AS n, c.value_text AS v
        FROM person_contact_points c
        JOIN people p ON p.id = c.person_id
        WHERE c.contact_kind = 'email' AND c.status = 'confirmed' AND p.status <> 'merged_away'
        """,
    ).fetchall()
    for row in rows:
        review.add_confirmed_address(
            ledger,
            address=str(row.get("v") or ""),
            person_id=str(row.get("pid") or ""),
            label=str(row.get("n") or ""),
        )
    ident = catalog_execute(
        conn,
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'communication_identities'
        """,
    ).fetchone()
    if ident:
        rows = catalog_execute(
            conn,
            """
            SELECT resolved_person_id::text AS pid, address_normalized AS v
            FROM communication_identities
            WHERE identity_kind = 'email' AND resolution_status = 'confirmed'
              AND resolved_person_id IS NOT NULL
            """,
        ).fetchall()
        labels = dict(ledger.person_label)
        for row in rows:
            pid = str(row.get("pid") or "")
            review.add_confirmed_address(
                ledger,
                address=str(row.get("v") or ""),
                person_id=pid,
                label=labels.get(pid, ""),
            )
    review.add_confirmed_address(
        ledger,
        address="",
        person_id=focal_person_id,
        label=focal_label,
    )
    if focal_label:
        ledger.person_label[str(focal_person_id)] = focal_label
    return ledger


def resolve_person(conn: Any, *, person_id: str | None, person_name: str | None) -> tuple[str, str]:
    if person_id:
        row = catalog_execute(
            conn,
            "SELECT id::text AS id, display_name AS n FROM people WHERE id::text = %s",
            (person_id,),
        ).fetchone()
        if not row:
            raise PreviewError("person_not_found")
        return str(row["id"]), str(row.get("n") or "")
    name = (person_name or "Peggy George").strip()
    rows = catalog_execute(
        conn,
        """
        SELECT id::text AS id, display_name AS n
        FROM people
        WHERE status <> 'merged_away' AND lower(coalesce(display_name, '')) = lower(%s)
        """,
        (name,),
    ).fetchall()
    if len(rows) == 1:
        return str(rows[0]["id"]), str(rows[0].get("n") or name)
    if len(rows) > 1:
        raise PreviewError("ambiguous_person")
    raise PreviewError("person_not_found")


def assigned_mbox_sources(conn: Any) -> list[str]:
    rows = catalog_execute(
        conn,
        """
        SELECT e.source_id::text AS sid, COUNT(*)::int AS n
        FROM evidence e
        JOIN sources s ON s.id = e.source_id
        WHERE e.evidence_kind = 'communication'
          AND s.source_kind = 'mbox_import'
        GROUP BY e.source_id
        HAVING COUNT(*) >= %s
        """,
        (MIN_ASSIGNED_MBOX_ROWS,),
    ).fetchall()
    ids = [str(r["sid"]) for r in rows]
    if not ids:
        raise PreviewError("no_assigned_mbox_source")
    return ids


def load_messages(conn: Any, *, addresses: list[str]) -> list[dict[str, Any]]:
    source_ids = assigned_mbox_sources(conn)
    addr_sql, addr_params = _addr_sql(addresses)
    catalog_execute(conn, "SET LOCAL statement_timeout = '60s'")
    rows = catalog_execute(
        conn,
        f"""
        SELECT e.id::text AS id, e.source_id::text AS source_id, e.payload_json AS payload
        FROM evidence e
        WHERE e.evidence_kind = 'communication'
          AND e.source_id::text = ANY(%s)
          AND lower(coalesce(e.payload_json->>'evidence_channel', 'email'))
              NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs')
          AND {addr_sql}
        ORDER BY e.id
        """,
        tuple([source_ids] + list(addr_params)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            continue
        out.append(
            message_from_payload(
                evidence_id=str(row["id"]),
                source_id=str(row["source_id"]),
                payload=payload,
            )
        )
    return out


def run_from_conn(conn: Any, *, person_id: str | None, person_name: str | None) -> dict[str, Any]:
    require_dbname(conn)
    catalog_execute(conn, "SET LOCAL idle_in_transaction_session_timeout = '120s'")
    pid, label = resolve_person(conn, person_id=person_id, person_name=person_name)
    addrs = load_confirmed_addresses(conn, pid)
    ledger = load_identity_ledger(conn, focal_person_id=pid, focal_label=label)
    messages = load_messages(conn, addresses=addrs)
    pack = reconstruct(messages, focal_person_id=pid, ledger=ledger)
    pack["loaded_rows"] = len(messages)
    pack["confirmed_address_count"] = len(addrs)
    pack["ledger_address_count"] = len(ledger.address_to_person)
    pack["ledger_person_count"] = len({p for p in ledger.address_to_person.values()})
    return pack


def write_counts(pack: dict[str, Any], counts_path: Path | None) -> dict[str, Any]:
    report = counts_report(pack)
    if counts_path is not None:
        counts_path.parent.mkdir(parents=True, exist_ok=True)
        counts_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="i14_peggy_preview")
    parser.add_argument("--fixture-json", help="Synthetic messages JSON; skips database")
    parser.add_argument("--counts-out")
    parser.add_argument("--review-out", help="Private TXT tree (refused for production unless emit env is set)")
    parser.add_argument("--representative-only", action="store_true")
    parser.add_argument("--census-only", action="store_true")
    parser.add_argument("--person-id")
    parser.add_argument("--person-name", default="Peggy George")
    parser.add_argument("--html-out", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.html_out:
        raise PreviewError("html_review_retired")
    if args.review_out and not args.fixture_json and not args.census_only:
        if os.environ.get("MEMORYBOX_I14_REVIEW_EMIT_PRIVATE", "").strip() != "1":
            raise PreviewError("private_review_emit_not_authorized")
    counts_out = Path(args.counts_out) if args.counts_out else None

    def _pack_from_fixture() -> dict[str, Any]:
        raw = json.loads(Path(args.fixture_json).read_text(encoding="utf-8"))
        messages = []
        for row in raw:
            if isinstance(row, dict) and "payload" in row:
                messages.append(
                    message_from_payload(
                        evidence_id=str(row.get("evidence_id") or row.get("id")),
                        source_id=str(row.get("source_id") or "src"),
                        payload=row["payload"],
                    )
                )
            else:
                messages.append(row)
        return reconstruct(messages)

    if args.fixture_json:
        pack = _pack_from_fixture()
    else:
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise PreviewError("MEMORYBOX_DATABASE_URL_missing")
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)
        try:
            pack = run_from_conn(conn, person_id=args.person_id, person_name=args.person_name)
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()
    if args.review_out and not args.census_only:
        meta = review.write_review_tree(
            pack, Path(args.review_out), representative_only=bool(args.representative_only)
        )
        pack["private_review_meta"] = {
            "packet_files": len(meta.get("packet_files") or []),
            "thread_count_written": meta.get("thread_count_written"),
            "original_files": meta.get("original_files"),
            "representative_coverage": {
                k: ("present" if v != "not_present_in_corpus" else v)
                for k, v in dict(meta.get("representative_coverage") or {}).items()
            },
        }
    report = write_counts(pack, counts_out)
    if pack.get("private_review_meta"):
        report = dict(report)
        report["private_review_emitted"] = True
        report["representative_coverage"] = pack["private_review_meta"]["representative_coverage"]
        assert_counts_only(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreviewError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(json.dumps({"ok": False, "error": "preview_failed"}), file=sys.stderr)
        raise SystemExit(1) from None
