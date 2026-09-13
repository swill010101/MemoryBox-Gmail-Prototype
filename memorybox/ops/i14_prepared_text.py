"""I14 prepared authored-text cleaner.

Owns quote-history removal for Prepared Communications. Immutable evidence is
never modified. I11A Ask must not re-run this pass later; it consumes the
prepared authored field.

Hotmail/Outlook.com often inlines the previous message after:

    Date: Thu, 29 Sep 2011 10:01:58 -0500
    Subject: Stuff
    From: user@example.test
    To: other@example.test

That block is reply history, not new authorship. Gmail ``On … wrote:`` and
``-----Original Message-----`` are the same class. Deliberate forwards are
labeled and kept separately, not treated as ordinary reply history.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SIG_LINE = re.compile(
    r"(?m)^(--)[ \t]*$|^Sent from my iPhone.*$|^Get Outlook for.*$|"
    r"^Sent from my (?:Galaxy|Android).*|^Get.*for iOS.*$",
    re.I,
)
LIST_FOOTER = re.compile(
    r"(?is)\n(?:-- \n.{0,400}|To unsubscribe\b.{0,400})\s*\Z",
)
GT_QUOTE = re.compile(r"(?m)^>+.*$")
ON_WROTE = re.compile(r"(?is)(?:^|\n)\s*On .{8,500}?\bwrote:\s*")
ORIGINAL_MSG = re.compile(r"(?im)^\s*-{5,}Original Message-{5,}\s*$")
OUTLOOK_FROM_SENT = re.compile(
    r"(?im)^\s*From:\s+.+\nSent:\s+.+\n(?:To:\s+.+\n)?(?:Cc:\s+.+\n)?(?:Subject:\s+.+\n)?"
)
HOTMAIL_DATE_BLOCK = re.compile(
    r"(?im)^\s*Date:\s+.+\n"
    r"(?:\s*\n)?"
    r"\s*Subject:\s+.+\n"
    r"(?:\s*\n)?"
    r"\s*From:\s+.+\n"
    r"(?:\s*\n)?"
    r"\s*To:\s+.+"
)
FWD_MARK = re.compile(
    r"(?im)^\s*(?:Begin forwarded message:|-{3,}\s*Forwarded (?:Message|message)\s*-{3,})\s*$"
)
FWD_SUBJ = re.compile(r"^\s*(fwd?|fw)\s*:", re.I)
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\]\"']+")
TRACKING_HINT = re.compile(
    r"(?i)utm_|unsubscribe|prefcenter|prefcentre|click\.|smetrics|"
    r"view(?: this)? email in (?:your )?browser|manage (?:your )?preferences|"
    r"privacy policy|terms (?:of|and) (?:use|service|carriage)|all rights reserved"
)
MARKETING_TAIL = re.compile(
    r"(?is)\n(?:to unsubscribe|unsubscribe|manage (?:your )?preferences|"
    r"privacy policy|this email was sent to|©|&copy;|all rights reserved).*\Z"
)
RESIDUE_HOTMAIL = HOTMAIL_DATE_BLOCK
RESIDUE_ON_WROTE = ON_WROTE
RESIDUE_ORIGINAL = ORIGINAL_MSG
RESIDUE_OUTLOOK = re.compile(r"(?im)^\s*From:\s+.+\nSent:\s+")


@dataclass
class PreparedText:
    authored: str
    forward_block: str
    method: str
    quote_history_removed: bool
    signature_removed: bool
    list_footer_removed: bool
    residue_class: str | None
    urls_stripped: bool = False
    forward_omitted: str = ""


def is_forward(*, subject: str, body: str) -> bool:
    """True only for an explicit forward marker, not a Fwd: subject with reply history."""
    return bool(FWD_MARK.search(body or ""))


def is_fwd_subject(subject: str) -> bool:
    return bool(FWD_SUBJ.match(subject or ""))


def sanitize_prepared(text: str) -> tuple[str, bool]:
    """Drop live URLs and trailing marketing/legal chrome from prepared text only."""
    raw = text or ""
    cut = URL_RE.sub("", raw)
    cut = MARKETING_TAIL.sub("", cut)
    urls = cut != raw
    compact = re.sub(r"\n{3,}", "\n\n", cut).strip()
    return compact, urls


def _norm_blob(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def forward_duplicates_prior(forward: str, priors: list[str]) -> bool:
    """True when the forwarded body is already represented as a prior thread message."""
    blob = _norm_blob(forward)
    if len(blob) < 80:
        return False
    for prior in priors:
        other = _norm_blob(prior)
        if len(other) < 80:
            continue
        if blob == other:
            return True
        shorter, longer = (blob, other) if len(blob) <= len(other) else (other, blob)
        if shorter in longer and len(shorter) >= 80:
            return True
    return False


def _first_match(
    text: str,
    specs: list[tuple[str, re.Pattern[str]]],
) -> tuple[re.Match[str] | None, str]:
    found: tuple[re.Match[str] | None, str] = (None, "")
    pos = len(text) + 1
    for name, pat in specs:
        m = pat.search(text)
        if m and m.start() < pos:
            pos = m.start()
            found = (m, name)
    return found


REPLY_SPECS: list[tuple[str, re.Pattern[str]]] = [
    ("hotmail_date_subject_from_to", HOTMAIL_DATE_BLOCK),
    ("on_wrote", ON_WROTE),
    ("original_message", ORIGINAL_MSG),
    ("outlook_from_sent", OUTLOOK_FROM_SENT),
]


def _inline_unquoted(text: str) -> str:
    """Keep authored islands between '>' quote lines; drop quote-only lines."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    saw_quote = False
    buffer: list[str] = []

    def flush() -> None:
        blob = "\n".join(buffer).strip()
        if blob:
            kept.append(blob)
        buffer.clear()

    for line in lines:
        if line.startswith(">"):
            saw_quote = True
            flush()
            continue
        buffer.append(line)
    flush()
    if not saw_quote:
        return text.strip()
    return "\n\n".join(kept).strip()


def _strip_sig_and_list(text: str) -> tuple[str, bool, bool]:
    body = text
    list_removed = False
    cut = LIST_FOOTER.sub("", body)
    if cut != body:
        list_removed = True
        body = cut.strip()
    stripped = SIG_LINE.sub("", body).strip()
    sig_removed = stripped != body.strip()
    return stripped, sig_removed, list_removed


def _remove_prior_blob(authored: str, prior: str) -> str:
    blob = (prior or "").strip()
    if len(blob) < 40:
        return authored
    if blob in authored and blob != authored.strip():
        return authored.replace(blob, "", 1).strip()
    pattern = re.compile(re.sub(r"\s+", r"\\s+", re.escape(blob)), re.I)
    if not pattern.search(authored):
        return authored
    cut = pattern.sub("", authored, count=1).strip()
    return cut if cut else authored


def _cut_reply_history(text: str) -> tuple[str, str, bool]:
    """Return (authored, method, removed). Forward markers are not reply cuts."""
    raw = (text or "").replace("\r\n", "\n")
    m, name = _first_match(raw, REPLY_SPECS)
    if not m:
        inline = _inline_unquoted(raw)
        removed = inline != raw.strip() and bool(GT_QUOTE.search(raw))
        return inline, ("gt_quote_inline" if removed else "none"), removed
    before = raw[: m.start()].rstrip()
    after = raw[m.end() :].lstrip("\n")
    if before.strip():
        authored = _inline_unquoted(before)
        return authored.strip(), name, True
    authored = _inline_unquoted(after)
    return authored.strip(), f"{name}_after_marker", True


def prepare_message_text(
    raw: str,
    *,
    subject: str = "",
    prior_authored: list[str] | None = None,
) -> PreparedText:
    original = raw or ""
    body = original.replace("\r\n", "\n")
    forward = ""
    method = "none"
    quote_removed = False
    forward_omitted = ""
    urls_stripped = False
    explicit = is_forward(subject=subject, body=body)
    if explicit:
        fm = FWD_MARK.search(body)
        authored = body[: fm.start()].strip() if fm else ""
        forward = body[fm.end() :].strip() if fm else body.strip()
        method = "explicit_forward"
        cut, cut_name, rem = _cut_reply_history(authored)
        if rem:
            authored = cut
            quote_removed = True
            method = f"explicit_forward_{cut_name}"
        if forward_duplicates_prior(forward, prior_authored or []):
            forward = ""
            forward_omitted = "duplicate_of_thread_message"
            method = "explicit_forward_duplicate_omitted"
            quote_removed = True
        else:
            quote_removed = False
    else:
        authored, method, quote_removed = _cut_reply_history(body)
        while authored:
            nxt, name, rem = _cut_reply_history(authored)
            if not rem or nxt == authored:
                break
            authored = nxt
            quote_removed = True
            method = name

    for prior in prior_authored or []:
        next_authored = _remove_prior_blob(authored, prior)
        if next_authored != authored:
            authored = next_authored
            quote_removed = True
            if method == "none":
                method = "prior_thread_body"
        if forward:
            trimmed = _remove_prior_blob(forward, prior)
            if trimmed != forward:
                forward = trimmed
                quote_removed = True
                if not forward.strip():
                    forward_omitted = forward_omitted or "duplicate_of_thread_message"

    authored, sig_removed, list_removed = _strip_sig_and_list(authored)
    authored, url_a = sanitize_prepared(authored)
    if forward:
        forward, url_f = sanitize_prepared(forward)
        urls_stripped = url_a or url_f
    else:
        urls_stripped = url_a
    residue = classify_residue(authored)
    return PreparedText(
        authored=authored,
        forward_block=forward,
        method=method,
        quote_history_removed=quote_removed,
        signature_removed=sig_removed,
        list_footer_removed=list_removed,
        residue_class=residue,
        urls_stripped=urls_stripped,
        forward_omitted=forward_omitted,
    )


def classify_residue(cleaned: str) -> str | None:
    text = cleaned or ""
    if RESIDUE_HOTMAIL.search(text):
        return "hotmail_date_subject_from_to"
    if RESIDUE_ON_WROTE.search(text):
        return "on_wrote"
    if RESIDUE_ORIGINAL.search(text):
        return "original_message"
    if RESIDUE_OUTLOOK.search(text):
        return "outlook_from_sent"
    return None


def _empty_class_counts() -> dict[str, dict[str, int]]:
    keys = (
        "hotmail_date_subject_from_to",
        "on_wrote",
        "original_message",
        "outlook_from_sent",
        "gt_quote",
        "explicit_forward_marker",
        "any_quote_or_forward_marker",
    )
    return {k: {"messages": 0, "threads": 0} for k in keys}


def raw_marker_classes(raw: str) -> list[str]:
    text = raw or ""
    found: list[str] = []
    if HOTMAIL_DATE_BLOCK.search(text):
        found.append("hotmail_date_subject_from_to")
    if ON_WROTE.search(text):
        found.append("on_wrote")
    if ORIGINAL_MSG.search(text):
        found.append("original_message")
    if OUTLOOK_FROM_SENT.search(text):
        found.append("outlook_from_sent")
    if GT_QUOTE.search(text):
        found.append("gt_quote")
    if FWD_MARK.search(text):
        found.append("explicit_forward_marker")
    return found


def _tally_classes(messages: list[dict], classes_for: callable) -> dict[str, dict[str, int]]:
    classes = _empty_class_counts()
    any_key = "any_quote_or_forward_marker"
    threads_by: dict[str, set[str]] = {k: set() for k in classes}
    for msg in messages:
        tid = str(msg.get("preview_thread_id") or msg.get("thread_id") or "")
        hits = classes_for(msg)
        if not hits:
            continue
        seen: set[str] = set()
        for klass in hits:
            if klass not in classes:
                continue
            classes[klass]["messages"] += 1
            threads_by[klass].add(tid)
            seen.add(klass)
        if seen:
            classes[any_key]["messages"] += 1
            threads_by[any_key].add(tid)
    for key, ids in threads_by.items():
        classes[key]["threads"] = len({i for i in ids if i})
    return classes


def residue_census(messages: list[dict]) -> dict[str, dict[str, int]]:
    def _hits(msg: dict) -> list[str]:
        klass = classify_residue(str(msg.get("cleaned_body") or ""))
        return [klass] if klass else []

    data = _tally_classes(messages, _hits)
    # Residue is leftover reply history in cleaned authored text, not forwards.
    data.pop("gt_quote", None)
    data.pop("explicit_forward_marker", None)
    data["any_residue"] = data.pop("any_quote_or_forward_marker")
    return data


def raw_marker_census(messages: list[dict]) -> dict[str, dict[str, int]]:
    return _tally_classes(
        messages,
        lambda msg: raw_marker_classes(str(msg.get("raw_body") or msg.get("body") or "")),
    )


def action_census(messages: list[dict]) -> dict[str, dict[str, int]]:
    keys = (
        "quote_history_removed",
        "signature_removed",
        "list_footer_removed",
        "explicit_forward",
        "voice_corpus",
    )
    classes = {k: {"messages": 0, "threads": 0} for k in keys}
    threads_by: dict[str, set[str]] = {k: set() for k in keys}
    methods: dict[str, int] = {}
    for msg in messages:
        tid = str(msg.get("preview_thread_id") or msg.get("thread_id") or "")
        method = str(msg.get("clean_method") or "none")
        methods[method] = methods.get(method, 0) + 1
        flags = {
            "quote_history_removed": bool(msg.get("quoted_removed")),
            "signature_removed": bool(msg.get("signature_removed")),
            "list_footer_removed": bool(msg.get("list_footer_removed")),
            "explicit_forward": bool(msg.get("forward_block")),
            "voice_corpus": bool(msg.get("voice_corpus")),
        }
        for key, on in flags.items():
            if not on:
                continue
            classes[key]["messages"] += 1
            threads_by[key].add(tid)
    for key, ids in threads_by.items():
        classes[key]["threads"] = len({i for i in ids if i})
    return {"flags": classes, "clean_methods": methods}
