"""FlightSim / local pipeline: Phase 1 → frozen FEV2 → Gemma/Sol → chunk.

Stops on Phase 1 failure. Does not widen identity matching.
Does not run models per chunk until both single-pass reports exist
for the same fixture hash.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.trusted_fev2_chunking import compare_chunked_vs_unchunked
from memorybox.ask.i11a.trusted_full_evidence_v2 import (
    ESTABLISHED_GEMMA_MODEL,
    freeze_trusted_full_evidence_v2,
    run_trusted_full_evidence_v2,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT = _REPO_ROOT / "docs" / "test-output" / "trusted-full-evidence-v2"


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    return path


def _write_phase2_summary_files(out: Path, result: dict[str, Any], stamp: str) -> None:
    """Stable + stamped FlightSim paste. Gate commits PHASE2_SUMMARY.txt to PR #77."""
    text = str(result.get("phase2_summary") or format_phase2_summary(result))
    result["phase2_summary"] = text
    try:
        (out / "PHASE2_SUMMARY.txt").write_text(text, encoding="utf-8")
        (out / f"PHASE2_SUMMARY_{stamp}.txt").write_text(text, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _try_model_run(
    fixture_path: str,
    *,
    provider: str,
    model: str,
    out_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    try:
        return run_trusted_full_evidence_v2(
            fixture_path,
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
            out_dir=out_dir,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "skipped": False,
            "error": f"{type(exc).__name__}:{exc}",
            "provider": provider,
            "model": model,
            "chunking": False,
        }


def run_trusted_evidence_pipeline(
    *,
    person_name: str,
    out_dir: Path | str | None = None,
    run_models: bool = True,
    gemma_model: str = ESTABLISHED_GEMMA_MODEL,
    sol_model: str | None = None,
    timeout_seconds: int = 1800,
    ask: str = "tell me what you know about this person",
) -> dict[str, Any]:
    """Phase 1 report → freeze → optional Gemma then Sol → structure chunk.

    Production retrieve is not person-hardcoded. The display name is an
    operator argument (FlightSim passes the Person under review).
    """
    out = Path(out_dir) if out_dir else _DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    from memorybox.person.trusted_identity import report_named_person_identity_trust

    phase1 = report_named_person_identity_trust(person_name)
    phase1_path = _write(out / f"PHASE1_{stamp}.json", phase1)
    result: dict[str, Any] = {
        "ok": False,
        "phase": 1,
        "person_name": person_name,
        "phase1_path": str(phase1_path),
        "phase1": {
            "ok": phase1.get("ok"),
            "trusted_addresses": phase1.get("trusted_addresses"),
            "trusted": phase1.get("trusted"),
            "counts": phase1.get("counts"),
            "per_trusted_address": phase1.get("per_trusted_address"),
            "unique_emails_by_trusted_address": phase1.get("unique_emails_by_trusted_address"),
            "unique_only_via_trusted_address": phase1.get("unique_only_via_trusted_address"),
            "shared_across_trusted_addresses": phase1.get("shared_across_trusted_addresses"),
            "unsupported_retrieve_addresses": phase1.get("unsupported_retrieve_addresses"),
            "unsupported_retrieve_hit_count": phase1.get("unsupported_retrieve_hit_count"),
            "retrieve_hit_count": phase1.get("retrieve_hit_count"),
            "gallery_email_count": phase1.get("gallery_email_count"),
            "untrusted_n": phase1.get("untrusted_n"),
            "untrusted_by_reason": phase1.get("untrusted_by_reason"),
            "phase1_summary": phase1.get("phase1_summary"),
        },
    }
    try:
        (out / f"PHASE1_SUMMARY_{stamp}.txt").write_text(
            str(phase1.get("phase1_summary") or ""),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        pass
    if not phase1.get("ok") or not phase1.get("trusted_addresses"):
        result["stop"] = "phase_1_failed — do not widen matching; attest or fix provenance"
        result["error"] = phase1.get("error") or "phase_1_not_ok"
        _write_phase2_summary_files(out, result, stamp)
        _write(out / f"PIPELINE_{stamp}.json", result)
        return result

    from memorybox.person import resolve_person_by_name

    resolved = resolve_person_by_name(person_name, create_if_missing=False, confirm=False)
    pid = str(getattr(resolved, "person_id", "") or getattr(resolved, "id", "") or "")
    freeze = freeze_trusted_full_evidence_v2(person_id=pid, ask=ask, out_dir=out)
    result["phase"] = 2
    result["freeze"] = {
        "ok": freeze.get("ok"),
        "fixture_path": freeze.get("fixture_path"),
        "input_sha256": freeze.get("input_sha256"),
        "evidence_type_counts": freeze.get("evidence_type_counts"),
        "email_evidence_ids": freeze.get("email_evidence_ids"),
        "trusted_addresses": freeze.get("trusted_addresses"),
        "error": freeze.get("error"),
    }
    if not freeze.get("ok") or not freeze.get("fixture_path"):
        result["stop"] = "phase_2_freeze_failed"
        _write_phase2_summary_files(out, result, stamp)
        _write(out / f"PIPELINE_{stamp}.json", result)
        return result

    fixture_path = str(freeze["fixture_path"])
    fixture_hash = freeze.get("input_sha256")
    result["larger_trusted_set"] = {
        "ok": False,
        "deferred": True,
        "reason": "after_both_single_pass_reports_only",
    }
    gemma: dict[str, Any] = {"ok": False, "skipped": True, "reason": "run_models=false"}
    sol: dict[str, Any] = {"ok": False, "skipped": True, "reason": "run_models=false"}
    if run_models:
        gemma = _try_model_run(
            fixture_path,
            provider="ollama",
            model=gemma_model,
            out_dir=out,
            timeout_seconds=timeout_seconds,
        )
        cloud_model = (sol_model or os.environ.get("MEMORYBOX_CLOUD_LLM_MODEL") or "").strip()
        if not cloud_model:
            sol = {
                "ok": False,
                "skipped": True,
                "reason": "no_sol_model — set --sol-model or MEMORYBOX_CLOUD_LLM_MODEL",
            }
        elif not (
            os.environ.get("MEMORYBOX_CLOUD_LLM_BASE_URL")
            and os.environ.get("MEMORYBOX_CLOUD_LLM_API_KEY")
        ):
            sol = {
                "ok": False,
                "skipped": True,
                "reason": "cloud_sol_not_configured",
            }
        else:
            sol = _try_model_run(
                fixture_path,
                provider="cloud",
                model=cloud_model,
                out_dir=out,
                timeout_seconds=timeout_seconds,
            )

    result["gemma"] = {
        "ok": gemma.get("ok"),
        "skipped": gemma.get("skipped"),
        "error": gemma.get("error") or gemma.get("reason"),
        "model": gemma.get("model") or gemma_model,
        "input_sha256": gemma.get("input_sha256") or fixture_hash,
        "report_path": gemma.get("report_path"),
        "phase2_report": gemma.get("phase2_report"),
    }
    result["sol"] = {
        "ok": sol.get("ok"),
        "skipped": sol.get("skipped"),
        "error": sol.get("error") or sol.get("reason"),
        "model": sol.get("model") or sol_model,
        "input_sha256": sol.get("input_sha256") or fixture_hash,
        "report_path": sol.get("report_path"),
        "phase2_report": sol.get("phase2_report"),
    }
    same_hash = (
        (gemma.get("input_sha256") or fixture_hash) == fixture_hash
        and (sol.get("input_sha256") or fixture_hash) == fixture_hash
    )
    both_single_pass = bool(gemma.get("ok")) and bool(sol.get("ok")) and same_hash
    chunk = compare_chunked_vs_unchunked(fixture_path)
    result["phase3_structure"] = chunk
    result["phase3_model_per_chunk"] = {
        "ran": False,
        "reason": (
            None
            if both_single_pass
            else "blocked_until_both_single_pass_reports_exist_for_same_fixture_hash"
        ),
    }
    if both_single_pass:
        # Phase 2 must land (and verify) before multi-hour chunk-model runs.
        result["phase"] = 2
        result["ok"] = True
        result["stop"] = "phase_2_complete — run chunk models after FEV2 verifier"
        result["phase3_model_per_chunk"] = {
            "ran": False,
            "reason": "after_phase2_verifier — run-trusted-fev2-chunked-models --from-dir",
        }
    elif gemma.get("ok") and not sol.get("ok"):
        result["ok"] = False
        result["stop"] = "phase_2_sol_incomplete — do not chunk-with-models yet"
    elif sol.get("ok") and not gemma.get("ok"):
        result["ok"] = False
        result["stop"] = "phase_2_gemma_incomplete — do not chunk-with-models yet"
    else:
        result["ok"] = False
        result["stop"] = "phase_2_models_not_run — fixture frozen; run Gemma then Sol on FlightSim"
    result["fixture_path"] = fixture_path
    result["input_sha256"] = fixture_hash
    _write_phase2_summary_files(out, result, stamp)
    _write(out / f"PIPELINE_{stamp}.json", result)
    return result


def format_phase2_summary(result: dict[str, Any]) -> str:
    """FlightSim-pasteable Phase 2 stop + Gemma/Sol skip reasons."""
    freeze = result.get("freeze") or {}
    gemma = result.get("gemma") or {}
    sol = result.get("sol") or {}
    return "\n".join(
        [
            "TRUSTED-EVIDENCE PHASE 2 SUMMARY",
            f"ok: {result.get('ok')}",
            f"stop: {result.get('stop')}",
            f"freeze_ok: {freeze.get('ok')} error={freeze.get('error') or ''}",
            f"fixture: {result.get('fixture_path') or freeze.get('fixture_path') or ''}",
            f"gemma: ok={gemma.get('ok')} skipped={gemma.get('skipped')} "
            f"error={gemma.get('error') or ''}",
            f"sol: ok={sol.get('ok')} skipped={sol.get('skipped')} "
            f"error={sol.get('error') or ''}",
        ]
    )
