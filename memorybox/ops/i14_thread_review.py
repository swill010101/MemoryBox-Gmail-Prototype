"""Canonical thread review packets vs Peggy-authored voice corpus.

Private TXT review trees are gitignored. This module never writes comms_* tables.
Authentication is address-ledger only (confirmed unique contact points). Display
names and nicknames (Peggy/Peggo/PegLeg) are labels after authentication, never
the authenticator.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import getaddresses
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from memorybox.person.phone_map import normalize_handle

REVIEW_TZ = ZoneInfo("America/Chicago")
PACKET_THREADS = 25
PEGGY_DISPLAY_HINTS = re.compile(r"\b(peggy|peggo|pegleg|peg\s*leg|peg)\b", re.I)

AUTH_PEGGY = "authenticated_peggy"
AUTH_OTHER = "authenticated_other"
UNVERIFIED = "unverified"

MARK_HELP = """
FOUNDER MARKS (write one line per thread in MARKS.txt)
  T-0001  accept_thread
  T-0001  split_here              (add message ref: T-0001-M-04)
  T-0001  merge_with_another      (add other thread: T-0012)
  T-0001  incorrect_participant
  T-0001  incorrect_ordering
  T-0001  quoted_text_removed_incorrectly
  T-0001  missing_message
  T-0001  needs_investigation
""".strip()

README_TEXT = """I14 Peggy visual thread review (private)

This folder is gitignored. It is not a production I14 write and is not Gallery.

Two products
  1. Canonical communication thread (this packet): every message in order,
     regardless of sender. This is what MemoryBox communications / Gallery
     context must preserve.
  2. Peggy-authored voice corpus: only messages whose From address is a
     confirmed unique contact for Peggy. Mail sent TO Peggy is not her voice.

Navigation
  INDEX.txt              one line per thread (searchable)
  packet-NNN.txt         about 25 canonical threads each; full prepared text
  originals/T-NNNN-M-NN.txt
                         immutable original for one message; open by Evidence-ref
  MARKS.txt              your marks (template in this README)

Open one original without the archive
  Each prepared message has Evidence-ref T-NNNN-M-NN.
  Open exactly originals/T-NNNN-M-NN.txt. Do not open other originals.

Do not commit this folder.
""".strip()

REQUIRED_PACKET_CASES = (
    "normal_two_person",
    "long_thread",
    "forwarded_message",
    "quoted_reply_stripping",
    "changed_subject",
    "attachment_indicators",
    "ambiguous_participant_identity",
    "likely_incorrect_split",
    "likely_incorrect_merge",
    "duplicate_across_extracts",
    "missing_or_malformed_message_id",
)


@dataclass
class IdentityLedger:
    focal_person_id: str
    address_to_person: dict[str, str] = field(default_factory=dict)
    person_label: dict[str, str] = field(default_factory=dict)
    ambiguous_addresses: set[str] = field(default_factory=set)

    def bind(self, address: str | None) -> dict[str, str]:
        addr = normalize_handle(address or "")
        if not addr or "@" not in addr:
            return {"status": UNVERIFIED, "person_id": "", "label": ""}
        if addr in self.ambiguous_addresses:
            return {"status": UNVERIFIED, "person_id": "", "label": ""}
        pid = self.address_to_person.get(addr)
        if not pid:
            return {"status": UNVERIFIED, "person_id": "", "label": ""}
        if pid == self.focal_person_id:
            return {"status": AUTH_PEGGY, "person_id": pid, "label": self.person_label.get(pid) or "Peggy"}
        return {
            "status": AUTH_OTHER,
            "person_id": pid,
            "label": self.person_label.get(pid) or "Person",
        }


def add_confirmed_address(ledger: IdentityLedger, *, address: str, person_id: str, label: str = "") -> None:
    addr = normalize_handle(address)
    pid = str(person_id or "").strip()
    if not addr or "@" not in addr or not pid:
        return
    existing = ledger.address_to_person.get(addr)
    if existing and existing != pid:
        ledger.address_to_person.pop(addr, None)
        ledger.ambiguous_addresses.add(addr)
        return
    if addr in ledger.ambiguous_addresses:
        return
    ledger.address_to_person[addr] = pid
    if label:
        ledger.person_label[pid] = label


def _parsed_parties(parsed: Any, header: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    if isinstance(parsed, list) and parsed:
        for item in parsed:
            if not isinstance(item, dict):
                continue
            addr = normalize_handle(str(item.get("normalized") or item.get("address") or ""))
            display = str(item.get("display_name") or "").strip()
            if not addr or "@" not in addr or addr in seen:
                continue
            seen.add(addr)
            out.append({"display": display, "address": addr})
        if out:
            return out
    texts: list[str] = []
    if isinstance(header, list):
        texts = [str(x) for x in header if str(x).strip()]
    elif header:
        texts = [str(header)]
    for name, addr in getaddresses(texts):
        norm = normalize_handle(addr or "")
        if not norm or "@" not in norm or norm in seen:
            continue
        seen.add(norm)
        out.append({"display": (name or "").strip(), "address": norm})
    return out


def extract_parties(payload: dict[str, Any] | None, msg: dict[str, Any] | None = None) -> dict[str, list[dict[str, str]]]:
    payload = payload or {}
    msg = msg or {}
    return {
        "from": _parsed_parties(payload.get("from_parsed") or msg.get("from_parsed"), payload.get("from") or msg.get("from")),
        "to": _parsed_parties(payload.get("to_parsed") or msg.get("to_parsed"), payload.get("to") or msg.get("to")),
        "cc": _parsed_parties(payload.get("cc_parsed") or msg.get("cc_parsed"), payload.get("cc") or msg.get("cc")),
        "bcc": _parsed_parties(payload.get("bcc_parsed") or msg.get("bcc_parsed"), payload.get("bcc") or msg.get("bcc")),
    }


def attachment_meta(payload: dict[str, Any] | None, msg: dict[str, Any] | None = None) -> list[dict[str, str]]:
    payload = payload or {}
    raw = payload.get("attachments") or (msg or {}).get("attachment_meta") or []
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("filename") or item.get("name") or "").strip()
        mime = str(item.get("mime_type") or item.get("content_type") or "").strip()
        if name or mime:
            out.append({"filename": name or "(unnamed)", "mime_type": mime or "unknown"})
    return out


def format_review_date(raw: str | None) -> str:
    text = str(raw or "").strip()
    if not text:
        return "unknown"
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return str(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(REVIEW_TZ)
    tzname = local.tzname() or "CT"
    return f"{local.strftime('%Y-%m-%d %H:%M:%S')} America/Chicago ({tzname})"


def _peggy_display_hint(display: str) -> bool:
    return bool(PEGGY_DISPLAY_HINTS.search(display or ""))


def classify_message(msg: dict[str, Any], ledger: IdentityLedger) -> dict[str, Any]:
    parties = extract_parties(msg.get("payload") if isinstance(msg.get("payload"), dict) else {}, msg)
    def _bind_list(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        bound: list[dict[str, Any]] = []
        for row in rows:
            auth = ledger.bind(row["address"])
            bound.append({**row, **auth})
        return bound

    from_b = _bind_list(parties["from"])
    to_b = _bind_list(parties["to"])
    cc_b = _bind_list(parties["cc"])
    bcc_b = _bind_list(parties["bcc"])
    sender = from_b[0] if from_b else {"status": UNVERIFIED, "address": "", "display": "", "person_id": "", "label": ""}
    authorship = sender["status"]
    if authorship == AUTH_PEGGY:
        authorship_label = "authenticated Peggy"
    elif authorship == AUTH_OTHER:
        authorship_label = f"authenticated other Person ({sender.get('label') or 'Person'})"
    else:
        authorship_label = "unverified"

    def _has(rows: list[dict[str, Any]], status: str) -> bool:
        return any(r.get("status") == status for r in rows)

    peggy_from = _has(from_b, AUTH_PEGGY)
    peggy_to = _has(to_b, AUTH_PEGGY) or _has(cc_b, AUTH_PEGGY) or _has(bcc_b, AUTH_PEGGY)
    recipients = to_b + cc_b + bcc_b
    unverified_sender = authorship == UNVERIFIED
    unverified_recipient = any(r.get("status") == UNVERIFIED for r in recipients)
    display_only = (not peggy_from) and _peggy_display_hint(str(sender.get("display") or ""))

    if peggy_from:
        direction = "sent_by_authenticated_peggy"
    elif peggy_to:
        direction = "sent_to_peggy_authored_other"
    elif from_b or to_b or cc_b or bcc_b:
        direction = "no_authenticated_peggy_participation"
    else:
        direction = "peggy_unresolved_direction"

    return {
        "from_parties": from_b,
        "to_parties": to_b,
        "cc_parties": cc_b,
        "bcc_parties": bcc_b,
        "authorship": authorship,
        "authorship_label": authorship_label,
        "voice_corpus": authorship == AUTH_PEGGY,
        "direction": direction,
        "unverified_sender": unverified_sender,
        "unverified_recipient": unverified_recipient,
        "display_name_only_peggy_rejected": display_only,
        "sent_by_authenticated_other": authorship == AUTH_OTHER,
        "ambiguous_participant": unverified_sender or unverified_recipient or (not from_b),
        "attachment_meta": attachment_meta(msg.get("payload") if isinstance(msg.get("payload"), dict) else {}, msg),
    }


def annotate_messages(messages: list[dict[str, Any]], ledger: IdentityLedger) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        tagged = dict(msg)
        tagged.update(classify_message(tagged, ledger))
        out.append(tagged)
    return out


def authorship_census(messages: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "sent_by_authenticated_peggy",
        "sent_to_peggy_authored_other",
        "peggy_unresolved_direction",
        "no_authenticated_peggy_participation",
        "sent_by_authenticated_other",
        "unverified_sender",
        "unverified_recipient",
        "display_name_only_peggy_rejected",
        "voice_corpus",
        "canonical_messages",
        "ambiguous_participant",
    )
    counts = {k: 0 for k in keys}
    counts["canonical_messages"] = len(messages)
    for msg in messages:
        direction = str(msg.get("direction") or "")
        if direction in counts:
            counts[direction] += 1
        if msg.get("sent_by_authenticated_other"):
            counts["sent_by_authenticated_other"] += 1
        if msg.get("unverified_sender"):
            counts["unverified_sender"] += 1
        if msg.get("unverified_recipient"):
            counts["unverified_recipient"] += 1
        if msg.get("display_name_only_peggy_rejected"):
            counts["display_name_only_peggy_rejected"] += 1
        if msg.get("voice_corpus"):
            counts["voice_corpus"] += 1
        if msg.get("ambiguous_participant"):
            counts["ambiguous_participant"] += 1
    return counts


def _format_party_line(rows: list[dict[str, Any]], *, empty: str = "(none)") -> str:
    if not rows:
        return empty
    bits: list[str] = []
    for row in rows:
        display = str(row.get("display") or "").strip() or row.get("address") or ""
        addr = str(row.get("address") or "")
        status = str(row.get("status") or UNVERIFIED)
        if status == AUTH_PEGGY:
            tag = "authenticated Peggy"
        elif status == AUTH_OTHER:
            tag = f"authenticated other Person ({row.get('label') or 'Person'})"
        else:
            tag = "unverified"
        bits.append(f"{display} <{addr}> [{tag}]")
    return "; ".join(bits)


def evidence_ref(thread_id: str, message_index: int) -> str:
    return f"{thread_id}-M-{message_index:02d}"


def format_thread_txt(thread: dict[str, Any]) -> str:
    tid = str(thread.get("preview_thread_id") or "T-0000")
    msgs = list(thread.get("messages") or [])
    dates = [format_review_date(m.get("timestamp")) for m in msgs]
    date_range = " .. ".join([dates[0], dates[-1]]) if dates else "unknown"
    participants: list[str] = []
    seen: set[str] = set()
    for msg in msgs:
        for row in (msg.get("from_parties") or []) + (msg.get("to_parties") or []) + (msg.get("cc_parties") or []):
            key = str(row.get("address") or "")
            if key and key not in seen:
                seen.add(key)
                participants.append(_format_party_line([row]))
    warnings = list(thread.get("warnings") or [])
    lines = [
        "=" * 78,
        f"BEGIN THREAD  {tid}",
        f"thread_review_id: {tid}",
        f"date_range: {date_range}",
        f"participants: {'; '.join(participants) if participants else '(none)'}",
        f"evidence_count: {thread.get('source_evidence_count', len(msgs))}",
        f"displayed_messages: {len(msgs)}",
        f"duplicates_omitted: {thread.get('duplicate_omitted', 0)}",
        f"excluded: {thread.get('excluded_in_thread', 0)}",
        f"threading_confidence: {thread.get('threading_confidence') or 'unknown'}",
        f"identity_confidence: {thread.get('identity_confidence') or 'unknown'}",
        f"warnings: {', '.join(warnings) if warnings else 'none'}",
        f"cases: {', '.join(thread.get('cases') or []) or 'none'}",
        f"voice_corpus_messages: {sum(1 for m in msgs if m.get('voice_corpus'))}",
        "-" * 78,
    ]
    for i, msg in enumerate(msgs, start=1):
        ref = evidence_ref(tid, i)
        atts = msg.get("attachment_meta") or []
        if atts:
            att_s = "; ".join(f"{a.get('filename')} ({a.get('mime_type')})" for a in atts)
        else:
            att_s = "none"
        cleaned = str(msg.get("cleaned_body") if msg.get("cleaned_body") is not None else msg.get("body") or "")
        lines.extend(
            [
                f"MESSAGE {i} of {len(msgs)}",
                f"From: {_format_party_line(msg.get('from_parties') or [])}",
                f"To: {_format_party_line(msg.get('to_parties') or [])}",
                f"Cc: {_format_party_line(msg.get('cc_parties') or [], empty='(none)')}",
                f"Date: {format_review_date(msg.get('timestamp'))}",
                f"Subject: {msg.get('subject') or '(none)'}",
                f"Authorship: {msg.get('authorship_label') or 'unverified'}",
                f"Voice corpus: {'yes' if msg.get('voice_corpus') else 'no'}",
                f"Attachments: {att_s}",
                f"Evidence-ref: {ref}",
                "Cleaned authored text:",
                cleaned if cleaned.strip() else "(empty)",
                "-" * 78,
            ]
        )
    lines.append(f"END THREAD  {tid}")
    lines.append("=" * 78)
    return "\n".join(lines) + "\n"


def index_line(thread: dict[str, Any]) -> str:
    tid = str(thread.get("preview_thread_id") or "T-0000")
    msgs = list(thread.get("messages") or [])
    start = str((msgs[0].get("timestamp") if msgs else "") or "")[:10]
    end = str((msgs[-1].get("timestamp") if msgs else "") or "")[:10]
    cases = ",".join(thread.get("cases") or []) or "none"
    warn = ",".join(thread.get("warnings") or []) or "none"
    ident = thread.get("identity_confidence") or "unknown"
    return (
        f"{tid} | {start}..{end} | msgs {len(msgs)} | ident {ident} | "
        f"voice {sum(1 for m in msgs if m.get('voice_corpus'))} | cases {cases} | warn {warn}"
    )


def thread_confidence(thread: dict[str, Any]) -> None:
    msgs = list(thread.get("messages") or [])
    statuses = {str(m.get("thread_status") or "") for m in msgs}
    if statuses == {"vendor+rfc"}:
        thread["threading_confidence"] = "vendor+rfc"
    elif "unthreaded" in statuses and len(msgs) > 1:
        thread["threading_confidence"] = "mixed_unthreaded"
    elif statuses == {"rfc"}:
        thread["threading_confidence"] = "rfc"
    elif statuses == {"vendor"}:
        thread["threading_confidence"] = "vendor"
    else:
        thread["threading_confidence"] = "+".join(sorted(s for s in statuses if s)) or "unknown"
    if any(m.get("ambiguous_participant") for m in msgs):
        thread["identity_confidence"] = "unverified_present"
    elif msgs and all(m.get("authorship") in {AUTH_PEGGY, AUTH_OTHER} for m in msgs):
        thread["identity_confidence"] = "all_authenticated"
    else:
        thread["identity_confidence"] = "mixed"


def packet_chunks(threads: list[dict[str, Any]], *, size: int = PACKET_THREADS) -> list[list[dict[str, Any]]]:
    if size < 1:
        size = PACKET_THREADS
    return [threads[i : i + size] for i in range(0, len(threads), size)]


def select_representative(threads: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    coverage: dict[str, str] = {}
    for case in REQUIRED_PACKET_CASES:
        hit = next((t for t in threads if case in (t.get("cases") or [])), None)
        if hit:
            tid = str(hit.get("preview_thread_id"))
            if tid not in seen:
                selected.append(hit)
                seen.add(tid)
            coverage[case] = tid
        else:
            coverage[case] = "not_present_in_corpus"
    return selected, coverage


def write_review_tree(pack: dict[str, Any], out_dir: Path, *, representative_only: bool = False) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    originals = out_dir / "originals"
    originals.mkdir(exist_ok=True)
    threads = list(pack.get("threads") or [])
    for thread in threads:
        thread_confidence(thread)
    if representative_only:
        chosen, coverage = select_representative(threads)
        chunks = [chosen] if chosen else [[]]
    else:
        coverage = {c: "full_corpus" for c in REQUIRED_PACKET_CASES}
        _, coverage_sel = select_representative(threads)
        coverage = coverage_sel
        chunks = packet_chunks(threads)
        chosen = threads
    (out_dir / "README.txt").write_text(README_TEXT + "\n\n" + MARK_HELP + "\n", encoding="utf-8")
    (out_dir / "MARKS.txt").write_text("# one mark per line: T-0001  accept_thread\n", encoding="utf-8")
    index_lines = [index_line(t) for t in (chosen if representative_only else threads)]
    (out_dir / "INDEX.txt").write_text("\n".join(index_lines) + ("\n" if index_lines else ""), encoding="utf-8")
    packet_files: list[str] = []
    for pi, chunk in enumerate(chunks, start=1):
        name = f"packet-{pi:03d}.txt"
        body = "\n".join(format_thread_txt(t) for t in chunk)
        (out_dir / name).write_text(body, encoding="utf-8")
        packet_files.append(name)
        for thread in chunk:
            tid = str(thread.get("preview_thread_id"))
            for i, msg in enumerate(thread.get("messages") or [], start=1):
                ref = evidence_ref(tid, i)
                original = "\n".join(
                    [
                        f"Evidence-ref: {ref}",
                        f"Date: {format_review_date(msg.get('timestamp'))}",
                        f"Subject: {msg.get('subject') or ''}",
                        f"From: {_format_party_line(msg.get('from_parties') or [])}",
                        f"To: {_format_party_line(msg.get('to_parties') or [])}",
                        f"Cc: {_format_party_line(msg.get('cc_parties') or [], empty='(none)')}",
                        "",
                        str(msg.get("raw_body") or msg.get("body") or ""),
                        "",
                    ]
                )
                (originals / f"{ref}.txt").write_text(original, encoding="utf-8")
    return {
        "packet_files": packet_files,
        "thread_count_written": len(chosen if representative_only else threads),
        "representative_coverage": coverage,
        "original_files": len(list(originals.glob("*.txt"))),
    }


def sanitized_layout_example() -> str:
    """Git-safe example using example.test addresses only."""
    ledger = IdentityLedger(focal_person_id="person-peggy")
    add_confirmed_address(ledger, address="peggy@example.test", person_id="person-peggy", label="Peggy Example")
    add_confirmed_address(ledger, address="alice@example.test", person_id="person-alice", label="Alice Example")
    msgs = annotate_messages(
        [
            {
                "timestamp": "2012-03-04T14:12:33+00:00",
                "subject": "Picnic",
                "from": "Alice Example <alice@example.test>",
                "to": ["Peggy Example <peggy@example.test>"],
                "from_parsed": [{"display_name": "Alice Example", "address": "alice@example.test", "normalized": "alice@example.test"}],
                "to_parsed": [{"display_name": "Peggy Example", "address": "peggy@example.test", "normalized": "peggy@example.test"}],
                "cleaned_body": "Can you bring lemonade?",
                "raw_body": "Can you bring lemonade?",
                "thread_status": "rfc",
                "attachment_meta": [],
            },
            {
                "timestamp": "2012-03-04T15:02:01+00:00",
                "subject": "Re: Picnic",
                "from": "Peggy Example <peggy@example.test>",
                "to": ["Alice Example <alice@example.test>"],
                "from_parsed": [{"display_name": "Peggy Example", "address": "peggy@example.test", "normalized": "peggy@example.test"}],
                "to_parsed": [{"display_name": "Alice Example", "address": "alice@example.test", "normalized": "alice@example.test"}],
                "cleaned_body": "Yes. I will bring lemonade.",
                "raw_body": "Yes. I will bring lemonade.",
                "thread_status": "rfc",
                "attachment_meta": [{"filename": "menu.txt", "mime_type": "text/plain"}],
            },
        ],
        ledger,
    )
    thread = {
        "preview_thread_id": "T-0001",
        "messages": msgs,
        "source_evidence_count": 2,
        "duplicate_omitted": 0,
        "excluded_in_thread": 0,
        "warnings": ["none"] if False else [],
        "cases": ["normal_two_person"],
    }
    thread_confidence(thread)
    return format_thread_txt(thread)
