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
    selected = list(person) + list(non_email)
    used = _estimate_tokens("\n".join(format_item_block(i) for i in selected))
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
            unsupported.append({"claim": claim.get("text") or claim.get("claim"), "reason": "missing_evidence_ids"})
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


def freeze_trusted_full_evidence_v2(
    *,
    person_id: str,
    ask: str,
    out_dir: Path | str | None = None,
    plan: Any | None = None,
    token_budget: int = SINGLE_PASS_TOKEN_BUDGET,
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
    items = select_single_pass_items(
        list(norm.get("items") or []),
        trusted_addrs=trusted,
        token_budget=token_budget,
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
        "fixture_kind": "full_evidence_v2_trusted",
        "ask": ask,
        "person_id": person_id,
        "trusted_addresses": sorted(trusted),
        "person_context": slim_person_context_for_model(person_context),
        "items": items,
        "evidence_type_counts": by_source,
        "email_evidence_ids": sorted(email_ids),
        "token_budget": token_budget,
        "estimated_tokens": _estimate_tokens(paste),
        "source_commit": _git_commit(),
        "built_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "chunking": False,
    }
    body["input_sha256"] = fev2_input_sha256(body)
    fname = f"FEV2_{body['built_at']}_{body['input_sha256'][:8]}.json"
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
    # If this is a historian prepared wrapper, reuse the established runner.
    if data.get("prepared"):
        result = run_fixture(
            fixture_path,
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
            out_dir=Path(out_dir) if out_dir else None,
        )
        doc = result.get("document") or {}
        email_ids = set(data.get("email_evidence_ids") or [])
        if not email_ids:
            for it in (data.get("items") or []):
                if str(it.get("source") or "") == "email":
                    email_ids.update(item_evidence_ids(it))
        grounding = score_email_grounding(doc, email_evidence_ids=email_ids)
        result["email_grounding"] = grounding
        result["input_sha256"] = stored
        result["chunking"] = False
        result["ok"] = bool(result.get("ok")) and bool(grounding.get("ok"))
        return result
    # Raw FEV2 pack: wrap as a minimal historian prepared payload is out of scope
    # without observations. Report freeze-only until prepared is attached.
    return {
        "ok": False,
        "error": "fixture_has_no_prepared_ask_relative_payload",
        "input_sha256": stored,
        "provider": provider,
        "model": model,
        "chunking": False,
        "hint": "Freeze via historian-prepared path or attach prepared before model run",
    }


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
