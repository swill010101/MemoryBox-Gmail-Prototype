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
from memorybox.ops.i14_prepared_text import TRACKING_HINT

REVIEW_TZ = ZoneInfo("America/Chicago")
MISSING_TS = datetime.min.replace(tzinfo=timezone.utc)


def parse_sent_at(raw: str | None) -> datetime | None:
    """Authoritative message time: payload sent_at parsed to a UTC instant."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def message_sort_key(msg: dict[str, Any]) -> tuple[int, datetime, str]:
    """Chronological order: UTC instant, then evidence_id. Missing timestamps sort last."""
    dt = parse_sent_at(str(msg.get("timestamp") or ""))
    missing = 0 if dt is not None else 1
    return (missing, dt or MISSING_TS, str(msg.get("evidence_id") or ""))


def string_sort_key(msg: dict[str, Any]) -> tuple[str, str]:
    return (str(msg.get("timestamp") or ""), str(msg.get("evidence_id") or ""))
PACKET_THREADS = 25
MAX_PACKET_THREADS = 25
MAX_PACKET_BYTES = 1_500_000
MAX_ORIGINAL_BYTES = 200_000
MAX_LONG_THREAD_FOR_PACKET = 16
PEGGY_DISPLAY_HINTS = re.compile(r"\b(peggy|peggo|pegleg|peg\s*leg|peg)\b", re.I)
COMMERCIAL_RETAIN = re.compile(
    r"\b(itinerary|boarding\s*pass|e-?ticket|check-?in|"
    r"confirmation\s*(number|code|#)|booking\s*(ref|code|number)|"
    r"reservation\s*(number|#)|hotel|cruise|rental\s*car|"
    r"medical\s+appointment|concert|festival\s+admission|"
    r"flight\s+[A-Z]{1,3}\s?\d{2,4})\b",
    re.I,
)
STRONG_LIFE_EVIDENCE = re.compile(
    r"\b(boarding\s*pass|e-?ticket|confirmation\s*(number|code|#)|"
    r"booking\s*(ref|code|number)|reservation\s*(number|#)|"
    r"flight\s+[A-Z]{1,3}\s?\d{2,4})\b",
    re.I,
)
COMMERCIAL_SUPPRESS = re.compile(
    r"\b(unsubscribe|newsletter|promo(?:tion)?|% off|special offer|weekly\s+deals|"
    r"flash sale|coupon|rewards?\s+points|buy\s+points|rapid\s+rewards|"
    r"your\s+receipt|order\s+has\s+shipped|package\s+delivered|"
    r"password\s+reset|verify\s+your\s+email|privacy\s+policy|"
    r"terms\s+of\s+(?:carriage|service)|manage\s+(?:your\s+)?preferences|"
    r"policy\s+(?:change|update)s?)\b",
    re.I,
)
COMMERCIAL_UNCERTAIN = re.compile(
    r"\b(order\s+confirmation|invoice|statement|tracking\s+number|payment\s+received)\b",
    re.I,
)
SUPPRESS_HOST = re.compile(
    r"(mailchimp|sendgrid|constantcontact|cmail\d+|sparkpost|marketing\.|promo\.|"
    r"deals\.|news\.|info@noreply)",
    re.I,
)
IMAGE_EXT = re.compile(r"\.(jpe?g|png|gif|webp|heic|bmp|tiff?)$", re.I)
PDF_EXT = re.compile(r"\.pdf$", re.I)

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

README_TEXT = """I14 Phase B — Prepared Communications and Threads
Person Pilot {person_pilot} review packet (private, gitignored)

This is not migration 035 validation and not the I11A Peggy Narrative.
035 does not store threads. This packet prototypes the future prepared layer.

Open (one file at a time)
  1. Open README.txt (this file).
  2. Open INDEX.txt and search for a thread id (T-NNNN).
  3. Open packet-001.txt only. Do not open a second packet; there is only one.
  4. To see an immutable original, open exactly originals/<Evidence-ref>.txt
     for that message. Close it before opening another original.

Bounds
  At most 25 threads in packet-001.txt. Full corpus is not in this folder.
  If a file would exceed size limits it is not written (fail closed).

Two products
  Canonical thread: every message, every participant, chronological.
  Voice corpus: From address is a confirmed unique Pilot contact only.

Commercial labels (Gallery default only; archive unchanged)
  commercial_retain    life evidence (travel, medical, meaningful events)
  commercial_suppress  ads/newsletters/routine receipts — hide by default
  commercial_uncertain keep but do not auto-display until resolved

Marks: see MARKS.txt
Do not commit this folder.
""".strip()


MARK_LINE = re.compile(r"^(T-\d{4})\s+(\S+)")


def parse_marks(text: str) -> dict[str, Any]:
    """Counts-only parse of MARKS.txt. Does not copy private thread bodies."""
    lines = 0
    unique: dict[str, str] = {}
    mark_counts: dict[str, int] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = MARK_LINE.match(line)
        if not m:
            continue
        lines += 1
        tid, mark = m.group(1), m.group(2)
        unique[tid] = mark
        mark_counts[mark] = mark_counts.get(mark, 0) + 1
    return {
        "mark_lines": lines,
        "unique_threads": len(unique),
        "accept_unique": sum(1 for v in unique.values() if v == "accept_thread"),
        "duplicate_thread_lines": max(0, lines - len(unique)),
        "mark_counts": mark_counts,
        "thread_ids": sorted(unique),
    }


REQUIRED_PACKET_CASES = (
    "normal_two_person",
    "long_thread",
    "forwarded_message",
    "quoted_reply_stripping",
    "changed_subject",
    "attachment_indicators",
    "ambiguous_participant_identity",
    "multiple_participants",
    "peggy_voice",
    "to_peggy_other_author",
    "no_peggy_participation",
    "commercial_retain",
    "commercial_suppress",
    "commercial_uncertain",
    "boundary_candidate_split",
    "boundary_candidate_merge",
    "likely_incorrect_split",
    "likely_incorrect_merge",
    "duplicate_across_extracts",
    "missing_or_malformed_message_id",
)


class ReviewError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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
            return {
                "status": AUTH_PEGGY,
                "person_id": pid,
                "label": self.person_label.get(pid) or focal_short_name(self),
            }
        return {
            "status": AUTH_OTHER,
            "person_id": pid,
            "label": self.person_label.get(pid) or "Person",
        }


def focal_short_name(ledger: IdentityLedger) -> str:
    label = str(ledger.person_label.get(ledger.focal_person_id) or "").strip()
    if label:
        return label.split()[0]
    return "Pilot"


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


def gallery_attachment_action(filename: str, mime: str) -> str:
    blob = f"{filename} {mime}".lower()
    if IMAGE_EXT.search(filename) or mime.lower() in {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/heic",
        "image/bmp",
        "image/tiff",
    }:
        return "view_image"
    if PDF_EXT.search(filename) or "pdf" in mime.lower():
        return "open_pdf"
    if mime.startswith("text/") or filename.lower().endswith((".txt", ".doc", ".docx")):
        return "open_document"
    return "record_only"


def classify_commercial(msg: dict[str, Any]) -> dict[str, str]:
    subject = str(msg.get("subject") or "")
    authored = str(msg.get("cleaned_body") or msg.get("body") or "")
    forward = str(msg.get("forward_block") or "")
    raw = str(msg.get("raw_body") or "")
    from_addr = ""
    parties = msg.get("from_parties") or []
    if parties:
        from_addr = str(parties[0].get("address") or "")
    elif msg.get("from_handle"):
        from_addr = str(msg.get("from_handle"))
    host = from_addr.split("@")[-1] if "@" in from_addr else from_addr
    life_blob = f"{subject}\n{authored}"
    commercial_blob = f"{subject}\n{authored}\n{forward}\n{raw[:4000]}"
    strong_life = bool(STRONG_LIFE_EVIDENCE.search(life_blob) or STRONG_LIFE_EVIDENCE.search(forward) or STRONG_LIFE_EVIDENCE.search(raw))
    weak_life = bool(COMMERCIAL_RETAIN.search(life_blob) or COMMERCIAL_RETAIN.search(forward))
    suppress = bool(
        COMMERCIAL_SUPPRESS.search(commercial_blob)
        or SUPPRESS_HOST.search(from_addr)
        or SUPPRESS_HOST.search(host)
        or TRACKING_HINT.search(raw)
        or TRACKING_HINT.search(forward)
    )
    uncertain = bool(COMMERCIAL_UNCERTAIN.search(subject) or COMMERCIAL_UNCERTAIN.search(forward))
    if strong_life:
        label = "commercial_retain"
    elif suppress:
        label = "commercial_suppress"
    elif weak_life:
        label = "commercial_retain"
    elif uncertain:
        label = "commercial_uncertain"
    else:
        label = "not_commercial"
    return {
        "commercial_class": label,
        "from_host_class": "suppressed_host" if SUPPRESS_HOST.search(from_addr) else "ordinary",
    }


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


def _focal_display_hint(display: str, ledger: IdentityLedger) -> bool:
    label = str(ledger.person_label.get(ledger.focal_person_id) or "")
    if re.search(r"peggy", label, re.I) or not label.strip():
        return _peggy_display_hint(display)
    first = focal_short_name(ledger)
    if len(first) < 3:
        return False
    return bool(re.search(rf"\b{re.escape(first)}\b", display or "", re.I))


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
    focal = focal_short_name(ledger)
    if authorship == AUTH_PEGGY:
        authorship_label = f"authenticated {focal}"
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
    display_only = (not peggy_from) and _focal_display_hint(str(sender.get("display") or ""), ledger)

    if peggy_from:
        direction = "sent_by_authenticated_peggy"
    elif peggy_to:
        direction = "sent_to_peggy_authored_other"
    elif from_b or to_b or cc_b or bcc_b:
        direction = "no_authenticated_peggy_participation"
    else:
        direction = "peggy_unresolved_direction"

    ident = {
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
    ident.update(classify_commercial({**msg, **ident}))
    for att in ident["attachment_meta"]:
        att["gallery_action"] = gallery_attachment_action(str(att.get("filename") or ""), str(att.get("mime_type") or ""))
    return ident


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
        "commercial_retain",
        "commercial_suppress",
        "commercial_uncertain",
        "not_commercial",
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
        cclass = str(msg.get("commercial_class") or "not_commercial")
        if cclass in counts:
            counts[cclass] += 1
        else:
            counts["not_commercial"] += 1
    return counts


def prepared_policy_census(threads: list[dict[str, Any]]) -> dict[str, Any]:
    from memorybox.ops.i14_prepared_text import ON_WROTE, TRACKING_HINT, URL_RE, is_forward

    lex_mismatch_threads = 0
    display_mismatch_threads = 0
    reply_header_messages = 0
    reply_header_threads = 0
    relay_dup_messages = 0
    relay_dup_threads = 0
    forwarded_commercial_messages = 0
    forwarded_tracking_messages = 0
    original_and_forward_dup_messages = 0
    for thread in threads:
        msgs = list(thread.get("messages") or [])
        if not msgs:
            continue
        lex = [str(m.get("evidence_id")) for m in sorted(msgs, key=string_sort_key)]
        inst = [str(m.get("evidence_id")) for m in sorted(msgs, key=message_sort_key)]
        shown = [str(m.get("evidence_id")) for m in msgs]
        if lex != inst:
            lex_mismatch_threads += 1
        if shown != inst:
            display_mismatch_threads += 1
        header_hit = False
        dup_hit = False
        priors: list[str] = []
        for msg in msgs:
            cleaned = str(msg.get("cleaned_body") or "")
            raw = str(msg.get("raw_body") or msg.get("body") or "")
            fwd = str(msg.get("forward_block") or "")
            if ON_WROTE.search(cleaned) or ("wrote:" in cleaned.lower() and ON_WROTE.search("\n" + cleaned)):
                reply_header_messages += 1
                header_hit = True
            subj = str(msg.get("subject") or "")
            if is_forward(subject=subj, body=raw) or fwd:
                if str(msg.get("commercial_class") or "") in {
                    "commercial_suppress",
                    "commercial_retain",
                    "commercial_uncertain",
                }:
                    forwarded_commercial_messages += 1
                if URL_RE.search(raw) and TRACKING_HINT.search(raw):
                    forwarded_tracking_messages += 1
            if str(msg.get("forward_omitted") or "") == "duplicate_of_thread_message":
                original_and_forward_dup_messages += 1
                relay_dup_messages += 1
                dup_hit = True
            elif fwd and forward_overlap(fwd, priors):
                relay_dup_messages += 1
                dup_hit = True
            if cleaned:
                priors.append(cleaned)
            if raw:
                priors.append(raw)
        if header_hit:
            reply_header_threads += 1
        if dup_hit:
            relay_dup_threads += 1
    return {
        "lexicographic_iso_mismatch_threads": lex_mismatch_threads,
        "display_order_mismatch_threads": display_mismatch_threads,
        "reply_header_in_cleaned": {"messages": reply_header_messages, "threads": reply_header_threads},
        "relay_or_duplicate_forward": {"messages": relay_dup_messages, "threads": relay_dup_threads},
        "forwarded_commercial_messages": forwarded_commercial_messages,
        "forwarded_with_tracking_urls_messages": forwarded_tracking_messages,
        "original_and_forward_duplicate_messages": original_and_forward_dup_messages,
        "timestamp_rule": "payload_sent_at_utc_instant",
        "tie_break": "evidence_id",
    }


def forward_overlap(forward: str, priors: list[str]) -> bool:
    from memorybox.ops.i14_prepared_text import forward_duplicates_prior

    return forward_duplicates_prior(forward, priors)


def _format_party_line(rows: list[dict[str, Any]], *, empty: str = "(none)") -> str:
    if not rows:
        return empty
    bits: list[str] = []
    for row in rows:
        display = str(row.get("display") or "").strip() or row.get("address") or ""
        addr = str(row.get("address") or "")
        status = str(row.get("status") or UNVERIFIED)
        if status == AUTH_PEGGY:
            tag = f"authenticated {str(row.get('label') or 'Pilot').split()[0]}"
        elif status == AUTH_OTHER:
            tag = f"authenticated other Person ({row.get('label') or 'Person'})"
        else:
            tag = "unverified"
        bits.append(f"{display} <{addr}> [{tag}]")
    return "; ".join(bits)


def evidence_ref(thread_id: str, message_index: int) -> str:
    return f"{thread_id}-M-{message_index:02d}"


FOCAL_CASE_ALIAS = {
    "peggy_voice": "focal_voice",
    "to_peggy_other_author": "to_focal_other_author",
    "no_peggy_participation": "no_focal_participation",
}


def _display_cases(cases: list[str] | None, *, person_pilot: int = 1) -> list[str]:
    rows = list(cases or [])
    if int(person_pilot or 1) <= 1:
        return rows
    return [FOCAL_CASE_ALIAS.get(c, c) for c in rows]


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
    cases = _display_cases(list(thread.get("cases") or []), person_pilot=int(thread.get("person_pilot") or 1))
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
        f"cases: {', '.join(cases) or 'none'}",
        f"voice_corpus_messages: {sum(1 for m in msgs if m.get('voice_corpus'))}",
        f"commercial: {thread.get('commercial_summary') or 'mixed_or_none'}",
        "-" * 78,
    ]
    for i, msg in enumerate(msgs, start=1):
        ref = evidence_ref(tid, i)
        atts = msg.get("attachment_meta") or []
        if atts:
            att_s = "; ".join(
                f"{a.get('filename')} ({a.get('mime_type')}; {a.get('gallery_action') or 'record_only'}; linked, not copied)"
                for a in atts
            )
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
                f"Commercial: {msg.get('commercial_class') or 'not_commercial'}",
                f"Attachments: {att_s}",
                f"Evidence-ref: {ref}",
                "Cleaned authored text:",
                cleaned if cleaned.strip() else "(empty)",
            ]
        )
        if msg.get("forward_block"):
            lines.extend(
                [
                    "Forwarded content (explicit, not voice, not reply-history):",
                    str(msg.get("forward_block")),
                ]
            )
        elif msg.get("forward_omitted"):
            lines.append(
                "Forwarded content omitted from prepared text "
                f"({msg.get('forward_omitted')}; immutable original via Evidence-ref)."
            )
        lines.append("-" * 78)
    lines.append(f"END THREAD  {tid}")
    lines.append("=" * 78)
    return "\n".join(lines) + "\n"


def index_line(thread: dict[str, Any]) -> str:
    tid = str(thread.get("preview_thread_id") or "T-0000")
    msgs = list(thread.get("messages") or [])
    start = str((msgs[0].get("timestamp") if msgs else "") or "")[:10]
    end = str((msgs[-1].get("timestamp") if msgs else "") or "")[:10]
    cases = ",".join(_display_cases(list(thread.get("cases") or []), person_pilot=int(thread.get("person_pilot") or 1))) or "none"
    warn = ",".join(thread.get("warnings") or []) or "none"
    ident = thread.get("identity_confidence") or "unknown"
    return (
        f"{tid} | {start}..{end} | msgs {len(msgs)} | ident {ident} | "
        f"voice {sum(1 for m in msgs if m.get('voice_corpus'))} | "
        f"comm {thread.get('commercial_summary') or '-'} | cases {cases} | warn {warn}"
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


def _subject_stem(subject: str) -> str:
    return re.sub(r"^\s*((re|fwd?|fw)\s*:)+\s*", "", (subject or "").strip().lower())


def enrich_thread_cases(threads: list[dict[str, Any]]) -> None:
    stems: dict[str, list[str]] = {}
    for thread in threads:
        msgs = list(thread.get("messages") or [])
        addrs: set[str] = set()
        commercials: set[str] = set()
        for msg in msgs:
            for row in (msg.get("from_parties") or []) + (msg.get("to_parties") or []) + (msg.get("cc_parties") or []):
                if row.get("address"):
                    addrs.add(str(row["address"]))
            commercials.add(str(msg.get("commercial_class") or "not_commercial"))
        cases = list(thread.get("cases") or [])
        if len(addrs) >= 3:
            cases.append("multiple_participants")
        if any(m.get("voice_corpus") for m in msgs):
            cases.append("peggy_voice")
        if any(m.get("direction") == "sent_to_peggy_authored_other" for m in msgs):
            cases.append("to_peggy_other_author")
        if any(m.get("direction") == "no_authenticated_peggy_participation" for m in msgs):
            cases.append("no_peggy_participation")
        for label in ("commercial_retain", "commercial_suppress", "commercial_uncertain"):
            if label in commercials:
                cases.append(label)
        gaps = False
        prev = None
        for msg in msgs:
            ts = str(msg.get("timestamp") or "")
            if prev and ts and ts[:10] and prev[:10]:
                try:
                    d0 = datetime.fromisoformat(prev.replace("Z", "+00:00")[:19])
                    d1 = datetime.fromisoformat(ts.replace("Z", "+00:00")[:19])
                    if abs((d1 - d0).days) >= 14:
                        gaps = True
                except ValueError:
                    pass
            prev = ts
        if gaps:
            cases.append("boundary_candidate_merge")
            thread.setdefault("warnings", []).append("boundary_candidate_merge")
        stem = _subject_stem(str((msgs[0].get("subject") if msgs else "") or ""))
        if stem:
            stems.setdefault(stem, []).append(str(thread.get("preview_thread_id")))
        life = [c for c in commercials if c != "not_commercial"]
        if len(life) == 1:
            thread["commercial_summary"] = next(iter(life))
        elif life:
            thread["commercial_summary"] = "mixed"
        else:
            thread["commercial_summary"] = "not_commercial"
        thread["cases"] = list(dict.fromkeys(cases))
    for stem, ids in stems.items():
        if len(ids) < 2:
            continue
        for thread in threads:
            if thread.get("preview_thread_id") in ids:
                cases = list(thread.get("cases") or [])
                cases.append("boundary_candidate_split")
                thread["cases"] = list(dict.fromkeys(cases))
                warns = list(thread.get("warnings") or [])
                warns.append("boundary_candidate_split")
                thread["warnings"] = list(dict.fromkeys(warns))


def _prefer_small(threads: list[dict[str, Any]], case: str) -> dict[str, Any] | None:
    hits = [t for t in threads if case in (t.get("cases") or [])]
    if not hits:
        return None
    if case == "long_thread":
        bounded = [t for t in hits if 8 <= len(t.get("messages") or []) <= MAX_LONG_THREAD_FOR_PACKET]
        hits = bounded or hits
    return sorted(hits, key=lambda t: (len(t.get("messages") or []), str(t.get("preview_thread_id"))))[0]


def select_founder_packet(threads: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    coverage: dict[str, str] = {}
    for case in REQUIRED_PACKET_CASES:
        hit = _prefer_small(threads, case)
        if not hit:
            coverage[case] = "not_present_in_corpus"
            continue
        tid = str(hit.get("preview_thread_id"))
        coverage[case] = tid
        if tid not in seen:
            if len(selected) >= MAX_PACKET_THREADS:
                coverage[case] = "omitted_packet_thread_limit"
                continue
            selected.append(hit)
            seen.add(tid)
    return selected, coverage


def packet_chunks(threads: list[dict[str, Any]], *, size: int = PACKET_THREADS) -> list[list[dict[str, Any]]]:
    if size < 1:
        size = PACKET_THREADS
    return [threads[i : i + size] for i in range(0, len(threads), size)]


def select_representative(threads: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    return select_founder_packet(threads)


def _original_text(thread: dict[str, Any], msg: dict[str, Any], index: int) -> str:
    tid = str(thread.get("preview_thread_id"))
    ref = evidence_ref(tid, index)
    body = str(msg.get("raw_body") or msg.get("body") or "")
    header = "\n".join(
        [
            f"Evidence-ref: {ref}",
            f"Date: {format_review_date(msg.get('timestamp'))}",
            f"Subject: {msg.get('subject') or ''}",
            f"From: {_format_party_line(msg.get('from_parties') or [])}",
            f"To: {_format_party_line(msg.get('to_parties') or [])}",
            f"Cc: {_format_party_line(msg.get('cc_parties') or [], empty='(none)')}",
            "",
        ]
    )
    raw = header + body + "\n"
    encoded = raw.encode("utf-8")
    if len(encoded) > MAX_ORIGINAL_BYTES:
        raise ReviewError("original_exceeds_limit")
    return raw


def write_review_tree(
    pack: dict[str, Any],
    out_dir: Path,
    *,
    representative_only: bool = False,
    founder_packet: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    originals = out_dir / "originals"
    originals.mkdir(exist_ok=True)
    threads = list(pack.get("threads") or [])
    person_pilot = int(pack.get("person_pilot") or 1)
    for thread in threads:
        thread["person_pilot"] = person_pilot
        thread_confidence(thread)
    enrich_thread_cases(threads)
    if founder_packet or representative_only:
        chosen, coverage = select_founder_packet(threads)
    else:
        if len(threads) > MAX_PACKET_THREADS:
            raise ReviewError("full_corpus_emit_refused")
        chosen = threads
        coverage = {c: "small_set" for c in REQUIRED_PACKET_CASES}
    if len(chosen) > MAX_PACKET_THREADS:
        raise ReviewError("packet_thread_limit")
    bodies = [format_thread_txt(t) for t in chosen]
    packet = "\n".join(bodies)
    packet_bytes = len(packet.encode("utf-8"))
    while packet_bytes > MAX_PACKET_BYTES and len(chosen) > 1:
        dropped = chosen.pop()
        coverage["dropped_for_size"] = str(dropped.get("preview_thread_id"))
        packet = "\n".join(format_thread_txt(t) for t in chosen)
        packet_bytes = len(packet.encode("utf-8"))
    if packet_bytes > MAX_PACKET_BYTES:
        raise ReviewError("packet_exceeds_limit")
    for extra in out_dir.glob("packet-*.txt"):
        extra.unlink()
    (out_dir / "README.txt").write_text(
        README_TEXT.format(person_pilot=int(pack.get("person_pilot") or 1)) + "\n\n" + MARK_HELP + "\n",
        encoding="utf-8",
    )
    marks_path = out_dir / "MARKS.txt"
    prior_marks = marks_path.read_text(encoding="utf-8") if marks_path.exists() else ""
    if not re.search(r"^T-\d{4}\b", prior_marks, re.M):
        marks_path.write_text("# one mark per line: T-0001  accept_thread\n", encoding="utf-8")
    index_lines = [index_line(t) for t in chosen]
    (out_dir / "INDEX.txt").write_text("\n".join(index_lines) + ("\n" if index_lines else ""), encoding="utf-8")
    (out_dir / "packet-001.txt").write_text(packet, encoding="utf-8")
    original_sizes: list[int] = []
    for thread in chosen:
        tid = str(thread.get("preview_thread_id"))
        for i, msg in enumerate(thread.get("messages") or [], start=1):
            text = _original_text(thread, msg, i)
            path = originals / f"{evidence_ref(tid, i)}.txt"
            path.write_text(text, encoding="utf-8")
            original_sizes.append(path.stat().st_size)
    sizes = {
        "packet_bytes": (out_dir / "packet-001.txt").stat().st_size,
        "index_bytes": (out_dir / "INDEX.txt").stat().st_size,
        "readme_bytes": (out_dir / "README.txt").stat().st_size,
        "original_files": len(original_sizes),
        "original_bytes_total": int(sum(original_sizes)),
        "original_bytes_max": int(max(original_sizes) if original_sizes else 0),
        "thread_count_written": len(chosen),
        "message_count_written": int(sum(len(t.get("messages") or []) for t in chosen)),
        "packet_files": 1,
        "limits": {
            "max_threads": MAX_PACKET_THREADS,
            "max_packet_bytes": MAX_PACKET_BYTES,
            "max_original_bytes": MAX_ORIGINAL_BYTES,
        },
    }
    return {
        "packet_files": ["packet-001.txt"],
        "thread_count_written": len(chosen),
        "representative_coverage": coverage,
        "original_files": len(original_sizes),
        "sizes": sizes,
        "load_contract": "open INDEX then packet-001.txt; open one originals/Evidence-ref.txt at a time",
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
