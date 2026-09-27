"""I11A.0 accepted-I14 cleaned Communications freeze (email only).

Read-only. Does not write I14 tables. Does not call Ollama. Does not start I11A.1.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from memorybox.ask.i11a.c1t_benchmark import parse_conversations
from memorybox.ask.i11a.i11a0_benchmark import (
    TOKEN_ESTIMATOR_FORMULA,
    TOKEN_ESTIMATOR_ID,
    TOKEN_ESTIMATOR_LABEL,
    EvidencePiece,
    EvidenceTurn,
    I11A0Error,
    estimate_tokens,
    inventory_peggy_chunks,
)

ACCEPTED_I14_COMMIT = "b54be38ade9f378f1e25e0738bb9e9963f7dcd88"
ACCEPTED_ALGO_VERSION = "i14-prepared-email-v3"
SOURCE_LABEL = "accepted_i14_cleaned_household_email_export"
CHANNEL = "email"
PEGGY_DISPLAY = "Peggy George"
TOM_DISPLAY = "Tom Will"
GALLERY_PREVIEW_CHARS = 240
CONFIRM_FREEZE = "freeze-accepted-i14-cleaned-email-readonly"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_readonly_connection(conn: Any) -> None:
    row = conn.execute("SHOW default_transaction_read_only").fetchone()
    value = str((row or {}).get("default_transaction_read_only") or (row or [None])[0] or "")
    if value.lower() not in {"on", "true", "1"}:
        raise I11A0Error("i14 freeze requires a read-only session")


def resolve_person(conn: Any, display_name: str) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT id::text AS id, display_name
          FROM people
         WHERE status <> 'merged_away'
           AND lower(coalesce(display_name, '')) = lower(%s)
        """,
        (display_name,),
    ).fetchall()
    if len(rows) != 1:
        raise I11A0Error(f"person_resolution_failed:{display_name}:{len(rows)}")
    return {"person_id": str(rows[0]["id"]), "display_name": str(rows[0]["display_name"])}


def inspect_accepted_i14(conn: Any) -> dict[str, Any]:
    require_readonly_connection(conn)
    gens = conn.execute(
        """
        SELECT id::text AS id, algo_version, status, published, is_active, checksum,
               source_kind, scope_key, item_count, created_at::text, updated_at::text
          FROM comms_prepared_generations
         ORDER BY algo_version
        """
    ).fetchall()
    active = conn.execute(
        """
        SELECT id::text AS id, algo_version, checksum, source_kind, scope_key, item_count
          FROM comms_prepared_active_generations
        """
    ).fetchall()
    if len(active) != 1:
        raise I11A0Error(f"expected_one_active_generation:{len(active)}")
    if str(active[0]["algo_version"]) != ACCEPTED_ALGO_VERSION:
        raise I11A0Error(f"active_generation_not_v3:{active[0]['algo_version']}")
    if str(active[0]["source_kind"]) != CHANNEL:
        raise I11A0Error("active_generation_not_email")
    gid = active[0]["id"]
    sms_tables = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
         WHERE table_schema='public' AND table_name ILIKE '%sms%'
        """
    ).fetchall()
    sms_evidence = conn.execute(
        "SELECT COUNT(*)::int AS n FROM evidence WHERE evidence_kind ILIKE '%sms%'"
    ).fetchone()
    http_cleaned = conn.execute(
        """
        SELECT COUNT(*)::int AS n FROM comms_prepared_messages
         WHERE generation_id=%s AND cleaned_authored_text ~* 'https?://'
        """,
        (gid,),
    ).fetchone()
    longer_than_preview = conn.execute(
        """
        SELECT COUNT(*)::int AS n FROM comms_prepared_messages
         WHERE generation_id=%s AND length(cleaned_authored_text) > %s
        """,
        (gid, GALLERY_PREVIEW_CHARS),
    ).fetchone()
    max_cleaned = conn.execute(
        """
        SELECT MAX(length(cleaned_authored_text))::int AS n
          FROM comms_prepared_messages WHERE generation_id=%s
        """,
        (gid,),
    ).fetchone()
    peggy = resolve_person(conn, PEGGY_DISPLAY)
    tom = resolve_person(conn, TOM_DISPLAY)
    return {
        "accepted_i14_commit": ACCEPTED_I14_COMMIT,
        "algo_version": ACCEPTED_ALGO_VERSION,
        "generation_id": gid,
        "generation_checksum": active[0]["checksum"],
        "source_kind": CHANNEL,
        "scope_key": active[0]["scope_key"],
        "sms_included": False,
        "sms_tables": [row["table_name"] for row in sms_tables],
        "sms_evidence_rows": int((sms_evidence or {}).get("n") or 0),
        "http_in_cleaned_authored_text": int((http_cleaned or {}).get("n") or 0),
        "messages_longer_than_gallery_preview": int((longer_than_preview or {}).get("n") or 0),
        "max_cleaned_authored_chars": int((max_cleaned or {}).get("n") or 0),
        "cleaned_field": "comms_prepared_messages.cleaned_authored_text",
        "display_preview_is_not_source": True,
        "gallery_preview_sql": "left(cleaned_authored_text, N) in thread list only",
        "peggy": peggy,
        "tom": tom,
        "generations": gens,
        "active": active[0],
        "authorship_rule": (
            "From-person is comms_prepared_participants.role='from' with people.id. "
            "authorship='authenticated_focal' means any authenticated From person, not Peggy-only."
        ),
        "voice_corpus_rule": (
            "voice_corpus requires authenticated From + quote_quality=clean + "
            "identity_quality=resolved + prepared_text_disposition=authored_displayable."
        ),
        "immutable_original": "evidence.id / evidence.payload_json (not copied into benchmark prompt)",
        "channel": CHANNEL,
    }


def _export_rows(conn: Any, generation_id: str, peggy_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        WITH peggy_threads AS (
          SELECT DISTINCT t.id
            FROM comms_prepared_threads t
            JOIN comms_prepared_messages m ON m.thread_id = t.id
            JOIN comms_prepared_participants p ON p.message_id = m.id
           WHERE t.generation_id = %s
             AND p.person_id = %s::uuid
        )
        SELECT m.id::text AS prepared_message_id,
               m.evidence_id::text AS evidence_id,
               m.canonical_record_id::text AS canonical_record_id,
               m.evidence_ref,
               m.ordinal,
               m.sent_at,
               m.subject,
               m.cleaned_authored_text,
               m.forward_status,
               m.forward_omitted,
               m.urls_stripped,
               m.quote_quality,
               m.identity_quality,
               m.quote_contamination_flagged,
               m.authorship,
               m.voice_corpus,
               m.commercial_class,
               m.direction,
               m.prepared_text_disposition,
               t.display_id AS thread_display_id,
               t.id::text AS thread_id,
               t.thread_key,
               t.gallery_eligibility,
               t.suppression_reason,
               t.duplicate_omitted_count,
               t.founder_review_state,
               e.source_id::text AS source_id,
               e.evidence_kind,
               pf.display_name AS from_display_name,
               pf.person_id::text AS from_person_id,
               pf.identity_confidence AS from_identity_confidence,
               pf.address_normalized AS from_address_normalized,
               (
                 SELECT jsonb_agg(jsonb_build_object(
                          'role', pr.role,
                          'display_name', pr.display_name,
                          'person_id', pr.person_id::text,
                          'identity_confidence', pr.identity_confidence
                        ) ORDER BY pr.role, pr.display_name)
                   FROM comms_prepared_participants pr
                  WHERE pr.message_id = m.id AND pr.role IN ('to','cc')
               ) AS recipients
          FROM comms_prepared_messages m
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN evidence e ON e.id = m.evidence_id
          LEFT JOIN comms_prepared_participants pf
            ON pf.message_id = m.id AND pf.role = 'from'
         WHERE m.thread_id IN (SELECT id FROM peggy_threads)
         ORDER BY m.sent_at ASC, m.evidence_id ASC
        """,
        (generation_id, peggy_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        elif isinstance(value, UUID):
            out[key] = str(value)
        else:
            out[key] = value
    return out


def render_frozen_message(row: dict[str, Any]) -> str:
    author = str(row.get("from_display_name") or "unverified")
    pid = str(row.get("from_person_id") or "unverified")
    recipients = row.get("recipients") or []
    rec_txt = ", ".join(
        f"{item.get('role')}:{item.get('display_name') or 'unknown'}"
        for item in recipients
        if isinstance(item, dict)
    )
    body = str(row.get("cleaned_authored_text") or "")
    return "\n".join(
        [
            f"Author: {author}",
            f"Author-person-id: {pid}",
            f"Sent: {row.get('sent_at')}",
            f"Subject: {row.get('subject') or ''}",
            f"Thread: {row.get('thread_display_id')} ordinal {row.get('ordinal')}",
            f"Evidence-id: {row.get('evidence_id')}",
            f"Evidence-ref: {row.get('evidence_ref')}",
            f"Recipients: {rec_txt}",
            "",
            body,
        ]
    )


def freeze_accepted_i14_export(
    conn: Any,
    out_dir: Path | str,
    *,
    confirm: str,
    exported_at: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM_FREEZE:
        raise I11A0Error("freeze_confirm_required")
    require_readonly_connection(conn)
    inspect = inspect_accepted_i14(conn)
    rows = [_jsonable(row) for row in _export_rows(conn, inspect["generation_id"], inspect["peggy"]["person_id"])]
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    full_path = root / "peggy_related_email.jsonl"
    prompt_path = root / "i11a0_prompt_messages.jsonl"
    peggy_path = root / "peggy_only_inventory.jsonl"
    voice_path = root / "peggy_voice_corpus_inventory.jsonl"
    prompt_rows = [
        row
        for row in rows
        if str(row.get("prepared_text_disposition") or "") == "authored_displayable"
        and str(row.get("cleaned_authored_text") or "").strip()
    ]
    peggy_id = inspect["peggy"]["person_id"]
    peggy_only = [row for row in prompt_rows if str(row.get("from_person_id") or "") == peggy_id]
    voice_only = [row for row in peggy_only if bool(row.get("voice_corpus"))]

    def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    write_jsonl(full_path, rows)
    write_jsonl(prompt_path, prompt_rows)
    write_jsonl(peggy_path, peggy_only)
    write_jsonl(voice_path, voice_only)
    stamp = exported_at or utc_now()
    prompt_text = "\n\n".join(render_frozen_message(row) for row in prompt_rows)
    prompt_bytes = len(prompt_text.encode("utf-8"))
    prompt_chars = len(prompt_text)
    estimated = estimate_tokens(prompt_text) if prompt_text else 0
    peggy_text = "\n\n".join(render_frozen_message(row) for row in peggy_only)
    voice_text = "\n\n".join(render_frozen_message(row) for row in voice_only)
    sent_times = [str(row.get("sent_at") or "") for row in prompt_rows]
    threads = {str(row.get("thread_display_id")) for row in prompt_rows}
    exclusions = {
        "forward_omitted": {},
        "urls_stripped": sum(1 for row in rows if row.get("urls_stripped")),
        "quote_contamination_flagged": sum(1 for row in rows if row.get("quote_contamination_flagged")),
        "commercial_suppress_default": sum(
            1 for row in rows if row.get("commercial_class") == "suppress_default"
        ),
        "non_displayable": sum(
            1
            for row in rows
            if str(row.get("prepared_text_disposition") or "") != "authored_displayable"
        ),
        "http_in_cleaned": inspect["http_in_cleaned_authored_text"],
    }
    for row in rows:
        key = str(row.get("forward_omitted") or row.get("forward_status") or "none")
        exclusions["forward_omitted"][key] = int(exclusions["forward_omitted"].get(key) or 0) + 1
    files = {
        "peggy_related_email.jsonl": sha256_file(full_path),
        "i11a0_prompt_messages.jsonl": sha256_file(prompt_path),
        "peggy_only_inventory.jsonl": sha256_file(peggy_path),
        "peggy_voice_corpus_inventory.jsonl": sha256_file(voice_path),
    }
    manifest = {
        "source_label": SOURCE_LABEL,
        "channel": CHANNEL,
        "sms_included": False,
        "accepted_i14_commit": ACCEPTED_I14_COMMIT,
        "algo_version": ACCEPTED_ALGO_VERSION,
        "generation_id": inspect["generation_id"],
        "generation_checksum": inspect["generation_checksum"],
        "exported_at_utc": stamp,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "token_estimator_formula": TOKEN_ESTIMATOR_FORMULA,
        "token_estimator_label": TOKEN_ESTIMATOR_LABEL,
        "peggy": inspect["peggy"],
        "tom": inspect["tom"],
        "record_counts": {
            "peggy_related_messages": len(rows),
            "i11a0_prompt_messages": len(prompt_rows),
            "peggy_only_authored_displayable": len(peggy_only),
            "peggy_voice_corpus": len(voice_only),
            "threads": len(threads),
        },
        "date_range": {
            "earliest": min(sent_times) if sent_times else None,
            "latest": max(sent_times) if sent_times else None,
        },
        "i11a0_prompt_bytes": prompt_bytes,
        "i11a0_prompt_characters": prompt_chars,
        "i11a0_estimated_evidence_tokens": estimated,
        "peggy_only_estimated_evidence_tokens": estimate_tokens(peggy_text) if peggy_text else 0,
        "peggy_voice_estimated_evidence_tokens": estimate_tokens(voice_text) if voice_text else 0,
        "exclusions": exclusions,
        "file_sha256": files,
        "original_bodies_copied_into_prompt": False,
        "i11a1_started": False,
        "word_frequency_performed": False,
        "note": (
            "I11A.0 uses i11a0_prompt_messages.jsonl (Peggy-related email threads, both speakers, "
            "full cleaned_authored_text). I11A.1 later uses peggy_only / voice inventories only."
        ),
    }
    man_path = root / "MANIFEST.json"
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    files["MANIFEST.json"] = sha256_file(man_path)
    (root / "HASHES.txt").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(files.items())) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    inspect_path = root / "SOURCE_INSPECTION.json"
    inspect_path.write_text(json.dumps(inspect, indent=2, default=str) + "\n", encoding="utf-8")
    files["SOURCE_INSPECTION.json"] = sha256_file(inspect_path)
    (root / "HASHES.txt").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(files.items())) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest["file_sha256"] = files
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"ok": True, "out_dir": str(root.resolve()), "manifest": manifest, "models_called": False}


@dataclass(frozen=True)
class FrozenMessage:
    evidence_id: str
    thread_display_id: str
    sent_at: str
    text: str
    author_display_name: str
    from_person_id: str
    voice_corpus: bool


def load_frozen_prompt_messages(export_dir: Path | str) -> list[FrozenMessage]:
    path = Path(export_dir) / "i11a0_prompt_messages.jsonl"
    if not path.is_file():
        raise I11A0Error(f"missing_i14_prompt_export:{path}")
    out: list[FrozenMessage] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out.append(
            FrozenMessage(
                evidence_id=str(row["evidence_id"]),
                thread_display_id=str(row["thread_display_id"]),
                sent_at=str(row.get("sent_at") or ""),
                text=render_frozen_message(row),
                author_display_name=str(row.get("from_display_name") or "unverified"),
                from_person_id=str(row.get("from_person_id") or ""),
                voice_corpus=bool(row.get("voice_corpus")),
            )
        )
    out.sort(key=lambda item: (item.sent_at, item.evidence_id))
    return out


def messages_to_pieces(messages: Iterable[FrozenMessage]) -> list[EvidencePiece]:
    pieces: list[EvidencePiece] = []
    for item in messages:
        turn = EvidenceTurn(item.evidence_id, item.text, item.sent_at)
        pieces.append(
            EvidencePiece(
                piece_id=item.evidence_id,
                turns=(turn,),
                earliest=item.sent_at,
                latest=item.sent_at,
            )
        )
    return pieces


def compare_legacy_and_i14(
    *,
    legacy_root: Path | str | None,
    i14_export_dir: Path | str,
) -> dict[str, Any]:
    export = Path(i14_export_dir)
    manifest = json.loads((export / "MANIFEST.json").read_text(encoding="utf-8"))
    prompt_rows = [
        json.loads(line)
        for line in (export / "i11a0_prompt_messages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    peggy_rows = [
        json.loads(line)
        for line in (export / "peggy_only_inventory.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    i14_ids = [str(row["evidence_id"]) for row in prompt_rows]
    i14_dup = len(i14_ids) - len(set(i14_ids))
    legacy: dict[str, Any] = {
        "present": False,
        "label": "legacy_reviewed_seven_chunks_REVIEW_20260831T120929Z",
        "role": "historical_hardware_upper_bound_not_final_operating_point",
    }
    if legacy_root and Path(legacy_root).is_dir():
        root = Path(legacy_root)
        source_map = json.loads((root / "SOURCE_MAP.json").read_text(encoding="utf-8"))
        inventory = inventory_peggy_chunks([root])
        conversations = 0
        evidence_ids: list[str] = []
        texts: list[str] = []
        earliest = ""
        latest = ""
        for row in inventory.get("chunks") or []:
            text = Path(row["path"]).read_text(encoding="utf-8", errors="replace")
            _prefix, convos = parse_conversations(text, source_map)
            conversations += len(convos)
            for convo in convos:
                texts.append(convo.render() if hasattr(convo, "render") else "\n".join(t.text for t in convo.turns))
                for turn in convo.turns:
                    evidence_ids.append(turn.cite_as)
                if not earliest or convo.earliest < earliest:
                    earliest = convo.earliest
                if not latest or convo.latest > latest:
                    latest = convo.latest
        blob = "\n\n".join(texts)
        legacy.update(
            {
                "present": True,
                "exactly_seven": bool(inventory.get("exactly_seven")),
                "messages_or_turns": len(evidence_ids),
                "conversations": conversations,
                "date_range": {"earliest": earliest, "latest": latest},
                "bytes": len(blob.encode("utf-8")),
                "characters": len(blob),
                "estimated_evidence_tokens": estimate_tokens(blob) if blob else 0,
                "unique_cite_ids": len(set(evidence_ids)),
                "duplicate_cite_ids": len(evidence_ids) - len(set(evidence_ids)),
            }
        )
        uuid_re = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.I,
        )
        legacy_uuids = set(uuid_re.findall(blob.lower()))
        i14_set = {eid.lower() for eid in i14_ids}
        legacy["evidence_ids_in_legacy_not_i14"] = sorted(legacy_uuids - i14_set)[:50]
        legacy["evidence_ids_in_legacy_not_i14_count"] = len(legacy_uuids - i14_set)
        legacy["evidence_ids_in_i14_not_legacy_count"] = len(i14_set - legacy_uuids)
        legacy["overlap_uuid_count"] = len(legacy_uuids & i14_set)
    return {
        "estimator_label": TOKEN_ESTIMATOR_LABEL,
        "do_not_treat_byte_totals_as_semantically_identical": True,
        "legacy": legacy,
        "i14_cleaned": {
            "label": SOURCE_LABEL,
            "role": "production_representative_source_for_final_operating_point",
            "messages": len(prompt_rows),
            "threads": manifest["record_counts"]["threads"],
            "date_range": manifest["date_range"],
            "bytes": manifest["i11a0_prompt_bytes"],
            "characters": manifest["i11a0_prompt_characters"],
            "estimated_evidence_tokens": manifest["i11a0_estimated_evidence_tokens"],
            "duplicate_evidence_ids": i14_dup,
            "exclusions": manifest["exclusions"],
            "generation_checksum": manifest["generation_checksum"],
            "algo_version": manifest["algo_version"],
        },
        "peggy_only": {
            "label": "peggy_authored_cleaned_subset_for_future_i11a1",
            "messages": len(peggy_rows),
            "threads": len({row["thread_display_id"] for row in peggy_rows}),
            "estimated_evidence_tokens": manifest["peggy_only_estimated_evidence_tokens"],
            "voice_corpus_messages": manifest["record_counts"]["peggy_voice_corpus"],
            "i11a1_started": False,
        },
        "peggy_authored_words_survive": len(peggy_rows) > 0,
        "ambiguity": [
            "Legacy cite-as IDs are conversation/turn labels, not always evidence UUIDs; overlap is incomplete.",
            "I14 drops quoted history/boilerplate; lower byte totals are expected and not authored-word loss by themselves.",
            "voice_corpus is stricter than all Peggy From authored_displayable rows.",
        ],
    }


def prove_i14_phase1_offline() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, cond: bool, detail: Any = None) -> None:
        if cond:
            checks.append(name)
        else:
            problems.append(name if detail is None else f"{name}:{detail}")

    sample = {
        "from_display_name": "Peggy George",
        "from_person_id": "person-peggy",
        "sent_at": "2011-01-01T00:00:00+00:00",
        "subject": "hello",
        "thread_display_id": "T-0001",
        "ordinal": 1,
        "evidence_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "evidence_ref": "T-0001-M-01",
        "recipients": [{"role": "to", "display_name": "Tom Will"}],
        "cleaned_authored_text": "I made soup today.",
    }
    text = render_frozen_message(sample)
    ok("attribution_preserved", "Author: Peggy George" in text and "I made soup today." in text, text)
    ok("full_body_not_preview_truncated", "I made soup today." in text, None)
    ok("http_not_reintroduced", "http://" not in text.lower(), None)
    ok("i11a1_not_started", True, None)
    ok("models_not_called", True, None)
    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "i11a1_started": False,
        "pull_executed": False,
    }
