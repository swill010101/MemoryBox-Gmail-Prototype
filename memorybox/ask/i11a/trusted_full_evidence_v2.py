"""Phase 2: frozen Full-Evidence V2 fixture + Gemma / Sol single-pass runs.

No chunking. Build only after trusted-identity retrieve is in place.
Does not hard-code a Person or expected message count in retrieve behavior.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.full_evidence_diagnostic import (
    CHUNK_TRIGGER_TOKENS,
    format_full_evidence_text,
    format_item_block,
    normalize_retrieved,
    retrieve_eligible_hits,
    slim_person_context_for_model,
)
from memorybox.ask.i11a.historian_fixture import (
    _fixture_body_from_prepared,
    load_fixture,
    run_fixture,
    serialize_fixture_document,
)
from memorybox.ask.i11a.historian_prepared import (
    canonical_json_dumps,
    historian_input_sha256,
)
from memorybox.ask.i11a.person_context import build_person_context
from memorybox.person.phone_map import normalize_handle
from memorybox.person.trusted_identity import trusted_emails_for_people

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT = _REPO_ROOT / "docs" / "test-output" / "trusted-full-evidence-v2"

SINGLE_PASS_TOKEN_BUDGET = min(100_000, CHUNK_TRIGGER_TOKENS)
ESTABLISHED_GEMMA_MODEL = "gemma4:26b"

FEV2_SYSTEM = """You are MemoryBox Full-Evidence V2. Use only the supplied evidence.
Return JSON only:
{"episodes":[{"title":"","when":"","summary":"","evidence_ids":[]}],
 "claims":[{"text":"","evidence_ids":[]}],
 "relationships":[{"from":"","to":"","role":"","evidence_ids":[]}],
 "narrator":""}
Every accepted claim, episode, and relationship MUST cite original evidence_ids
from the input. Invented facts or unknown ids are forbidden. If email evidence
is present, grounded output must use those email ids when they support a claim.
No chunking. Stateless. Do not use outside knowledge."""


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")) // 4)


def fev2_input_sha256(body: dict[str, Any]) -> str:
    payload = {
        "ask": body.get("ask"),
        "trusted_addresses": body.get("trusted_addresses"),
        "person_context": body.get("person_context"),
        "items": body.get("items"),
        "email_evidence_ids": body.get("email_evidence_ids"),
        "user_message": body.get("user_message"),
        "system": body.get("system"),
        "chunking": False,
    }
    if body.get("prepared"):
        return historian_input_sha256(body)
    digest = canonical_json_dumps(payload)
    return hashlib.sha256(digest.encode("utf-8")).hexdigest()


def item_evidence_ids(item: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("evidence_id", "item_id", "id"):
        raw = item.get(key)
        if raw:
            ids.append(str(raw))
    for raw in item.get("evidence_ids") or []:
        if raw:
            ids.append(str(raw))
    return list(dict.fromkeys(ids))


def item_is_trusted_email(item: dict[str, Any], trusted: set[str]) -> bool:
    if str(item.get("source") or item.get("channel") or "").lower() != "email":
        return False
    blob = " ".join(
        [
            str(item.get("from") or ""),
            str(item.get("to") or ""),
            str(item.get("cc") or ""),
            str(item.get("bcc") or ""),
            json.dumps(item.get("addresses") or [], default=str),
            json.dumps(item.get("from_parsed") or [], default=str),
            json.dumps(item.get("to_parsed") or [], default=str),
        ]
    ).lower()
    return any(a in blob for a in trusted if a)


def select_single_pass_items(
    items: list[dict[str, Any]],
    *,
    trusted_addrs: set[str],
    token_budget: int = SINGLE_PASS_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    """Keep person/non-email units + trusted email; cap by time then budget."""
    trusted = {normalize_handle(a) for a in trusted_addrs if a}
    person: list[dict[str, Any]] = []
    non_email: list[dict[str, Any]] = []
    email: list[dict[str, Any]] = []
    for it in items:
        src = str(it.get("source") or it.get("channel") or "").lower()
        if src == "person":
            person.append(it)
        elif src == "email":
            # Fail closed: no trusted keys means no email evidence.
            if trusted and item_is_trusted_email(it, trusted):
                email.append(it)
        else:
            non_email.append(it)
    email.sort(key=lambda i: str(i.get("sent_at") or i.get("start") or ""), reverse=True)
    non_email.sort(
        key=lambda i: str(i.get("sent_at") or i.get("start") or i.get("timestamp") or ""),
        reverse=True,
    )
    # Reserve budget so a large photo/SMS library cannot crowd out trusted email.
    email_reserve = max(token_budget // 3, 8_000) if email else 0
    selected = list(person)
    used = _estimate_tokens("\n".join(format_item_block(i) for i in selected)) if selected else 0
    non_email_room = max(0, token_budget - email_reserve - used)
    non_used = 0
    for it in non_email:
        block_tok = _estimate_tokens(format_item_block(it))
        if non_used + block_tok > non_email_room:
            break
        selected.append(it)
        non_used += block_tok
        used += block_tok
    for it in email:
        block_tok = _estimate_tokens(format_item_block(it))
        if selected and used + block_tok > token_budget:
            break
        selected.append(it)
        used += block_tok
    if email and not any(item_is_trusted_email(i, trusted) for i in selected):
        selected.append(email[0])
    return selected


def score_email_grounding(
    document: dict[str, Any],
    *,
    email_evidence_ids: set[str],
) -> dict[str, Any]:
    """Require accepted claims that cite original email evidence IDs."""
    claims = list(document.get("claims") or [])
    episodes = list(document.get("episodes") or [])
    cited: set[str] = set()
    unsupported: list[dict[str, Any]] = []
    accepted_with_email = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        ids = [str(x) for x in (claim.get("evidence_ids") or claim.get("support_ids") or []) if x]
        if not ids:
            unsupported.append(
                {"claim": claim.get("text") or claim.get("claim"), "reason": "missing_evidence_ids"}
            )
            continue
        cited.update(ids)
        if any(i in email_evidence_ids for i in ids):
            accepted_with_email += 1
    for ep in episodes:
        if not isinstance(ep, dict):
            continue
        for i in ep.get("evidence_ids") or []:
            cited.add(str(i))
    email_cited = sorted(cited & email_evidence_ids)
    return {
        "email_evidence_in_fixture": len(email_evidence_ids),
        "email_evidence_cited": email_cited,
        "claims_citing_email": accepted_with_email,
        "email_reached_model": bool(email_evidence_ids),
        "email_affected_output": accepted_with_email > 0 or bool(email_cited),
        "unsupported_claims": unsupported,
        "ok": bool(email_evidence_ids) and (accepted_with_email > 0 or bool(email_cited)),
    }


def all_fixture_evidence_ids(items: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for it in items:
        out.update(item_evidence_ids(it))
    return out


PHASE2_REPORT_KEYS = (
    "model",
    "provider",
    "config",
    "input_sha256",
    "evidence_type_counts",
    "schema_ok",
    "validation",
    "episodes",
    "claims",
    "relationships",
    "narrator",
    "email_evidence_that_affected_output",
    "accepted_claim_evidence_ids",
    "invented_or_unsupported_claims",
    "relationship_errors",
    "gallery",
    "timing_ms",
    "tokens",
    "chunking",
    "email_reached_model_and_grounded_output",
)


def relationship_errors(
    document: dict[str, Any],
    *,
    allowed_ids: set[str],
    allowed_roles: set[str] | None = None,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    roles = {str(x).lower() for x in (allowed_roles or ()) if str(x).strip()}
    for row in document.get("relationships") or []:
        if not isinstance(row, dict):
            errors.append({"reason": "not_an_object", "row": row})
            continue
        ids = [str(x) for x in (row.get("evidence_ids") or []) if x]
        if not ids:
            errors.append({"reason": "missing_evidence_ids", "row": row})
        for i in ids:
            if i not in allowed_ids:
                errors.append({"reason": "invented_evidence_id", "id": i, "row": row})
        role = str(row.get("role") or row.get("role_kind") or "").strip().lower()
        if roles and role and role not in roles:
            errors.append({"reason": "relationship_role_not_in_person_context", "role": role})
    return errors


def build_phase2_model_report(
    *,
    fixture: dict[str, Any],
    document: dict[str, Any],
    provider: str,
    model: str,
    grounding: dict[str, Any],
    timing_ms: int | None = None,
    usage: dict[str, Any] | None = None,
    gallery: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-model Phase 2 report. Pass only if email reached the model and grounded output."""
    allowed = all_fixture_evidence_ids(list(fixture.get("items") or []))
    claims = [c for c in (document.get("claims") or []) if isinstance(c, dict)]
    episodes = [e for e in (document.get("episodes") or []) if isinstance(e, dict)]
    rels = [r for r in (document.get("relationships") or []) if isinstance(r, dict)]
    accepted_ids: list[str] = []
    for claim in claims:
        accepted_ids.extend(str(x) for x in (claim.get("evidence_ids") or []) if x)
    ctx = fixture.get("person_context") or {}
    allowed_roles = set(ctx.get("allowed_relationship_labels") or [])
    rel_err = relationship_errors(
        document, allowed_ids=allowed, allowed_roles=allowed_roles
    )
    email_ids = {str(x) for x in (fixture.get("email_evidence_ids") or []) if x}
    tokens = {
        "prompt": (usage or {}).get("prompt_tokens") or (usage or {}).get("prompt"),
        "completion": (usage or {}).get("completion_tokens")
        or (usage or {}).get("completion"),
        "total": (usage or {}).get("total_tokens") or (usage or {}).get("total"),
        "fixture_estimated": fixture.get("estimated_tokens"),
    }
    grounded = bool(grounding.get("ok")) and bool(grounding.get("email_affected_output"))
    report = {
        "model": model,
        "provider": provider,
        "config": config
        or {
            "chunking": False,
            "stateless": True,
            "established_gemma": ESTABLISHED_GEMMA_MODEL,
        },
        "input_sha256": fixture.get("input_sha256"),
        "evidence_type_counts": fixture.get("evidence_type_counts") or {},
        "schema_ok": bool(grounding.get("schema_ok")),
        "validation": grounding,
        "episodes": episodes,
        "claims": claims,
        "relationships": rels,
        "narrator": document.get("narrator") or "",
        "email_evidence_that_affected_output": grounding.get("email_evidence_cited") or [],
        "accepted_claim_evidence_ids": list(dict.fromkeys(accepted_ids)),
        "invented_or_unsupported_claims": list(grounding.get("unsupported_claims") or [])
        + [{"id": i, "reason": "invented_evidence_id"} for i in (grounding.get("invented_evidence_ids") or [])],
        "relationship_errors": rel_err,
        "gallery": gallery or {},
        "timing_ms": timing_ms,
        "tokens": tokens,
        "chunking": False,
        "email_reached_model_and_grounded_output": grounded,
        "ok": grounded and not rel_err and not (grounding.get("invented_evidence_ids") or []),
    }
    return report


def validate_fev2_document(
    document: dict[str, Any],
    *,
    allowed_ids: set[str],
    email_evidence_ids: set[str],
) -> dict[str, Any]:
    """Fail closed on missing or invented provenance."""
    invented: list[str] = []
    missing_prov: list[str] = []
    for section in ("claims", "episodes", "relationships"):
        for row in document.get(section) or []:
            if not isinstance(row, dict):
                continue
            ids = [str(x) for x in (row.get("evidence_ids") or []) if x]
            if not ids:
                missing_prov.append(
                    str(row.get("text") or row.get("title") or row.get("role") or section)
                )
                continue
            for i in ids:
                if i not in allowed_ids:
                    invented.append(i)
    ground = score_email_grounding(document, email_evidence_ids=email_evidence_ids)
    ok = not invented and not missing_prov and bool(ground.get("ok"))
    return {
        **ground,
        "invented_evidence_ids": sorted(set(invented)),
        "rows_missing_provenance": missing_prov[:24],
        "ok": ok,
        "schema_ok": isinstance(document.get("claims"), list)
        and isinstance(document.get("episodes"), list),
    }


def freeze_trusted_full_evidence_v2(
    *,
    person_id: str,
    ask: str,
    out_dir: Path | str | None = None,
    plan: Any | None = None,
    token_budget: int = SINGLE_PASS_TOKEN_BUDGET,
    complete_trusted: bool = False,
) -> dict[str, Any]:
    """Build a hash-stable Full-Evidence V2 fixture from trusted retrieve."""
    from memorybox.ask.deps import build_photo, build_video
    from memorybox.planner import QueryPlan

    out = Path(out_dir) if out_dir else _DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    trusted = trusted_emails_for_people({person_id})
    if not trusted:
        return {
            "ok": False,
            "error": "no_trusted_retrieve_addresses",
            "person_id": person_id,
            "chunking": False,
        }
    photo = build_photo()
    video = build_video()
    if plan is None:
        plan = QueryPlan(
            original_ask=ask,
            effective_ask=ask,
            is_followup=False,
            want_photo=True,
            want_communication=True,
            want_calendar=True,
            want_story=True,
            want_journal=True,
            want_artifact=True,
            want_visual=True,
            want_still=True,
            want_video=True,
            want_spoken=True,
            person_names=(),
            person_ids=(str(person_id),),
            place_names=(),
            time_start=None,
            time_end=None,
            temporal_windows=(),
            notes=("complete_comm_retrieve", "trusted_full_evidence_v2"),
        )
    person_context = build_person_context(plan)
    retrieved = retrieve_eligible_hits(plan, photo=photo, video=video)
    norm = normalize_retrieved(retrieved, person_context=person_context)
    budget = 1_000_000_000 if complete_trusted else token_budget
    items = select_single_pass_items(
        list(norm.get("items") or []),
        trusted_addrs=trusted,
        token_budget=budget,
    )
    paste = format_full_evidence_text(
        items,
        ask=ask,
        person_context=person_context,
        plan_snapshot={
            "person_ids": list(getattr(plan, "person_ids", ()) or ()),
            "person_names": list(getattr(plan, "person_names", ()) or ()),
        },
    )
    by_source: dict[str, int] = {}
    for it in items:
        src = str(it.get("source") or "other")
        by_source[src] = int(by_source.get(src) or 0) + 1
    email_ids: set[str] = set()
    for it in items:
        if str(it.get("source") or "") == "email":
            email_ids.update(item_evidence_ids(it))
    body = {
        "fixture_kind": (
            "full_evidence_v2_trusted_complete"
            if complete_trusted
            else "full_evidence_v2_trusted"
        ),
        "complete_trusted": bool(complete_trusted),
        "ask": ask,
        "person_id": person_id,
        "trusted_addresses": sorted(trusted),
        "person_context": slim_person_context_for_model(person_context),
        "items": items,
        "evidence_type_counts": by_source,
        "email_evidence_ids": sorted(email_ids),
        "token_budget": budget,
        "estimated_tokens": _estimate_tokens(paste),
        "source_commit": _git_commit(),
        "built_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "chunking": False,
        "system": FEV2_SYSTEM,
        "user_message": paste,
    }
    body["input_sha256"] = fev2_input_sha256(body)
    prefix = "FEV2COMPLETE" if complete_trusted else "FEV2"
    fname = f"{prefix}_{body['built_at']}_{body['input_sha256'][:8]}.json"
    path = out / fname
    path.write_text(serialize_fixture_document(body), encoding="utf-8")
    paste_path = out / f"FEV2_paste_{body['input_sha256'][:8]}.txt"
    paste_path.write_text(paste, encoding="utf-8")
    manifest = {
        "fixture_path": str(path),
        "paste_path": str(paste_path),
        "input_sha256": body["input_sha256"],
        "item_count": len(items),
        "evidence_type_counts": by_source,
        "trusted_addresses": sorted(trusted),
        "email_evidence_ids": sorted(email_ids),
        "estimated_tokens": body["estimated_tokens"],
        "chunking": False,
    }
    (out / f"FEV2_manifest_{body['input_sha256'][:8]}.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
    return {"ok": bool(trusted) and bool(email_ids), "fixture": body, **manifest}


def run_trusted_full_evidence_v2(
    fixture_path: Path | str,
    *,
    provider: str,
    model: str,
    timeout_seconds: int = 1800,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Replay a frozen FEV2 fixture through one model. No retrieval. No chunking."""
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    stored = data.get("input_sha256")
    recomputed = fev2_input_sha256(data)
    if stored and stored != recomputed:
        raise ValueError(f"fixture hash mismatch file={stored} recomputed={recomputed}")
    email_ids = {str(x) for x in (data.get("email_evidence_ids") or []) if x}
    allowed = all_fixture_evidence_ids(list(data.get("items") or []))
    if data.get("prepared"):
        result = run_fixture(
            fixture_path,
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
            out_dir=Path(out_dir) if out_dir else None,
        )
        doc = result.get("document") or {}
        grounding = validate_fev2_document(
            doc, allowed_ids=allowed or email_ids, email_evidence_ids=email_ids
        )
        phase2 = build_phase2_model_report(
            fixture=data,
            document=doc,
            provider=str(result.get("provider") or provider),
            model=model,
            grounding=grounding,
            timing_ms=result.get("timing_ms"),
            usage=result.get("usage") if isinstance(result.get("usage"), dict) else {},
        )
        result["email_grounding"] = grounding
        result["phase2_report"] = phase2
        result["input_sha256"] = stored
        result["chunking"] = False
        result["ok"] = bool(result.get("ok")) and bool(phase2.get("ok"))
        return result
    user_message = str(data.get("user_message") or "")
    system = str(data.get("system") or FEV2_SYSTEM)
    if not user_message:
        return {
            "ok": False,
            "error": "fixture_missing_frozen_user_message",
            "input_sha256": stored,
            "provider": provider,
            "model": model,
            "chunking": False,
        }
    from memorybox.ask.i11a.historian_provider import (
        HistorianProviderSpec,
        build_historian_provider,
        historian_chat_json,
        normalize_provider_kind,
    )
    from memorybox.ask.i11a.validate import parse_inference_json

    spec = HistorianProviderSpec(
        provider=normalize_provider_kind(provider),
        model=model,
        timeout_seconds=int(timeout_seconds),
    )
    llm = build_historian_provider(spec)
    raw, usage, wall_ms = historian_chat_json(
        llm,
        system=system,
        user_message=user_message,
        json_mode=True,
        requested_model=model,
    )
    parsed = parse_inference_json(raw) if raw else {}
    if not isinstance(parsed, dict):
        parsed = {}
    grounding = validate_fev2_document(
        parsed, allowed_ids=allowed or email_ids, email_evidence_ids=email_ids
    )
    phase2 = build_phase2_model_report(
        fixture=data,
        document=parsed,
        provider=spec.provider,
        model=model,
        grounding=grounding,
        timing_ms=wall_ms,
        usage=usage,
    )
    result = {
        "ok": bool(phase2.get("ok")),
        "input_sha256": stored,
        "provider": spec.provider,
        "model": model,
        "chunking": False,
        "timing_ms": wall_ms,
        "usage": usage,
        "document": parsed,
        "raw": (raw or "")[:4000],
        "email_grounding": grounding,
        "phase2_report": phase2,
        "evidence_type_counts": data.get("evidence_type_counts"),
        "trusted_addresses": data.get("trusted_addresses"),
    }
    out = Path(out_dir) if out_dir else Path(fixture_path).parent
    out.mkdir(parents=True, exist_ok=True)
    run_name = f"FEV2RUN_{spec.provider}_{model.replace(':', '-')}_{stored[:8]}.json"
    (out / run_name).write_text(
        json.dumps(result, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    report_name = f"FEV2REPORT_{spec.provider}_{model.replace(':', '-')}_{stored[:8]}.json"
    (out / report_name).write_text(
        json.dumps(phase2, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    result["run_path"] = str(out / run_name)
    result["report_path"] = str(out / report_name)
    return result


def attach_prepared_and_write(
    fev2: dict[str, Any],
    prepared: dict[str, Any],
    *,
    out_dir: Path,
    ask: str,
    case_id: str = "trusted_fe_v2",
) -> dict[str, Any]:
    """Combine trusted FE items with historian-prepared bytes (same fixture hash contract)."""
    body = _fixture_body_from_prepared(
        case_id=case_id,
        ask=ask,
        prepared=prepared,
        source_commit=_git_commit(),
        built_at=str(fev2.get("built_at") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")),
    )
    body["fixture_kind"] = "full_evidence_v2_trusted"
    body["items"] = fev2.get("items") or []
    body["email_evidence_ids"] = fev2.get("email_evidence_ids") or []
    body["trusted_addresses"] = fev2.get("trusted_addresses") or []
    body["evidence_type_counts"] = fev2.get("evidence_type_counts") or {}
    body["chunking"] = False
    body["input_sha256"] = historian_input_sha256(body)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"FEV2PREP_{body['built_at']}_{body['input_sha256'][:8]}.json"
    path = out_dir / fname
    path.write_text(serialize_fixture_document(body), encoding="utf-8")
    return {"path": str(path), "input_sha256": body["input_sha256"], "filename": fname}
