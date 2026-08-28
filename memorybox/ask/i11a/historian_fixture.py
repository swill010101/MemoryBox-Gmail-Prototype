"""I11A historian frozen-fixture build + model runner (dev/test infrastructure).

Fixtures freeze deterministic prepared input at the ASK_RELATIVE boundary.
Runs replay only historian + narrator model calls — no archive retrieval.

Provider design: same fixture bytes to local Ollama or (future) cloud API.
Cloud requires explicit --provider cloud; never silent.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.i11a.historian_prepared import (
    FIXTURE_VERSION,
    canonical_json_normalize,
    count_ho_units,
    count_rollups,
    duplicate_higher_order_count,
    historian_input_sha256,
    plan_from_snapshot,
)
from memorybox.ask.i11a.historian_provider import (
    HistorianProviderSpec,
    build_historian_provider,
    historian_chat_json,
    historian_chat_text,
    normalize_provider_kind,
    sanitize_model_for_filename,
)
from memorybox.ask.i11a.infer import (
    apply_inference_to_pack,
    outline_from_inference,
    run_historian_from_prepared_input,
)
from memorybox.ask.i11a.reason import (
    ASK_RELATIVE_SYSTEM,
    ask_relative_schema_ok,
    ask_relative_semantic_ok,
    view_from_model_json,
)
from memorybox.ask.i11a.validate import parse_inference_json, validate_inference
from memorybox.ask.i11a_regression import REGRESSION_ASKS
from memorybox.ask.narrative import SYSTEM_PROMPT as NARRATOR_SYSTEM, pack_for_narrator, synthesize_tell
from memorybox.providers.base import ProviderUnavailable

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_FIXTURE_DIR = _REPO_ROOT / "docs" / "test-output" / "historian-fixtures"
_DEFAULT_RUN_DIR = _REPO_ROOT / "docs" / "test-output" / "historian-runs"

HISTORIAN_CASES: dict[str, str] = {
    "peggy": REGRESSION_ASKS[0],
    "january_2025": REGRESSION_ASKS[1],
    "vegas": REGRESSION_ASKS[2],
    "alaska": REGRESSION_ASKS[3],
}

CASE_ORDER: tuple[str, ...] = ("peggy", "january_2025", "vegas", "alaska")


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


def _jsonable(value: Any) -> Any:
    return canonical_json_normalize(value)


def serialize_fixture_document(body: dict[str, Any]) -> str:
    """Write format: pretty JSON with stable key order; values are JSON-native."""
    normalized = canonical_json_normalize(body)
    return json.dumps(normalized, indent=2, ensure_ascii=False, sort_keys=True)


def _fixture_body_from_prepared(
    *,
    case_id: str,
    ask: str,
    prepared: dict[str, Any],
    source_commit: str,
    built_at: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "fixture_version": FIXTURE_VERSION,
        "case_id": case_id,
        "ask": ask,
        "prepared": _jsonable(prepared),
        "digests": {
            "eligible_evidence_id_digest": (prepared.get("accounting") or {}).get(
                "eligible_evidence_id_digest"
            ),
            "semantic_unit_fingerprint_digest": (prepared.get("accounting") or {}).get(
                "semantic_unit_fingerprint_digest"
            ),
            "validated_observation_digest": (prepared.get("accounting") or {}).get(
                "validated_observation_digest"
            ),
        },
    }
    body["input_sha256"] = historian_input_sha256(body)
    body["source_commit"] = source_commit
    body["built_at"] = built_at
    return body


def fixture_filename(case_id: str, built_at: str, input_sha256: str) -> str:
    return f"HISTFIX_{case_id}_{built_at}_{input_sha256[:8]}.json"


def run_filename(
    case_id: str,
    provider_kind: str,
    model: str,
    run_at: str,
    input_sha256: str,
) -> str:
    model_part = sanitize_model_for_filename(model)
    prov = sanitize_model_for_filename(provider_kind)
    return f"HISTRUN_{case_id}_{prov}_{model_part}_{run_at}_{input_sha256[:8]}.json"


def build_fixture_for_case(
    orch: Any,
    case_id: str,
    *,
    ask: str | None = None,
    out_dir: Path | None = None,
    built_at: str | None = None,
) -> dict[str, Any]:
    """Run production pipeline through historian prep; zero Ask-relative/narrator calls."""
    ask_text = ask or HISTORIAN_CASES[case_id]
    stamp = built_at or _utc_stamp()
    commit = _git_commit()
    session_id = f"histfix-{case_id}-{uuid4()}"
    result = orch.ask(
        ask_text,
        session_id=session_id,
        narrate=False,
        inference_stage="ask",
        stop_before_historian=True,
    )
    pack = getattr(result, "narrative_pack", None) or {}
    prepared = pack.get("historian_prepared")
    if not prepared:
        raise RuntimeError(f"fixture build for {case_id!r} did not produce historian_prepared")
    acc = (pack.get("inference") or {}).get("accounting") or prepared.get("accounting") or {}
    if int(acc.get("ask_relative_calls") or 0) > 0:
        raise RuntimeError(f"fixture build for {case_id!r} performed Ask-relative calls")
    body = _fixture_body_from_prepared(
        case_id=case_id,
        ask=ask_text,
        prepared=prepared,
        source_commit=commit,
        built_at=stamp,
    )
    out_dir = out_dir or _DEFAULT_FIXTURE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = fixture_filename(case_id, stamp, body["input_sha256"])
    path = out_dir / fname
    path.write_text(serialize_fixture_document(body), encoding="utf-8")
    stats = prepared.get("ask_relative_payload_stats") or {}
    ho = prepared.get("semantic_higher_order") or {}
    ru = prepared.get("semantic_rollups") or {}
    eligible = prepared.get("eligible_observations") or []
    return {
        "case_id": case_id,
        "ask": ask_text,
        "filename": fname,
        "path": str(path),
        "bytes": path.stat().st_size,
        "input_sha256": body["input_sha256"],
        "payload_bytes": stats.get("payload_bytes"),
        "approx_tokens": stats.get("approx_tokens"),
        "validated_observation_count": len(eligible),
        "rollup_count": count_rollups(ru),
        "ho_unit_count": count_ho_units(ho),
        "duplicate_ho_id_count": duplicate_higher_order_count(ho),
        "source_commit": commit,
        "observation_extract_calls": int(acc.get("extract_calls") or 0),
        "ask_relative_calls": int(acc.get("ask_relative_calls") or 0),
    }


def build_all_fixtures(
    orch: Any,
    *,
    cases: tuple[str, ...] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Build all canonical cases in one preparation run."""
    stamp = _utc_stamp()
    selected = cases or CASE_ORDER
    entries: list[dict[str, Any]] = []
    for case_id in selected:
        if case_id not in HISTORIAN_CASES:
            raise ValueError(f"unknown historian case {case_id!r}")
        entries.append(
            build_fixture_for_case(orch, case_id, out_dir=out_dir, built_at=stamp)
        )
    manifest = {
        "manifest_version": 1,
        "built_at": stamp,
        "source_commit": _git_commit(),
        "cases": entries,
    }
    out_dir = out_dir or _DEFAULT_FIXTURE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_name = f"HISTFIX_manifest_{stamp}.json"
    manifest_path = out_dir / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_filename"] = manifest_name
    return manifest


def load_fixture(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    stored = data.get("input_sha256")
    recomputed = historian_input_sha256(data)
    if stored and stored != recomputed:
        raise ValueError(
            f"fixture input SHA mismatch: file={stored} recomputed={recomputed}"
        )
    return data


def verify_fixture_sha_roundtrip(body: dict[str, Any]) -> bool:
    """True when write→read preserves input_sha256 (builder/loader contract)."""
    text = serialize_fixture_document(body)
    loaded = json.loads(text)
    stored = loaded.get("input_sha256")
    if not stored:
        return False
    return stored == historian_input_sha256(loaded)


def load_manifest(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _pack_after_inference(prepared: dict[str, Any], inf: dict[str, Any]) -> dict[str, Any]:
    pack = dict(prepared.get("pack_minimal") or {})
    pack["person_context"] = prepared.get("person_context")
    pack["request_context"] = prepared.get("request_context")
    pack["semantic_observations"] = prepared.get("observations")
    pack["semantic_ir"] = inf.get("semantic_ir") or prepared.get("semantic_ir")
    pack["semantic_rollups"] = inf.get("semantic_rollups") or prepared.get("semantic_rollups")
    pack["semantic_higher_order"] = inf.get("semantic_higher_order") or prepared.get(
        "semantic_higher_order"
    )
    pack["ask_relative_view"] = inf.get("ask_relative_view")
    pack["inference"] = {
        "ok": inf.get("ok"),
        "fail_closed": inf.get("fail_closed"),
        "reason": inf.get("reason"),
        "error_class": inf.get("error_class"),
    }
    if inf.get("ok") and inf.get("document"):
        plan = plan_from_snapshot(prepared.get("plan_snapshot") or {})
        pack["validated_inference"] = inf["document"]
        pack["life_period_outline"] = outline_from_inference(inf["document"], plan)
        vol = pack.get("volume") if isinstance(pack.get("volume"), dict) else {}
        outline = pack.get("life_period_outline") or {}
        vol["narrator_input_n"] = len(outline.get("episodes") or [])
        vol["supplied_to_model_n"] = vol["narrator_input_n"]
        pack["volume"] = vol
    return pack


def run_fixture(
    fixture_path: Path | str,
    *,
    provider: str = "ollama",
    model: str,
    timeout_seconds: int = 1800,
    out_dir: Path | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Replay one fixture: Ask-relative + validation + narrator. No retrieval."""
    fixture = load_fixture(fixture_path)
    prepared = fixture.get("prepared") or {}
    case_id = str(fixture.get("case_id") or "unknown")
    ask = str(fixture.get("ask") or prepared.get("ask") or "")
    input_sha = str(fixture.get("input_sha256") or "")
    provider_kind = normalize_provider_kind(provider)
    spec = HistorianProviderSpec(
        provider=provider_kind,
        model=model,
        timeout_seconds=int(timeout_seconds),
    )
    llm = build_historian_provider(spec)
    run_at = _utc_stamp()
    commit = source_commit or _git_commit()

    system = str(prepared.get("ask_relative_system") or ASK_RELATIVE_SYSTEM)
    user_payload = prepared.get("ask_relative_user_payload") or {}
    user_message = prepared.get("ask_relative_user_message") or json.dumps(
        user_payload, default=str
    )
    sys_chars = len(system)
    user_chars = len(user_message)
    request_bytes = len(system.encode("utf-8")) + len(user_message.encode("utf-8"))

    result: dict[str, Any] = {
        "case_id": case_id,
        "ask": ask,
        "fixture_filename": Path(fixture_path).name,
        "fixture_sha256": input_sha,
        "source_commit": commit,
        "provider": provider_kind,
        "requested_model": model,
        "actual_model": model,
        "timeout_seconds": int(timeout_seconds),
        "json_mode": bool(prepared.get("json_mode", True)),
        "temperature": prepared.get("temperature"),
        "provider_options": prepared.get("provider_options"),
        "system_chars": sys_chars,
        "system_bytes": len(system.encode("utf-8")),
        "user_chars": user_chars,
        "user_bytes": len(user_message.encode("utf-8")),
        "request_bytes": request_bytes,
        "estimated_input_tokens": _estimate_tokens(system + user_message),
        "ask_relative_schema_valid": False,
        "downstream_validation_valid": False,
        "narrator_called": False,
        "status": "error",
        "error_class": None,
        "error_message": None,
        "final_result_status": "error",
    }

    raw_view = ""
    partial_raw = ""
    ask_usage: dict[str, Any] = {}
    ask_wall_ms = 0
    narrator_text = ""
    narrator_usage: dict[str, Any] = {}
    narrator_wall_ms = 0
    parsed_view: dict[str, Any] | None = None
    schema_ok = False
    sem_ok = False
    schema_reason = ""
    sem_reason = ""
    inf: dict[str, Any] = {}

    try:
        raw_view, ask_usage, ask_wall_ms = historian_chat_json(
            llm,
            system=system,
            user_payload=user_payload,
            json_mode=bool(prepared.get("json_mode", True)),
            requested_model=model,
        )
        result["actual_model"] = ask_usage.get("model") or model
        result["actual_provider"] = ask_usage.get("provider_key") or provider_kind
        result["prompt_eval_count"] = ask_usage.get("prompt_eval_count")
        result["eval_count"] = ask_usage.get("eval_count")
        result["load_duration"] = ask_usage.get("load_duration")
        result["prompt_eval_duration"] = ask_usage.get("prompt_eval_duration")
        result["eval_duration"] = ask_usage.get("eval_duration")
        result["ollama_total_duration"] = ask_usage.get("total_duration")
        result["ask_relative_wall_ms"] = ask_wall_ms
        result["raw_ask_relative"] = raw_view

        parsed_view = parse_inference_json(raw_view)
        eligible = prepared.get("eligible_observations") or []
        rolled = prepared.get("semantic_rollups") or {}
        ho = prepared.get("semantic_higher_order") or {}
        if parsed_view is None:
            schema_ok, schema_reason = False, "ask-relative output is not valid JSON"
            sem_ok, sem_reason = False, schema_reason
        else:
            schema_ok, schema_reason = ask_relative_schema_ok(parsed_view)
            if schema_ok:
                sem_ok, sem_reason = ask_relative_semantic_ok(
                    parsed_view,
                    rollups=rolled,
                    observations=eligible,
                    higher_order=ho,
                )
            else:
                sem_ok, sem_reason = False, schema_reason
        result["ask_relative_schema_valid"] = schema_ok
        result["parsed_ask_relative"] = parsed_view
        result["schema_reason"] = None if schema_ok else schema_reason
        result["semantic_reason"] = None if sem_ok else sem_reason

        if schema_ok and sem_ok:
            plan = plan_from_snapshot(prepared.get("plan_snapshot") or {})
            kind_hint = prepared.get("ask_kind_hint") or ""
            view = view_from_model_json(
                parsed_view,
                eligible,
                ask=ask,
                ask_kind_hint=kind_hint,
                rollups=rolled,
                higher_order=ho,
                allow_fallback=False,
            )
            pack = dict(prepared.get("pack_minimal") or {})
            pack["person_context"] = prepared.get("person_context")
            validated = validate_inference(
                view,
                pack=pack,
                person_context=prepared.get("person_context"),
            )
            downstream_ok = bool(validated.get("ok"))
            result["downstream_validation_valid"] = downstream_ok
            inf = {
                "ok": downstream_ok,
                "fail_closed": not downstream_ok,
                "document": validated.get("document"),
                "ask_relative_view": view,
                "semantic_ir": prepared.get("semantic_ir"),
                "semantic_rollups": rolled,
                "semantic_higher_order": ho,
                "error_class": None if downstream_ok else "MODEL_OUTPUT",
                "reason": None if downstream_ok else "validation failed",
            }
            if downstream_ok and inf.get("document"):
                full_pack = _pack_after_inference(prepared, inf)
                result["narrator_called"] = True
                narrator_payload = pack_for_narrator(full_pack)
                nar_user = json.dumps(narrator_payload, default=str)
                result["narrator_input_bytes"] = len(nar_user.encode("utf-8"))
                result["narrator_input_tokens_est"] = _estimate_tokens(nar_user)
                narrator_text, narrator_usage, narrator_wall_ms = historian_chat_text(
                    llm,
                    system=NARRATOR_SYSTEM,
                    user_text=nar_user,
                    json_mode=False,
                    requested_model=model,
                )
                result["narrator_wall_ms"] = narrator_wall_ms
                result["narrator_prompt_eval_count"] = narrator_usage.get("prompt_eval_count")
                result["narrator_eval_count"] = narrator_usage.get("eval_count")
                result["narrator_total_duration"] = narrator_usage.get("total_duration")
                result["raw_narrator"] = narrator_text
                from memorybox.ask.narrative import _strip_debug_leak, ground_narrative

                cleaned = _strip_debug_leak(narrator_text)
                grounded, rejected = ground_narrative(cleaned, full_pack)
                if grounded:
                    result["final_narrative"] = grounded
                    result["status"] = "ok"
                    result["final_result_status"] = "ok"
                    result["error_class"] = None
                else:
                    result["final_narrative"] = None
                    result["status"] = "error"
                    result["final_result_status"] = "narrator_rejected"
                    result["error_class"] = "MODEL_OUTPUT"
                    result["error_message"] = "Narration added unsupported detail and was rejected."
                    if rejected:
                        result["narrator_rejected"] = rejected[:8]
            else:
                result["status"] = "error"
                result["final_result_status"] = "validation_failed"
                result["error_class"] = "MODEL_OUTPUT"
                result["error_message"] = inf.get("reason") or "downstream validation failed"
        else:
            result["status"] = "error"
            result["final_result_status"] = "ask_relative_invalid"
            result["error_class"] = "MODEL_OUTPUT"
            result["error_message"] = schema_reason if not schema_ok else sem_reason

    except ProviderUnavailable as exc:
        msg = str(exc)
        partial_raw = raw_view or partial_raw
        if "timed out" in msg.lower():
            result["error_class"] = "PROVIDER_TIMEOUT"
            result["error_message"] = msg
            result["final_result_status"] = "timeout"
        else:
            result["error_class"] = "PROVIDER_TRANSPORT"
            result["error_message"] = msg
            result["final_result_status"] = "provider_error"
        if partial_raw:
            result["raw_ask_relative_partial"] = partial_raw
    except Exception as exc:  # noqa: BLE001
        from memorybox.ask.i11a.historian_provider import (
            HistorianCloudNotAvailable,
            HistorianModelMismatch,
            HistorianProviderError,
        )

        if isinstance(exc, HistorianModelMismatch):
            result["error_class"] = "MODEL_MISMATCH"
        elif isinstance(exc, HistorianCloudNotAvailable):
            result["error_class"] = "CLOUD_NOT_AVAILABLE"
        elif isinstance(exc, HistorianProviderError):
            result["error_class"] = "PROVIDER_CONFIG"
        else:
            result["error_class"] = type(exc).__name__
        result["error_message"] = str(exc)
        result["final_result_status"] = "error"

    out_dir = out_dir or _DEFAULT_RUN_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_name = run_filename(case_id, provider_kind, result["actual_model"], run_at, input_sha)
    txt_name = json_name.replace(".json", ".txt")
    json_path = out_dir / json_name
    txt_path = out_dir / txt_name
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    txt_path.write_text(
        _format_human_report(result, narrator_text=narrator_text, raw_ask_relative=raw_view),
        encoding="utf-8",
    )
    result["json_path"] = str(json_path)
    result["txt_path"] = str(txt_path)
    result["json_bytes"] = json_path.stat().st_size
    result["txt_bytes"] = txt_path.stat().st_size
    return result


def _format_human_report(
    result: dict[str, Any],
    *,
    narrator_text: str,
    raw_ask_relative: str,
) -> str:
    lines = [
        f"CASE: {result.get('case_id')}",
        f"ASK: {result.get('ask')}",
        f"FIXTURE: {result.get('fixture_filename')}",
        f"INPUT SHA: {result.get('fixture_sha256')}",
        f"PROVIDER: {result.get('provider')}",
        f"MODEL REQUESTED: {result.get('requested_model')}",
        f"MODEL ACTUAL: {result.get('actual_model')}",
        f"TIMEOUT: {result.get('timeout_seconds')}",
        f"INPUT TOKENS EST: {result.get('estimated_input_tokens')}",
        f"PROMPT_EVAL_COUNT: {result.get('prompt_eval_count')}",
        f"OUTPUT TOKENS: {result.get('eval_count')}",
        f"MODEL TIME (ask-relative wall ms): {result.get('ask_relative_wall_ms')}",
        f"WALL TIME (ask-relative wall ms): {result.get('ask_relative_wall_ms')}",
        f"ASK_RELATIVE STATUS: {result.get('final_result_status')}",
        f"SCHEMA VALID: {result.get('ask_relative_schema_valid')}",
        f"VALIDATION: {result.get('downstream_validation_valid')}",
        f"NARRATOR CALLED: {'yes' if result.get('narrator_called') else 'no'}",
        "",
    ]
    if raw_ask_relative:
        lines.extend(
            [
                "ASK-RELATIVE RAW RESPONSE",
                "-" * 60,
                raw_ask_relative,
                "",
            ]
        )
    lines.extend(
        [
            "=" * 60,
            "MODEL RESPONSE",
            "=" * 60,
            "",
        ]
    )
    tail = _response_tail(result, narrator_text=narrator_text, raw_ask_relative=raw_ask_relative)
    lines.append(tail)
    return "\n".join(lines)


def _response_tail(
    result: dict[str, Any],
    *,
    narrator_text: str,
    raw_ask_relative: str,
) -> str:
    if result.get("narrator_called") and result.get("final_narrative"):
        return str(result["final_narrative"])
    if result.get("narrator_called") and narrator_text:
        return narrator_text
    if raw_ask_relative and not result.get("downstream_validation_valid"):
        return raw_ask_relative
    if result.get("raw_ask_relative_partial"):
        return "[PARTIAL MODEL RESPONSE]\n" + str(result["raw_ask_relative_partial"])
    if result.get("error_class") == "PROVIDER_TIMEOUT":
        limit = result.get("timeout_seconds") or "?"
        return f"[NO MODEL RESPONSE — PROVIDER TIMEOUT AFTER {limit} SECONDS]"
    if raw_ask_relative:
        return raw_ask_relative
    return "[NO MODEL RESPONSE]"


def run_manifest(
    manifest_path: Path | str,
    *,
    provider: str = "ollama",
    model: str,
    timeout_seconds: int = 1800,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Run all fixtures in manifest sequentially (same model, no concurrency)."""
    manifest = load_manifest(manifest_path)
    base = Path(manifest_path).parent
    runs: list[dict[str, Any]] = []
    for entry in manifest.get("cases") or []:
        fname = entry.get("filename") or entry.get("fixture_filename")
        if not fname:
            continue
        fixture_path = base / fname
        runs.append(
            run_fixture(
                fixture_path,
                provider=provider,
                model=model,
                timeout_seconds=timeout_seconds,
                out_dir=out_dir,
            )
        )
    return {
        "manifest": Path(manifest_path).name,
        "provider": normalize_provider_kind(provider),
        "model": model,
        "runs": runs,
    }


def run_historian_fixture_cli(
    *,
    fixture: str | None = None,
    manifest: str | None = None,
    provider: str = "ollama",
    model: str,
    timeout: int = 1800,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    if not model:
        raise ValueError("--model is required")
    if manifest:
        return run_manifest(
            manifest,
            provider=provider,
            model=model,
            timeout_seconds=timeout,
            out_dir=out_dir,
        )
    if not fixture:
        raise ValueError("provide --fixture or --manifest")
    return run_fixture(
        fixture,
        provider=provider,
        model=model,
        timeout_seconds=timeout,
        out_dir=out_dir,
    )


def build_historian_fixtures_cli(
    *,
    cases: tuple[str, ...] | None = None,
    out_dir: Path | None = None,
    flightsim: bool = False,
) -> dict[str, Any]:
    import os

    from memorybox.app import get_orchestrator

    if flightsim:
        os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
    orch = get_orchestrator()
    return build_all_fixtures(orch, cases=cases, out_dir=out_dir)
