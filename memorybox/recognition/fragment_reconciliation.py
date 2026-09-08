"""Legacy HVRT half-second fragment reconciliation — presentation layer only.

Corpus: People and sources on the accepted 22-video manifest only. Not archive-wide.
No DB writes; source videos, observations and provenance remain immutable.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

POLICY = "i13-legacy-hvrt-fragment-v1"
MIN_FRAGMENT_SEC = 0.5
MAX_FRAGMENT_SEC = 2.0
BASE_ELIGIBILITY = {
    "provider_key": "hvrt",
    "method": "mb_native_i8b",
    "status": "accepted",
    "authority": "ai_inferred",
    "confirmation_state": "system_associated",
}

PILOT_SOURCE = "vid-c57dbd21f993f6d1"
PILOT_RUN = "7aa4cda7-2d49-456c-a107-9d896cc37b53"
SECOND_SOURCE = "vid-da41273dbd9ac4bb"
SECOND_RUN = "bd94ab11-fb4f-4b8a-b993-339e535f84e6"

_DEFAULT_ALLOWLIST = {
    "policy": POLICY,
    "manifest_id": "p2-i13-flightsim-22",
    "review_reference": "founder-reviewed-two-source-pilot-2026-09-05",
    "approved_source_runs": [
        {"video_external_id": PILOT_SOURCE, "processing_run_id": PILOT_RUN, "relative_path": "20111105_1532.MP4"},
        {"video_external_id": SECOND_SOURCE, "processing_run_id": SECOND_RUN, "relative_path": "20111105_1530.MP4"},
    ],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def manifest_path() -> Path:
    return _repo_root() / "docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json"


def allowlist_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "legacy_hvrt_fragment_allowlist.json"


def load_manifest_sources() -> list[dict[str, Any]]:
    raw = json.loads(manifest_path().read_text(encoding="utf-8"))
    return list(raw["manifest"]["sources"])


def manifest_source_ids() -> frozenset[str]:
    return frozenset(str(s["video_external_id"]) for s in load_manifest_sources())


def load_allowlist() -> dict[str, Any]:
    path = allowlist_path()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return deepcopy(_DEFAULT_ALLOWLIST)


def approved_source_runs() -> frozenset[tuple[str, str]]:
    data = load_allowlist()
    out = set()
    for row in data.get("approved_source_runs") or []:
        src = str(row.get("video_external_id") or "").strip()
        run = str(row.get("processing_run_id") or "").strip()
        if src and run:
            out.add((src, run))
    return frozenset(out)


def moment_duration_sec(row: dict[str, Any]) -> float | None:
    try:
        start = float(row.get("start_sec"))
        end = float(row.get("end_sec"))
    except (TypeError, ValueError):
        return None
    return round(end - start, 6)


def is_fragment_duration(duration: float | None) -> bool:
    if duration is None:
        return False
    return MIN_FRAGMENT_SEC <= duration <= MAX_FRAGMENT_SEC


def matches_base_eligibility(row: dict[str, Any]) -> bool:
    if str(row.get("video_provider_key") or row.get("provider_key") or "") != BASE_ELIGIBILITY["provider_key"]:
        return False
    for key in ("method", "status", "authority", "confirmation_state"):
        if str(row.get(key) or "") != BASE_ELIGIBILITY[key]:
            return False
    return is_fragment_duration(moment_duration_sec(row))


def is_pilot_evidence(
    source: str | None,
    provider: str | None,
    evidence: dict[str, Any] | None,
) -> bool:
    """Approved pilot source runs — retrieval dedupe protection (no duration gate)."""
    e = evidence or {}
    src = str(source or e.get("video_external_id") or "").strip()
    if str(provider or e.get("video_provider_key") or "") != BASE_ELIGIBILITY["provider_key"]:
        return False
    run = str(e.get("processing_run_id") or "").strip()
    if not run or (src, run) not in approved_source_runs():
        return False
    for key in ("method", "status", "authority", "confirmation_state"):
        if str(e.get(key) or "") != BASE_ELIGIBILITY[key]:
            return False
    return True


def is_reconcilable_fragment(
    source: str | None,
    provider: str | None,
    evidence: dict[str, Any] | None,
    *,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> bool:
    """Manifest-scoped legacy HVRT fragment eligible for source-card projection."""
    if not is_pilot_evidence(source, provider, evidence):
        return False
    e = evidence or {}
    src = str(source or e.get("video_external_id") or "").strip()
    if src not in manifest_source_ids():
        return False
    row = dict(e)
    row.setdefault("video_external_id", src)
    row.setdefault("start_sec", start_sec)
    row.setdefault("end_sec", end_sec)
    if provider:
        row.setdefault("provider_key", provider)
        row.setdefault("video_provider_key", provider)
    return matches_base_eligibility(row)


def partition_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("video_provider_key") or row.get("provider_key") or "hvrt"),
        str(row.get("video_external_id") or ""),
        str(row.get("person_id") or row.get("mb_person_id") or ""),
        str(row.get("processing_run_id") or (row.get("appearance_evidence") or {}).get("processing_run_id") or ""),
        str(row.get("model_version") or (row.get("appearance_evidence") or {}).get("model_version") or ""),
    )


def preview_projection(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Read-only before/after counts for founder review."""
    eligible = [r for r in rows if matches_base_eligibility(r)]
    off_manifest = [r for r in rows if str(r.get("video_external_id") or "") not in manifest_source_ids()]
    groups: dict[tuple, list[dict[str, Any]]] = {}
    suppressed = 0
    for row in eligible:
        src = str(row["video_external_id"])
        run = str(row.get("processing_run_id") or "")
        if (src, run) not in approved_source_runs():
            continue
        key = partition_key(row)
        groups.setdefault(key, []).append(row)
    for members in groups.values():
        if len(members) > 1:
            suppressed += len(members) - 1
    return {
        "policy": POLICY,
        "inventory_rows": len(rows),
        "eligible_fragment_rows": len(eligible),
        "off_manifest_rows": len(off_manifest),
        "before_gallery_cards": len(eligible),
        "after_source_cards": len(groups),
        "suppressed_duplicate_presentations": suppressed,
        "retained_moment_rows": len(eligible),
        "partitions": [
            {
                "provider_key": key[0],
                "video_external_id": key[1],
                "person_id": key[2],
                "processing_run_id": key[3],
                "model_version": key[4],
                "moment_count": len(members),
                "start_secs": sorted(float(m.get("start_sec") or 0) for m in members),
                "moment_ids": [str(m.get("id")) for m in members],
            }
            for key, members in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][3]))
        ],
    }
