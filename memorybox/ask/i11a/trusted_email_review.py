"""Prepare date-bounded Peggy email conversations for human review.

No model calls. No year-fair sample. No 200-message cap. No body truncation.
Do not reuse FEV2 fe8a128c. Do not upload MODEL_PASTE to git.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.authored import authored_email_text, plain_email_body
from memorybox.ask.i11a.trusted_full_evidence_v2 import (
    ESTABLISHED_GEMMA_MODEL,
    FEV2_OLLAMA_GEN_ROOM,
    _speaker_label,
    _thread_subject,
    _turn_when,
    apply_flightsim_app_env,
)
from memorybox.ask.retrieve import _payload_email_addresses, _sql_confirmed_email_addrs
from memorybox.explore.email_attach import split_quoted_email
from memorybox.person.phone_map import normalize_handle
from memorybox.person.trusted_identity import trusted_emails_for_people

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT = _REPO_ROOT / "docs" / "test-output" / "trusted-email-review"
_FORBIDDEN_FREEZE_PREFIX = "fe8a128c"
_FIVE_YEARS = 5
_OUTPUT_TOKEN_ROOM = FEV2_OLLAMA_GEN_ROOM
_SAFETY_TOKEN_ROOM = 2_048
_RFC_ID = re.compile(r"<[^>]+>")

EMAIL_REVIEW_SYSTEM = """You are a careful family historian for MemoryBox.

Objective: Read the trusted email conversations in the user message and write
what can actually be known about the person named in ASK. Treat each
conversation as who said what, and when. Summarize that life evidence in
readable prose. Do not invent facts, dates, or relationships. Do not treat
header names as family unless the conversation text itself says so.

Use only this packet. No outside knowledge. No MemoryBox memory. No ChatGPT
history. Stateless. No chunking. No hierarchical summarization.

The narrator field must be readable, evidence-grounded prose about the person
— not a metadata list, id roster, or header dump.

Return JSON only:
{"episodes":[{"title":"","when":"","summary":"","evidence_ids":[]}],
 "claims":[{"text":"","evidence_ids":[]}],
 "relationships":[{"from":"","to":"","role":"","evidence_ids":[]}],
 "narrator":""}
Cite each accepted claim, episode, and relationship with the [email_N] tag
printed on that turn. Invented ids are forbidden."""


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
    return max(1, len((text or "").encode("utf-8")) // 4)


def _payload_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _parse_sent_at(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        if len(text) >= 10:
            try:
                return datetime.fromisoformat(text[:10]).replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None


def _rfc_ids(*parts: Any) -> list[str]:
    found: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, (list, tuple)):
            texts = [str(x) for x in part]
        else:
            texts = [str(part)]
        for text in texts:
            for match in _RFC_ID.findall(text):
                found.append(match.strip())
            bare = text.strip()
            if bare.startswith("<") and bare.endswith(">"):
                found.append(bare)
    return list(dict.fromkeys(x for x in found if x))


def classify_body_source(payload: dict[str, Any]) -> tuple[str, str]:
    """Return (kind, recovered_text). kind is plain_text / html_recovered /
    snippet_only / missing."""
    text = str(payload.get("body_text") or "").strip()
    html = str(payload.get("body_html") or payload.get("html") or "").strip()
    snippet = str(payload.get("snippet") or "").strip()
    recovered = plain_email_body(payload)
    if text:
        return "plain_text", recovered or text
    if html and recovered:
        return "html_recovered", recovered
    if snippet and (not recovered or recovered == snippet):
        return "snippet_only", recovered or snippet
    if recovered:
        return "html_recovered", recovered
    return "missing", ""


def message_is_peggy_authored(payload: dict[str, Any], trusted: set[str]) -> bool:
    if payload.get("from_owner") is True:
        froms = {
            normalize_handle(str(r.get("normalized") or r.get("address") or ""))
            for r in (payload.get("from_parsed") or [])
            if isinstance(r, dict)
        }
        if not froms or (froms & trusted):
            return True
    for rec in payload.get("from_parsed") or []:
        if not isinstance(rec, dict):
            continue
        addr = normalize_handle(str(rec.get("normalized") or rec.get("address") or ""))
        if addr and addr in trusted:
            return True
    blob = str(payload.get("from") or payload.get("from_raw") or "")
    for match in re.finditer(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob
    ):
        if normalize_handle(match.group(0)) in trusted:
            return True
    return False


@dataclass
class LightRow:
    evidence_id: str
    sent_at: datetime | None
    thread_id: str
    rfc_message_id: str
    reply_ids: list[str]
    from_addrs: set[str]
    addresses: set[str]
    peggy_authored: bool
    subject: str
    skip: bool


@dataclass
class PreparedMessage:
    evidence_id: str
    sent_at: datetime | None
    in_interval: bool
    peggy_authored: bool
    body_kind: str
    authored: str
    quoted: str
    quote_kept: bool
    quote_uncertain: bool
    payload: dict[str, Any] = field(repr=False)
    cite_as: str = ""


def _mailbox_skip(payload: dict[str, Any]) -> bool:
    skip = str(payload.get("mailbox_skip") or payload.get("skip_reason") or "").strip().lower()
    if skip in {"spam", "trash"}:
        return True
    labels = payload.get("gmail_labels") or payload.get("labels") or []
    blob = " ".join(str(x).lower() for x in labels)
    return "spam" in blob or "trash" in blob


def inventory_trusted_email_light(
    *,
    trusted: set[str],
) -> list[LightRow]:
    """sent_at / thread keys only. Does not load HTML bodies."""
    from memorybox.db import connection

    addr_sql, addr_params = _sql_confirmed_email_addrs(trusted)
    if addr_sql == "FALSE":
        return []
    where = (
        "evidence_kind = 'communication' AND "
        "lower(coalesce(payload_json->>'evidence_channel', 'email')) "
        "NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs') AND "
        f"({addr_sql})"
    )
    rows: list[LightRow] = []
    last_id: Any = None
    with connection() as conn:
        while True:
            clause = where
            params = list(addr_params)
            if last_id is not None:
                clause = f"({where}) AND id > %s"
                params.append(last_id)
            fetched = conn.execute(
                f"""
                SELECT id,
                       payload_json->>'sent_at' AS sent_at,
                       payload_json->>'thread_id' AS thread_id,
                       coalesce(
                           payload_json->>'rfc_message_id',
                           payload_json->>'message_id',
                           ''
                       ) AS rfc_message_id,
                       payload_json->>'in_reply_to' AS in_reply_to,
                       payload_json->'in_reply_to_ids' AS in_reply_to_ids,
                       payload_json->>'references' AS refs,
                       payload_json->'from_parsed' AS from_parsed,
                       payload_json->>'from' AS from_header,
                       payload_json->'to_parsed' AS to_parsed,
                       payload_json->>'to' AS to_header,
                       payload_json->'cc_parsed' AS cc_parsed,
                       payload_json->>'cc' AS cc_header,
                       payload_json->>'subject' AS subject,
                       lower(coalesce(
                           payload_json->>'mailbox_skip',
                           payload_json->>'skip_reason',
                           ''
                       )) AS skip,
                       lower(coalesce(
                           payload_json->>'evidence_channel', 'email'
                       )) AS ch
                FROM evidence
                WHERE {clause}
                ORDER BY id
                LIMIT 2000
                """,
                params,
            ).fetchall()
            if not fetched:
                break
            for raw in fetched:
                last_id = raw["id"]
                if str(raw["ch"] or "email") != "email":
                    continue
                payload_lite = {
                    "from_parsed": raw["from_parsed"] or [],
                    "from": raw["from_header"],
                    "to_parsed": raw["to_parsed"] or [],
                    "to": raw["to_header"],
                    "cc_parsed": raw["cc_parsed"] or [],
                    "cc": raw["cc_header"],
                    "in_reply_to": raw["in_reply_to"],
                    "in_reply_to_ids": raw["in_reply_to_ids"] or [],
                    "references": raw["refs"],
                    "rfc_message_id": raw["rfc_message_id"],
                    "mailbox_skip": raw["skip"],
                }
                if str(raw["skip"] or "").strip() in {"spam", "trash"}:
                    continue
                reply_ids = _rfc_ids(
                    raw["in_reply_to"],
                    raw["in_reply_to_ids"],
                    raw["refs"],
                )
                rows.append(
                    LightRow(
                        evidence_id=str(raw["id"]),
                        sent_at=_parse_sent_at(raw["sent_at"]),
                        thread_id=str(raw["thread_id"] or "").strip(),
                        rfc_message_id=str(raw["rfc_message_id"] or "").strip(),
                        reply_ids=reply_ids,
                        from_addrs=_payload_email_addresses(
                            {
                                "from_parsed": payload_lite.get("from_parsed"),
                                "from": payload_lite.get("from"),
                            }
                        ),
                        addresses=_payload_email_addresses(payload_lite),
                        peggy_authored=message_is_peggy_authored(payload_lite, trusted),
                        subject=str(raw["subject"] or ""),
                        skip=False,
                    )
                )
            if len(fetched) < 2000:
                break
    return rows


def propose_five_year_interval(rows: list[LightRow]) -> dict[str, Any]:
    dated = [r for r in rows if r.sent_at is not None]
    if not dated:
        return {"ok": False, "error": "no_dated_trusted_email"}
    years = sorted({r.sent_at.year for r in dated if r.sent_at})
    lo, hi = years[0], years[-1]
    if hi - lo + 1 <= _FIVE_YEARS:
        start = datetime(lo, 1, 1, tzinfo=timezone.utc)
        end = datetime(hi, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        authored = sum(1 for r in dated if r.peggy_authored)
        rfc = sum(1 for r in dated if r.thread_id or r.reply_ids)
        return {
            "ok": True,
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "why": (
                f"Trusted archive only spans {lo}–{hi} ({hi - lo + 1} year"
                f"{'s' if hi != lo else ''}); using the complete dated span. "
                f"Peggy-authored={authored}; RFC-or-reply-linked={rfc}."
            ),
            "peggy_authored": authored,
            "rfc_or_reply_linked": rfc,
            "message_n": len(dated),
            "year_min": lo,
            "year_max": hi,
            "windows_considered": 1,
        }
    best: dict[str, Any] | None = None
    considered = 0
    for start_year in range(lo, hi - _FIVE_YEARS + 2):
        end_year = start_year + _FIVE_YEARS - 1
        win = [
            r
            for r in dated
            if r.sent_at and start_year <= r.sent_at.year <= end_year
        ]
        if not win:
            continue
        considered += 1
        authored = sum(1 for r in win if r.peggy_authored)
        rfc = sum(1 for r in win if r.thread_id or r.reply_ids)
        score = (authored, rfc, len(win))
        cand = {
            "ok": True,
            "start": f"{start_year:04d}-01-01",
            "end": f"{end_year:04d}-12-31",
            "peggy_authored": authored,
            "rfc_or_reply_linked": rfc,
            "message_n": len(win),
            "year_min": start_year,
            "year_max": end_year,
            "score": score,
        }
        if best is None or score > tuple(best["score"]):
            best = cand
    if best is None:
        return {"ok": False, "error": "no_window"}
    best["why"] = (
        f"Among {considered} contiguous {_FIVE_YEARS}-year windows in {lo}–{hi}, "
        f"{best['start'][:4]}–{best['end'][:4]} has the most Peggy-authored "
        f"trusted messages ({best['peggy_authored']}) and the most "
        f"RFC/reply-linked messages ({best['rfc_or_reply_linked']})."
    )
    best["windows_considered"] = considered
    best.pop("score", None)
    return best


def _confirmed_keys(row: LightRow) -> list[str]:
    keys: list[str] = []
    tid = row.thread_id
    if tid and tid != row.evidence_id:
        keys.append(f"tid:{tid}")
    if row.rfc_message_id:
        mid = row.rfc_message_id
        if not mid.startswith("<"):
            mid = f"<{mid}>" if "@" in mid else mid
        keys.append(f"rfc:{mid}")
    for rid in row.reply_ids:
        keys.append(f"rfc:{rid}")
    return keys


def _subject_key(row: LightRow) -> str | None:
    subj = re.sub(r"^(?:(?:re|fw|fwd)\s*:\s*)+", "", row.subject or "", flags=re.I)
    subj = re.sub(r"\s+", " ", subj).strip().lower()
    addrs = ",".join(sorted(a for a in (row.addresses or row.from_addrs) if a))
    if subj and addrs:
        return f"subj:{subj}|{addrs}"
    return None


class _UF:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def group_conversations(rows: list[LightRow]) -> list[dict[str, Any]]:
    """Confirmed RFC/thread groups vs uncertain subject/address fallback."""
    uf = _UF()
    key_to_ids: dict[str, list[str]] = defaultdict(list)
    by_id = {r.evidence_id: r for r in rows}
    for row in rows:
        uf.add(row.evidence_id)
        for key in _confirmed_keys(row):
            key_to_ids[key].append(row.evidence_id)
    for ids in key_to_ids.values():
        head = ids[0]
        for other in ids[1:]:
            uf.union(head, other)
    confirmed: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if _confirmed_keys(row) or uf.find(row.evidence_id) != row.evidence_id:
            confirmed[uf.find(row.evidence_id)].append(row.evidence_id)
        else:
            # singleton unless later attached; keep as ungrouped for now
            pass
    confirmed_ids = {i for ids in confirmed.values() for i in ids}
    # Attach isolated messages that share a confirmed key already unioned
    for row in rows:
        if row.evidence_id in confirmed_ids:
            continue
        keys = _confirmed_keys(row)
        if keys:
            confirmed[uf.find(row.evidence_id)].append(row.evidence_id)
            confirmed_ids.add(row.evidence_id)

    used = set(confirmed_ids)
    uncertain: dict[str, list[str]] = defaultdict(list)
    singletons: list[str] = []
    for row in rows:
        if row.evidence_id in used:
            continue
        skey = _subject_key(row)
        if skey:
            uncertain[skey].append(row.evidence_id)
        else:
            singletons.append(row.evidence_id)

    out: list[dict[str, Any]] = []
    for root, ids in confirmed.items():
        uniq = list(dict.fromkeys(ids))
        if not uniq:
            continue
        out.append(
            {
                "grouping": "confirmed",
                "grouping_detail": "rfc_thread_or_in_reply_to",
                "message_ids": uniq,
                "root": root,
            }
        )
    for skey, ids in uncertain.items():
        uniq = list(dict.fromkeys(ids))
        if len(uniq) == 1:
            out.append(
                {
                    "grouping": "singleton",
                    "grouping_detail": "no_reply_identifier",
                    "message_ids": uniq,
                    "root": uniq[0],
                }
            )
        else:
            out.append(
                {
                    "grouping": "uncertain",
                    "grouping_detail": "subject_and_addresses_only",
                    "message_ids": uniq,
                    "root": skey,
                }
            )
    for eid in singletons:
        out.append(
            {
                "grouping": "singleton",
                "grouping_detail": "no_reply_identifier",
                "message_ids": [eid],
                "root": eid,
            }
        )
    _ = by_id
    return out


def load_payloads(evidence_ids: list[str]) -> dict[str, dict[str, Any]]:
    from memorybox.db import connection
    from uuid import UUID

    out: dict[str, dict[str, Any]] = {}
    raw_ids: list[Any] = []
    for eid in evidence_ids:
        try:
            raw_ids.append(UUID(str(eid)))
        except (ValueError, TypeError):
            raw_ids.append(eid)
    if not raw_ids:
        return out
    with connection() as conn:
        for i in range(0, len(raw_ids), 400):
            chunk = raw_ids[i : i + 400]
            fetched = conn.execute(
                """
                SELECT id, payload_json
                FROM evidence
                WHERE id = ANY(%s)
                """,
                (chunk,),
            ).fetchall()
            for row in fetched:
                out[str(row["id"])] = _payload_dict(row["payload_json"])
    return out


def _prepare_message(
    evidence_id: str,
    payload: dict[str, Any],
    *,
    trusted: set[str],
    in_interval: bool,
    sibling_authored: list[str],
) -> PreparedMessage:
    kind, recovered = classify_body_source(payload)
    authored, flags = authored_email_text(recovered)
    turns = split_quoted_email(recovered)
    quoted_bits: list[str] = []
    for turn in turns[1:]:
        body = str((turn or {}).get("body") or "").strip()
        if len(body) < 20:
            continue
        if any(body in prior and body != prior for prior in sibling_authored if prior):
            continue
        quoted_bits.append(body)
    quoted = "\n\n".join(quoted_bits).strip()
    return PreparedMessage(
        evidence_id=evidence_id,
        sent_at=_parse_sent_at(payload.get("sent_at")),
        in_interval=in_interval,
        peggy_authored=message_is_peggy_authored(payload, trusted),
        body_kind=kind,
        authored=authored,
        quoted=quoted,
        quote_kept=bool(quoted),
        quote_uncertain=bool(flags.get("quote_uncertain") or quoted),
        payload=payload,
    )


def inspect_gemma_context(model: str = ESTABLISHED_GEMMA_MODEL) -> dict[str, Any]:
    apply_flightsim_app_env()
    from memorybox.config import OLLAMA_AUTODETECT_URLS, settings
    from memorybox.providers.llm._ollama_http import (
        ollama_context_length,
        ollama_has_model,
        ollama_reachable,
        ollama_show,
    )

    base = (settings.ollama_base_url or "").strip()
    if not base:
        for url in OLLAMA_AUTODETECT_URLS:
            if ollama_reachable(url):
                base = url
                break
    env_ctx = (os.environ.get("MEMORYBOX_FEV2_OLLAMA_NUM_CTX") or "").strip()
    info: dict[str, Any] = {
        "model": model,
        "ollama_base_url": base or None,
        "reachable": bool(base and ollama_reachable(base)),
        "has_model": False,
        "show_context_length": None,
        "env_num_ctx": int(env_ctx) if env_ctx.isdigit() else None,
        "configured_num_ctx": None,
        "configured_source": "unknown",
        "output_token_room": _OUTPUT_TOKEN_ROOM,
        "safety_token_room": _SAFETY_TOKEN_ROOM,
        "usable_input_tokens": None,
    }
    if not base:
        return info
    info["has_model"] = ollama_has_model(base, model)
    show = None
    if info["has_model"]:
        try:
            show = ollama_show(base, model)
        except Exception as exc:  # noqa: BLE001
            info["show_error"] = f"{type(exc).__name__}:{exc}"
    ctx = ollama_context_length(show)
    info["show_context_length"] = ctx
    if info["env_num_ctx"]:
        info["configured_num_ctx"] = info["env_num_ctx"]
        info["configured_source"] = "MEMORYBOX_FEV2_OLLAMA_NUM_CTX"
    elif ctx:
        info["configured_num_ctx"] = ctx
        info["configured_source"] = "ollama_show"
    if info["configured_num_ctx"]:
        info["usable_input_tokens"] = max(
            0,
            int(info["configured_num_ctx"])
            - _OUTPUT_TOKEN_ROOM
            - _SAFETY_TOKEN_ROOM,
        )
    return info


def measure_prompt_tokens(system: str, user: str, *, model: str) -> dict[str, Any]:
    combined = system + "\n\n" + user
    estimated = _estimate_tokens(combined)
    measured = None
    apply_flightsim_app_env()
    from memorybox.config import settings
    from memorybox.providers.llm._ollama_http import ollama_reachable, ollama_tokenize

    base = (settings.ollama_base_url or "").strip()
    if base and ollama_reachable(base):
        tokens = ollama_tokenize(base, model, combined)
        if tokens is not None:
            measured = len(tokens)
    return {
        "estimated_tokens_bytes_div_4": estimated,
        "measured_tokens_ollama_tokenize": measured,
        "measurement": "measured" if measured is not None else "estimate_only",
    }


def _in_interval(when: datetime | None, start: datetime, end: datetime) -> bool:
    if when is None:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return start <= when <= end


def render_model_paste(
    *,
    ask: str,
    person_name: str,
    trusted: set[str],
    interval: dict[str, Any],
    conversations: list[dict[str, Any]],
) -> tuple[str, str, list[dict[str, Any]]]:
    """Return system, user, and citation rows."""
    cites: list[dict[str, Any]] = []
    blocks: list[str] = []
    n = 0
    for conv in conversations:
        msgs: list[PreparedMessage] = list(conv["messages"])
        if not msgs:
            continue
        subject = _thread_subject(
            {"subject": (msgs[0].payload.get("subject") if msgs else "")}
        )
        grouping = conv["grouping"]
        label = {
            "confirmed": "confirmed reply sequence (RFC thread / In-Reply-To)",
            "uncertain": "uncertain grouping (subject + addresses only)",
            "singleton": "single message; no reply identifier",
        }.get(grouping, grouping)
        lines = [
            f"BEGIN CONVERSATION: {subject}",
            f"grouping: {label}",
        ]
        for msg in msgs:
            n += 1
            cite = f"email_{n}"
            msg.cite_as = cite
            speaker = _speaker_label(
                {
                    "from_parsed": msg.payload.get("from_parsed") or [],
                    "from": msg.payload.get("from") or msg.payload.get("from_raw"),
                },
                trusted=trusted,
                person_name=person_name,
            )
            when = _turn_when(msg.payload.get("sent_at"))
            loc = "in_interval" if msg.in_interval else "linked_context_outside_interval"
            if not msg.in_interval:
                lines.append(
                    f"{when}, {speaker} said: [{cite}]  "
                    f"(linked context; outside the candidate interval)"
                )
            else:
                lines.append(f"{when}, {speaker} said: [{cite}]")
            body = (msg.authored or "").strip() or "(no message text — body missing)"
            lines.append(body)
            if msg.quote_kept and msg.quoted:
                lines.append("")
                lines.append(
                    "[quoted/forwarded text kept; not present as another "
                    "turn in this conversation; source uncertain]"
                )
                lines.append(msg.quoted)
            lines.append("")
            cites.append(
                {
                    "cite_as": cite,
                    "evidence_id": msg.evidence_id,
                    "sent_at": str(msg.payload.get("sent_at") or ""),
                    "in_interval": msg.in_interval,
                    "location": loc,
                    "peggy_authored": msg.peggy_authored,
                    "body_kind": msg.body_kind,
                    "grouping": grouping,
                    "grouping_detail": conv.get("grouping_detail"),
                    "conversation_subject": subject,
                    "quote_kept": msg.quote_kept,
                }
            )
        lines.append("END CONVERSATION")
        blocks.append("\n".join(lines).rstrip())
    user = "\n".join(
        [
            f"ASK: {ask}",
            f"Person under review: {person_name}",
            f"Trusted mailbox: {', '.join(sorted(trusted))}",
            f"Candidate interval: {interval.get('start')} to {interval.get('end')}",
            "Linked context outside that interval is labeled on the turn.",
            "Cite a turn with the [email_N] tag on that speaker line.",
            "",
            "===== TRUSTED EMAIL CONVERSATIONS =====",
            "",
            *(blocks or ["(no qualifying Peggy-authored conversations in this interval)"]),
        ]
    ).rstrip() + "\n"
    return EMAIL_REVIEW_SYSTEM, user, cites


def _parse_interval_bounds(start: str, end: str) -> tuple[datetime, datetime]:
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    if s.tzinfo is None:
        s = s.replace(tzinfo=timezone.utc)
    if e.tzinfo is None:
        e = e.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    return s, e


def prepare_trusted_email_review(
    *,
    person_name: str,
    ask: str = "tell me what you know about this person",
    out_dir: Path | str | None = None,
    interval_start: str | None = None,
    interval_end: str | None = None,
) -> dict[str, Any]:
    """Inventory, propose/use a date window, write local review files. No models."""
    apply_flightsim_app_env()
    from memorybox.person import resolve_person_by_name

    out_root = Path(out_dir) if out_dir else _DEFAULT_OUT
    resolved = resolve_person_by_name(person_name, create_if_missing=False, confirm=False)
    pid = str(getattr(resolved, "person_id", "") or getattr(resolved, "id", "") or "")
    if not pid:
        return {"ok": False, "error": "person_not_found", "person_name": person_name}
    trusted = {normalize_handle(a) for a in trusted_emails_for_people({pid}) if a}
    if not trusted:
        return {"ok": False, "error": "no_trusted_retrieve_addresses", "person_id": pid}
    if person_name.strip().lower() == "peggy george" and "peggo417@hotmail.com" not in trusted:
        return {
            "ok": False,
            "error": "peggo417_not_trusted — do not re-attest from this command",
            "person_id": pid,
            "trusted_addresses": sorted(trusted),
        }

    light = inventory_trusted_email_light(trusted=trusted)
    inventory = {
        "trusted_message_n": len(light),
        "dated_n": sum(1 for r in light if r.sent_at),
        "peggy_authored_n": sum(1 for r in light if r.peggy_authored),
        "year_min": min((r.sent_at.year for r in light if r.sent_at), default=None),
        "year_max": max((r.sent_at.year for r in light if r.sent_at), default=None),
        "rfc_or_reply_n": sum(1 for r in light if r.thread_id or r.reply_ids),
    }
    proposed = propose_five_year_interval(light)
    if interval_start and interval_end:
        interval = {
            "ok": True,
            "start": interval_start,
            "end": interval_end,
            "why": "operator-supplied interval",
            "operator_override": True,
        }
    else:
        interval = proposed
    if not interval.get("ok"):
        return {
            "ok": False,
            "error": interval.get("error") or "interval_unavailable",
            "inventory": inventory,
            "proposed_interval": proposed,
        }

    start, end = _parse_interval_bounds(str(interval["start"]), str(interval["end"]))
    groups = group_conversations(light)
    in_window_ids = {
        r.evidence_id
        for r in light
        if _in_interval(r.sent_at, start, end)
    }
    primary_groups: list[dict[str, Any]] = []
    context_ids: set[str] = set()
    by_id = {r.evidence_id: r for r in light}
    for g in groups:
        ids = list(g["message_ids"])
        members = [by_id[i] for i in ids if i in by_id]
        if not any(m.peggy_authored for m in members):
            continue
        in_ids = [m.evidence_id for m in members if m.evidence_id in in_window_ids]
        if not in_ids:
            continue
        if not any(by_id[i].peggy_authored for i in in_ids):
            # Peggy-authored only in linked context — keep if confirmed chain
            if g["grouping"] != "confirmed":
                continue
        extra = []
        if g["grouping"] == "confirmed":
            extra = [m.evidence_id for m in members if m.evidence_id not in in_window_ids]
            context_ids.update(extra)
        primary_groups.append({**g, "in_interval_ids": in_ids, "context_ids": extra})

    need_ids = sorted(
        {i for g in primary_groups for i in (g["in_interval_ids"] + g["context_ids"])}
    )
    payloads = load_payloads(need_ids)

    conversations: list[dict[str, Any]] = []
    body_counts = {
        "plain_text": 0,
        "html_recovered": 0,
        "snippet_only": 0,
        "missing": 0,
    }
    for g in primary_groups:
        ordered_ids = sorted(
            g["in_interval_ids"] + g["context_ids"],
            key=lambda i: (
                str((payloads.get(i) or {}).get("sent_at") or ""),
                i,
            ),
        )
        sibling_authored: list[str] = []
        msgs: list[PreparedMessage] = []
        for eid in ordered_ids:
            payload = payloads.get(eid) or {}
            if _mailbox_skip(payload):
                continue
            msg = _prepare_message(
                eid,
                payload,
                trusted=trusted,
                in_interval=eid in in_window_ids,
                sibling_authored=sibling_authored,
            )
            if msg.authored:
                sibling_authored.append(msg.authored)
            body_counts[msg.body_kind] = int(body_counts.get(msg.body_kind) or 0) + 1
            msgs.append(msg)
        if not any(m.peggy_authored for m in msgs):
            continue
        conversations.append({**g, "messages": msgs})

    display = person_name
    system, user, cites = render_model_paste(
        ask=ask,
        person_name=display,
        trusted=trusted,
        interval=interval,
        conversations=conversations,
    )
    gemma = inspect_gemma_context()
    tokens = measure_prompt_tokens(system, user, model=ESTABLISHED_GEMMA_MODEL)
    estimated = int(tokens["estimated_tokens_bytes_div_4"])
    measured = tokens.get("measured_tokens_ollama_tokenize")
    prompt_tokens = int(measured if measured is not None else estimated)
    usable = gemma.get("usable_input_tokens")
    fits = None if usable is None else prompt_tokens <= int(usable)
    shorter = None
    if fits is False:
        shorter = _propose_shorter_interval(
            light, start, end, usable=int(usable or 0), estimated_full=estimated
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / f"REVIEW_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    paste_text = (
        "===== SYSTEM INSTRUCTIONS =====\n"
        + system
        + "\n\n===== USER QUESTION AND EVIDENCE =====\n"
        + user
    )
    digest = hashlib.sha256(paste_text.encode("utf-8")).hexdigest()
    if digest.startswith(_FORBIDDEN_FREEZE_PREFIX):
        return {"ok": False, "error": "hash_collision_forbidden_prefix"}

    (run_dir / "MODEL_PASTE.txt").write_text(paste_text, encoding="utf-8")
    source_map = {
        "person_name": person_name,
        "person_id": pid,
        "trusted_addresses": sorted(trusted),
        "interval": interval,
        "proposed_interval": proposed,
        "inventory": inventory,
        "citations": cites,
        "conversations": [
            {
                "grouping": c["grouping"],
                "grouping_detail": c.get("grouping_detail"),
                "in_interval_n": sum(1 for m in c["messages"] if m.in_interval),
                "linked_context_n": sum(1 for m in c["messages"] if not m.in_interval),
                "peggy_authored_n": sum(1 for m in c["messages"] if m.peggy_authored),
                "message_ids": [m.evidence_id for m in c["messages"]],
            }
            for c in conversations
        ],
        "forbidden_reuse": ["fe8a128c"],
        "source_commit": _git_commit(),
        "frozen_input_sha256": digest,
    }
    (run_dir / "SOURCE_MAP.json").write_text(
        json.dumps(source_map, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    in_interval_msgs = sum(1 for c in conversations for m in c["messages"] if m.in_interval)
    context_msgs = sum(1 for c in conversations for m in c["messages"] if not m.in_interval)
    peggy_n = sum(1 for c in conversations for m in c["messages"] if m.peggy_authored)
    report = "\n".join(
        [
            "TRUSTED EMAIL REVIEW — PREPARATION REPORT",
            "Models were not called.",
            f"source_commit: {_git_commit()}",
            f"person: {person_name} id={pid}",
            f"trusted_mailbox: {', '.join(sorted(trusted))}",
            f"inventory_trusted_messages: {inventory['trusted_message_n']} "
            f"dated={inventory['dated_n']} peggy_authored={inventory['peggy_authored_n']} "
            f"years={inventory['year_min']}-{inventory['year_max']}",
            f"proposed_interval: {proposed.get('start')} to {proposed.get('end')}",
            f"proposed_why: {proposed.get('why')}",
            f"used_interval: {interval.get('start')} to {interval.get('end')} "
            f"override={bool(interval.get('operator_override'))}",
            f"used_why: {interval.get('why')}",
            f"conversations: {len(conversations)} "
            f"(confirmed={sum(1 for c in conversations if c['grouping']=='confirmed')} "
            f"uncertain={sum(1 for c in conversations if c['grouping']=='uncertain')} "
            f"singleton={sum(1 for c in conversations if c['grouping']=='singleton')})",
            f"messages_in_interval: {in_interval_msgs}",
            f"linked_context_outside_interval: {context_msgs}",
            f"peggy_authored_in_pack: {peggy_n}",
            f"body_plain_text: {body_counts['plain_text']}",
            f"body_html_recovered: {body_counts['html_recovered']}",
            f"body_snippet_only: {body_counts['snippet_only']}",
            f"body_missing: {body_counts['missing']}",
            "body_marker_counts_are_not_recovery — see body_* fields.",
            f"no_200_cap: True  no_2500_truncate: True  no_token_budget_cut: True",
            f"estimated_tokens_bytes_div_4: {tokens['estimated_tokens_bytes_div_4']}",
            f"measured_tokens_ollama_tokenize: {tokens['measured_tokens_ollama_tokenize']}",
            f"token_measurement: {tokens['measurement']}",
            f"gemma_model: {gemma.get('model')}",
            f"gemma_reachable: {gemma.get('reachable')} has_model={gemma.get('has_model')}",
            f"gemma_configured_num_ctx: {gemma.get('configured_num_ctx')} "
            f"source={gemma.get('configured_source')}",
            f"gemma_show_context_length: {gemma.get('show_context_length')}",
            f"usable_input_tokens: {usable} "
            f"(ctx minus output {_OUTPUT_TOKEN_ROOM} and safety {_SAFETY_TOKEN_ROOM})",
            f"fits_configured_gemma: {fits}",
            f"shorter_interval_if_needed: {json.dumps(shorter, default=str) if shorter else ''}",
            f"frozen_input_sha256: {digest}",
            f"MODEL_PASTE: {run_dir / 'MODEL_PASTE.txt'}",
            f"SOURCE_MAP: {run_dir / 'SOURCE_MAP.json'}",
            f"PREPARATION_REPORT: {run_dir / 'PREPARATION_REPORT.txt'}",
            "Do not git-add MODEL_PASTE or SOURCE_MAP. Do not reuse fe8a128c.",
            "Do not run Gemma until Tom approves this interval and paste.",
        ]
    ) + "\n"
    (run_dir / "PREPARATION_REPORT.txt").write_text(report, encoding="utf-8")
    (run_dir / "LOCAL_MANIFEST.json").write_text(
        json.dumps(
            {
                "frozen_input_sha256": digest,
                "interval": interval,
                "model_paste": str(run_dir / "MODEL_PASTE.txt"),
                "source_commit": _git_commit(),
                "person_name": person_name,
                "ask": ask,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "models_called": False,
        "person_id": pid,
        "inventory": inventory,
        "proposed_interval": proposed,
        "interval": interval,
        "conversation_n": len(conversations),
        "messages_in_interval": in_interval_msgs,
        "linked_context_n": context_msgs,
        "body_counts": body_counts,
        "tokens": tokens,
        "gemma": gemma,
        "fits_configured_gemma": fits,
        "shorter_interval_if_needed": shorter,
        "frozen_input_sha256": digest,
        "run_dir": str(run_dir),
        "model_paste": str(run_dir / "MODEL_PASTE.txt"),
        "source_map": str(run_dir / "SOURCE_MAP.json"),
        "preparation_report": str(run_dir / "PREPARATION_REPORT.txt"),
        "preparation_report_text": report,
        "later_gemma_only": (
            "python -m memorybox run-trusted-email-review-gemma "
            f"--paste-dir {run_dir} --require-hash {digest}"
        ),
    }


def _propose_shorter_interval(
    rows: list[LightRow],
    start: datetime,
    end: datetime,
    *,
    usable: int,
    estimated_full: int,
) -> dict[str, Any]:
    """Longest contiguous year span from the same start that should fit.

    Estimate only — does not rewrite the paste.
    """
    if estimated_full <= 0:
        return {"ok": False, "error": "no_estimate"}
    dated = [
        r
        for r in rows
        if r.sent_at and start <= (r.sent_at.replace(tzinfo=r.sent_at.tzinfo or timezone.utc)) <= end
    ]
    years = sorted({r.sent_at.year for r in dated if r.sent_at})
    if not years:
        return {"ok": False, "error": "no_years"}
    ratio = usable / float(estimated_full)
    keep_n = max(1, int(len(dated) * ratio))
    dated.sort(key=lambda r: r.sent_at or datetime.min.replace(tzinfo=timezone.utc))
    kept = dated[:keep_n]
    if not kept or not kept[-1].sent_at:
        return {"ok": False, "error": "empty_shorter"}
    return {
        "ok": True,
        "start": start.date().isoformat(),
        "end": kept[-1].sent_at.date().isoformat(),
        "why": (
            "Estimate-only shorter contiguous interval from the same start "
            f"so ~{usable} usable Gemma tokens can hold the pack. "
            "Not applied. Tom must approve a new prepare run."
        ),
        "estimated_method": "proportional_message_cut_from_full_estimate",
    }


def run_trusted_email_review_gemma(
    *,
    paste_dir: Path | str,
    require_hash: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """Later-use Ollama/Gemma-only replay of an approved paste. No Sol. No refreeze."""
    apply_flightsim_app_env()
    path = Path(paste_dir)
    paste_path = path / "MODEL_PASTE.txt" if path.is_dir() else path
    if not paste_path.is_file():
        return {"ok": False, "error": "model_paste_missing", "path": str(paste_path)}
    text = paste_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    want = (require_hash or "").strip().lower()
    if not want or digest.lower() != want:
        return {
            "ok": False,
            "error": "hash_mismatch_or_missing — will not run Gemma on a different paste",
            "expected": want,
            "actual": digest,
        }
    if digest.startswith(_FORBIDDEN_FREEZE_PREFIX):
        return {"ok": False, "error": "forbidden_fe8a128c"}
    if "===== SYSTEM INSTRUCTIONS =====" not in text:
        return {"ok": False, "error": "paste_missing_system_marker"}
    _, rest = text.split("===== SYSTEM INSTRUCTIONS =====", 1)
    if "===== USER QUESTION AND EVIDENCE =====" not in rest:
        return {"ok": False, "error": "paste_missing_user_marker"}
    system, user = rest.split("===== USER QUESTION AND EVIDENCE =====", 1)
    system = system.strip()
    user = user.strip()
    from memorybox.config import OLLAMA_AUTODETECT_URLS, settings
    from memorybox.providers.llm._ollama_http import (
        ollama_chat,
        ollama_has_model,
        ollama_reachable,
    )

    base = (settings.ollama_base_url or "").strip()
    if not base:
        for url in OLLAMA_AUTODETECT_URLS:
            if ollama_reachable(url):
                base = url
                break
    model = ESTABLISHED_GEMMA_MODEL
    if not base or not ollama_has_model(base, model):
        return {
            "ok": False,
            "error": f"ollama_model_missing:{model}",
            "skipped": True,
            "provider": "ollama",
        }
    content, usage = ollama_chat(
        base,
        model,
        system,
        user,
        format_json=True,
        timeout=int(timeout_seconds),
    )
    return {
        "ok": True,
        "provider": "ollama",
        "model": model,
        "cloud": False,
        "pipeline": False,
        "chunking": False,
        "refreeze": False,
        "input_sha256": digest,
        "raw": content,
        "usage": usage,
    }
