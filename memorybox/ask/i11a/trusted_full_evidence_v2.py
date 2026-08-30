"""Phase 2: frozen Full-Evidence V2 fixture + Gemma / Sol single-pass runs.

No chunking. Build only after trusted-identity retrieve is in place.
Does not hard-code a Person or expected message count in retrieve behavior.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.full_evidence_diagnostic import (
    CHUNK_TRIGGER_TOKENS,
    format_item_block,
    normalize_retrieved,
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


def fev2_ollama_num_ctx(estimated_tokens: int | None) -> int:
    """Ollama window large enough for the frozen paste, not the model default.

    FlightSim Gemma finished the 241k-token starve in 11s and cited email_1
    because default num_ctx tail-truncated the year-fair mail.
    ``MEMORYBOX_FEV2_OLLAMA_NUM_CTX`` overrides when a host OOMs at 128k.
    """
    override = (os.environ.get("MEMORYBOX_FEV2_OLLAMA_NUM_CTX") or "").strip()
    if override.isdigit():
        return max(2_048, min(int(override), FEV2_OLLAMA_NUM_CTX_MAX))
    need = int(estimated_tokens or 0) + FEV2_OLLAMA_GEN_ROOM
    return max(FEV2_OLLAMA_NUM_CTX_MIN, min(need, FEV2_OLLAMA_NUM_CTX_MAX))


def apply_flightsim_app_env() -> dict[str, Any]:
    """Load MEMORYBOX_CLOUD_LLM_* from repo config/*.env into os.environ.

    FlightSim last skipped Sol with no_sol_model because the Python pipeline
    only saw process env. cmd `for /f` set lines can miss; startmb vars stay
    in PowerShell. Does not clobber keys already set.
    """
    import importlib.util

    export = _REPO_ROOT / "tools" / "export-memorybox-app-env.py"
    spec = importlib.util.spec_from_file_location("export_memorybox_app_env", export)
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.apply_unset_keys_to_environ())

SINGLE_PASS_TOKEN_BUDGET = min(100_000, CHUNK_TRIGGER_TOKENS)
PERSON_FACT_TOKEN_CAP = 4_000
MIN_SINGLE_PASS_EMAILS_WHEN_ARCHIVE_LARGE = 8
SINGLE_PASS_EMAIL_RETRIEVE_CAP = 200
SINGLE_PASS_EMAIL_BODY_CHARS = 2_500
ESTABLISHED_GEMMA_MODEL = "gemma4:26b"
FEV2_OLLAMA_NUM_CTX_MIN = 32_768
FEV2_OLLAMA_NUM_CTX_MAX = 131_072
FEV2_OLLAMA_GEN_ROOM = 4_096
# FlightSim 2026-08-29: 1 email + 241k-token person card. Remap can make
# that Gemma report look ok — it is not a year-fair Phase 2 freeze.
LEGACY_STARVED_FREEZE_HASH_PREFIX = "3cf95fa4"
_PLACEHOLDER_EVIDENCE_ID = re.compile(
    r"^(?P<kind>email|person|calendar|sms|story|journal|artifact|travel|photo|video)_(?P<n>\d+)$",
    re.I,
)

FEV2_SYSTEM = """You are MemoryBox Full-Evidence V2. Use only the supplied evidence.
Return JSON only:
{"episodes":[{"title":"","when":"","summary":"","evidence_ids":[]}],
 "claims":[{"text":"","evidence_ids":[]}],
 "relationships":[{"from":"","to":"","role":"","evidence_ids":[]}],
 "narrator":""}
Every accepted claim, episode, and relationship MUST cite original evidence_ids
from the input (the UUID after evidence_id: and/or the cite_as token such as
email_1 / person_1 printed on that same block). Invented facts or unknown ids
are forbidden. If email evidence is present, grounded output must use those
email ids when they support a claim.
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
    for key in ("evidence_id", "item_id", "id", "native_id", "cite_as"):
        raw = item.get(key)
        if raw:
            ids.append(str(raw))
    for raw in item.get("evidence_ids") or []:
        if raw:
            ids.append(str(raw))
    return list(dict.fromkeys(ids))


def attach_fev2_cite_aliases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bind Gemma-style email_1 / person_1 to the nth item of that source.

    FlightSim gemma4:26b read the Christmas-wishlist mail and still cited
    email_1 / person_1. Those tokens are aliases of the real evidence_id,
    not invented ids, when they appear on the block.
    """
    counts: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for it in items:
        slim = dict(it)
        src = str(it.get("source") or it.get("channel") or "other").lower() or "other"
        counts[src] = int(counts.get(src) or 0) + 1
        slim["cite_as"] = f"{src}_{counts[src]}"
        out.append(slim)
    return out


def item_is_trusted_email(item: dict[str, Any], trusted: set[str]) -> bool:
    """Structured From/To/CC/BCC (incl. Hotmail from_parsed). Never people[]."""
    if str(item.get("source") or item.get("channel") or "").lower() != "email":
        return False
    trusted_n = {normalize_handle(a) for a in trusted if a}
    if not trusted_n:
        return False
    found: set[str] = set()
    for rec in (
        list(item.get("from_parsed") or [])
        + list(item.get("to_parsed") or [])
        + list(item.get("cc_parsed") or [])
        + list(item.get("bcc_parsed") or [])
    ):
        if isinstance(rec, dict):
            n = normalize_handle(str(rec.get("normalized") or rec.get("address") or ""))
            if n and "@" in n:
                found.add(n)
    for raw in list(item.get("addresses") or []):
        n = normalize_handle(str(raw))
        if n and "@" in n:
            found.add(n)
    blob = " ".join(
        str(item.get(k) or "")
        for k in ("from", "to", "cc", "bcc", "from_header", "to_header")
    )
    for m in re.finditer(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob
    ):
        n = normalize_handle(m.group(0))
        if n and "@" in n:
            found.add(n)
    return bool(found & trusted_n)


def _trim_fev2_email_payloads(hits: list[Any]) -> None:
    """Cap HTML/text on the hit before normalize (200 full Takeout bodies)."""
    n = SINGLE_PASS_EMAIL_BODY_CHARS
    keys = ("body_text", "body_html", "html", "text", "snippet")
    for hit in hits:
        payload = getattr(hit, "payload", None)
        if not isinstance(payload, dict):
            continue
        for key in keys:
            val = payload.get(key)
            if isinstance(val, str) and len(val) > n:
                payload[key] = val[:n]


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
                email.append(_cap_single_pass_email_body(it))
        else:
            non_email.append(it)
    # Keep retrieve order (year-fair sample). Newest-only packing
    # collapsed Peggy's archive to late spam after the person card ate budget.
    non_email.sort(
        key=lambda i: str(i.get("sent_at") or i.get("start") or i.get("timestamp") or ""),
        reverse=True,
    )
    capped_person: list[dict[str, Any]] = []
    for it in person:
        block_tok = _estimate_tokens(format_item_block(it))
        if block_tok <= PERSON_FACT_TOKEN_CAP:
            capped_person.append(it)
            continue
        # FlightSim dumped 1,568 header aliases into person facts (~240k tokens)
        # and starved trusted mail down to one message. Cap the card.
        slim = dict(it)
        facts = slim.get("facts") if isinstance(slim.get("facts"), dict) else {}
        keep = {
            "display_name": facts.get("display_name") or slim.get("title"),
            "aliases": list(facts.get("aliases") or [])[:12],
            "communication_identities": list(facts.get("communication_identities") or [])[:8],
        }
        slim["facts"] = keep
        slim["body"] = json.dumps(keep, indent=2, default=str, ensure_ascii=False)
        capped_person.append(slim)
    # Trusted email first. Calendar/story/journal fill whatever budget remains.
    selected = list(capped_person)
    used = _estimate_tokens("\n".join(format_item_block(i) for i in selected)) if selected else 0
    for it in email:
        block_tok = _estimate_tokens(format_item_block(it))
        if selected and used + block_tok > token_budget:
            break
        selected.append(it)
        used += block_tok
    for it in non_email:
        block_tok = _estimate_tokens(format_item_block(it))
        if selected and used + block_tok > token_budget:
            break
        selected.append(it)
        used += block_tok
    if email and not any(item_is_trusted_email(i, trusted) for i in selected):
        selected.append(email[0])
    # Model default num_ctx often truncates the tail. Person-first + a fat
    # card is how FlightSim Gemma cited placeholders after 11s on 241k tokens.
    # Email first so a short window still grounds on trusted mail.
    ordered_email: list[dict[str, Any]] = []
    ordered_person: list[dict[str, Any]] = []
    ordered_other: list[dict[str, Any]] = []
    for it in selected:
        src = str(it.get("source") or it.get("channel") or "").lower()
        if src == "email":
            ordered_email.append(it)
        elif src == "person":
            ordered_person.append(it)
        else:
            ordered_other.append(it)
    return attach_fev2_cite_aliases(ordered_email + ordered_person + ordered_other)


def _cap_single_pass_email_body(item: dict[str, Any]) -> dict[str, Any]:
    """Keep enough of each message for grounding without one HTML body eating the budget."""
    body = str(item.get("body") or "")
    if len(body) <= SINGLE_PASS_EMAIL_BODY_CHARS:
        return item
    slim = dict(item)
    slim["body"] = (
        body[:SINGLE_PASS_EMAIL_BODY_CHARS].rstrip() + "\n…[truncated for single-pass]"
    )
    return slim


def remap_placeholder_evidence_ids(
    document: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Map Gemma-style email_1 / person_1 onto the nth fixture item of that source."""
    by_kind: dict[str, list[str]] = {}
    for it in items:
        src = str(it.get("source") or "").lower()
        ids = item_evidence_ids(it)
        if not src or not ids:
            continue
        by_kind.setdefault(src, []).append(ids[0])
    allowed = all_fixture_evidence_ids(items)

    def rewrite(eid: Any) -> str:
        raw = str(eid)
        if raw in allowed:
            return raw
        match = _PLACEHOLDER_EVIDENCE_ID.match(raw)
        if not match:
            return raw
        kind = match.group("kind").lower()
        idx = int(match.group("n"))
        bucket = by_kind.get(kind) or []
        if 1 <= idx <= len(bucket):
            return bucket[idx - 1]
        return raw

    rewritten = json.loads(json.dumps(document, default=str))
    for section in ("claims", "episodes", "relationships"):
        for row in rewritten.get(section) or []:
            if not isinstance(row, dict):
                continue
            ids = row.get("evidence_ids")
            if isinstance(ids, list):
                row["evidence_ids"] = [rewrite(x) for x in ids]
    return rewritten


def cap_single_pass_retrieved_emails(mail: list[Any]) -> list[Any]:
    """Year-fair sample so freeze does not normalize the whole trusted archive.

    ``search_email_messages`` still scans identity-closed rows; this cap is
    what the model sees. Complete Person retrieve must stay unbounded.
    """
    from memorybox.ask.retrieve import _year_fair_slice

    if len(mail) <= SINGLE_PASS_EMAIL_RETRIEVE_CAP:
        return list(mail)
    sliced, _truncated = _year_fair_slice(mail, SINGLE_PASS_EMAIL_RETRIEVE_CAP)
    return list(sliced)


def single_pass_email_coverage_ok(
    *,
    retrieved_email_n: int,
    selected_email_n: int,
    complete_trusted: bool,
) -> bool:
    """Refuse a 1-email freeze when trusted retrieve already has an archive."""
    if selected_email_n <= 0:
        return False
    if complete_trusted:
        return True
    if int(retrieved_email_n) >= 20:
        return int(selected_email_n) >= MIN_SINGLE_PASS_EMAILS_WHEN_ARCHIVE_LARGE
    return True


def fixture_selected_email_count(data: dict[str, Any]) -> int:
    counts = data.get("evidence_type_counts")
    if isinstance(counts, dict) and counts.get("email") is not None:
        return int(counts.get("email") or 0)
    if data.get("selected_email_count") is not None:
        return int(data.get("selected_email_count") or 0)
    return sum(
        1
        for it in (data.get("items") or [])
        if isinstance(it, dict) and str(it.get("source") or "").lower() == "email"
    )


def fixture_is_single_pass_coverage_ok(data: dict[str, Any]) -> bool:
    """Reject the 1-email 3cf95fa4 freeze and any archive-starved sample."""
    digest = str(data.get("input_sha256") or "")
    if digest.startswith(LEGACY_STARVED_FREEZE_HASH_PREFIX):
        return False
    selected = fixture_selected_email_count(data)
    archive = int(
        data.get("archive_email_count") or data.get("retrieved_email_count") or 0
    )
    return single_pass_email_coverage_ok(
        retrieved_email_n=archive,
        selected_email_n=selected,
        complete_trusted=bool(data.get("complete_trusted")),
    )


def format_trusted_fev2_paste(
    items: list[dict[str, Any]],
    *,
    ask: str,
    person_context: dict[str, Any],
) -> str:
    """Historian paste plus the exact evidence_ids models must copy."""
    items = attach_fev2_cite_aliases(list(items))
    email_items: list[dict[str, Any]] = []
    other_items: list[dict[str, Any]] = []
    for it in items:
        if str(it.get("source") or it.get("channel") or "").lower() == "email":
            email_items.append(it)
        else:
            other_items.append(it)
    ordered = email_items + other_items
    allowed: list[str] = []
    for it in ordered:
        allowed.extend(item_evidence_ids(it))
    allowed = list(dict.fromkeys(a for a in allowed if a))
    slim = slim_person_context_for_model(person_context)

    def _blocks(rows: list[dict[str, Any]]) -> list[str]:
        out: list[str] = []
        for it in rows:
            clean = {
                k: v
                for k, v in it.items()
                if k
                not in {
                    "content_fingerprint",
                    "retrieved_index",
                    "normalization",
                    "raw_body_chars",
                    "metadata",
                }
            }
            out.append(format_item_block(clean))
        return out

    # Email blocks before the full id roster. Ollama default num_ctx often
    # truncates the tail — a 100k-token ALLOWED list at the top is how the
    # model never sees trusted mail and invents email_1.
    parts = [
        "Cite evidence_ids by copying evidence_id or cite_as from the evidence blocks.",
        "cite_as tokens such as email_1 are valid only when printed on a block.",
        "",
        "Use only the Person context and evidence below. Do not invent facts.",
        f"ASK: {ask}",
        "",
        "===== TRUSTED EMAIL EVIDENCE =====",
        "",
        *(_blocks(email_items) or ["(no trusted email in this freeze)"]),
        "",
        "===== PERSON CONTEXT =====",
        "",
        json.dumps(slim, indent=2, default=str, ensure_ascii=False),
        "",
        "===== OTHER EVIDENCE =====",
        "",
        *_blocks(other_items),
        "",
        "ALLOWED_EVIDENCE_IDS: " + ", ".join(allowed),
    ]
    return "\n".join(parts).rstrip() + "\n"


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
    if plan is None:
        # Year-fair trusted email + slim person. Calendar/story/journal/artifact
        # scans stay off unless complete_trusted — FlightSim calendar paging
        # loads every ICS payload_json before limit=12.
        plan = QueryPlan(
            original_ask=ask,
            effective_ask=ask,
            is_followup=False,
            want_photo=False,
            want_communication=True,
            want_calendar=complete_trusted,
            want_story=complete_trusted,
            want_journal=complete_trusted,
            want_artifact=complete_trusted,
            want_visual=False,
            want_still=False,
            want_video=False,
            want_spoken=False,
            person_names=(),
            person_ids=(str(person_id),),
            place_names=(),
            time_start=None,
            time_end=None,
            temporal_windows=(),
            notes=("complete_comm_retrieve", "trusted_full_evidence_v2"),
        )
    print(
        f"fev2 freeze: person={person_id} trusted={sorted(trusted)} "
        f"complete_trusted={complete_trusted} email_cap={SINGLE_PASS_EMAIL_RETRIEVE_CAP}",
        file=sys.stderr,
        flush=True,
    )
    person_context = build_person_context(plan)
    from memorybox.ask import retrieve as R

    print("fev2 freeze: year-fair trusted email light scan", file=sys.stderr, flush=True)
    mail = list(
        R.search_email_messages(plan, limit=SINGLE_PASS_EMAIL_RETRIEVE_CAP) or []
    )
    archive_email_n = len(mail)
    if mail:
        head = mail[0]
        match_total = getattr(head, "match_total", None)
        if match_total is None and isinstance(head, dict):
            match_total = head.get("match_total")
        archive_email_n = int(match_total or archive_email_n)
    mail = cap_single_pass_retrieved_emails(mail)
    _trim_fev2_email_payloads(mail)
    print(
        f"fev2 freeze: email archive={archive_email_n} sample={len(mail)}",
        file=sys.stderr,
        flush=True,
    )
    cal = (
        list(R.search_calendar_events(plan, limit=12) or [])
        if plan.want_calendar
        else []
    )
    stories = list(R.search_stories(plan, limit=12) or []) if plan.want_story else []
    journals = list(R.search_journals(plan, limit=12) or []) if plan.want_journal else []
    artifacts = (
        list(R.search_artifacts(plan, limit=12) or []) if plan.want_artifact else []
    )
    retrieved = {
        "evidence": mail + cal,
        "photos": [],
        "videos": [],
        "stories": stories,
        "journals": journals,
        "artifacts": artifacts,
        "guided_capture": [],
        "photo_status": {"skipped": "single_pass_no_unbounded_immich"},
        "video_status": {"skipped": "single_pass_no_unbounded_immich"},
        "sms_status": {"skipped": "single_pass_no_unbounded_sms"},
        "calendar_status": {
            "skipped": None if cal else "single_pass_no_calendar_scan"
        },
        "story_status": {"skipped": None if stories else "single_pass_no_story_scan"},
    }
    print("fev2 freeze: normalize + pack trusted email", file=sys.stderr, flush=True)
    norm = normalize_retrieved(retrieved, person_context=person_context)
    budget = 1_000_000_000 if complete_trusted else token_budget
    items = select_single_pass_items(
        list(norm.get("items") or []),
        trusted_addrs=trusted,
        token_budget=budget,
    )
    paste = format_trusted_fev2_paste(
        items,
        ask=ask,
        person_context=person_context,
    )
    by_source: dict[str, int] = {}
    for it in items:
        src = str(it.get("source") or "other")
        by_source[src] = int(by_source.get(src) or 0) + 1
    email_ids: set[str] = set()
    for it in items:
        if str(it.get("source") or "") == "email":
            email_ids.update(item_evidence_ids(it))
    selected_email_n = int(by_source.get("email") or 0)
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
        "archive_email_count": archive_email_n,
        "freeze_email_sample_n": len(mail),
        "selected_email_count": selected_email_n,
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
    print(
        f"fev2 freeze: wrote {path.name} selected_email={selected_email_n} "
        f"tokens={body['estimated_tokens']}",
        file=sys.stderr,
        flush=True,
    )
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
        "archive_email_count": archive_email_n,
        "freeze_email_sample_n": len(mail),
        "chunking": False,
    }
    (out / f"FEV2_manifest_{body['input_sha256'][:8]}.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
    retrieved_email_n = archive_email_n
    coverage_ok = single_pass_email_coverage_ok(
        retrieved_email_n=retrieved_email_n,
        selected_email_n=selected_email_n,
        complete_trusted=bool(complete_trusted),
    )
    error = None
    if not trusted:
        error = "no_trusted_retrieve_addresses"
    elif not email_ids:
        error = "no_trusted_email_in_fixture"
    elif not coverage_ok:
        error = "trusted_email_starved"
    return {
        "ok": error is None,
        "error": error,
        "retrieved_email_count": retrieved_email_n,
        "selected_email_count": selected_email_n,
        "freeze_email_sample_n": len(mail),
        "fixture": body,
        **manifest,
    }


def run_trusted_full_evidence_v2(
    fixture_path: Path | str,
    *,
    provider: str,
    model: str,
    timeout_seconds: int = 1800,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Replay a frozen FEV2 fixture through one model. No retrieval. No chunking."""
    apply_flightsim_app_env()
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    stored = data.get("input_sha256")
    recomputed = fev2_input_sha256(data)
    if stored and stored != recomputed:
        raise ValueError(f"fixture hash mismatch file={stored} recomputed={recomputed}")
    if not data.get("complete_trusted") and not fixture_is_single_pass_coverage_ok(data):
        return {
            "ok": False,
            "skipped": True,
            "error": "trusted_email_starved_fixture",
            "input_sha256": stored,
            "provider": provider,
            "model": model,
            "chunking": False,
            "selected_email_count": fixture_selected_email_count(data),
        }
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
        doc = remap_placeholder_evidence_ids(
            result.get("document") or {}, list(data.get("items") or [])
        )
        result["document"] = doc
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
        num_ctx=fev2_ollama_num_ctx(
            int(data.get("estimated_tokens") or _estimate_tokens(user_message))
        ),
    )
    if spec.provider == "ollama":
        from memorybox.config import OLLAMA_AUTODETECT_URLS, settings
        from memorybox.providers.llm._ollama_http import ollama_has_model, ollama_reachable

        base = (settings.ollama_base_url or "").strip()
        if not base:
            for url in OLLAMA_AUTODETECT_URLS:
                if ollama_reachable(url):
                    base = url
                    break
        if not base or not ollama_has_model(base, model):
            return {
                "ok": False,
                "skipped": True,
                "error": f"ollama_model_missing:{model}",
                "input_sha256": stored,
                "provider": spec.provider,
                "model": model,
                "chunking": False,
            }
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
    parsed = remap_placeholder_evidence_ids(parsed, list(data.get("items") or []))
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
