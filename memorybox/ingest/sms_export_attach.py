"""P2-BL-I7-01: join Export Attachments filenames onto existing SMS rows.

Vendor CSV names are usually UUID-style. The Downloads dump uses
`YYYY-MM-DD HH MM SS - Chat - Type`. UUID/exact matching stays first.
Same-second collisions stay unmatched. Files without a message are
orphans — this module never invents messages.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from memorybox.ingest.sms_attach_cache import media_object_path, put_media_object

_EXPORT_PREFIX = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<h>\d{2}) (?P<m>\d{2}) (?P<s>\d{2}) - (?P<rest>.+)$"
)
_ISO_WALL = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2}):(\d{2})")
_COLLISION_SUFFIX = re.compile(r"-\d+$")
_PHONE_LIKE = re.compile(r"^[+\d][\d\s\-().]{5,}$")
_UUID_IN_NAME = re.compile(
    r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})"
)
_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    "__pycache__",
    "node_modules",
    "sms-attachments",
}
_TYPE_LABELS = (
    "web link",
    "voice message",
    "voice memo",
    "contact card",
    "photo",
    "video",
    "audio",
    "attachment",
    "sticker",
    "location",
    "animated",
    "gif",
    "document",
    "file",
)
_INDEX: "ExportAttachIndex | None" = None
_INDEX_KEY = ""


@dataclass(frozen=True)
class ParsedExportName:
    wall_clock: str
    chat: str
    attach_type: str
    filename: str


@dataclass(frozen=True)
class ExportFile:
    path: Path
    wall_clock: str
    chat: str
    folder_chat: str
    parsed_chat: str
    attach_type: str
    name: str


@dataclass
class OpenSlot:
    evidence_id: UUID
    att_index: int
    wall_clock: str
    thread_id: str
    group_name: str
    sender_name: str
    participants: list[str]
    attachment_type: str
    filename: str


@dataclass
class ExportAttachIndex:
    files: list[ExportFile] = field(default_factory=list)
    by_name: dict[str, Path] = field(default_factory=dict)
    by_uuid: dict[str, Path] = field(default_factory=dict)
    roots: list[Path] = field(default_factory=list)

    def lookup_uuid_or_name(self, name: str) -> Path | None:
        key = (name or "").casefold()
        if key and key in self.by_name:
            return self.by_name[key]
        uuid_m = _UUID_IN_NAME.search(name or "")
        if uuid_m:
            hit = self.by_uuid.get(uuid_m.group(1).casefold())
            if hit is not None:
                return hit
            compact = uuid_m.group(1).replace("-", "").casefold()
            hit = self.by_uuid.get(compact)
            if hit is not None:
                return hit
        if "__" in (name or ""):
            after = Path(name).name.split("__", 1)[1].casefold()
            if after in self.by_name:
                return self.by_name[after]
        return None


def wall_clock_from_sent_at(sent_at: str | None) -> str | None:
    text = (sent_at or "").strip()
    if not text:
        return None
    m = _ISO_WALL.search(text)
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}"


def _strip_collision_suffix(text: str) -> str:
    return _COLLISION_SUFFIX.sub("", (text or "").strip())


def normalize_chat(text: str) -> str:
    cleaned = _strip_collision_suffix(text or "")
    return re.sub(r"\s+", " ", cleaned).strip().casefold()


def chat_tokens(text: str) -> list[str]:
    return [part.strip() for part in normalize_chat(text).split("&") if part.strip()]


def _name_prefix(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) < 3:
        return False
    if not longer.startswith(shorter):
        return False
    rest = longer[len(shorter) :]
    if rest == "" or rest[0] in {" ", "-"}:
        return True
    # Export names often truncate mid-token ("Rick Geor" / "Rick George").
    return len(shorter) >= 4 and rest.replace(" ", "").isalpha()


def chat_matches(
    export_chat: str,
    *,
    thread_id: str = "",
    group_name: str = "",
) -> bool:
    export_n = normalize_chat(export_chat)
    if not export_n:
        return False
    for label in (thread_id, group_name):
        raw = str(label or "").strip()
        if not raw or _PHONE_LIKE.match(raw):
            continue
        label_n = normalize_chat(raw)
        if export_n == label_n:
            return True
        export_parts = chat_tokens(export_chat)
        label_parts = chat_tokens(raw)
        if (
            export_parts
            and label_parts
            and len(export_parts) == len(label_parts)
            and all(_name_prefix(a, b) for a, b in zip(export_parts, label_parts))
        ):
            return True
    return False


def _split_chat_type(rest: str) -> tuple[str, str]:
    text = (rest or "").strip()
    if " - " not in text:
        return text, ""
    chat, typ = text.rsplit(" - ", 1)
    typ_n = typ.strip().casefold()
    if any(typ_n == label or typ_n.startswith(label) for label in _TYPE_LABELS):
        return chat.strip(), typ.strip()
    return text, ""


def parse_export_filename(name: str) -> ParsedExportName | None:
    base = Path(name or "").name
    if not base or base.startswith("."):
        return None
    m = _EXPORT_PREFIX.match(base)
    if not m:
        return None
    rest = m.group("rest")
    suffix = Path(base).suffix
    rest_no_ext = rest
    if suffix and rest.lower().endswith(suffix.lower()):
        rest_no_ext = rest[: -len(suffix)]
    chat, typ = _split_chat_type(rest_no_ext)
    if not chat:
        return None
    wall = f"{m.group('date')} {m.group('h')}:{m.group('m')}:{m.group('s')}"
    return ParsedExportName(
        wall_clock=wall,
        chat=chat,
        attach_type=typ,
        filename=base,
    )


def attachment_search_roots(payload: dict[str, Any] | None = None) -> list[Path]:
    roots: list[Path] = []
    extra = (os.environ.get("MEMORYBOX_SMS_ATTACHMENTS_DIR") or "").strip()
    if extra:
        roots.append(Path(extra).expanduser())
    src = (os.environ.get("MEMORYBOX_SOURCES_ROOT") or "").strip()
    if src:
        roots.append(Path(src) / "sms-attachments")
        roots.append(Path(src) / "sms")
    roots.append(Path(r"\\media-server\photos\MemoryBox\Sources\sms-attachments"))
    if payload:
        cov = payload.get("source_coverage") or {}
        loc = str(payload.get("source_locator") or "")
        import_path = str(cov.get("import_path") or "")
        if not import_path and "#row=" in loc:
            import_path = loc.split("#row=", 1)[0]
        if import_path:
            p = Path(import_path)
            parent = p.parent if p.suffix.lower() == ".csv" else p
            roots.append(parent)
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(root)
    return out


def reset_export_index() -> None:
    global _INDEX, _INDEX_KEY
    _INDEX = None
    _INDEX_KEY = ""


def _remember_name(index: ExportAttachIndex, path: Path) -> None:
    name = path.name
    index.by_name[name.casefold()] = path
    if "__" in name:
        index.by_name[name.split("__", 1)[-1].casefold()] = path
    uuid_m = _UUID_IN_NAME.search(name)
    if uuid_m:
        index.by_uuid[uuid_m.group(1).casefold()] = path
        index.by_uuid[uuid_m.group(1).replace("-", "").casefold()] = path


def build_export_index(roots: Iterable[Path], *, depth: int = 4) -> ExportAttachIndex:
    index = ExportAttachIndex(roots=list(roots))
    seen_paths: set[str] = set()
    seen_roots: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key in seen_roots:
            continue
        seen_roots.add(key)
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        stack: list[tuple[Path, int, str]] = [(root, 0, "")]
        while stack:
            cur, level, folder_chat = stack.pop()
            try:
                children = list(cur.iterdir())
            except OSError:
                continue
            for child in children:
                try:
                    loc = str(child.resolve()) if child.exists() else str(child)
                except OSError:
                    loc = str(child)
                if loc.casefold() in seen_paths:
                    continue
                try:
                    if child.is_file():
                        if not child.stat().st_size:
                            continue
                        seen_paths.add(loc.casefold())
                        _remember_name(index, child)
                        parsed = parse_export_filename(child.name)
                        if parsed is None:
                            continue
                        chat = folder_chat or parsed.chat
                        index.files.append(
                            ExportFile(
                                path=child,
                                wall_clock=parsed.wall_clock,
                                chat=chat,
                                folder_chat=folder_chat,
                                parsed_chat=parsed.chat,
                                attach_type=parsed.attach_type,
                                name=child.name,
                            )
                        )
                    elif child.is_dir() and level < depth:
                        if child.name.casefold() in _SKIP_DIR_NAMES:
                            continue
                        next_chat = folder_chat
                        if level == 0:
                            next_chat = child.name
                        stack.append((child, level + 1, next_chat))
                except OSError:
                    continue
    return index


def get_export_index(roots: list[Path] | None = None) -> ExportAttachIndex:
    global _INDEX, _INDEX_KEY
    use = list(roots or attachment_search_roots())
    key = "|".join(str(p) for p in use)
    if _INDEX is not None and _INDEX_KEY == key:
        return _INDEX
    _INDEX = build_export_index(use)
    _INDEX_KEY = key
    return _INDEX


def _file_chats(item: ExportFile) -> list[str]:
    if item.folder_chat:
        return [item.folder_chat]
    out: list[str] = []
    for raw in (item.chat, item.parsed_chat):
        if raw and raw not in out:
            out.append(raw)
    return out


def file_matches_slot(item: ExportFile, slot: OpenSlot) -> bool:
    if item.wall_clock != slot.wall_clock:
        return False
    return any(
        chat_matches(chat, thread_id=slot.thread_id, group_name=slot.group_name)
        for chat in _file_chats(item)
    )


def unique_export_pairs(
    files: list[ExportFile], slots: list[OpenSlot]
) -> tuple[list[tuple[OpenSlot, ExportFile]], dict[str, int]]:
    """1 file + 1 slot only. Any same-second collision stays unmatched."""
    file_to_slots: list[list[int]] = []
    slot_to_files: list[list[int]] = [[] for _ in slots]
    for fi, item in enumerate(files):
        hits: list[int] = []
        for si, slot in enumerate(slots):
            if file_matches_slot(item, slot):
                hits.append(si)
                slot_to_files[si].append(fi)
        file_to_slots.append(hits)

    pairs: list[tuple[OpenSlot, ExportFile]] = []
    used_files: set[int] = set()
    used_slots: set[int] = set()
    ambiguous_slots: set[int] = set()
    for si, fis in enumerate(slot_to_files):
        if len(fis) != 1:
            if len(fis) > 1:
                ambiguous_slots.add(si)
            continue
        fi = fis[0]
        if len(file_to_slots[fi]) != 1:
            if len(file_to_slots[fi]) > 1:
                ambiguous_slots.update(file_to_slots[fi])
            continue
        pairs.append((slots[si], files[fi]))
        used_files.add(fi)
        used_slots.add(si)

    orphan_files = sum(1 for i, hits in enumerate(file_to_slots) if i not in used_files and not hits)
    collision_files = sum(1 for i, hits in enumerate(file_to_slots) if i not in used_files and hits)
    return pairs, {
        "unique": len(pairs),
        "ambiguous_slots": len(ambiguous_slots),
        "orphan_files": orphan_files,
        "collision_files": collision_files,
        "unmatched_slots": sum(1 for i in range(len(slots)) if i not in used_slots),
    }


def _payload_dict(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _open_slots(rows: list[dict[str, Any]], *, conn: Any) -> list[OpenSlot]:
    slots: list[OpenSlot] = []
    for row in rows:
        payload = _payload_dict(row)
        atts = [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]
        if not atts:
            continue
        wall = wall_clock_from_sent_at(str(payload.get("sent_at") or ""))
        if not wall:
            continue
        eid = row["id"]
        thread_id = str(payload.get("thread_id") or "")
        group_name = str(payload.get("group_name") or "")
        sender_name = str(payload.get("sender_name") or "")
        participants = [
            str(p) for p in (payload.get("participants") or []) if str(p).strip()
        ]
        for idx, att in enumerate(atts):
            mid = str(att.get("media_object_id") or "").strip()
            if mid and media_object_path(mid, conn=conn) is not None:
                continue
            slots.append(
                OpenSlot(
                    evidence_id=eid,
                    att_index=idx,
                    wall_clock=wall,
                    thread_id=thread_id,
                    group_name=group_name,
                    sender_name=sender_name,
                    participants=participants,
                    attachment_type=str(att.get("attachment_type") or ""),
                    filename=str(att.get("filename") or ""),
                )
            )
    return slots


def backfill_unique_export_attachments(
    source_id: UUID,
    *,
    conn: Any,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Copy uniquely matched export files onto existing SMS evidence. Not Immich."""
    from memorybox.ingest import store as store

    index = get_export_index(roots)
    rows = store.list_evidence_for_source(source_id, conn=conn)
    slots = _open_slots(rows, conn=conn)
    pairs, stats = unique_export_pairs(index.files, slots)
    stored = 0
    by_eid: dict[UUID, list[tuple[int, ExportFile]]] = {}
    for slot, item in pairs:
        by_eid.setdefault(slot.evidence_id, []).append((slot.att_index, item))
    for eid, items in by_eid.items():
        row = store.get_evidence(eid, conn=conn)
        if not row:
            continue
        payload = _payload_dict(row)
        atts = [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]
        changed = False
        for idx, item in items:
            if idx < 0 or idx >= len(atts):
                continue
            att = atts[idx]
            try:
                data = item.path.read_bytes()
            except OSError:
                continue
            if not data:
                continue
            rec = put_media_object(
                data,
                str(att.get("filename") or item.name),
                source_id=source_id,
                conn=conn,
                mime_type=str(att.get("mime_type") or "") or None,
            )
            if rec is None:
                continue
            att["media_object_id"] = rec["media_object_id"]
            att["content_hash"] = rec["content_hash"]
            att["byte_size"] = rec["byte_size"]
            att["mime_type"] = rec.get("mime_type") or att.get("mime_type")
            att["resolved_path"] = rec["uri"]
            att["bytes_present"] = True
            att["bytes_ingested"] = True
            att["promoted_to_immich"] = False
            att["standalone_explore_media"] = False
            att["match_method"] = "export_unique"
            att["export_filename"] = item.name
            changed = True
            stored += 1
        if changed:
            payload["attachments"] = atts
            store.update_evidence_payload(eid, payload, conn=conn)
    still_missing = 0
    rows = store.list_evidence_for_source(source_id, conn=conn)
    for row in rows:
        payload = _payload_dict(row)
        for att in payload.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            mid = str(att.get("media_object_id") or "").strip()
            if mid and media_object_path(mid, conn=conn) is not None:
                continue
            still_missing += 1
    return {
        "stored": stored,
        "unique": stats["unique"],
        "ambiguous_slots": stats["ambiguous_slots"],
        "orphan_files": stats["orphan_files"],
        "collision_files": stats["collision_files"],
        "unmatched_slots": stats["unmatched_slots"],
        "still_missing": still_missing,
        "export_files_indexed": len(index.files),
    }


def self_check() -> dict[str, bool]:
    """Pure matcher checks — no database, no message invention."""
    sample = "2019-12-11 18 34 38 - Andrew George & Peggy George & Rick Geor-2 - Web link"
    parsed = parse_export_filename(sample)
    photo = parse_export_filename("2020-03-15 14 02 00 - Peggy - Photo.jpg")
    unique_file = ExportFile(
        path=Path("Peggy/2020-03-15 14 02 00 - Peggy - Photo.jpg"),
        wall_clock="2020-03-15 14:02:00",
        chat="Peggy",
        folder_chat="Peggy",
        parsed_chat="Peggy",
        attach_type="Photo",
        name="2020-03-15 14 02 00 - Peggy - Photo.jpg",
    )
    unique_slot = OpenSlot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000001"),
        att_index=0,
        wall_clock="2020-03-15 14:02:00",
        thread_id="Peggy",
        group_name="",
        sender_name="Tom Will",
        participants=["Peggy"],
        attachment_type="image",
        filename="78715179111__AF89223C-3F6A-417B-A3C2-485DF14A8835.JPG",
    )
    group_chat = "Andrew George & Peggy George & Rick George"
    collide_a = ExportFile(
        path=Path("g/a.jpg"),
        wall_clock="2019-12-11 18:34:38",
        chat=group_chat,
        folder_chat=group_chat,
        parsed_chat="Andrew George & Peggy George & Rick Geor",
        attach_type="Photo",
        name="2019-12-11 18 34 38 - Andrew George & Peggy George & Rick Geor - Photo.jpg",
    )
    collide_b = ExportFile(
        path=Path("g/b.jpg"),
        wall_clock="2019-12-11 18:34:38",
        chat=group_chat,
        folder_chat=group_chat,
        parsed_chat="Andrew George & Peggy George & Rick Geor-2",
        attach_type="Photo",
        name="2019-12-11 18 34 38 - Andrew George & Peggy George & Rick Geor-2 - Photo.jpg",
    )
    slot_g1 = OpenSlot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000002"),
        att_index=0,
        wall_clock="2019-12-11 18:34:38",
        thread_id=group_chat,
        group_name="",
        sender_name="",
        participants=[],
        attachment_type="image",
        filename="a.JPG",
    )
    slot_g2 = OpenSlot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000003"),
        att_index=0,
        wall_clock="2019-12-11 18:34:38",
        thread_id=group_chat,
        group_name="",
        sender_name="",
        participants=[],
        attachment_type="image",
        filename="b.JPG",
    )
    orphan = ExportFile(
        path=Path("other/2018-01-01 00 00 00 - Other - Photo.jpg"),
        wall_clock="2018-01-01 00:00:00",
        chat="Other",
        folder_chat="Other",
        parsed_chat="Other",
        attach_type="Photo",
        name="2018-01-01 00 00 00 - Other - Photo.jpg",
    )
    pairs_ok, stats_ok = unique_export_pairs([unique_file], [unique_slot])
    pairs_bad, stats_bad = unique_export_pairs(
        [collide_a, collide_b, orphan], [slot_g1, slot_g2]
    )
    return {
        "parse_web_link": bool(
            parsed
            and parsed.wall_clock == "2019-12-11 18:34:38"
            and parsed.attach_type.lower() == "web link"
            and "Andrew George" in parsed.chat
        ),
        "parse_photo": bool(
            photo
            and photo.wall_clock == "2020-03-15 14:02:00"
            and photo.chat == "Peggy"
            and photo.attach_type.lower() == "photo"
        ),
        "chat_truncated_group": chat_matches(
            "Andrew George & Peggy George & Rick Geor-2",
            thread_id=group_chat,
        ),
        "chat_rejects_other": not chat_matches("Peggy", thread_id=group_chat),
        "wall_clock_iso": wall_clock_from_sent_at("2020-03-15T14:02:00+00:00")
        == "2020-03-15 14:02:00",
        "unique_pairs": len(pairs_ok) == 1 and stats_ok["unique"] == 1,
        "collision_unmatched": len(pairs_bad) == 0
        and stats_bad["ambiguous_slots"] == 2
        and stats_bad["orphan_files"] == 1,
    }
