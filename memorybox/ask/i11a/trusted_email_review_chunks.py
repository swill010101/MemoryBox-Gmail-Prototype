"""Deterministic token-aware chunks from a frozen trusted email review paste.

No model calls during preparation. Parent MODEL_PASTE.txt is never modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.trusted_email_review import (
    EMAIL_REVIEW_SYSTEM,
    ESTABLISHED_GEMMA_MODEL,
    _REPLAY_BIND_MARK,
    _estimate_tokens,
    _parse_sent_at,
    encode_replay_binding,
    extract_replay_binding,
    replay_binding_payload,
)

_MARKER_SYSTEM = "===== SYSTEM INSTRUCTIONS ====="
_MARKER_USER = "===== USER QUESTION AND EVIDENCE ====="
_MARKER_CONV = "===== TRUSTED EMAIL CONVERSATIONS ====="
_BEGIN_CONV = "BEGIN CONVERSATION:"
_END_CONV = "END CONVERSATION"

ADVERTISED_CONTEXT = 262_144
OUTPUT_RESERVE = 4_096
SAFETY_RESERVE = 2_048
DEFAULT_TARGET_ESTIMATED_TOKENS = 180_000
USABLE_INPUT_TOKENS = ADVERTISED_CONTEXT - OUTPUT_RESERVE - SAFETY_RESERVE

_TURN_HEADER = re.compile(
    r"(?:said:|service-generated|authorship unresolved).*\[(email_\d+)\]"
    r"|\[(email_\d+)\].*(?:said:|service-generated|authorship unresolved)",
    re.I,
)
_CITE_TAG = re.compile(r"\[(email_\d+)\]")


def _turn_header_cite(line: str) -> str:
    m = _TURN_HEADER.search(line)
    if not m:
        return ""
    return m.group(1) or m.group(2) or ""


def _is_turn_header(line: str) -> bool:
    return bool(_turn_header_cite(line))

EMAIL_REVIEW_CHUNK_SYSTEM = EMAIL_REVIEW_SYSTEM.replace(
    "Stateless. No chunking. No hierarchical summarization.",
    (
        "This message is chunk {chunk_n} of {chunk_m} from a larger frozen packet. "
        "It contains partial evidence only and is incomplete by design. "
        "Use only evidence printed in this chunk. Do not infer completeness from "
        "how the chunk begins or ends. Preserve uncertainty and missing-context "
        "warnings. Return the same JSON schema. Every accepted claim, episode, "
        "and relationship must cite [email_N] tags present in this chunk only. "
        "Do not invent or cite evidence ids that are not in this chunk."
    ),
)


@dataclass
class ParsedTurn:
    cite_as: str
    lines: list[str]
    sent_at: datetime | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


@dataclass
class ParsedConversation:
    conv_index: int
    subject: str
    header_lines: list[str]
    turns: list[ParsedTurn]
    raw_block: str

    @property
    def cite_as(self) -> list[str]:
        return [t.cite_as for t in self.turns]

    @property
    def earliest(self) -> datetime:
        dts = [t.sent_at for t in self.turns if t.sent_at is not None]
        if dts:
            return min(dts)
        return datetime.max.replace(tzinfo=timezone.utc)


@dataclass
class ChunkUnit:
    """One packable slice: whole conversation or turn-range within one."""

    conv_index: int
    subject: str
    header_lines: list[str]
    turns: list[ParsedTurn]
    continuation_before: str | None = None
    continuation_after: str | None = None
    split: bool = False
    split_part: int | None = None
    split_parts: int | None = None

    @property
    def cite_as(self) -> list[str]:
        return [t.cite_as for t in self.turns]

    def render_block(self) -> str:
        lines = list(self.header_lines)
        if self.continuation_before:
            lines.append(self.continuation_before)
        for turn in self.turns:
            lines.extend(turn.lines)
            lines.append("")
        if self.continuation_after:
            lines.append(self.continuation_after)
        lines.append(_END_CONV)
        return "\n".join(lines).rstrip()


@dataclass
class PreparedChunk:
    chunk_index: int
    units: list[ChunkUnit]
    system: str
    user: str
    binding_json: str
    paste_text: str
    sha256: str
    estimated_tokens: int
    date_start: str | None
    date_end: str | None
    conversation_ids: list[int]
    evidence_ids: list[str]
    cite_as: list[str]
    message_count: int
    conversation_count: int
    conversation_splits: list[dict[str, Any]] = field(default_factory=list)
    unavoidable_oversize: bool = False


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _parse_turns(body_lines: list[str]) -> list[ParsedTurn]:
    turns: list[ParsedTurn] = []
    current: ParsedTurn | None = None
    for line in body_lines:
        if _is_turn_header(line):
            if current is not None:
                turns.append(current)
            cite = _turn_header_cite(line)
            current = ParsedTurn(cite_as=cite, lines=[line])
            continue
        if current is None:
            continue
        current.lines.append(line)
    if current is not None:
        turns.append(current)
    return turns


def _parse_conversations(user_tail: str) -> list[ParsedConversation]:
    if _MARKER_CONV not in user_tail:
        return []
    _, conv_blob = user_tail.split(_MARKER_CONV, 1)
    parts = re.split(r"(?=BEGIN CONVERSATION:)", conv_blob)
    out: list[ParsedConversation] = []
    idx = 0
    for part in parts:
        part = part.strip()
        if not part.startswith(_BEGIN_CONV):
            continue
        if _END_CONV not in part:
            continue
        block, _ = part.rsplit(_END_CONV, 1)
        block = block.strip()
        lines = block.splitlines()
        if not lines:
            continue
        subject = lines[0][len(_BEGIN_CONV) :].strip()
        header_lines = [lines[0]]
        body_start = 1
        if len(lines) > 1 and lines[1].startswith("grouping:"):
            header_lines.append(lines[1])
            body_start = 2
        turns = _parse_turns(lines[body_start:])
        out.append(
            ParsedConversation(
                conv_index=idx,
                subject=subject,
                header_lines=header_lines,
                turns=turns,
                raw_block=part.strip() + "\n" + _END_CONV,
            )
        )
        idx += 1
    return out


def _attach_citation_times(
    conversations: list[ParsedConversation],
    citations: list[dict[str, Any]],
) -> None:
    by_cite = {str(c.get("cite_as") or ""): c for c in citations}
    for conv in conversations:
        for turn in conv.turns:
            row = by_cite.get(turn.cite_as) or {}
            turn.sent_at = _parse_sent_at(row.get("sent_at"))


def _sort_conversations(conversations: list[ParsedConversation]) -> list[ParsedConversation]:
    return sorted(
        conversations,
        key=lambda c: (c.earliest, c.conv_index, c.subject.casefold()),
    )


def _chunk_system(chunk_n: int, chunk_m: int) -> str:
    return (
        EMAIL_REVIEW_CHUNK_SYSTEM.replace("{chunk_n}", str(chunk_n)).replace(
            "{chunk_m}", str(chunk_m)
        )
    )


def _chunk_binding_json(source_map: dict[str, Any]) -> str:
    budget = dict(source_map.get("budget") or {})
    proposed = dict((budget.get("proposed_request") or {}))
    proposed["num_ctx"] = ADVERTISED_CONTEXT
    proposed["num_predict"] = OUTPUT_RESERVE
    proposed["output_reserve"] = OUTPUT_RESERVE
    proposed["provider"] = proposed.get("provider") or "ollama"
    proposed["model"] = proposed.get("model") or ESTABLISHED_GEMMA_MODEL
    proposed["temperature"] = proposed.get("temperature", 0.1)
    budget["proposed_request"] = proposed
    budget["capacity_certainty"] = budget.get("capacity_certainty") or "advertised_only"
    return encode_replay_binding({"budget": budget})


def _user_header(user_prefix: str) -> str:
    if _MARKER_CONV in user_prefix:
        return user_prefix.split(_MARKER_CONV, 1)[0].rstrip()
    return user_prefix.rstrip()


def _chunk_metadata_lines(*, chunk_n: int, chunk_m: int, units: list[ChunkUnit]) -> list[str]:
    lines = [
        f"===== CHUNK {chunk_n} OF {chunk_m} — PARTIAL EVIDENCE =====",
        (
            "This chunk is incomplete by design. Use only the conversations below. "
            "Do not infer completeness from the chunk boundary."
        ),
        f"chunk_index: {chunk_n}",
        f"chunk_total: {chunk_m}",
        f"conversation_units: {len(units)}",
    ]
    for u in units:
        if u.continuation_before:
            lines.append(u.continuation_before)
        if u.continuation_after:
            lines.append(f"continuation_after: {u.continuation_after}")
    return lines


def _build_chunk_paste(
    *,
    chunk_n: int,
    chunk_m: int,
    system: str,
    binding_json: str,
    user_header: str,
    units: list[ChunkUnit],
) -> str:
    meta = _chunk_metadata_lines(chunk_n=chunk_n, chunk_m=chunk_m, units=units)
    conv_blocks = [u.render_block() for u in units]
    user = "\n".join(
        [
            user_header,
            "",
            *meta,
            "",
            _MARKER_CONV,
            "",
            *conv_blocks,
        ]
    ).rstrip() + "\n"
    return (
        f"{_MARKER_SYSTEM}\n"
        f"{system.rstrip()}\n\n"
        f"{_REPLAY_BIND_MARK}\n"
        f"{binding_json}\n\n"
        f"{_MARKER_USER}\n"
        f"{user}"
    )


def _estimate_chunk_tokens(paste: str) -> int:
    return _estimate_tokens(paste)


def _units_token_estimate(
    *,
    chunk_n: int,
    chunk_m: int,
    user_header: str,
    binding_json: str,
    units: list[ChunkUnit],
) -> int:
    system = _chunk_system(chunk_n, chunk_m)
    paste = _build_chunk_paste(
        chunk_n=chunk_n,
        chunk_m=chunk_m,
        system=system,
        binding_json=binding_json,
        user_header=user_header,
        units=units,
    )
    return _estimate_chunk_tokens(paste)


def _evidence_ids_for_cites(
    cite_as: list[str], citations: list[dict[str, Any]]
) -> list[str]:
    by_cite = {str(c.get("cite_as") or ""): str(c.get("evidence_id") or "") for c in citations}
    return [by_cite[c] for c in cite_as if by_cite.get(c)]


def _date_range(units: list[ChunkUnit]) -> tuple[str | None, str | None]:
    dts: list[datetime] = []
    for u in units:
        for t in u.turns:
            if t.sent_at is not None:
                dts.append(t.sent_at)
    if not dts:
        return None, None
    lo, hi = min(dts), max(dts)
    return lo.date().isoformat(), hi.date().isoformat()


def _split_conversation_units(
    conv: ParsedConversation,
    *,
    target: int,
    user_header: str,
    binding_json: str,
    chunk_m_placeholder: int,
) -> list[ChunkUnit]:
    """Split one oversized conversation at turn boundaries only."""
    if not conv.turns:
        return [
            ChunkUnit(
                conv_index=conv.conv_index,
                subject=conv.subject,
                header_lines=list(conv.header_lines),
                turns=[],
            )
        ]
    parts: list[ChunkUnit] = []
    bucket: list[ParsedTurn] = []
    part = 1
    total_parts = 0  # filled after we know count

    def _flush(is_last: bool) -> None:
        nonlocal bucket, part
        if not bucket:
            return
        before = None
        after = None
        if part > 1:
            before = (
                f"===== CONTINUATION — conversation continued from earlier chunk "
                f"(part {part}) ====="
            )
        if not is_last:
            after = (
                f"===== CONTINUATION — conversation continues in a later chunk "
                f"(part {part}) ====="
            )
        parts.append(
            ChunkUnit(
                conv_index=conv.conv_index,
                subject=conv.subject,
                header_lines=list(conv.header_lines),
                turns=list(bucket),
                continuation_before=before,
                continuation_after=after,
                split=True,
                split_part=part,
            )
        )
        bucket = []
        part += 1

    for turn in conv.turns:
        trial = bucket + [turn]
        unit = ChunkUnit(
            conv_index=conv.conv_index,
            subject=conv.subject,
            header_lines=list(conv.header_lines),
            turns=trial,
        )
        est = _units_token_estimate(
            chunk_n=1,
            chunk_m=max(2, chunk_m_placeholder),
            user_header=user_header,
            binding_json=binding_json,
            units=[unit],
        )
        if bucket and est > target:
            _flush(is_last=False)
            bucket = [turn]
        else:
            bucket = trial
    _flush(is_last=True)
    total_parts = len(parts)
    for p in parts:
        p.split_parts = total_parts
    return parts


def _pack_units(
    conversations: list[ParsedConversation],
    *,
    target: int,
    user_header: str,
    binding_json: str,
) -> tuple[list[list[ChunkUnit]], list[dict[str, Any]]]:
    """Greedy pack whole conversations; split only when one alone exceeds target."""
    sorted_convs = _sort_conversations(conversations)
    chunk_units: list[list[ChunkUnit]] = []
    current: list[ChunkUnit] = []
    splits: list[dict[str, Any]] = []

    def _estimate_current(extra: list[ChunkUnit] | None = None) -> int:
        units = current + (extra or [])
        return _units_token_estimate(
            chunk_n=max(1, len(chunk_units) + 1),
            chunk_m=max(1, len(chunk_units) + 1),
            user_header=user_header,
            binding_json=binding_json,
            units=units,
        )

    for conv in sorted_convs:
        whole = ChunkUnit(
            conv_index=conv.conv_index,
            subject=conv.subject,
            header_lines=list(conv.header_lines),
            turns=list(conv.turns),
        )
        alone = _units_token_estimate(
            chunk_n=1,
            chunk_m=1,
            user_header=user_header,
            binding_json=binding_json,
            units=[whole],
        )
        if alone > target:
            if len(conv.turns) <= 1:
                splits.append(
                    {
                        "conv_index": conv.conv_index,
                        "subject": conv.subject,
                        "parts": 1,
                        "cite_as": conv.cite_as,
                        "reason": "single_turn_exceeds_target_unsplittable",
                    }
                )
                if current and _estimate_current([whole]) > target:
                    chunk_units.append(current)
                    current = [whole]
                else:
                    current.append(whole)
                continue
            split_parts = _split_conversation_units(
                conv,
                target=target,
                user_header=user_header,
                binding_json=binding_json,
                chunk_m_placeholder=max(2, len(sorted_convs)),
            )
            splits.append(
                {
                    "conv_index": conv.conv_index,
                    "subject": conv.subject,
                    "parts": len(split_parts),
                    "cite_as": conv.cite_as,
                    "reason": "single_conversation_exceeds_target",
                }
            )
            for part in split_parts:
                if current and _estimate_current([part]) > target:
                    chunk_units.append(current)
                    current = [part]
                elif current:
                    trial = current + [part]
                    if _units_token_estimate(
                        chunk_n=1,
                        chunk_m=1,
                        user_header=user_header,
                        binding_json=binding_json,
                        units=trial,
                    ) <= target:
                        current = trial
                    else:
                        chunk_units.append(current)
                        current = [part]
                else:
                    current = [part]
            continue
        if current and _estimate_current([whole]) > target:
            chunk_units.append(current)
            current = [whole]
        else:
            current.append(whole)
    if current:
        chunk_units.append(current)
    return chunk_units, splits


def _resolve_paste_paths(paste_dir: Path | str) -> tuple[Path, Path, Path]:
    """Return (artifact_dir, model_paste_path, source_map_path).

    Accepts either a review directory or a direct MODEL_PASTE.txt path (same as replay).
    """
    path = Path(paste_dir)
    if path.is_dir():
        artifact_dir = path
        paste_path = path / "MODEL_PASTE.txt"
    else:
        artifact_dir = path.parent
        paste_path = path
    smap_path = artifact_dir / "SOURCE_MAP.json"
    return artifact_dir, paste_path, smap_path


def _load_frozen_parent(paste_dir: Path | str, require_hash: str) -> dict[str, Any]:
    artifact_dir, paste_path, smap_path = _resolve_paste_paths(paste_dir)
    if not paste_path.is_file():
        return {"ok": False, "error": "model_paste_missing", "path": str(paste_path)}
    if not smap_path.is_file():
        return {"ok": False, "error": "source_map_missing", "path": str(smap_path)}
    paste_bytes = paste_path.read_bytes()
    paste_text = paste_bytes.decode("utf-8")
    digest = _sha256_bytes(paste_bytes)
    want = (require_hash or "").strip().lower()
    smap_hint: str | None = None
    if smap_path.is_file():
        try:
            smap_hint = str(
                json.loads(smap_path.read_text(encoding="utf-8")).get("frozen_input_sha256")
                or ""
            ).strip().lower() or None
        except (json.JSONDecodeError, OSError):
            smap_hint = None
    if not want or digest.lower() != want:
        err: dict[str, Any] = {
            "ok": False,
            "error": "parent_hash_mismatch",
            "expected": want,
            "actual": digest,
            "paste_path": str(paste_path),
        }
        if smap_hint:
            err["source_map_frozen_input_sha256"] = smap_hint
            if smap_hint == digest.lower():
                err["hint"] = (
                    "MODEL_PASTE.txt matches SOURCE_MAP.json but not --require-hash. "
                    "Use the actual hash above, or locate the review directory "
                    "for the frozen packet you intended."
                )
            else:
                err["hint"] = (
                    "MODEL_PASTE.txt does not match SOURCE_MAP.json or --require-hash. "
                    "Do not chunk until the paste and sidecar are reconciled."
                )
        else:
            err["hint"] = (
                "Use the actual hash of MODEL_PASTE.txt as --require-hash, or point "
                "--paste-dir at the review directory for the intended frozen packet."
            )
        return err
    smap_bytes = smap_path.read_bytes()
    smap_text = smap_bytes.decode("utf-8")
    smap_sha = _sha256_bytes(smap_bytes)
    try:
        source_map = json.loads(smap_text)
    except json.JSONDecodeError:
        return {"ok": False, "error": "source_map_invalid_json"}
    mapped = str(source_map.get("frozen_input_sha256") or "").strip().lower()
    if mapped != digest.lower():
        report_path = artifact_dir / "PREPARATION_REPORT.txt"
        report_hash: str | None = None
        if report_path.is_file():
            for line in report_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("frozen_input_sha256:"):
                    report_hash = line.split(":", 1)[1].strip().lower()
                    break
        err = {
            "ok": False,
            "error": "source_map_hash_mismatch",
            "paste_sha256": digest,
            "source_map_frozen_input_sha256": mapped,
            "paste_path": str(paste_path),
            "source_map_path": str(smap_path),
        }
        if report_hash:
            err["preparation_report_frozen_input_sha256"] = report_hash
        if report_hash and report_hash == mapped and report_hash != digest.lower():
            err["hint"] = (
                "SOURCE_MAP.json and PREPARATION_REPORT.txt agree, but MODEL_PASTE.txt "
                "on disk was changed after prepare. Restore the original MODEL_PASTE.txt "
                f"for hash {mapped}, resync-trusted-email-review-freeze if the on-disk "
                "paste is the reviewed canonical input, or locate another REVIEW_* directory."
            )
        elif report_hash and report_hash == digest.lower() and report_hash != mapped:
            err["hint"] = (
                "MODEL_PASTE.txt matches PREPARATION_REPORT.txt but SOURCE_MAP.json is "
                "stale. Run resync-trusted-email-review-freeze if the paste is reviewed "
                "canonical, or re-run prepare-trusted-email-review."
            )
        else:
            err["hint"] = (
                "Paste and sidecar disagree. Inspect PREPARATION_REPORT.txt and scan "
                "other REVIEW_* directories for a matching paste/sidecar pair before "
                "chunking."
            )
        return err
    if _MARKER_SYSTEM not in paste_text or _MARKER_USER not in paste_text:
        return {"ok": False, "error": "paste_missing_markers"}
    return {
        "ok": True,
        "paste_dir": str(artifact_dir),
        "paste_path": str(paste_path),
        "source_map_path": str(smap_path),
        "paste_text": paste_text,
        "paste_sha256": digest,
        "source_map_sha256": smap_sha,
        "source_map": source_map,
    }


def _cite_as_in_paste(paste_text: str) -> list[str]:
    if _MARKER_CONV in paste_text:
        _, conv_blob = paste_text.split(_MARKER_CONV, 1)
    else:
        conv_blob = paste_text
    return sorted(set(_CITE_TAG.findall(conv_blob)))


def resync_trusted_email_review_freeze(
    *,
    paste_dir: Path | str,
    require_paste_hash: str,
) -> dict[str, Any]:
    """Align SOURCE_MAP (and LOCAL_MANIFEST) to reviewed MODEL_PASTE on disk.

    Never modifies MODEL_PASTE.txt. Refuses when paste cite_as tags disagree with
    SOURCE_MAP citations — in that case re-prepare instead of patching hashes alone.
    """
    artifact_dir, paste_path, smap_path = _resolve_paste_paths(paste_dir)
    if not paste_path.is_file():
        return {"ok": False, "error": "model_paste_missing", "path": str(paste_path)}
    if not smap_path.is_file():
        return {"ok": False, "error": "source_map_missing", "path": str(smap_path)}
    paste_bytes = paste_path.read_bytes()
    paste_text = paste_bytes.decode("utf-8")
    digest = _sha256_bytes(paste_bytes)
    want = (require_paste_hash or "").strip().lower()
    if not want or digest.lower() != want:
        return {
            "ok": False,
            "error": "paste_hash_mismatch",
            "expected": want,
            "actual": digest,
            "paste_path": str(paste_path),
        }
    if _MARKER_SYSTEM not in paste_text or _MARKER_USER not in paste_text:
        return {"ok": False, "error": "paste_missing_markers"}
    try:
        source_map = json.loads(smap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "error": "source_map_invalid_json"}
    old_hash = str(source_map.get("frozen_input_sha256") or "").strip().lower()
    if old_hash == digest.lower():
        return {
            "ok": True,
            "already_synced": True,
            "paste_dir": str(artifact_dir),
            "paste_sha256": digest,
            "source_map_sha256": _file_sha256(smap_path),
            "models_called": False,
        }
    citations = list(source_map.get("citations") or [])
    paste_cites = _cite_as_in_paste(paste_text)
    smap_cites = sorted(
        {str(c.get("cite_as") or "") for c in citations if c.get("cite_as")}
    )
    missing_in_smap = sorted(set(paste_cites) - set(smap_cites))
    missing_in_paste = sorted(set(smap_cites) - set(paste_cites))
    if missing_in_smap or missing_in_paste:
        return {
            "ok": False,
            "error": "cite_as_mismatch_between_paste_and_source_map",
            "paste_sha256": digest,
            "source_map_frozen_input_sha256": old_hash,
            "missing_in_source_map": missing_in_smap,
            "missing_in_paste": missing_in_paste,
            "hint": (
                "SOURCE_MAP citations do not match the reviewed paste. Re-run "
                "prepare-trusted-email-review; do not patch frozen_input_sha256 alone."
            ),
        }
    source_map["frozen_input_sha256"] = digest
    smap_text = json.dumps(source_map, indent=2, default=str, ensure_ascii=False) + "\n"
    smap_path.write_text(smap_text, encoding="utf-8", newline="\n")
    smap_sha = _sha256_bytes(smap_text.encode("utf-8"))
    manifest_path = artifact_dir / "LOCAL_MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["frozen_input_sha256"] = digest
            manifest_path.write_text(
                json.dumps(manifest, indent=2, default=str, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except json.JSONDecodeError:
            pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_lines = [
        "TRUSTED EMAIL REVIEW — FREEZE RESYNC REPORT",
        f"resynced_at: {stamp}",
        "Models were not called.",
        f"paste_path: {paste_path}",
        f"previous_frozen_input_sha256: {old_hash}",
        f"reviewed_paste_sha256: {digest}",
        f"source_map_sha256: {smap_sha}",
        f"cite_as_n: {len(paste_cites)}",
        "MODEL_PASTE.txt was not modified.",
    ]
    report_path = artifact_dir / "FREEZE_RESYNC_REPORT.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "already_synced": False,
        "paste_dir": str(artifact_dir),
        "paste_sha256": digest,
        "previous_frozen_input_sha256": old_hash,
        "source_map_sha256": smap_sha,
        "source_map_path": str(smap_path),
        "report_path": str(report_path),
        "models_called": False,
        "hint": (
            f"Sidecar synced to reviewed paste. Chunk with --require-hash {digest}."
        ),
    }


def _parse_parent_paste(paste_text: str) -> dict[str, Any]:
    _, rest = paste_text.split(_MARKER_SYSTEM, 1)
    if _REPLAY_BIND_MARK not in rest or _MARKER_USER not in rest:
        return {"ok": False, "error": "paste_structure_invalid"}
    system_part, after_bind = rest.split(_REPLAY_BIND_MARK, 1)
    bind_raw, user = after_bind.split(_MARKER_USER, 1)
    system = system_part.strip()
    binding = extract_replay_binding(paste_text)
    if binding is None:
        try:
            binding = json.loads(bind_raw.strip())
        except json.JSONDecodeError:
            binding = None
    conversations = _parse_conversations(user)
    return {
        "ok": True,
        "system": system,
        "binding": binding,
        "user_header": _user_header(user),
        "conversations": conversations,
    }


def prepare_trusted_email_review_chunks(
    *,
    paste_dir: Path | str,
    require_hash: str,
    target_estimated_tokens: int = DEFAULT_TARGET_ESTIMATED_TOKENS,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Split a frozen parent paste into deterministic local chunk files. No models."""
    artifact_dir, _, _ = _resolve_paste_paths(paste_dir)
    out = Path(out_dir) if out_dir else artifact_dir
    out.mkdir(parents=True, exist_ok=True)
    loaded = _load_frozen_parent(paste_dir, require_hash)
    if not loaded.get("ok"):
        return loaded
    parsed = _parse_parent_paste(loaded["paste_text"])
    if not parsed.get("ok"):
        return parsed
    source_map = loaded["source_map"]
    citations = list(source_map.get("citations") or [])
    conversations = list(parsed["conversations"])
    _attach_citation_times(conversations, citations)
    if not conversations:
        return {"ok": False, "error": "no_conversations_in_parent_paste"}
    binding_json = _chunk_binding_json(source_map)
    user_header = parsed["user_header"]
    chunk_unit_groups, conv_splits = _pack_units(
        conversations,
        target= int(target_estimated_tokens),
        user_header=user_header,
        binding_json=binding_json,
    )
    chunk_m = len(chunk_unit_groups)
    if chunk_m < 1:
        return {"ok": False, "error": "no_chunks_produced"}
    prepared: list[PreparedChunk] = []
    for i, units in enumerate(chunk_unit_groups, start=1):
        system = _chunk_system(i, chunk_m)
        paste = _build_chunk_paste(
            chunk_n=i,
            chunk_m=chunk_m,
            system=system,
            binding_json=binding_json,
            user_header=user_header,
            units=units,
        )
        sha = _sha256_text(paste)
        cite_as = [c for u in units for c in u.cite_as]
        evidence_ids = _evidence_ids_for_cites(cite_as, citations)
        ds, de = _date_range(units)
        est = _estimate_chunk_tokens(paste)
        unavoidable = est > target_estimated_tokens
        unit_splits = [
            {
                "conv_index": u.conv_index,
                "subject": u.subject,
                "split": u.split,
                "split_part": u.split_part,
                "split_parts": u.split_parts,
                "continuation_before": u.continuation_before,
                "continuation_after": u.continuation_after,
            }
            for u in units
            if u.split
        ]
        prepared.append(
            PreparedChunk(
                chunk_index=i,
                units=units,
                system=system,
                user=paste.split(_MARKER_USER, 1)[1],
                binding_json=binding_json,
                paste_text=paste,
                sha256=sha,
                estimated_tokens=est,
                date_start=ds,
                date_end=de,
                conversation_ids=sorted({u.conv_index for u in units}),
                evidence_ids=evidence_ids,
                cite_as=cite_as,
                message_count=len(cite_as),
                conversation_count=len({u.conv_index for u in units}),
                conversation_splits=unit_splits,
                unavoidable_oversize=unavoidable,
            )
        )
        fname = f"CHUNK_{i:03d}_MODEL_PASTE.txt"
        (out / fname).write_text(paste, encoding="utf-8")
    parent_cites = [str(c.get("cite_as") or "") for c in citations if c.get("cite_as")]
    chunk_cites: list[str] = []
    for ch in prepared:
        chunk_cites.extend(ch.cite_as)
    missing = sorted(set(parent_cites) - set(chunk_cites))
    duplicate = sorted({c for c in chunk_cites if chunk_cites.count(c) > 1})
    budget = source_map.get("budget") or {}
    capacity = str(budget.get("capacity_certainty") or "estimate_only")
    manifest = {
        "parent_packet_sha256": loaded["paste_sha256"],
        "source_map_sha256": loaded["source_map_sha256"],
        "chunk_count": chunk_m,
        "target_estimated_tokens": int(target_estimated_tokens),
        "advertised_context": ADVERTISED_CONTEXT,
        "output_reserve": OUTPUT_RESERVE,
        "safety_reserve": SAFETY_RESERVE,
        "usable_input_tokens": USABLE_INPUT_TOKENS,
        "capacity_certainty": capacity,
        "estimation_method": "bytes_div_4_including_system_binding_metadata",
        "models_called": False,
        "conversation_splits": conv_splits,
        "evidence_id_audit": {
            "parent_cite_as_n": len(parent_cites),
            "chunk_cite_as_n": len(chunk_cites),
            "missing_cite_as": missing,
            "duplicate_cite_as": duplicate,
            "ok": not missing and not duplicate,
        },
        "chunks": [
            {
                "chunk_index": ch.chunk_index,
                "chunk_sha256": ch.sha256,
                "paste_file": f"CHUNK_{ch.chunk_index:03d}_MODEL_PASTE.txt",
                "deterministic_order": ch.chunk_index,
                "date_range": {"start": ch.date_start, "end": ch.date_end},
                "conversation_ids": ch.conversation_ids,
                "evidence_ids": ch.evidence_ids,
                "cite_as": ch.cite_as,
                "message_count": ch.message_count,
                "conversation_count": ch.conversation_count,
                "estimated_input_tokens": ch.estimated_tokens,
                "estimation_method": "bytes_div_4_including_system_binding_metadata",
                "target_estimated_tokens": int(target_estimated_tokens),
                "advertised_context": ADVERTISED_CONTEXT,
                "output_reserve": OUTPUT_RESERVE,
                "safety_reserve": SAFETY_RESERVE,
                "capacity_certainty": capacity,
                "conversation_splits": ch.conversation_splits,
                "unavoidable_oversize": ch.unavoidable_oversize,
            }
            for ch in prepared
        ],
    }
    (out / "CHUNK_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    report_lines = [
        "TRUSTED EMAIL REVIEW — CHUNK PREPARATION REPORT",
        "Models were not called.",
        f"parent_packet_sha256: {loaded['paste_sha256']}",
        f"source_map_sha256: {loaded['source_map_sha256']}",
        f"chunk_count: {chunk_m}",
        f"target_estimated_tokens: {target_estimated_tokens}",
        f"advertised_context: {ADVERTISED_CONTEXT}",
        f"output_reserve: {OUTPUT_RESERVE}",
        f"safety_reserve: {SAFETY_RESERVE}",
        f"capacity_certainty: {capacity}",
        f"evidence_id_audit_ok: {manifest['evidence_id_audit']['ok']}",
        f"missing_cite_as: {json.dumps(missing)}",
        f"duplicate_cite_as: {json.dumps(duplicate)}",
        f"conversation_splits: {json.dumps(conv_splits)}",
    ]
    for ch in prepared:
        report_lines.append(
            f"chunk_{ch.chunk_index:03d}: sha256={ch.sha256} "
            f"tokens~={ch.estimated_tokens} messages={ch.message_count} "
            f"conversations={ch.conversation_count} "
            f"dates={ch.date_start}..{ch.date_end} "
            f"oversize_unavoidable={ch.unavoidable_oversize}"
        )
    report = "\n".join(report_lines) + "\n"
    (out / "CHUNK_PREPARATION_REPORT.txt").write_text(report, encoding="utf-8")
    if missing or duplicate:
        return {
            "ok": False,
            "error": "evidence_id_audit_failed",
            "manifest": manifest,
            "preparation_report_text": report,
        }
    return {
        "ok": True,
        "models_called": False,
        "parent_packet_sha256": loaded["paste_sha256"],
        "source_map_sha256": loaded["source_map_sha256"],
        "chunk_count": chunk_m,
        "manifest_path": str(out / "CHUNK_MANIFEST.json"),
        "report_path": str(out / "CHUNK_PREPARATION_REPORT.txt"),
        "preparation_report_text": report,
        "manifest": manifest,
        "chunks": [
            {
                "chunk_index": ch.chunk_index,
                "chunk_sha256": ch.sha256,
                "paste_file": f"CHUNK_{ch.chunk_index:03d}_MODEL_PASTE.txt",
                "estimated_input_tokens": ch.estimated_tokens,
            }
            for ch in prepared
        ],
    }


def plan_trusted_email_review_chunk_gemma(
    *,
    paste_dir: Path | str,
    require_parent_hash: str,
    chunk_index: int,
    require_chunk_hash: str,
) -> dict[str, Any]:
    """Build one chunk Ollama request or refuse. No network."""
    from memorybox.providers.llm._ollama_http import ollama_chat_request_payload

    artifact_dir, _, _ = _resolve_paste_paths(paste_dir)
    parent = _load_frozen_parent(paste_dir, require_parent_hash)
    if not parent.get("ok"):
        return parent
    manifest_path = artifact_dir / "CHUNK_MANIFEST.json"
    if not manifest_path.is_file():
        return {"ok": False, "error": "chunk_manifest_missing"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(manifest.get("parent_packet_sha256") or "").lower() != str(
        parent["paste_sha256"]
    ).lower():
        return {"ok": False, "error": "manifest_parent_hash_mismatch"}
    rows = [c for c in (manifest.get("chunks") or []) if int(c.get("chunk_index") or 0) == int(chunk_index)]
    if not rows:
        return {"ok": False, "error": "chunk_index_not_in_manifest", "chunk_index": chunk_index}
    row = rows[0]
    chunk_file = artifact_dir / str(row.get("paste_file") or "")
    if not chunk_file.is_file():
        return {"ok": False, "error": "chunk_paste_missing", "path": str(chunk_file)}
    chunk_text = chunk_file.read_text(encoding="utf-8")
    chunk_sha = _sha256_text(chunk_text)
    want_chunk = (require_chunk_hash or "").strip().lower()
    if not want_chunk or chunk_sha.lower() != want_chunk:
        return {
            "ok": False,
            "error": "chunk_hash_mismatch",
            "expected": want_chunk,
            "actual": chunk_sha,
        }
    env_ctx = (os.environ.get("MEMORYBOX_FEV2_OLLAMA_NUM_CTX") or "").strip()
    if not env_ctx.isdigit() or int(env_ctx) != ADVERTISED_CONTEXT:
        return {
            "ok": False,
            "error": "fev2_num_ctx_required",
            "required": str(ADVERTISED_CONTEXT),
            "observed": env_ctx or None,
        }
    if _MARKER_SYSTEM not in chunk_text or _MARKER_USER not in chunk_text:
        return {"ok": False, "error": "chunk_paste_missing_markers"}
    _, rest = chunk_text.split(_MARKER_SYSTEM, 1)
    system, after_bind = rest.split(_REPLAY_BIND_MARK, 1)
    bind_raw, user = after_bind.split(_MARKER_USER, 1)
    system = system.strip()
    user = user.strip()
    if "partial evidence" not in system.lower() and "chunk" not in system.lower():
        return {"ok": False, "error": "chunk_system_missing_partial_warning"}
    try:
        binding = json.loads(bind_raw.strip())
    except json.JSONDecodeError:
        return {"ok": False, "error": "chunk_binding_invalid"}
    if int(binding.get("num_ctx") or 0) != ADVERTISED_CONTEXT:
        return {"ok": False, "error": "chunk_binding_num_ctx_mismatch"}
    if int(binding.get("num_predict") or 0) != OUTPUT_RESERVE:
        return {"ok": False, "error": "chunk_binding_num_predict_mismatch"}
    est = int(row.get("estimated_input_tokens") or _estimate_chunk_tokens(chunk_text))
    if est > USABLE_INPUT_TOKENS:
        return {
            "ok": False,
            "error": "chunk_oversize_for_reviewed_budget",
            "estimated_input_tokens": est,
            "usable_input_tokens": USABLE_INPUT_TOKENS,
        }
    model = str(binding.get("model") or ESTABLISHED_GEMMA_MODEL)
    payload = ollama_chat_request_payload(
        model,
        system,
        user,
        format_json=True,
        temperature=float(binding.get("temperature") or 0.1),
        num_ctx=ADVERTISED_CONTEXT,
        num_predict=OUTPUT_RESERVE,
    )
    return {
        "ok": True,
        "provider": "ollama",
        "model": model,
        "parent_packet_sha256": parent["paste_sha256"],
        "chunk_index": int(chunk_index),
        "chunk_sha256": chunk_sha,
        "estimated_input_tokens": est,
        "request_payload": payload,
        "replay_binding": binding,
        "num_ctx": ADVERTISED_CONTEXT,
        "num_predict": OUTPUT_RESERVE,
        "chunking": True,
        "models_called": False,
    }


def run_trusted_email_review_chunk_gemma(
    *,
    paste_dir: Path | str,
    require_parent_hash: str,
    chunk_index: int,
    require_chunk_hash: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """Run Gemma on one explicitly selected chunk only."""
    from memorybox.ask.i11a.trusted_email_review import apply_flightsim_app_env
    from memorybox.config import OLLAMA_AUTODETECT_URLS, settings
    from memorybox.providers.llm._ollama_http import (
        ollama_chat,
        ollama_has_model,
        ollama_reachable,
    )

    apply_flightsim_app_env()
    plan = plan_trusted_email_review_chunk_gemma(
        paste_dir=paste_dir,
        require_parent_hash=require_parent_hash,
        chunk_index=chunk_index,
        require_chunk_hash=require_chunk_hash,
    )
    if not plan.get("ok"):
        return plan
    base = (settings.ollama_base_url or "").strip()
    if not base:
        for url in OLLAMA_AUTODETECT_URLS:
            if ollama_reachable(url):
                base = url
                break
    model = str(plan.get("model") or ESTABLISHED_GEMMA_MODEL)
    if not base or not ollama_has_model(base, model):
        return {
            "ok": False,
            "error": f"ollama_model_missing:{model}",
            "skipped": True,
            "provider": "ollama",
            "request_payload": plan.get("request_payload"),
        }
    req = plan["request_payload"]
    t0 = time.monotonic()
    content, usage = ollama_chat(
        base,
        model,
        req["messages"][0]["content"],
        req["messages"][1]["content"],
        format_json=True,
        timeout=int(timeout_seconds),
        num_ctx=int(plan["num_ctx"]),
        num_predict=int(plan["num_predict"]),
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    out_dir = artifact_dir
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"CHUNK_{int(chunk_index):03d}_GEMMA_{stamp}"
    result = {
        "ok": True,
        "provider": "ollama",
        "model": model,
        "parent_packet_sha256": plan.get("parent_packet_sha256"),
        "chunk_index": int(chunk_index),
        "chunk_sha256": plan.get("chunk_sha256"),
        "request_payload": req,
        "raw": content,
        "usage": usage,
        "elapsed_ms": elapsed_ms,
        "prompt_eval_count": (usage or {}).get("prompt_eval_count"),
        "eval_count": (usage or {}).get("eval_count"),
        "chunking": True,
    }
    (out_dir / f"{base_name}_request.json").write_text(
        json.dumps(req, indent=2, default=str),
        encoding="utf-8",
    )
    (out_dir / f"{base_name}_response.json").write_text(
        json.dumps(result, indent=2, default=str),
        encoding="utf-8",
    )
    return result
