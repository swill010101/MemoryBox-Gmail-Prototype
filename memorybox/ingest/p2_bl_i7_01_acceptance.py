"""P2-BL-I7-01 — Export Attachments → existing SMS rows (no wipe)."""
from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.ingest.sms_export_attach import (
    build_export_index,
    reset_export_index,
    self_check,
)


PHOTO = (
    Path(__file__).resolve().parents[1] / "providers" / "_fixtures" / "photo.jpg"
)


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _write_csv(path: Path) -> None:
    headers = [
        "Chat Session",
        "Message Date",
        "Delivered Date",
        "Read Date",
        "Edited Date",
        "Service",
        "Type",
        "Sender ID",
        "Sender Name",
        "Recipients",
        "Status",
        "Replying to",
        "Subject",
        "Text",
        "Attachment",
        "Attachment type",
        "Tapback",
        "Unsend",
        "Latitude",
        "Longitude",
        "Shared Location",
        "Export Notes",
    ]
    group = "I701 Alpha & I701 Beta & I701 Gamma"
    rows = [
        [
            "I701 Unique",
            "2020-03-15 14:02:00",
            "",
            "",
            "",
            "iMessage",
            "Outgoing",
            "+15550101991",
            "Tom Will",
            "+15550101991",
            "Read",
            "",
            "",
            "unique export photo",
            "78715179111__AF89223C-3F6A-417B-A3C2-485DF14A8835.JPG",
            "image",
            "",
            "",
            "",
            "",
            "",
            "keep-me",
        ],
        [
            group,
            "2019-12-11 18:34:38",
            "",
            "",
            "",
            "iMessage",
            "Incoming",
            "+15550101992",
            "Andrew George",
            "+15550101991",
            "Read",
            "",
            "",
            "collision a",
            "78715179111__BB89223C-3F6A-417B-A3C2-485DF14A8835.JPG",
            "image",
            "",
            "",
            "",
            "",
            "",
            "keep-me",
        ],
        [
            group,
            "2019-12-11 18:34:38",
            "",
            "",
            "",
            "iMessage",
            "Incoming",
            "+15550101993",
            "Peggy George",
            "+15550101991",
            "Read",
            "",
            "",
            "collision b",
            "78715179111__CC89223C-3F6A-417B-A3C2-485DF14A8835.JPG",
            "image",
            "",
            "",
            "",
            "",
            "",
            "keep-me",
        ],
        [
            "I701 Missing",
            "2018-05-05 09:00:00",
            "",
            "",
            "",
            "SMS",
            "Incoming",
            "+15550101994",
            "Nobody",
            "+15550101991",
            "Read",
            "",
            "",
            "db slot no file",
            "78715179111__DD89223C-3F6A-417B-A3C2-485DF14A8835.JPG",
            "image",
            "",
            "",
            "",
            "",
            "",
            "keep-me",
        ],
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_attach_tree(root: Path) -> None:
    photo = PHOTO.read_bytes()
    unique = root / "I701 Unique"
    group = root / "I701 Alpha & I701 Beta & I701 Gamma"
    orphan = root / "I701 Orphan"
    for folder in (unique, group, orphan):
        folder.mkdir(parents=True, exist_ok=True)
    (unique / "2020-03-15 14 02 00 - I701 Unique - Photo.jpg").write_bytes(photo)
    (group / "2019-12-11 18 34 38 - I701 Alpha & I701 Beta & I701 Gamm - Photo.jpg").write_bytes(
        photo
    )
    (group / "2019-12-11 18 34 38 - I701 Alpha & I701 Beta & I701 Gamm-2 - Photo.jpg").write_bytes(
        photo
    )
    (orphan / "2017-06-01 12 00 00 - I701 Orphan - Photo.jpg").write_bytes(photo)
    (orphan / "2019-12-11 18 34 38 - I701 Alpha & I701 Beta & I701 Gamm-2 - Web link").write_bytes(
        b"https://example.invalid/not-a-message"
    )


def _logic(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.ingest import store as store
    from memorybox.ingest.comms_sms import ingest_sms

    matcher = self_check()
    _check(
        "i7_01_matcher_self_check",
        all(matcher.values()),
        checks,
        problems,
        f"matcher={matcher}",
    )

    token = uuid4().hex[:8]
    tmp = Path(os.environ.get("TMPDIR") or "/tmp") / f"mb-i7-01-{token}"
    sms_dir = tmp / "sms"
    attach_dir = tmp / "attach"
    sms_dir.mkdir(parents=True, exist_ok=True)
    attach_dir.mkdir(parents=True, exist_ok=True)
    csv_path = sms_dir / "messages.csv"
    _write_csv(csv_path)
    _write_attach_tree(attach_dir)
    before = csv_path.read_bytes()

    index = build_export_index([attach_dir])
    nested_root = tmp / "wrapper"
    shutil.copytree(attach_dir / "I701 Unique", nested_root / "Export Attachments" / "I701 Unique")
    nested_index = build_export_index([nested_root])
    _check(
        "i7_01_index_export_names",
        len(index.files) >= 5
        and index.lookup_uuid_or_name(
            "78715179111__AF89223C-3F6A-417B-A3C2-485DF14A8835.JPG"
        )
        is None
        and any(f.folder_chat == "I701 Unique" for f in nested_index.files),
        checks,
        problems,
        f"indexed={len(index.files)} nested={len(nested_index.files)}",
    )

    prev_dir = os.environ.get("MEMORYBOX_SMS_ATTACHMENTS_DIR")
    prev_cache = os.environ.get("MEMORYBOX_SMS_ATTACH_CACHE")
    cache_dir = tmp / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MEMORYBOX_SMS_ATTACH_CACHE"] = str(cache_dir)
    os.environ.pop("MEMORYBOX_SMS_ATTACHMENTS_DIR", None)
    reset_export_index()
    source_id = None
    try:
        first = ingest_sms(str(csv_path), label=f"i7-01-{token}")
        _check(
            "i7_01_first_ingest_no_bytes",
            bool(first.get("ok"))
            and int(first.get("inserted") or 0) == 4
            and int(first.get("attachments_stored") or 0) == 0,
            checks,
            problems,
            f"first={first.get('inserted')} stored={first.get('attachments_stored')}",
        )
        second = ingest_sms(
            str(csv_path),
            label=f"i7-01-{token}",
            attachments_dir=str(attach_dir),
        )
        after = csv_path.read_bytes()
        _check(
            "i7_01_no_wipe_hash_skip",
            bool(second.get("ok"))
            and int(second.get("inserted") or 0) == 0
            and int(second.get("skipped") or 0) == 4
            and before == after
            and bool(second.get("original_untouched")),
            checks,
            problems,
            f"inserted={second.get('inserted')} skipped={second.get('skipped')}",
        )
        missing = ingest_sms(str(csv_path), attachments_dir=str(tmp / "no-such-folder"))
        _check(
            "i7_01_missing_dir_fails_loud",
            missing.get("ok") is False
            and "attachments-dir" in str(missing.get("error") or "").lower(),
            checks,
            problems,
            f"missing_dir={missing.get('error')}",
        )
        _check(
            "i7_01_unique_backfill_and_collisions",
            bool(second.get("attachment_bytes_hunted"))
            and int((second.get("attachment_export_stats") or {}).get("export_files_indexed") or 0) >= 5
            and int(second.get("attachments_stored") or 0) == 1
            and int(second.get("attachments_ambiguous") or 0) == 2
            and int(second.get("attachment_orphan_files") or 0) == 2
            and int(second.get("attachments_missing") or 0) == 3,
            checks,
            problems,
            (
                f"stored={second.get('attachments_stored')} "
                f"ambiguous={second.get('attachments_ambiguous')} "
                f"orphans={second.get('attachment_orphan_files')} "
                f"missing={second.get('attachments_missing')}"
            ),
        )
        source_id = second.get("source_id")
        rows = store.list_evidence_for_source(UUID(str(source_id))) if source_id else []
        payloads = [_payload(r) for r in rows]
        unique_p = next(
            (p for p in payloads if "unique export photo" in str(p.get("body_text") or "")),
            {},
        )
        collide_p = [
            p
            for p in payloads
            if str(p.get("body_text") or "").startswith("collision")
        ]
        missing_p = next(
            (p for p in payloads if "db slot no file" in str(p.get("body_text") or "")),
            {},
        )
        unique_att = (unique_p.get("attachments") or [{}])[0]
        _check(
            "i7_01_unique_row_has_bytes",
            unique_att.get("bytes_ingested") is True
            and unique_att.get("match_method") == "export_unique"
            and unique_att.get("promoted_to_immich") is False
            and "I701 Unique" in str(unique_att.get("export_filename") or ""),
            checks,
            problems,
            f"unique_att={unique_att}",
        )
        _check(
            "i7_01_collision_and_orphan_unmatched",
            all(
                not (a.get("bytes_ingested") or a.get("media_object_id"))
                for p in collide_p
                for a in (p.get("attachments") or [])
            )
            and not (missing_p.get("attachments") or [{}])[0].get("bytes_ingested"),
            checks,
            problems,
            "same-second files and unmatched DB slots stay off the message",
        )
        _check(
            "i7_01_no_invented_messages",
            len(rows) == 4,
            checks,
            problems,
            f"evidence_count={len(rows)}",
        )
    finally:
        if source_id:
            from memorybox.db import connection as db_connection

            with db_connection() as conn:
                conn.execute(
                    "DELETE FROM evidence WHERE source_id = %s",
                    (UUID(str(source_id)),),
                )
        reset_export_index()
        if prev_dir is None:
            os.environ.pop("MEMORYBOX_SMS_ATTACHMENTS_DIR", None)
        else:
            os.environ["MEMORYBOX_SMS_ATTACHMENTS_DIR"] = prev_dir
        if prev_cache is None:
            os.environ.pop("MEMORYBOX_SMS_ATTACH_CACHE", None)
        else:
            os.environ["MEMORYBOX_SMS_ATTACH_CACHE"] = prev_cache
        shutil.rmtree(tmp, ignore_errors=True)


def run_p2_bl_i7_01_acceptance(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    root = Path(__file__).resolve().parents[1]
    comms = (root / "ingest" / "comms_sms.py").read_text(encoding="utf-8")
    export_mod = (root / "ingest" / "sms_export_attach.py").read_text(encoding="utf-8")
    main = (root / "__main__.py").read_text(encoding="utf-8")
    _check(
        "i7_01_module_present",
        "backfill_unique_export_attachments" in comms
        and "unique_export_pairs" in export_mod
        and "never invents messages" in export_mod
        and "--attachments-dir" in main
        and "inspect-sms-attachments" in main
        and "probe_attachments_dir" in export_mod
        and "wipe" not in comms.lower(),
        checks,
        problems,
        "Matcher is a backfill; ingest-sms does not wipe",
    )
    try:
        _logic(checks, problems)
    except Exception as exc:  # noqa: BLE001
        _check(
            "i7_01_logic_suite",
            False,
            checks,
            problems,
            f"logic suite error: {type(exc).__name__}: {exc}",
        )
    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "ok": overall,
        "checks": checks,
        "problems": problems,
        "meta": {
            "increment": "P2-BL-I7-01",
            "mode": "flightsim" if flightsim else "harness",
            "reopens_i7": False,
        },
        "note": (
            "Thin follow-up after I7 ACCEPTED. Does not wipe SMS evidence. "
            "Unique timestamp+chat matches only; collisions and orphans stay unmatched."
        ),
    }
