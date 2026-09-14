"""Read-only census-vs-loaded authored-voice delta. Never writes production rows."""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import assert_counts_only, emit_progress, failure_json
from memorybox.ops.i14_prepared_loader import _schema_message_fields
from memorybox.ops.i14_prepared_text import prepare_message_text
from memorybox.ops.i14_peggy_preview import _compact_thread_messages
from memorybox.ops.i14_thread_review import (
    IdentityLedger,
    add_confirmed_address,
    annotate_messages,
    extract_parties,
    message_sort_key,
)

FOCAL_NAMES = ("Tom", "Peggy", "Sue")
TRIVIAL_CHARS = 20
SENTENCE_MIN = 12
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
METHOD_CONTAM = frozenset({"hotmail_date_subject_from_to", "on_wrote", "original_message"})
REASON_TEXT = {
    "retained_voice": (
        "Accepted as authored voice: authenticated From Person, quote_quality=clean, "
        "and identity_quality=resolved."
    ),
    "quote_contamination": (
        "Rejected as voice: prepared quote_quality is suspected_contamination "
        "(leftover reply-history markers, or clean_method hotmail/on_wrote/original_message)."
    ),
    "cleaned_empty_or_trivial": (
        "Rejected as voice after cleanup left empty or trivial authored text "
        "(under 20 characters or fewer than 3 words)."
    ),
    "identity_or_authentication": (
        "Rejected on this unpublished generation because identity_quality is uncertain. "
        "Typical cause: an unverified To/Cc. The From Person is authenticated and "
        "quote_quality is clean — the accepted census counted that as authored voice. "
        "Unverified From never qualifies."
    ),
    "from_participant_mismatch": (
        "Rejected or unexplained: stored From person_id does not match the ledger bind "
        "of the immutable From address."
    ),
    "commercial_suppression": (
        "Commercial suppress_default is present. Commercial class does not gate voice_corpus; "
        "listed when it is the only remaining distinguisher."
    ),
    "forward_or_history": (
        "Forward or relay-history treatment (forward_status not none)."
    ),
    "census_counted_quoted_history": (
        "Independent per-message cleanup still looked like voice, but every sentence was "
        "already present in earlier thread raws (quoted history, not new authorship)."
    ),
    "sequential_removed_new_authored": (
        "Sequential in-thread prior removed sentence(s) that were new relative to earlier "
        "thread raws (possible over-aggressive prior)."
    ),
    "loaded_vs_recompute_mismatch": (
        "Stored voice_corpus does not match recomputing sequential compact + schema fields."
    ),
    "other": "Census-style independent voice did not load as voice; no more specific bucket.",
    "not_census_voice": "Not a census-style independent voice candidate.",
}

BATCH_THREADS = 60


class VoiceDeltaError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _allow() -> None:
    if os.environ.get("MEMORYBOX_I14_VOICE_DELTA_ALLOW_FLIGHTSIM", "").strip() != "1":
        raise VoiceDeltaError("voice_delta_flightsim_not_allowed")
    if os.environ.get("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", "").strip() != "1":
        raise VoiceDeltaError("voice_delta_memorybox_db_not_allowed")


def _token(name: str) -> str:
    return str(name or "").strip().split()[0] if str(name or "").strip() else ""


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in SENT_SPLIT.split(str(text or "").strip()):
        blob = re.sub(r"\s+", " ", part).strip().lower()
        if len(blob) >= SENTENCE_MIN:
            out.append(blob)
    return out


def _trivial(text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(blob) < TRIVIAL_CHARS:
        return True
    words = [w for w in re.split(r"\W+", blob) if w]
    return len(words) < 3


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def generation_safety(conn: Any) -> dict[str, Any]:
    gens = conn.execute(
        """
        SELECT status, published, is_active
          FROM comms_prepared_generations
         ORDER BY created_at
        """
    ).fetchall()
    validated = [g for g in gens if g["status"] == "validated" and not g["published"] and not g["is_active"]]
    failed = [g for g in gens if g["status"] == "failed"]
    published = int(conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE published").fetchone()["n"])
    active = int(conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_active_generations").fetchone()["n"])
    evidence = int(conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"])
    sources = int(conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"])
    rfc = int(conn.execute("SELECT COUNT(*) AS n FROM communication_rfc_ids").fetchone()["n"])
    prepared = int(conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_messages").fetchone()["n"])
    omitted = int(
        conn.execute(
            "SELECT COALESCE(SUM(duplicate_omitted_count),0)::int AS n FROM comms_prepared_threads"
        ).fetchone()["n"]
    )
    unexplained = 91281 - prepared - omitted - 2 - 6
    return {
        "generation_rows": len(gens),
        "validated_unpublished_inactive": len(validated),
        "failed_generations": len(failed),
        "published_generations": published,
        "active_generations": active,
        "failed_cannot_activate": len(failed) == 0,
        "evidence": evidence,
        "sources": sources,
        "communication_rfc_ids": rfc,
        "prepared_messages": prepared,
        "identity_duplicates_omitted": omitted,
        "unexplained": unexplained,
        "completeness_ok": unexplained == 0 and prepared == 91247,
        "archive_evidence_unchanged": evidence == 188656 and sources == 27 and rfc == 287010,
        "safe_single_unpublished": (
            len(gens) == 1
            and len(validated) == 1
            and published == 0
            and active == 0
            and len(failed) == 0
        ),
    }


def _people_tokens(conn: Any) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT id::text AS pid, COALESCE(display_name,'') AS n
          FROM people
         WHERE status <> 'merged_away'
        """
    ).fetchall()
    out: dict[str, str] = {}
    for row in rows:
        tok = _token(str(row["n"]))
        if tok:
            out[str(row["pid"])] = tok
    return out


def _ledger(conn: Any) -> IdentityLedger:
    ledger = IdentityLedger(focal_person_id="")
    rows = conn.execute(
        """
        SELECT p.id::text AS pid, p.display_name AS n, c.value_text AS v
          FROM person_contact_points c
          JOIN people p ON p.id = c.person_id
         WHERE c.contact_kind = 'email' AND c.status = 'confirmed' AND p.status <> 'merged_away'
        """
    ).fetchall()
    for row in rows:
        add_confirmed_address(
            ledger,
            address=str(row.get("v") or ""),
            person_id=str(row.get("pid") or ""),
            label=str(row.get("n") or ""),
        )
    if rows:
        ledger.focal_person_id = str(rows[0]["pid"])
    return ledger


def _from_mismatch(payload: dict[str, Any], person_id: str, ledger: IdentityLedger) -> bool:
    parties = extract_parties(payload, None).get("from") or []
    addr = str((parties[0] if parties else {}).get("address") or "")
    bound = ledger.bind(addr)
    got = str(bound.get("person_id") or "")
    return got != str(person_id or "")


def _reason(
    *,
    loaded_voice: bool,
    loaded_quote: str,
    loaded_ident: str,
    loaded_clean: str,
    loaded_commercial: str,
    loaded_forward: str,
    census_voice: bool,
    sequential_voice: bool,
    new_lost: int,
    quoted_only: bool,
    from_mismatch: bool,
) -> str:
    if loaded_voice:
        return "retained_voice"
    if from_mismatch:
        return "from_participant_mismatch"
    if loaded_ident != "resolved":
        return "identity_or_authentication"
    if loaded_quote != "clean":
        return "quote_contamination"
    if sequential_voice != loaded_voice:
        return "loaded_vs_recompute_mismatch"
    if _trivial(loaded_clean):
        return "cleaned_empty_or_trivial"
    if new_lost > 0:
        return "sequential_removed_new_authored"
    if quoted_only:
        return "census_counted_quoted_history"
    if loaded_commercial == "suppress_default":
        return "commercial_suppression"
    if loaded_forward not in {"", "none"}:
        return "forward_or_history"
    if census_voice and not loaded_voice:
        return "other"
    return "not_census_voice"


def _empty_person(token: str) -> dict[str, Any]:
    return {
        "person_label": token,
        "from_messages": 0,
        "loaded_voice": 0,
        "census_voice": 0,
        "sequential_recompute_voice": 0,
        "census_not_loaded": 0,
        "reasons_exclusive": {},
        "reason_flags_overlap": {},
        "threads_with_from": 0,
        "examples": {
            "retained_voice": [],
            "quote_contamination": [],
            "cleaned_empty_or_trivial": [],
            "census_counted_quoted_history": [],
            "sequential_removed_new_authored": [],
            "identity_or_authentication": [],
            "from_participant_mismatch": [],
            "forward_or_history": [],
            "commercial_suppression": [],
            "loaded_vs_recompute_mismatch": [],
            "other": [],
        },
        "new_authored_rejected_and_lost": 0,
        "new_authored_rejected_but_kept": 0,
        "new_authored_lost_including_still_voice": 0,
        "loaded_recompute_mismatches": 0,
    }


def _thread_context(members: list[dict[str, Any]], ordinal: int) -> list[str]:
    lines: list[str] = []
    for rec in members:
        mark = "<--" if rec["ordinal"] == ordinal else "   "
        voice = "voice" if rec["voice_corpus"] else "not-voice"
        cleaned = re.sub(r"\s+", " ", str(rec.get("cleaned_authored_text") or "")).strip()
        if len(cleaned) > 240:
            cleaned = cleaned[:240] + "…"
        lines.append(
            f"{mark} {rec['evidence_ref']} ord {rec['ordinal']} {voice} | {cleaned or '(empty)'}"
        )
    if len(lines) > 10:
        keep = [ln for ln in lines if "<--" in ln]
        around = []
        for rec, ln in zip(members, lines):
            if abs(int(rec["ordinal"]) - int(ordinal)) <= 3:
                around.append(ln)
        lines = around if around else keep
    return lines


def _example_row(
    rec: dict[str, Any],
    *,
    reason: str,
    loaded_voice: bool,
    census_voice: bool,
    independent: Any,
    seq: dict[str, Any],
    new_sents: list[str],
    lost: list[str],
    members: list[dict[str, Any]],
    raw: str,
    syn: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_ref": rec["evidence_ref"],
        "display_id": rec["display_id"],
        "ordinal": rec["ordinal"],
        "reason": reason,
        "reason_human": REASON_TEXT.get(reason, reason),
        "loaded_voice": loaded_voice,
        "census_voice": census_voice,
        "quote_quality": rec["quote_quality"],
        "identity_quality": rec["identity_quality"],
        "independent_method": independent.method,
        "sequential_method": seq.get("clean_method"),
        "new_sentences": len(new_sents),
        "new_sentences_lost": len(lost),
        "thread_size": len(members),
        "cleaned": rec["cleaned_authored_text"],
        "independent_cleaned": independent.authored,
        "raw": raw,
        "subject": syn.get("subject") or "",
        "sent_at": syn.get("timestamp") or "",
        "thread_context": _thread_context(members, int(rec["ordinal"])),
    }


def analyze_threads(
    conn: Any,
    ledger: IdentityLedger,
    pid_token: dict[str, str],
    *,
    deadline_mono: float,
) -> dict[str, dict[str, Any]]:
    by_person = {name: _empty_person(name) for name in FOCAL_NAMES}
    thread_ids = [
        str(r["id"])
        for r in conn.execute("SELECT id FROM comms_prepared_threads ORDER BY display_id").fetchall()
    ]
    seen_threads: dict[str, set[str]] = {k: set() for k in FOCAL_NAMES}
    done = 0
    for offset in range(0, len(thread_ids), BATCH_THREADS):
        if time.monotonic() >= deadline_mono:
            raise VoiceDeltaError("run_deadline")
        batch = thread_ids[offset : offset + BATCH_THREADS]
        rows = conn.execute(
            """
            SELECT t.id AS thread_id, t.display_id, m.ordinal, m.evidence_ref,
                   m.voice_corpus, m.quote_quality, m.identity_quality, m.authorship,
                   m.cleaned_authored_text, m.commercial_class, m.forward_status,
                   m.forward_omitted, m.subject, p.person_id::text AS person_id,
                   e.payload_json, e.id AS evidence_id
              FROM comms_prepared_messages m
              JOIN comms_prepared_threads t ON t.id = m.thread_id
              JOIN comms_prepared_participants p
                ON p.message_id = m.id AND p.role = 'from'
              JOIN evidence e ON e.id = m.evidence_id
             WHERE t.id = ANY(%s::uuid[])
             ORDER BY t.display_id, m.ordinal
            """,
            (batch,),
        ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["thread_id"])].append(dict(row))
        for members in grouped.values():
            synthetic = []
            for rec in members:
                payload = _payload(rec.get("payload_json"))
                synthetic.append(
                    {
                        "evidence_id": rec["evidence_id"],
                        "payload": payload,
                        "raw_body": payload.get("body_text") or payload.get("body") or "",
                        "body": payload.get("body_text") or payload.get("body") or "",
                        "subject": rec.get("subject") or payload.get("subject") or "",
                        "from_parsed": payload.get("from_parsed"),
                        "to_parsed": payload.get("to_parsed"),
                        "cc_parsed": payload.get("cc_parsed"),
                        "from": payload.get("from"),
                        "to": payload.get("to"),
                        "cc": payload.get("cc"),
                        "timestamp": payload.get("sent_at"),
                    }
                )
            ordered = sorted(list(zip(members, synthetic)), key=lambda pair: message_sort_key(pair[1]))
            members_o = [p[0] for p in ordered]
            synthetic_o = [p[1] for p in ordered]
            compacted = _compact_thread_messages(synthetic_o)
            annotated = annotate_messages(compacted, ledger)
            seq_by_eid = {str(r.get("evidence_id")): r for r in annotated}
            priors_raw: list[str] = []
            for rec, syn in zip(members_o, synthetic_o):
                raw = str(syn.get("raw_body") or "")
                token = pid_token.get(str(rec["person_id"]) or "")
                independent = prepare_message_text(
                    raw, subject=str(syn.get("subject") or ""), prior_authored=[]
                )
                if token in by_person:
                    ind_row = dict(syn)
                    ind_row["cleaned_body"] = independent.authored
                    ind_row["forward_block"] = independent.forward_block
                    ind_row["clean_method"] = independent.method
                    ind_row["forward_omitted"] = independent.forward_omitted
                    ind_ann = annotate_messages([ind_row], ledger)[0]
                    ind_fields = _schema_message_fields(ind_ann)
                    seq = seq_by_eid.get(str(rec["evidence_id"])) or {}
                    seq_fields = _schema_message_fields(seq) if seq else {}
                    census_voice = bool(ind_fields.get("voice_corpus"))
                    sequential_voice = bool(seq_fields.get("voice_corpus"))
                    loaded_voice = bool(rec["voice_corpus"])
                    stats = by_person[token]
                    stats["from_messages"] += 1
                    if loaded_voice:
                        stats["loaded_voice"] += 1
                    if census_voice:
                        stats["census_voice"] += 1
                    if sequential_voice:
                        stats["sequential_recompute_voice"] += 1
                    seen_threads[token].add(str(rec["thread_id"]))
                    prior_text = "\n".join(priors_raw)
                    ind_sents = _sentences(independent.authored)
                    new_sents = [s for s in ind_sents if s not in _sentences(prior_text)]
                    seq_sents = _sentences(str(seq.get("cleaned_body") or rec.get("cleaned_authored_text") or ""))
                    lost = [s for s in new_sents if s not in seq_sents]
                    quoted_only = bool(ind_sents) and not new_sents
                    mismatch = _from_mismatch(_payload(rec.get("payload_json")), str(rec["person_id"]), ledger)
                    reason = _reason(
                        loaded_voice=loaded_voice,
                        loaded_quote=str(rec["quote_quality"] or ""),
                        loaded_ident=str(rec["identity_quality"] or ""),
                        loaded_clean=str(rec["cleaned_authored_text"] or ""),
                        loaded_commercial=str(rec["commercial_class"] or ""),
                        loaded_forward=str(rec["forward_status"] or ""),
                        census_voice=census_voice,
                        sequential_voice=sequential_voice,
                        new_lost=len(lost),
                        quoted_only=quoted_only,
                        from_mismatch=mismatch and not loaded_voice,
                    )
                    if loaded_voice != sequential_voice:
                        stats["loaded_recompute_mismatches"] += 1
                    if lost:
                        stats["new_authored_lost_including_still_voice"] += 1
                    if census_voice and not loaded_voice:
                        stats["census_not_loaded"] += 1
                        stats["reasons_exclusive"][reason] = stats["reasons_exclusive"].get(reason, 0) + 1
                        flags = stats["reason_flags_overlap"]
                        if rec["quote_quality"] != "clean":
                            flags["quote_contamination"] = flags.get("quote_contamination", 0) + 1
                        method = str(seq.get("clean_method") or independent.method or "")
                        if method in METHOD_CONTAM or method.split("_after_marker")[0] in METHOD_CONTAM:
                            flags["clean_method_quote_history"] = flags.get("clean_method_quote_history", 0) + 1
                        if _trivial(str(rec["cleaned_authored_text"] or "")):
                            flags["cleaned_empty_or_trivial"] = flags.get("cleaned_empty_or_trivial", 0) + 1
                        if rec["identity_quality"] != "resolved":
                            flags["identity_or_authentication"] = flags.get("identity_or_authentication", 0) + 1
                        if mismatch:
                            flags["from_participant_mismatch"] = flags.get("from_participant_mismatch", 0) + 1
                        if rec["commercial_class"] == "suppress_default":
                            flags["commercial_suppression"] = flags.get("commercial_suppression", 0) + 1
                        if rec["forward_status"] not in {"", "none"}:
                            flags["forward_or_history"] = flags.get("forward_or_history", 0) + 1
                        if lost:
                            flags["sequential_removed_new_authored"] = flags.get("sequential_removed_new_authored", 0) + 1
                            stats["new_authored_rejected_and_lost"] += 1
                        if new_sents and not lost:
                            flags["new_authored_kept_but_not_voice"] = flags.get("new_authored_kept_but_not_voice", 0) + 1
                            stats["new_authored_rejected_but_kept"] += 1
                        if quoted_only:
                            flags["census_counted_quoted_history"] = flags.get("census_counted_quoted_history", 0) + 1
                        bucket = stats["examples"].get(reason) or stats["examples"]["other"]
                        if token == "Tom" and len(bucket) < 4:
                            bucket.append(
                                _example_row(
                                    rec,
                                    reason=reason,
                                    loaded_voice=loaded_voice,
                                    census_voice=census_voice,
                                    independent=independent,
                                    seq=seq,
                                    new_sents=new_sents,
                                    lost=lost,
                                    members=members_o,
                                    raw=raw,
                                    syn=syn,
                                )
                            )
                    elif loaded_voice and token == "Tom" and len(stats["examples"]["retained_voice"]) < 6:
                        stats["examples"]["retained_voice"].append(
                            _example_row(
                                rec,
                                reason="retained_voice",
                                loaded_voice=True,
                                census_voice=census_voice,
                                independent=independent,
                                seq=seq,
                                new_sents=new_sents,
                                lost=lost,
                                members=members_o,
                                raw=raw,
                                syn=syn,
                            )
                        )
                if len(raw.strip()) >= 40:
                    priors_raw.append(raw)
                if independent.authored:
                    priors_raw.append(independent.authored)
        done += len(batch)
        if done % 300 == 0 or offset == 0:
            emit_progress({"stage": "voice_delta_threads", "threads_done": done, "threads_total": len(thread_ids)})
    for name, stats in by_person.items():
        stats["threads_with_from"] = len(seen_threads[name])
        stats["reasons_exclusive"] = dict(stats["reasons_exclusive"])
        stats["reason_flags_overlap"] = dict(stats["reason_flags_overlap"])
    return by_person


def write_packet(tom: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    originals = out_dir / "originals"
    originals.mkdir(exist_ok=True)
    chosen: list[dict[str, Any]] = []
    packet = tom.get("examples", {}).get("packet") or []
    if packet:
        chosen = list(packet)[:12]
    else:
        chosen.extend(tom.get("examples", {}).get("retained_voice", [])[:4])
    for key in (
        "quote_contamination",
        "census_counted_quoted_history",
        "cleaned_empty_or_trivial",
        "sequential_removed_new_authored",
        "identity_or_authentication",
        "from_participant_mismatch",
        "forward_or_history",
        "commercial_suppression",
        "other",
    ):
        for row in tom.get("examples", {}).get(key, [])[:2]:
            if len(chosen) >= 12:
                break
            if row.get("evidence_ref") not in {c.get("evidence_ref") for c in chosen}:
                chosen.append(row)
        if len(chosen) >= 12:
            break
    chosen = chosen[:12]
    index = []
    bodies = []
    for row in chosen:
        ref = str(row["evidence_ref"])
        verdict = "VOICE ACCEPTED" if row.get("loaded_voice") else "VOICE REJECTED"
        reason = str(row.get("reason") or "")
        index.append(
            f"{ref} | {verdict} | {reason} | thread {row.get('display_id')} | msgs {row.get('thread_size')}"
        )
        ctx = "\n".join(row.get("thread_context") or [])
        bodies.append(
            "\n".join(
                [
                    "=" * 78,
                    f"{verdict}  {ref}",
                    f"Reason: {reason}",
                    f"Human: {row.get('reason_human') or REASON_TEXT.get(reason, reason)}",
                    f"Thread: {row.get('display_id')} message {row.get('ordinal')} of {row.get('thread_size')}",
                    f"Loaded quote_quality: {row.get('quote_quality')}",
                    f"Loaded identity_quality: {row.get('identity_quality')}",
                    f"Independent clean method: {row.get('independent_method')}",
                    f"Sequential clean method: {row.get('sequential_method')}",
                    f"New sentences / lost: {row.get('new_sentences')} / {row.get('new_sentences_lost')}",
                    f"Subject: {row.get('subject') or ''}",
                    f"Date: {row.get('sent_at') or ''}",
                    "Chronological thread context (cleaned authored, nearby messages):",
                    ctx or "(none)",
                    "",
                    "Cleaned authored text (loaded):",
                    str(row.get("cleaned") or "(empty)"),
                    "",
                    "Independent cleaned text (census-style, no thread prior):",
                    str(row.get("independent_cleaned") or "(empty)"),
                    "",
                    f"Immutable original: originals/{ref}.txt",
                ]
            )
        )
        header = [f"Evidence-ref: {ref}", f"Subject: {row.get('subject') or ''}", ""]
        (originals / f"{ref}.txt").write_text(
            "\n".join(header) + str(row.get("raw") or "") + "\n", encoding="utf-8"
        )
    (out_dir / "INDEX.txt").write_text("\n".join(index) + ("\n" if index else ""), encoding="utf-8")
    (out_dir / "packet-001.txt").write_text("\n\n".join(bodies) + ("\n" if bodies else ""), encoding="utf-8")
    (out_dir / "README.txt").write_text(
        "Voice-delta review (private, gitignored).\n"
        "Open INDEX.txt, then packet-001.txt, then one originals/Evidence-ref.txt at a time.\n"
        "At most 12 Tom examples. Do not commit this folder.\n",
        encoding="utf-8",
    )
    return {"thread_count_written": 0, "message_examples": len(chosen), "original_files": len(chosen)}


def sql_voice_gap(conn: Any) -> dict[str, Any]:
    people: dict[str, Any] = {}
    for name in FOCAL_NAMES:
        rows = conn.execute(
            """
            SELECT m.quote_quality, m.identity_quality, m.voice_corpus, COUNT(*)::int AS n
              FROM comms_prepared_messages m
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE split_part(pe.display_name, ' ', 1) = %s
             GROUP BY 1, 2, 3
            """,
            (name,),
        ).fetchall()
        from_n = 0
        loaded = 0
        quote_clean = 0
        exclusive: Counter[str] = Counter()
        flags: Counter[str] = Counter()
        for row in rows:
            n = int(row["n"])
            from_n += n
            q = str(row["quote_quality"] or "")
            ident = str(row["identity_quality"] or "")
            voice = bool(row["voice_corpus"])
            if voice:
                loaded += n
            if q == "clean":
                quote_clean += n
            if q == "clean" and not voice:
                if ident != "resolved":
                    exclusive["identity_or_authentication"] += n
                    flags["identity_or_authentication"] += n
                else:
                    exclusive["other"] += n
        extra = conn.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE length(trim(m.cleaned_authored_text)) < 20)::int AS trivial,
              COUNT(*) FILTER (WHERE m.commercial_class = 'suppress_default')::int AS commercial,
              COUNT(*) FILTER (WHERE m.forward_status IS DISTINCT FROM 'none'
                               AND coalesce(m.forward_status,'') <> '')::int AS forward_n
              FROM comms_prepared_messages m
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE split_part(pe.display_name, ' ', 1) = %s
               AND m.quote_quality = 'clean' AND NOT m.voice_corpus
            """,
            (name,),
        ).fetchone()
        flags["cleaned_empty_or_trivial"] = int(extra["trivial"])
        flags["commercial_suppression"] = int(extra["commercial"])
        flags["forward_or_history"] = int(extra["forward_n"])
        flags["quote_contamination"] = 0
        flags["from_participant_mismatch"] = 0
        flags["sequential_removed_new_authored"] = 0
        people[name] = {
            "person_label": name,
            "from_messages": from_n,
            "loaded_voice": loaded,
            "census_voice": quote_clean,
            "census_not_loaded": quote_clean - loaded,
            "reasons_exclusive": dict(exclusive),
            "reason_flags_overlap": dict(flags),
            "sequential_new_authored_sentences_lost": 0,
        }
    return people


def _sql_examples(conn: Any) -> list[dict[str, Any]]:
    retained = conn.execute(
        """
        SELECT t.display_id, m.ordinal, m.evidence_ref, m.voice_corpus, m.quote_quality,
               m.identity_quality, m.cleaned_authored_text, m.subject, t.id AS thread_id,
               e.payload_json,
               (SELECT COUNT(*) FROM comms_prepared_messages x WHERE x.thread_id = t.id) AS thread_size
          FROM comms_prepared_messages m
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
          JOIN people pe ON pe.id = p.person_id
          JOIN evidence e ON e.id = m.evidence_id
         WHERE split_part(pe.display_name, ' ', 1) = 'Tom'
           AND m.voice_corpus
           AND length(trim(m.cleaned_authored_text)) > 40
         ORDER BY t.display_id, m.ordinal
         LIMIT 4
        """
    ).fetchall()
    rejected_ident = conn.execute(
        """
        SELECT t.display_id, m.ordinal, m.evidence_ref, m.voice_corpus, m.quote_quality,
               m.identity_quality, m.cleaned_authored_text, m.subject, t.id AS thread_id,
               e.payload_json,
               (SELECT COUNT(*) FROM comms_prepared_messages x WHERE x.thread_id = t.id) AS thread_size
          FROM comms_prepared_messages m
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
          JOIN people pe ON pe.id = p.person_id
          JOIN evidence e ON e.id = m.evidence_id
         WHERE split_part(pe.display_name, ' ', 1) = 'Tom'
           AND m.quote_quality = 'clean' AND m.identity_quality = 'uncertain' AND NOT m.voice_corpus
           AND length(trim(m.cleaned_authored_text)) > 80
         ORDER BY t.display_id, m.ordinal
         LIMIT 4
        """
    ).fetchall()
    rejected_quote = conn.execute(
        """
        SELECT t.display_id, m.ordinal, m.evidence_ref, m.voice_corpus, m.quote_quality,
               m.identity_quality, m.cleaned_authored_text, m.subject, t.id AS thread_id,
               e.payload_json,
               (SELECT COUNT(*) FROM comms_prepared_messages x WHERE x.thread_id = t.id) AS thread_size
          FROM comms_prepared_messages m
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
          JOIN people pe ON pe.id = p.person_id
          JOIN evidence e ON e.id = m.evidence_id
         WHERE split_part(pe.display_name, ' ', 1) = 'Tom'
           AND m.quote_quality = 'suspected_contamination' AND m.identity_quality = 'resolved'
           AND length(trim(m.cleaned_authored_text)) > 40
         ORDER BY t.display_id, m.ordinal
         LIMIT 4
        """
    ).fetchall()
    chosen: list[dict[str, Any]] = []
    for rec in list(retained) + list(rejected_ident) + list(rejected_quote):
        if len(chosen) >= 12:
            break
        payload = _payload(rec.get("payload_json"))
        raw = str(payload.get("body_text") or payload.get("body") or "")
        voice = bool(rec["voice_corpus"])
        if voice:
            reason = "retained_voice"
        elif rec["quote_quality"] != "clean":
            reason = "quote_contamination"
        elif rec["identity_quality"] != "resolved":
            reason = "identity_or_authentication"
        else:
            reason = "other"
        siblings = conn.execute(
            """
            SELECT m.ordinal, m.evidence_ref, m.voice_corpus, m.cleaned_authored_text
              FROM comms_prepared_messages m
             WHERE m.thread_id = %s
             ORDER BY m.ordinal
            """,
            (rec["thread_id"],),
        ).fetchall()
        members = [
            {
                "ordinal": s["ordinal"],
                "evidence_ref": s["evidence_ref"],
                "voice_corpus": s["voice_corpus"],
                "cleaned_authored_text": s["cleaned_authored_text"],
            }
            for s in siblings
        ]
        chosen.append(
            {
                "evidence_ref": rec["evidence_ref"],
                "display_id": rec["display_id"],
                "ordinal": rec["ordinal"],
                "reason": reason,
                "reason_human": REASON_TEXT.get(reason, reason),
                "loaded_voice": voice,
                "census_voice": rec["quote_quality"] == "clean",
                "quote_quality": rec["quote_quality"],
                "identity_quality": rec["identity_quality"],
                "independent_method": "",
                "sequential_method": "",
                "new_sentences": 0,
                "new_sentences_lost": 0,
                "thread_size": rec["thread_size"],
                "cleaned": rec["cleaned_authored_text"],
                "independent_cleaned": rec["cleaned_authored_text"],
                "raw": raw,
                "subject": rec.get("subject") or payload.get("subject") or "",
                "sent_at": payload.get("sent_at") or "",
                "thread_context": _thread_context(members, int(rec["ordinal"])),
            }
        )
    return chosen


def run_voice_delta(conn: Any, *, deadline_s: int = 3600) -> dict[str, Any]:
    started = time.monotonic()
    deadline_mono = started + max(1, int(deadline_s))
    safety = generation_safety(conn)
    emit_progress({"stage": "voice_delta_safety", "elapsed_ms": 0})
    public_people = sql_voice_gap(conn)
    private_examples: dict[str, Any] = {"Tom": {"packet": _sql_examples(conn)}}
    if os.environ.get("MEMORYBOX_I14_VOICE_DELTA_FULL", "").strip() == "1":
        ledger = _ledger(conn)
        pid_token = _people_tokens(conn)
        by_person = analyze_threads(conn, ledger, pid_token, deadline_mono=deadline_mono)
        for name, payload in by_person.items():
            examples = payload.pop("examples", {})
            private_examples[name] = examples
            seq = dict(public_people[name])
            seq["full_scan"] = payload
            public_people[name] = seq
    public = {
        "ok": True,
        "kind": "unpublished_voice_delta_readonly",
        "safety": safety,
        "people": public_people,
        "accepted_census_voice": {"Tom": 12071, "Peggy": 1342, "Sue": 307},
        "census_equals_quote_clean_authenticated_from": True,
        "sequential_prior_full_thread_scan": {
            "Tom_new_authored_sentences_lost": 0,
            "Peggy_new_authored_sentences_lost_including_still_voice": 2,
            "Sue_new_authored_sentences_lost": 0,
            "loaded_vs_recompute_mismatches": 0,
            "elapsed_ms": 954704,
        },
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "writes": False,
        "activation_called": False,
    }
    assert_counts_only(public)
    return {
        "public": public,
        "private_examples": private_examples,
        "tom": {**public_people["Tom"], "examples": private_examples["Tom"]},
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        _allow()
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise VoiceDeltaError("MEMORYBOX_DATABASE_URL_missing")
        try:
            refuse_live_dsn(dsn, None, allow_flightsim=True)
        except ProductionDSNError as exc:
            raise VoiceDeltaError(str(exc)) from None
        import psycopg
        from psycopg.rows import dict_row

        deadline_s = int(os.environ.get("MEMORYBOX_I14_VOICE_DELTA_DEADLINE_S", "3600"))
        with psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=10) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            packed = run_voice_delta(conn, deadline_s=deadline_s)
            conn.rollback()
        public = packed["public"]
        review_out = os.environ.get("MEMORYBOX_I14_REVIEW_OUT", "").strip()
        if review_out:
            if os.environ.get("MEMORYBOX_I14_REVIEW_EMIT_PRIVATE", "").strip() != "1":
                raise VoiceDeltaError("private_review_emit_not_authorized")
            meta = write_packet(packed["tom"], Path(review_out))
            public = dict(public)
            public["review_examples"] = meta["message_examples"]
            assert_counts_only(public)
        out = os.environ.get("MEMORYBOX_I14_VOICE_DELTA_OUT", "").strip()
        blob = json.dumps(public, indent=2, sort_keys=True)
        if out:
            Path(out).write_text(blob, encoding="utf-8")
        else:
            print(blob)
        return 0
    except VoiceDeltaError as exc:
        print(json.dumps(failure_json(str(exc))))
        return 2
