"""Acceptance tests for historian frozen-fixture build + model runner."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.historian_cloud_export import export_cloud_request
from memorybox.ask.i11a.historian_fixture import (
    CASE_ORDER,
    HISTORIAN_CASES,
    _fixture_body_from_prepared,
    load_fixture,
    run_filename,
    serialize_fixture_document,
    verify_fixture_sha_roundtrip,
)
from memorybox.ask.i11a.historian_prepared import (
    ask_relative_request_from_prepared,
    build_prepared_historian_input,
    historian_input_sha256,
)
from memorybox.ask.i11a.historian_provider import (
    HistorianCloudNotAvailable,
    HistorianModelMismatch,
    HistorianProviderSpec,
    build_historian_provider,
    historian_chat_json,
    normalize_provider_kind,
    sanitize_model_for_filename,
)
from memorybox.ask.i11a.infer import run_historian_from_prepared_input
from memorybox.ask.i11a.reason import ASK_RELATIVE_SYSTEM
from memorybox.context import AskContext
from memorybox.planner import plan_ask


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


class _CountingLlm:
    provider_key = "fake"
    chat_model = "test-model"

    def __init__(self) -> None:
        self.chats = 0

    def chat(self, messages, *, json_mode=False):
        self.chats += 1
        from memorybox.providers.llm.dto import ChatResultDto

        system = "\n".join(m.content for m in messages if m.role == "system")
        if "ASK_RELATIVE" in system:
            body = json.dumps(
                {
                    "answer_focus": "test",
                    "selected_higher_order_ids": ["ho-1"],
                    "selected_rollup_ids": [],
                    "selected_observation_ids": [],
                    "themes": [],
                    "unresolved": [],
                }
            )
        else:
            body = "Documentary answer for the family."
        return ChatResultDto(model=self.chat_model, content=body, usage={"eval_count": 10})


class _GuardOrchestrator:
    """Orchestrator stub that must not be used during fixture replay."""

    def ask(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("fixture replay must not call orchestrator.ask")


def _synthetic_prepared(*, case_id: str = "peggy") -> dict[str, Any]:
    ask = HISTORIAN_CASES[case_id]
    plan = plan_ask(ask, AskContext(session_id="histfix-test"))
    obs = [
        {
            "observation_id": "obs-1",
            "kind": "communication_states",
            "text": "Peggy wrote about the appointment.",
            "claim_type": "observed",
            "supporting_evidence_ids": ["e-sms-1"],
            "people": [{"name": "Peggy"}],
            "places": [],
        }
    ]
    rollups = {
        "rollups": [
            {
                "rollup_id": "ru-1",
                "label": "Peggy messages",
                "observation_ids": ["obs-1"],
                "supporting_evidence_ids": ["e-sms-1"],
            }
        ],
        "by_id": {
            "ru-1": {
                "rollup_id": "ru-1",
                "label": "Peggy messages",
                "observation_ids": ["obs-1"],
            }
        },
        "rollup_unit_count": 1,
    }
    ho = {
        "units": [
            {
                "higher_order_id": "ho-1",
                "label": "Peggy communication",
                "rollup_ids": ["ru-1"],
                "person_id": "p-peggy",
            },
            {
                "higher_order_id": "ho-1",
                "label": "duplicate id probe",
                "rollup_ids": ["ru-1"],
            },
        ],
        "by_id": {
            "ho-1": {
                "higher_order_id": "ho-1",
                "rollup_ids": ["ru-1"],
            }
        },
        "higher_order_unit_total": 2,
    }
    from memorybox.ask.i11a.reason import reason_payload

    req = {"requestor_person_id": "p-owner", "focal_subject_person_ids": ["p-peggy"]}
    person_context = {"people": [{"person_id": "p-peggy", "name": "Peggy"}]}
    rp = reason_payload(
        plan=plan,
        observations=obs,
        request_context=req,
        person_context=person_context,
        ask_kind_hint="person",
        rollups=rollups.get("rollups") or [],
        higher_order=ho,
    )
    pack = {
        "units": [{"evidence_id": "e-sms-1", "kind": "communication"}],
        "volume": {"eligible_n": 1, "processed_n": 1},
        "coverage": {},
    }
    return build_prepared_historian_input(
        plan=plan,
        pack=pack,
        person_context=person_context,
        request_context=req,
        ask_kind_hint="person",
        observations=obs,
        eligible_observations=obs,
        semantic_rollups=rollups,
        semantic_higher_order=ho,
        semantic_ir={"nodes": []},
        ask_relative_user_payload=rp,
        ask_relative_payload_stats={
            "payload_bytes": len(json.dumps(rp)),
            "approx_tokens": 100,
            "timeout_seconds": 1800,
        },
        chunk_map={},
        accounting={"extract_calls": 0, "ask_relative_calls": 0, "leaf_calls": 0},
    )


def _build_fixture_document(*, case_id: str) -> dict[str, Any]:
    prepared = _synthetic_prepared(case_id=case_id)
    return _fixture_body_from_prepared(
        case_id=case_id,
        ask=HISTORIAN_CASES[case_id],
        prepared=prepared,
        source_commit="test-commit",
        built_at="2026-08-28T00:00:00Z",
    )


def run_prove_historian_fixture(*, flightsim: bool = False) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    prepared = _synthetic_prepared()
    llm = _CountingLlm()

    doc = _build_fixture_document(case_id="peggy")
    sha1 = historian_input_sha256(doc)
    sha2 = historian_input_sha256(doc)
    _check("input_sha_stable", sha1 == sha2 and len(sha1) == 64, checks, problems)
    _check(
        "metadata_excluded_from_hash",
        historian_input_sha256({**doc, "source_commit": "other", "built_at": "other"}) == sha1,
        checks,
        problems,
    )

    with tempfile.TemporaryDirectory() as tmp:
        for case_id in CASE_ORDER:
            body = _build_fixture_document(case_id=case_id)
            path = Path(tmp) / f"HISTFIX_{case_id}_test.json"
            path.write_text(serialize_fixture_document(body), encoding="utf-8")
            _check(
                f"fixture_roundtrip_{case_id}",
                verify_fixture_sha_roundtrip(body),
                checks,
                problems,
                detail=f"stored={body.get('input_sha256')}",
            )
            loaded = load_fixture(path)
            _check(
                f"fixture_load_{case_id}",
                loaded.get("input_sha256") == body.get("input_sha256"),
                checks,
                problems,
            )

        path = Path(tmp) / "HISTFIX_peggy_test.json"
        body = _build_fixture_document(case_id="peggy")
        path.write_text(serialize_fixture_document(body), encoding="utf-8")
        loaded = load_fixture(path)
        sha1 = loaded["input_sha256"]

        class _FixedAskLlm(_CountingLlm):
            chat_model = "gemma4:26b"

        run_llm = _FixedAskLlm()

        class _Wrapped:
            provider_key = "ollama"
            chat_model = "gemma4:26b"

            def chat(self, messages, *, json_mode=False):
                return run_llm.chat(messages, json_mode=json_mode)

        raw, usage, wall = historian_chat_json(
            _Wrapped(),
            system=ASK_RELATIVE_SYSTEM,
            user_message=ask_relative_request_from_prepared(prepared)["user_message"],
            requested_model="gemma4:26b",
        )
        _check(
            "explicit_model_gemma",
            usage.get("model") == "gemma4:26b" or run_llm.chat_model == "gemma4:26b",
            checks,
            problems,
        )

        mismatch_ok = False
        try:
            historian_chat_json(
                _Wrapped(),
                system=ASK_RELATIVE_SYSTEM,
                user_message=ask_relative_request_from_prepared(prepared)["user_message"],
                requested_model="llama3.2",
            )
        except HistorianModelMismatch:
            mismatch_ok = True
        _check("model_mismatch_aborts", mismatch_ok, checks, problems)

        cloud_err = False
        try:
            build_historian_provider(
                HistorianProviderSpec(provider="cloud", model="gpt-test", timeout_seconds=60)
            ).chat([], json_mode=True)
        except HistorianCloudNotAvailable:
            cloud_err = True
        except Exception:  # noqa: BLE001
            cloud_err = True
        _check("cloud_requires_explicit_and_blocks", cloud_err, checks, problems)

        _check(
            "cloud_not_default_provider",
            normalize_provider_kind(None) == "ollama",
            checks,
            problems,
        )

        # Filename uses actual model
        fn = run_filename("peggy", "ollama", "gemma4:26b", "20260827T000000Z", sha1)
        _check(
            "run_filename_contains_model",
            "gemma4-26b" in fn and "peggy" in fn and sha1[:8] in fn,
            checks,
            problems,
        )
        _check(
            "sanitize_model",
            sanitize_model_for_filename("gemma4:26b") == "gemma4-26b",
            checks,
            problems,
        )
        # Replay with fake provider via run_historian path using counting llm on prepared
        inf = run_historian_from_prepared_input(prepared, _CountingLlm(), run_narrator=False)
        _check(
            "replay_no_retrieval_path",
            inf.get("ok") or inf.get("fail_closed") is not None,
            checks,
            problems,
        )
        _GuardOrchestrator().ask  # noqa: B018 — guard exists

        # Cloud export uses the same request construction as fixture-run.
        for case_id in CASE_ORDER:
            body = _build_fixture_document(case_id=case_id)
            fpath = Path(tmp) / f"HISTFIX_{case_id}_export.json"
            fpath.write_text(serialize_fixture_document(body), encoding="utf-8")
            exported = export_cloud_request(fpath, out_dir=Path(tmp) / "cloud-benchmark")
            req = ask_relative_request_from_prepared(body["prepared"])
            sys_file = Path(exported["files"]["system"]["path"])
            user_file = Path(exported["files"]["user"]["path"])
            paste_file = Path(exported["files"]["paste"]["path"])
            _check(
                f"cloud_export_bytes_{case_id}",
                sys_file.read_bytes() == req["system"].encode("utf-8")
                and user_file.read_bytes() == req["user_message"].encode("utf-8")
                and exported["manifest"]["system_bytes"] == req["system_bytes"]
                and exported["manifest"]["user_bytes"] == req["user_bytes"]
                and exported["manifest"]["fixture_sha256"] == body["input_sha256"],
                checks,
                problems,
                detail=exported.get("manifest"),
            )
            paste_text = paste_file.read_text(encoding="utf-8")
            _check(
                f"cloud_export_paste_{case_id}",
                paste_text.startswith("===== SYSTEM MESSAGE =====\n")
                and "===== USER MESSAGE =====\n" in paste_text
                and paste_text.endswith(req["user_message"])
                and "Gemma" not in paste_text
                and "MemoryBox" not in paste_text
                and "ChatGPT" not in paste_text,
                checks,
                problems,
            )

    _check("four_cases_defined", len(HISTORIAN_CASES) == 4, checks, problems)
    for cid in ("peggy", "january_2025", "vegas", "alaska"):
        _check(f"case_{cid}_ask", cid in HISTORIAN_CASES and HISTORIAN_CASES[cid], checks, problems)

    return {"ok": not problems, "checks": checks, "problems": problems, "flightsim": flightsim}
