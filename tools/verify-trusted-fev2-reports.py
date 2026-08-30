#!/usr/bin/env python3
"""Audit frozen Gemma + Sol Full-Evidence V2 reports.

Phase 2 complete only when both single-pass reports exist, share the freeze
hash, email grounded the output, and chunking is still off. Phase 3 models
are not accepted here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path("docs/test-output/trusted-full-evidence-v2")
ESTABLISHED_GEMMA = "gemma4:26b"


def _unwrap(report: dict[str, Any]) -> dict[str, Any]:
    if isinstance(report.get("phase2_report"), dict):
        return report["phase2_report"]
    return report


def _latest(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def _json_hash(path: Path, *keys: str) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(data.get("phase2_report"), dict):
        data = data["phase2_report"]
    for key in keys:
        val = str(data.get(key) or "").strip()
        if val:
            return val
    return ""


def _match_hash_or_latest(paths: list[Path], want_hash: str) -> Path | None:
    """Prefer reports for this freeze. Do not pair Sol with a stale Gemma hash."""
    if want_hash:
        matched = [p for p in paths if _json_hash(p, "input_sha256") == want_hash]
        if matched:
            return _latest(matched)
    return _latest(paths)


def discover_reports(out_dir: Path) -> dict[str, Any]:
    gemma_paths = sorted(out_dir.glob("FEV2REPORT_ollama_*.json"))
    sol_paths = sorted(
        list(out_dir.glob("FEV2REPORT_cloud_*.json"))
        + list(out_dir.glob("FEV2REPORT_openai_*.json"))
    )
    pipeline_paths = sorted(out_dir.glob("PIPELINE_*.json"))
    fixtures = [
        p
        for p in out_dir.glob("FEV2_*.json")
        if not p.name.startswith("FEV2REPORT_")
        and not p.name.startswith("FEV2CHUNK_")
        and not p.name.startswith("FEV2COMPLETE_")
        and not p.name.startswith("FEV2_paste_")
        and not p.name.startswith("FEV2_manifest_")
    ]
    fixture_path = _latest(fixtures)
    fixture_hash = _json_hash(fixture_path, "input_sha256") if fixture_path else ""
    pipeline_path = _latest(pipeline_paths)
    if pipeline_path and fixture_hash:
        pipe_hash = _json_hash(pipeline_path, "input_sha256")
        if pipe_hash and pipe_hash != fixture_hash:
            pipeline_path = None
    return {
        "gemma_path": _match_hash_or_latest(gemma_paths, fixture_hash),
        "sol_path": _match_hash_or_latest(sol_paths, fixture_hash),
        "pipeline_path": pipeline_path,
        "fixture_path": fixture_path,
        "fixture_hash": fixture_hash,
    }


def audit_fev2_reports(
    gemma: dict[str, Any] | None,
    sol: dict[str, Any] | None,
    *,
    pipeline: dict[str, Any] | None = None,
    fixture_hash: str | None = None,
    chunk_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    problems: list[str] = []

    def check(req_id: str, name: str, ok: bool, evidence: Any = None) -> None:
        checks.append(
            {
                "id": req_id,
                "requirement": name,
                "ok": bool(ok),
                "evidence": evidence,
            }
        )
        if not ok:
            problems.append(f"{req_id}: {name}")

    g = _unwrap(gemma or {})
    s = _unwrap(sol or {})
    check("P2-1", "Gemma Phase 2 report present", bool(g), {"keys": list(g.keys())[:8]})
    check("P2-2", "Sol Phase 2 report present", bool(s), {"keys": list(s.keys())[:8]})
    check("P2-3", "Gemma ok=true", g.get("ok") is True, {"ok": g.get("ok")})
    check("P2-4", "Sol ok=true", s.get("ok") is True, {"ok": s.get("ok")})
    g_hash = str(g.get("input_sha256") or "")
    s_hash = str(s.get("input_sha256") or "")
    freeze = str(fixture_hash or g_hash or s_hash)
    check(
        "P2-5",
        "same freeze hash on Gemma and Sol",
        bool(g_hash) and g_hash == s_hash and (not fixture_hash or g_hash == fixture_hash),
        {"gemma": g_hash, "sol": s_hash, "fixture": fixture_hash},
    )
    check(
        "P2-6",
        "Gemma email grounded output",
        g.get("email_reached_model_and_grounded_output") is True,
        {"email_reached_model_and_grounded_output": g.get("email_reached_model_and_grounded_output")},
    )
    check(
        "P2-7",
        "Sol email grounded output",
        s.get("email_reached_model_and_grounded_output") is True,
        {"email_reached_model_and_grounded_output": s.get("email_reached_model_and_grounded_output")},
    )
    check(
        "P2-8",
        "single-pass (chunking false)",
        g.get("chunking") is not True and s.get("chunking") is not True,
        {"gemma_chunking": g.get("chunking"), "sol_chunking": s.get("chunking")},
    )
    g_model = str(g.get("model") or "").split("@")[0].strip()
    g_model_canon = ESTABLISHED_GEMMA if (
        g_model == ESTABLISHED_GEMMA
        or g_model == f"{ESTABLISHED_GEMMA}:latest"
        or g_model.startswith(f"{ESTABLISHED_GEMMA}:")
    ) else g_model
    check(
        "P2-9",
        f"established Gemma model is {ESTABLISHED_GEMMA}",
        g_model_canon == ESTABLISHED_GEMMA,
        {"model": g_model},
    )
    check(
        "P2-10",
        "no invented/unsupported Gemma claims",
        not (g.get("invented_or_unsupported_claims") or []),
        {"invented_or_unsupported_claims": g.get("invented_or_unsupported_claims")},
    )
    check(
        "P2-11",
        "no invented/unsupported Sol claims",
        not (s.get("invented_or_unsupported_claims") or []),
        {"invented_or_unsupported_claims": s.get("invented_or_unsupported_claims")},
    )
    if pipeline:
        check(
            "P2-12",
            "pipeline Gemma not skipped",
            (pipeline.get("gemma") or {}).get("skipped") is not True
            and (pipeline.get("gemma") or {}).get("ok") is True,
            {"gemma": pipeline.get("gemma")},
        )
        check(
            "P2-13",
            "pipeline Sol not skipped",
            (pipeline.get("sol") or {}).get("skipped") is not True
            and (pipeline.get("sol") or {}).get("ok") is True,
            {"sol": pipeline.get("sol")},
        )
        p_hash = str(pipeline.get("input_sha256") or "")
        if p_hash:
            check(
                "P2-14",
                "pipeline freeze hash matches reports",
                p_hash == freeze == g_hash == s_hash,
                {"pipeline": p_hash, "reports": freeze},
            )
    if chunk_structure is not None:
        check(
            "P3-0",
            "L1 chunk structure covers frozen items with no loss",
            chunk_structure.get("ok") is True
            and not (chunk_structure.get("evidence_lost") or []),
            {
                "ok": chunk_structure.get("ok"),
                "evidence_lost": chunk_structure.get("evidence_lost"),
                "missing_semantic_unit_kinds": chunk_structure.get(
                    "missing_semantic_unit_kinds"
                ),
            },
        )

    return {
        "ok": not problems,
        "phase2_complete": not problems,
        "problems": problems,
        "checks": checks,
        "input_sha256": freeze,
        "chunking": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="", help="Directory with FEV2REPORT_*.json")
    parser.add_argument("--gemma", default="", help="Gemma report path")
    parser.add_argument("--sol", default="", help="Sol report path")
    args = parser.parse_args(argv)
    out_dir = Path(args.dir) if args.dir else DEFAULT_DIR
    gemma: dict[str, Any] | None = None
    sol: dict[str, Any] | None = None
    pipeline: dict[str, Any] | None = None
    fixture_hash: str | None = None
    chunk_structure: dict[str, Any] | None = None
    if args.gemma and args.sol:
        gemma = json.loads(Path(args.gemma).read_text(encoding="utf-8"))
        sol = json.loads(Path(args.sol).read_text(encoding="utf-8"))
    else:
        found = discover_reports(out_dir)
        if not found["gemma_path"] or not found["sol_path"]:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "phase2_complete": False,
                        "problems": [
                            "missing FEV2REPORT_ollama_* and/or FEV2REPORT_cloud_* "
                            f"in {out_dir}"
                        ],
                    },
                    indent=2,
                )
            )
            print("FAIL  trusted FEV2 reports missing", file=sys.stderr)
            return 1
        gemma = json.loads(found["gemma_path"].read_text(encoding="utf-8"))
        sol = json.loads(found["sol_path"].read_text(encoding="utf-8"))
        if found["pipeline_path"]:
            pipeline = json.loads(found["pipeline_path"].read_text(encoding="utf-8"))
            fixture_hash = str(pipeline.get("input_sha256") or "") or None
        if found.get("fixture_path"):
            from memorybox.ask.i11a.trusted_fev2_chunking import (
                compare_chunked_vs_unchunked,
            )

            chunk_structure = compare_chunked_vs_unchunked(found["fixture_path"])
        else:
            chunk_structure = {
                "ok": False,
                "evidence_lost": ["missing_frozen_fev2_fixture"],
            }
    audit = audit_fev2_reports(
        gemma,
        sol,
        pipeline=pipeline,
        fixture_hash=fixture_hash,
        chunk_structure=chunk_structure,
    )
    print(json.dumps(audit, indent=2, default=str))
    if not audit.get("ok"):
        print("FAIL  trusted FEV2 Gemma/Sol reports", file=sys.stderr)
        return 1
    print("PASS  trusted FEV2 Gemma/Sol reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
