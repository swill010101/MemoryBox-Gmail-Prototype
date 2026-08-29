"""Peggy full-evidence historian benchmark + compression funnel (diagnostic only).

Freezes the successful full-evidence Peggy experiment, measures the compression
funnel, and builds Level-1 complete-coverage chunks. No LLM. No production I11A
behavior changes.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.full_evidence_diagnostic import (
    PEGGY_ASK,
    DIAGNOSTIC_VERSION as FULL_EVIDENCE_DIAG_VERSION,
    estimate_tokens,
    format_cloud_paste,
    format_full_evidence_text,
    normalize_retrieved,
    resolve_peggy_plan,
    retrieve_eligible_hits,
    _source_metrics,
    _total_metrics,
)
from memorybox.ask.i11a.full_evidence_l1_chunker import run_l1_chunker
from memorybox.ask.i11a.historian_prepared import (
    ask_relative_request_from_prepared,
    count_ho_units,
    count_rollups,
    plan_to_snapshot,
)
from memorybox.ask.i11a.person_context import build_person_context, slim_person_context_for_model
from memorybox.person.phone_map import normalize_handle

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_BENCH_DIR = _REPO_ROOT / "docs" / "test-output" / "historian-full-evidence" / "peggy"

BENCHMARK_VERSION = 1


def _utc_stamp(when: datetime | None = None) -> str:
    return (when or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _family_inventory(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        by_src[str(it.get("source") or "other")].append(it)

    sms = by_src.get("sms") or []
    email = by_src.get("email") or []
    sms_channels = {str(it.get("thread_id") or "") for it in sms if it.get("thread_id")}
    email_threads = {str(it.get("thread_id") or "") for it in email if it.get("thread_id")}

    def _sz(members: list[dict[str, Any]]) -> dict[str, Any]:
        from memorybox.ask.i11a.full_evidence_diagnostic import format_item_block

        text = "\n".join(format_item_block(m) for m in members)
        b = text.encode("utf-8")
        dates = sorted(str(m.get("timestamp") or "") for m in members if m.get("timestamp"))
        return {
            "count": len(members),
            "bytes": len(b),
            "characters": len(text),
            "estimated_tokens": estimate_tokens(text) if text else 0,
            "earliest_date": dates[0] if dates else None,
            "latest_date": dates[-1] if dates else None,
        }

    families = {src: _sz(members) for src, members in sorted(by_src.items())}
    total_text_parts = []
    for src in sorted(by_src):
        from memorybox.ask.i11a.full_evidence_diagnostic import format_item_block

        total_text_parts.extend(format_item_block(m) for m in by_src[src])
    total_text = "\n".join(total_text_parts)
    total_b = total_text.encode("utf-8")
    all_dates = sorted(str(it.get("timestamp") or "") for it in items if it.get("timestamp"))

    return {
        "total_eligible_evidence_items": len(items),
        "sms_message_count": len(sms),
        "sms_conversation_channel_count": len(sms_channels),
        "email_message_count": len(email),
        "email_thread_count": len(email_threads),
        "calendar_count": len(by_src.get("calendar") or []),
        "photo_count": len(by_src.get("photo") or []),
        "video_count": len(by_src.get("video") or []),
        "story_count": len(by_src.get("story") or []),
        "journal_count": len(by_src.get("journal") or []),
        "artifact_count": len(by_src.get("artifact") or []),
        "travel_derived_count": len(by_src.get("travel") or []),
        "person_fact_count": len(by_src.get("person") or []),
        "guided_capture_count": len(by_src.get("guided_capture") or []),
        "other_family_counts": {
            k: len(v)
            for k, v in by_src.items()
            if k
            not in {
                "sms",
                "email",
                "calendar",
                "photo",
                "video",
                "story",
                "journal",
                "artifact",
                "travel",
                "person",
                "guided_capture",
            }
        },
        "by_family": families,
        "total": {
            "count": len(items),
            "bytes": len(total_b),
            "characters": len(total_text),
            "estimated_tokens": estimate_tokens(total_text) if total_text else 0,
            "earliest_date": all_dates[0] if all_dates else None,
            "latest_date": all_dates[-1] if all_dates else None,
        },
    }


def _layer_size(label: str, count: int, payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, default=str, ensure_ascii=False)
    b = text.encode("utf-8")
    return {
        "layer": label,
        "count": count,
        "bytes": len(b),
        "characters": len(text),
        "estimated_tokens": estimate_tokens(text) if text else 0,
    }


def build_compression_funnel(
    items: list[dict[str, Any]],
    *,
    fixture_path: Path | str | None = None,
    historian_run_path: Path | str | None = None,
    prepared_units: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Measure full evidence → units → observations → rollups → HO → narrator."""
    inventory = _family_inventory(items)
    layers: list[dict[str, Any]] = []

    full_layer = _layer_size(
        "full_normalized_evidence",
        inventory["total"]["count"],
        "\n".join(
            __import__(
                "memorybox.ask.i11a.full_evidence_diagnostic", fromlist=["format_item_block"]
            ).format_item_block(it)
            for it in items
        ),
    )
    layers.append(full_layer)

    fixture_info: dict[str, Any] = {"available": False}
    if fixture_path and Path(fixture_path).is_file():
        from memorybox.ask.i11a.historian_fixture import load_fixture

        fixture = load_fixture(fixture_path)
        prepared = fixture.get("prepared") or {}
        fixture_info = {
            "available": True,
            "path": str(fixture_path),
            "input_sha256": fixture.get("input_sha256"),
            "case_id": fixture.get("case_id"),
        }
        # Prepared semantic units (pre-extract / pack units if present).
        pack_min = prepared.get("pack_minimal") or {}
        units = prepared_units
        if units is None:
            units = list(pack_min.get("units") or [])
            # Prefer accounting if richer.
            acc = prepared.get("accounting") or {}
            unit_n = int(acc.get("units_generated") or acc.get("eligible_units") or len(units))
        else:
            unit_n = len(units)
            acc = prepared.get("accounting") or {}
        # Use observations list size for units when pack_minimal only has stubs.
        if unit_n <= len(units) and acc.get("units_passed_to_inference"):
            # Keep both: generated vs passed.
            pass
        observations = prepared.get("observations") or []
        eligible = prepared.get("eligible_observations") or []
        ru = prepared.get("semantic_rollups") or {}
        ho = prepared.get("semantic_higher_order") or {}
        req = ask_relative_request_from_prepared(prepared)

        layers.append(
            _layer_size(
                "prepared_semantic_units",
                int(acc.get("units_generated") or unit_n or len(units)),
                units if units else {"accounting_units_generated": acc.get("units_generated")},
            )
        )
        layers[-1]["units_passed_to_inference"] = acc.get("units_passed_to_inference")
        layers[-1]["units_model_extract"] = acc.get("units_model_extract")

        layers.append(_layer_size("all_observations", len(observations), observations))
        layers.append(
            _layer_size("validated_observations", len(eligible), eligible)
        )
        rollup_n = count_rollups(ru if isinstance(ru, dict) else {})
        layers.append(_layer_size("rollups", rollup_n, ru))
        ho_n = count_ho_units(ho if isinstance(ho, dict) else {})
        layers.append(_layer_size("higher_order_units", ho_n, ho))
        layers.append(
            _layer_size(
                "ask_relative_request",
                1,
                str(req.get("system") or "") + "\n" + str(req.get("user_message") or ""),
            )
        )
        layers[-1]["system_bytes"] = req.get("system_bytes")
        layers[-1]["user_bytes"] = req.get("user_bytes")
        layers[-1]["request_bytes"] = req.get("request_bytes")
    else:
        layers.append(
            {
                "layer": "prepared_semantic_units",
                "count": None,
                "bytes": None,
                "characters": None,
                "estimated_tokens": None,
                "unavailable": True,
                "reason": "histfix_fixture_required",
            }
        )
        for name in (
            "all_observations",
            "validated_observations",
            "rollups",
            "higher_order_units",
            "ask_relative_request",
        ):
            layers.append(
                {
                    "layer": name,
                    "count": None,
                    "bytes": None,
                    "characters": None,
                    "estimated_tokens": None,
                    "unavailable": True,
                    "reason": "histfix_fixture_required",
                }
            )

    narrator_layer: dict[str, Any] = {
        "layer": "narrator_input",
        "count": None,
        "bytes": None,
        "characters": None,
        "estimated_tokens": None,
        "unavailable": True,
        "reason": "historian_run_not_provided",
    }
    if historian_run_path and Path(historian_run_path).is_file():
        run = json.loads(Path(historian_run_path).read_text(encoding="utf-8"))
        nb = run.get("narrator_input_bytes")
        nt = run.get("narrator_input_tokens_est")
        if nb is not None:
            narrator_layer = {
                "layer": "narrator_input",
                "count": 1,
                "bytes": int(nb),
                "characters": int(nb),  # approx when only bytes known
                "estimated_tokens": int(nt) if nt is not None else max(1, int(nb) // 4),
                "unavailable": False,
                "source_run": str(historian_run_path),
            }
    layers.append(narrator_layer)

    # Reduction steps (measurement only — no judgment).
    reductions: list[dict[str, Any]] = []
    prev = None
    for layer in layers:
        if layer.get("unavailable") or layer.get("estimated_tokens") is None:
            prev = layer
            continue
        if prev and not prev.get("unavailable") and prev.get("estimated_tokens") is not None:
            pt = int(prev["estimated_tokens"] or 0)
            ct = int(layer["estimated_tokens"] or 0)
            reductions.append(
                {
                    "from": prev["layer"],
                    "to": layer["layer"],
                    "tokens_before": pt,
                    "tokens_after": ct,
                    "tokens_removed": max(0, pt - ct),
                    "retention_ratio": (round(ct / pt, 6) if pt else None),
                }
            )
        prev = layer

    largest = None
    if reductions:
        largest = max(reductions, key=lambda r: int(r.get("tokens_removed") or 0))

    return {
        "inventory": inventory,
        "layers": layers,
        "reductions": reductions,
        "largest_token_reduction_step": largest,
        "fixture": fixture_info,
        "note": "Measurement only — no judgment about whether reduction is good or bad.",
    }


def format_funnel_table(funnel: dict[str, Any]) -> str:
    lines = [
        "PEGGY COMPRESSION FUNNEL (measurement only)",
        "",
        f"{'layer':<28} {'count':>10} {'bytes':>12} {'est_tokens':>12}",
        "-" * 66,
    ]
    for layer in funnel.get("layers") or []:
        if layer.get("unavailable"):
            lines.append(
                f"{layer.get('layer', ''):<28} {'n/a':>10} {'n/a':>12} {'n/a':>12}"
            )
            continue
        lines.append(
            f"{str(layer.get('layer') or ''):<28} "
            f"{str(layer.get('count')):>10} "
            f"{str(layer.get('bytes')):>12} "
            f"{str(layer.get('estimated_tokens')):>12}"
        )
    lines.append("")
    lines.append("Largest token reduction step (by absolute tokens removed):")
    largest = funnel.get("largest_token_reduction_step")
    if largest:
        lines.append(
            f"  {largest.get('from')} → {largest.get('to')}: "
            f"removed {largest.get('tokens_removed')} tokens "
            f"(retention={largest.get('retention_ratio')})"
        )
    else:
        lines.append("  (insufficient layers to compare)")
    lines.append("")
    inv = funnel.get("inventory") or {}
    lines.append("Full-evidence inventory:")
    for key in (
        "total_eligible_evidence_items",
        "sms_message_count",
        "sms_conversation_channel_count",
        "email_message_count",
        "email_thread_count",
        "calendar_count",
        "photo_count",
        "video_count",
        "story_count",
        "journal_count",
        "artifact_count",
        "travel_derived_count",
        "person_fact_count",
    ):
        lines.append(f"  {key}: {inv.get(key)}")
    total = inv.get("total") or {}
    lines.append(
        f"  total bytes/chars/tokens: {total.get('bytes')} / "
        f"{total.get('characters')} / {total.get('estimated_tokens')}"
    )
    lines.append(
        f"  date range: {total.get('earliest_date')} .. {total.get('latest_date')}"
    )
    lines.append("")
    return "\n".join(lines)


def _load_items_from_dir(src: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Load normalized items + person_context from a prior full-evidence export."""
    items_path = src / "PEGGY_FULL_EVIDENCE_ITEMS.json"
    metrics_path = src / "PEGGY_FULL_EVIDENCE_METRICS.json"
    if not items_path.is_file():
        raise FileNotFoundError(f"missing {items_path}")
    doc = json.loads(items_path.read_text(encoding="utf-8"))
    items = list(doc.get("items") or [])
    person_context: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    if metrics_path.is_file():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    # Person context may be embedded in paste/evidence; prefer regenerating slim from metrics plan.
    return items, person_context, metrics


def freeze_benchmark_artifacts(
    out_dir: Path,
    *,
    items: list[dict[str, Any]],
    person_context: dict[str, Any],
    ask: str,
    plan: Any | None = None,
    metrics_extra: dict[str, Any] | None = None,
    gpt_response_path: Path | str | None = None,
    gpt_response_text: str | None = None,
) -> dict[str, Any]:
    """Write frozen Peggy full-evidence benchmark pack with hashes + commit."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    commit = _git_commit()

    evidence_txt = format_full_evidence_text(
        items,
        ask=ask,
        person_context=person_context,
        plan_snapshot=plan_to_snapshot(plan) if plan is not None else {},
    )
    paste = format_cloud_paste(items, ask=ask, person_context=person_context)

    evidence_path = out_dir / "PEGGY_FULL_EVIDENCE.txt"
    paste_path = out_dir / "CLOUDREQ_peggy_full_evidence_paste.txt"
    metrics_path = out_dir / "PEGGY_FULL_EVIDENCE_METRICS.json"
    items_path = out_dir / "PEGGY_FULL_EVIDENCE_ITEMS.json"

    evidence_path.write_text(evidence_txt, encoding="utf-8")
    paste_path.write_text(paste, encoding="utf-8")

    rc: dict[str, int] = {
        "person": 0,
        "sms": 0,
        "email": 0,
        "photo": 0,
        "video": 0,
    }
    for it in items:
        src = str(it.get("source") or "other")
        rc[src] = int(rc.get(src) or 0) + 1
    by_source = _source_metrics(items, retrieved_counts=rc, duplicates={})
    totals = _total_metrics(items, retrieved_total=len(items), duplicates_total=0)

    metrics = {
        "diagnostic_version": FULL_EVIDENCE_DIAG_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "built_at": stamp,
        "source_commit": commit,
        "ask": ask,
        "by_source": by_source,
        "total": totals,
        "llm_calls": 0,
        "production_inference_modified": False,
        "frozen_benchmark": True,
        **(metrics_extra or {}),
    }
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    items_path.write_text(
        json.dumps(
            {
                "benchmark_version": BENCHMARK_VERSION,
                "ask": ask,
                "item_count": len(items),
                "item_ids": [it.get("item_id") for it in items],
                "content_fingerprints": [it.get("content_fingerprint") for it in items],
                "person_context": slim_person_context_for_model(person_context),
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    gpt_name = "GPT56SOL_peggy_full_evidence_response.txt"
    gpt_path = out_dir / gpt_name
    gpt_preserved = False
    if gpt_response_text:
        gpt_path.write_text(gpt_response_text, encoding="utf-8")
        gpt_preserved = True
    elif gpt_response_path and Path(gpt_response_path).is_file():
        shutil.copy2(gpt_response_path, gpt_path)
        gpt_preserved = True

    file_hashes = {
        "PEGGY_FULL_EVIDENCE.txt": _sha256_file(evidence_path),
        "PEGGY_FULL_EVIDENCE_METRICS.json": _sha256_file(metrics_path),
        "CLOUDREQ_peggy_full_evidence_paste.txt": _sha256_file(paste_path),
        "PEGGY_FULL_EVIDENCE_ITEMS.json": _sha256_file(items_path),
    }
    if gpt_preserved:
        file_hashes[gpt_name] = _sha256_file(gpt_path)

    manifest = {
        "manifest_version": 1,
        "benchmark_version": BENCHMARK_VERSION,
        "case_id": "peggy",
        "ask": ask,
        "built_at": stamp,
        "source_commit": commit,
        "item_count": len(items),
        "content_fingerprint_digest": _sha256_text(
            json.dumps([it.get("content_fingerprint") for it in items], ensure_ascii=False)
        ),
        "file_sha256": file_hashes,
        "gpt56sol_response_preserved": gpt_preserved,
        "note": (
            "Frozen full-evidence Peggy benchmark for historian A/B. "
            "Cloud answer is a benchmark artifact only — not production logic."
        ),
    }
    manifest_path = out_dir / "BENCHMARK_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return {
        "out_dir": str(out_dir),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "metrics_path": str(metrics_path),
        "gpt_preserved": gpt_preserved,
    }


def run_historian_full_evidence_benchmark(
    *,
    out_dir: Path | str | None = None,
    ask: str | None = None,
    fixture_path: Path | str | None = None,
    historian_run_path: Path | str | None = None,
    from_dir: Path | str | None = None,
    gpt_response: Path | str | None = None,
    plan: Any | None = None,
    person_context: dict[str, Any] | None = None,
    retrieved: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    repair_address: str | None = None,
    address_hint: str | None = None,
) -> dict[str, Any]:
    """End-to-end: freeze pack + funnel metrics + L1 chunks + proofs."""
    from memorybox.ask.deps import build_photo, build_video

    out = Path(out_dir) if out_dir else _DEFAULT_BENCH_DIR
    out.mkdir(parents=True, exist_ok=True)
    ask_text = (ask or PEGGY_ASK).strip()
    identity_diag: dict[str, Any] = {}
    repair_result: dict[str, Any] | None = None

    if items is None and from_dir:
        items, loaded_pc, prior_metrics = _load_items_from_dir(Path(from_dir))
        if person_context is None and loaded_pc:
            person_context = loaded_pc
        # Recover person_context from items JSON if present.
        items_doc = json.loads(
            (Path(from_dir) / "PEGGY_FULL_EVIDENCE_ITEMS.json").read_text(encoding="utf-8")
        )
        if person_context is None and isinstance(items_doc.get("person_context"), dict):
            person_context = {"focal_subjects": [], **items_doc["person_context"]}
            # slim form may already be nested; accept as-is for paste
            if "focal_subjects" in items_doc["person_context"]:
                person_context = items_doc["person_context"]
        _ = prior_metrics

    if items is None:
        photo = build_photo()
        video = build_video()
        if plan is None:
            plan = resolve_peggy_plan(photo=photo, ask=ask_text)
        pids = [str(p) for p in (getattr(plan, "person_ids", ()) or ()) if p]
        if repair_address and pids:
            from memorybox.person.comm_identity import repair_email_identity_contacts

            repair_result = repair_email_identity_contacts(
                pids[0],
                known_address=repair_address,
                force_rediscover=False,
            )
        if person_context is None:
            person_context = build_person_context(plan)
        if retrieved is None:
            retrieved = retrieve_eligible_hits(plan, photo=photo, video=video)
        try:
            from memorybox.person.comm_identity import diagnose_email_retrieve_gap

            identity_diag = diagnose_email_retrieve_gap(
                pids,
                address_hint=address_hint or repair_address,
            )
        except Exception as exc:  # noqa: BLE001
            identity_diag = {"error": str(exc), "person_ids": pids}
        norm = normalize_retrieved(retrieved, person_context=person_context)
        items = list(norm["items"])
    else:
        if person_context is None:
            person_context = {"focal_subjects": [], "allowed_relationship_labels": []}

    # A. Freeze benchmark pack
    metrics_extra: dict[str, Any] = {
        "email_identity_diag": identity_diag,
    }
    if repair_result is not None:
        metrics_extra["email_identity_repair"] = repair_result
    freeze = freeze_benchmark_artifacts(
        out,
        items=items,
        person_context=person_context,
        ask=ask_text,
        plan=plan,
        gpt_response_path=gpt_response,
        metrics_extra=metrics_extra,
    )

    # Persist a standalone identity diag for FlightSim paste.
    diag_path = out / "PEGGY_EMAIL_IDENTITY_DIAG.json"
    diag_path.write_text(
        json.dumps(
            {
                "repair": repair_result,
                "diag": identity_diag,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    # Address-centric gate: unambiguous FlightSim pass/fail for this goal.
    metrics_doc: dict[str, Any] = {}
    metrics_path = out / "PEGGY_FULL_EVIDENCE_METRICS.json"
    if metrics_path.is_file():
        try:
            metrics_doc = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            metrics_doc = {}
    email_src = (metrics_doc.get("by_source") or {}).get("email") or {}
    email_n = int(
        email_src.get("retrieved_item_count")
        or email_src.get("normalized_item_count")
        or 0
    )
    focals = (person_context or {}).get("focal_subjects") or []
    focal_names = [str(f.get("display_name") or "") for f in focals if isinstance(f, dict)]
    confirmed = list((identity_diag or {}).get("confirmed_emails") or [])
    inventories = list((identity_diag or {}).get("address_inventories") or [])
    # Prefer inventory for a confirmed address that shows Peg Legg structured;
    # fall back to first inventory (no address hardcode in the gate path).
    peggo_inv = None
    for inv in inventories:
        structured_try = (inv or {}).get("structured_header") or {}
        if bool(structured_try.get("has_peg_legg")):
            peggo_inv = inv
            break
    if peggo_inv is None and confirmed:
        want = {normalize_handle(str(a)) for a in confirmed if a}
        peggo_inv = next(
            (
                inv
                for inv in inventories
                if normalize_handle(str(inv.get("address") or "")) in want
            ),
            None,
        )
    if peggo_inv is None and inventories:
        peggo_inv = inventories[0]
    structured = (peggo_inv or {}).get("structured_header") or {}
    quoted = (peggo_inv or {}).get("quoted_body_headers_only") or {}

    # Gallery uses the same search_email_messages path as Ask — assert email > 0
    # so the gate covers the full objective (Gallery + Full-Evidence V2).
    gallery_email_n = 0
    gallery_match_total = 0
    gallery_error: str | None = None
    try:
        from memorybox.explore.find import _attach_visible_email

        gallery_plan = {
            "person_names": list(getattr(plan, "person_names", ()) or ()) if plan else focal_names,
            "person_ids": list(getattr(plan, "person_ids", ()) or ()) if plan else [
                str(f.get("person_id") or "")
                for f in focals
                if isinstance(f, dict) and f.get("person_id")
            ],
            "original_ask": ask_text,
            "effective_ask": ask_text,
            "notes": list(getattr(plan, "notes", ()) or ()) if plan else ["complete_comm_retrieve"],
            "gallery_show_email": True,
        }
        _items, gallery_email_n, gallery_match_total = _attach_visible_email(
            [],
            {"plan": gallery_plan, "evidence_hits": []},
            ask_text=ask_text,
            show_email=True,
        )
        gallery_email_n = int(gallery_email_n or 0)
        gallery_match_total = int(gallery_match_total or 0)
    except Exception as exc:  # noqa: BLE001
        gallery_error = str(exc)

    gallery_ok = gallery_email_n > 0 or gallery_match_total > 0
    # When replaying --from-dir without a live plan, Gallery may be unavailable;
    # require Gallery only on live retrieve paths (plan present).
    require_gallery = plan is not None and from_dir is None
    gate = {
        "gate": "address_centric_email_identity",
        "stop": "gallery_and_full_evidence_v2 — no historian summarization",
        "ok": bool(
            email_n > 0
            and confirmed
            and any(" " in n for n in focal_names)
            and (gallery_ok if require_gallery else True)
            and bool((identity_diag or {}).get("identity_closure_ok"))
            and (
                peggo_inv is None
                or bool(structured.get("has_peg_legg"))
            )
        ),
        "requirements": {
            "full_evidence_email_gt_0": email_n > 0,
            "gallery_email_gt_0": gallery_ok if require_gallery else None,
            "person_has_confirmed_email": bool(confirmed),
            "person_is_multi_token": any(" " in n for n in focal_names),
            "identity_closure_ok": bool((identity_diag or {}).get("identity_closure_ok")),
            "structured_has_peg_legg": bool(structured.get("has_peg_legg")),
            "peggo417_structured_has_peg_legg": bool(structured.get("has_peg_legg")),
        },
        "by_source_email": email_src,
        "email_retrieved_item_count": email_n,
        "gallery_email_n": gallery_email_n,
        "gallery_match_total": gallery_match_total,
        "gallery_error": gallery_error,
        "focal_display_names": focal_names,
        "confirmed_emails": confirmed,
        "probe_address": (peggo_inv or {}).get("address"),
        "peggo417_inventory": {
            "present": peggo_inv is not None,
            "structured_has_peg_legg": structured.get("has_peg_legg"),
            "structured_has_peggy_george": structured.get("has_peggy_george"),
            "quoted_has_peggy_george": quoted.get("has_peggy_george"),
            "quoted_has_peg_legg": quoted.get("has_peg_legg"),
            "structured_names": structured.get("distinct_display_names"),
            "quoted_names": quoted.get("distinct_display_names"),
        },
        "likely_blocker": (identity_diag or {}).get("likely_blocker"),
        "flightsim": bool(os.environ.get("MEMORYBOX_P1_RUNTIME_HOST")),
    }
    gate_path = out / "ADDRESS_CENTRIC_GATE.json"
    gate_path.write_text(
        json.dumps(gate, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # B. Compression funnel
    funnel = build_compression_funnel(
        items,
        fixture_path=fixture_path,
        historian_run_path=historian_run_path,
    )
    funnel_json_path = out / "PEGGY_COMPRESSION_FUNNEL.json"
    funnel_txt_path = out / "PEGGY_COMPRESSION_FUNNEL.txt"
    funnel_json_path.write_text(
        json.dumps(funnel, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    funnel_txt_path.write_text(format_funnel_table(funnel), encoding="utf-8")

    # C–G. Level-1 complete-coverage chunker
    l1 = run_l1_chunker(items, person_context=person_context, ask=ask_text)
    for ch in l1["chunks"]:
        (out / ch["filename"]).write_text(ch["file_text"], encoding="utf-8")
    chunk_manifest_path = out / "PEGGY_L1_CHUNK_MANIFEST.json"
    chunk_manifest_path.write_text(
        json.dumps(l1["manifest"], indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    report = {
        "ok": bool(l1["proof"].get("ok")),
        "benchmark_version": BENCHMARK_VERSION,
        "out_dir": str(out),
        "ask": ask_text,
        "item_count": len(items),
        "full_evidence_estimated_tokens": (funnel.get("inventory") or {}).get("total", {}).get(
            "estimated_tokens"
        ),
        "chunk_count": len(l1["chunks"]),
        "chunk_token_sizes": [c.get("estimated_tokens") for c in l1["chunks"]],
        "sms_segmentation_rules": l1["sms_rules"],
        "compaction": l1["compaction"],
        "completeness_proof": l1["proof"],
        "largest_funnel_reduction": funnel.get("largest_token_reduction_step"),
        "chunk_files": [c.get("filename") for c in l1["chunks"]],
        "paths": {
            "benchmark_manifest": freeze["manifest_path"],
            "full_evidence": str(out / "PEGGY_FULL_EVIDENCE.txt"),
            "metrics": str(out / "PEGGY_FULL_EVIDENCE_METRICS.json"),
            "paste": str(out / "CLOUDREQ_peggy_full_evidence_paste.txt"),
            "email_identity_diag": str(diag_path),
            "address_centric_gate": str(gate_path),
            "funnel_json": str(funnel_json_path),
            "funnel_txt": str(funnel_txt_path),
            "l1_chunk_manifest": str(chunk_manifest_path),
            "chunks": [str(out / c["filename"]) for c in l1["chunks"]],
        },
        "email_identity_diag": identity_diag,
        "email_identity_repair": repair_result,
        "address_centric_gate": gate,
        "gpt56sol_response_preserved": freeze.get("gpt_preserved"),
        "llm_calls": 0,
        "production_inference_modified": False,
        "source_commit": _git_commit(),
    }
    report_path = out / "BENCHMARK_REPORT.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    if not report["ok"]:
        raise RuntimeError("completeness proof failed — see BENCHMARK_REPORT.json")
    return report


def run_historian_full_evidence_benchmark_cli(
    *,
    out_dir: Path | str | None = None,
    ask: str | None = None,
    fixture: Path | str | None = None,
    historian_run: Path | str | None = None,
    from_dir: Path | str | None = None,
    gpt_response: Path | str | None = None,
    flightsim: bool = False,
    repair_address: str | None = None,
    address_hint: str | None = None,
) -> dict[str, Any]:
    if flightsim:
        import os

        os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
    return run_historian_full_evidence_benchmark(
        out_dir=out_dir,
        ask=ask,
        fixture_path=fixture,
        historian_run_path=historian_run,
        from_dir=from_dir,
        gpt_response=gpt_response,
        repair_address=repair_address,
        address_hint=address_hint,
    )
