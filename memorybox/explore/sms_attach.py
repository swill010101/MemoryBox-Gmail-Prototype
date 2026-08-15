"""Serve SMS/iMessage attachments and copy them into MemoryBox (not Immich)."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import zipfile
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ingest.comms_sms import default_sms_export_path
from memorybox.ingest.sms_attach_cache import (
    cache_get,
    cache_put,
    cache_root,
    media_object_path,
)
from memorybox.ingest.store import get_evidence

_UUID_IN_NAME = re.compile(
    r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})"
)


class SmsAttachError(Exception):
    pass


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    atts = [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]
    if atts:
        return atts
    meta = payload.get("source_metadata") or {}
    if not isinstance(meta, dict):
        return []
    raw = str(meta.get("Attachment") or meta.get("attachment") or "").strip()
    if not raw:
        return []
    kind = str(meta.get("Attachment type") or meta.get("attachment_type") or "").strip()
    return [
        {
            "filename": Path(raw).name,
            "source_ref": raw,
            "attachment_type": kind or None,
        }
    ]


def _search_roots(payload: dict[str, Any] | None = None) -> list[Path]:
    roots: list[Path] = [cache_root()]
    extra = (os.environ.get("MEMORYBOX_SMS_ATTACHMENTS_DIR") or "").strip()
    if extra:
        roots.append(Path(extra).expanduser())
    export = default_sms_export_path()
    if export is not None:
        parent = export.parent
        stem = export.stem
        roots.extend(
            [
                parent,
                parent / stem,
                parent / f"{stem} Attachments",
                parent / f"{stem}_Attachments",
                parent / "Messages Attachments",
                parent / "sms-attachments",
                parent / "attachments",
                parent / "Attachments",
            ]
        )
    src = (os.environ.get("MEMORYBOX_SOURCES_ROOT") or "").strip()
    if src:
        roots.append(Path(src) / "sms")
        roots.append(Path(src) / "sms-attachments")
    roots.append(Path(r"\\media-server\photos\MemoryBox\Sources\sms"))
    roots.append(Path(r"\\media-server\photos\MemoryBox\Sources\sms-attachments"))
    roots.extend(_payload_roots(payload))
    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _name_forms(name: str) -> list[str]:
    forms = [name]
    stem = Path(name).stem
    suffix = Path(name).suffix
    if "__" in stem:
        after = stem.split("__", 1)[1]
        forms.extend([after + suffix, after])
    uuid_m = _UUID_IN_NAME.search(name)
    if uuid_m:
        u = uuid_m.group(1)
        forms.extend([u + suffix, u + suffix.lower(), u + suffix.upper(), u.replace("-", "") + suffix])
    out: list[str] = []
    seen: set[str] = set()
    for item in forms:
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dir_candidates(root: Path, name: str) -> list[Path]:
    names = _name_forms(name)
    hits: list[Path] = []
    for item in names:
        hits.extend(
            [
                root / item,
                root / "attachments" / item,
                root / "Attachments" / item,
                root / "SMS Attachments" / item,
                root / "iMessage Attachments" / item,
                root / "iMazing Attachments" / item,
            ]
        )
    prefix = name.split("__", 1)[0] if "__" in name else ""
    if prefix:
        for item in names:
            hits.extend(
                [
                    root / prefix / item,
                    root / prefix / "attachments" / item,
                    root / prefix / "Attachments" / item,
                    root / f"+{prefix}" / item,
                    root / f"+1{prefix}" / item,
                ]
            )
    try:
        if not root.is_dir():
            return hits
        for child in root.iterdir():
            if not child.is_dir():
                continue
            for item in names:
                hits.append(child / item)
                hits.append(child / "attachments" / item)
                hits.append(child / "Attachments" / item)
            try:
                for grand in child.iterdir():
                    if grand.is_dir():
                        for item in names:
                            hits.append(grand / item)
                            hits.append(grand / "attachments" / item)
                            hits.append(grand / "Attachments" / item)
            except OSError:
                continue
    except OSError:
        return hits
    return hits


def _name_matches(found: str, wanted: str, uuid: str | None) -> bool:
    a = found.casefold()
    b = wanted.casefold()
    if a == b:
        return True
    if a.endswith(b) or b.endswith(a):
        return True
    if "__" in b:
        suffix = b.split("__", 1)[-1]
        if suffix and a.endswith(suffix):
            return True
    if uuid:
        compact = uuid.replace("-", "").casefold()
        if uuid.casefold() in a or compact in a.replace("-", ""):
            return True
    return False


def _walk_match(root: Path, name: str, uuid: str | None, *, depth: int = 3) -> Path | None:
    """Bounded directory walk — do not recurse a whole NAS share."""
    try:
        if not root.is_dir():
            return None
    except OSError:
        return None
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        cur, level = stack.pop()
        try:
            children = list(cur.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                if child.is_file() and _name_matches(child.name, name, uuid):
                    return child
                if child.is_dir() and level < depth:
                    stack.append((child, level + 1))
            except OSError:
                continue
    return None


_INDEX: dict[str, str] | None = None
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff"}


def _payload_roots(payload: dict[str, Any] | None) -> list[Path]:
    roots: list[Path] = []
    if not payload:
        return roots
    cov = payload.get("source_coverage") or {}
    loc = str(payload.get("source_locator") or "")
    import_path = str(cov.get("import_path") or "")
    if not import_path and "#row=" in loc:
        import_path = loc.split("#row=", 1)[0]
    if import_path:
        p = Path(import_path)
        parent = p.parent if p.suffix.lower() == ".csv" else p
        stem = p.stem
        roots.extend(
            [
                parent,
                parent / stem,
                parent / f"{stem} Attachments",
                parent / f"{stem}_Attachments",
                parent / "Messages Attachments",
                parent / "sms-attachments",
                parent / "attachments",
                parent / "Attachments",
            ]
        )
    return roots


def _index_file() -> Path:
    return Path(__file__).resolve().parents[2] / ".memorybox_sms_attach_index.json"


def _remember_index_hit(keys: list[str], path: Path) -> None:
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
    loc = str(path)
    for key in keys:
        if key:
            _INDEX[key] = loc


def _lookup_index(name: str, uuid: str | None) -> Path | None:
    global _INDEX
    if _INDEX is None:
        try:
            raw = json.loads(_index_file().read_text(encoding="utf-8"))
            _INDEX = raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError):
            _INDEX = {}
    keys = [name.casefold()]
    if "__" in name:
        keys.append(name.split("__", 1)[-1].casefold())
    if uuid:
        keys.append(uuid.casefold())
        keys.append(uuid.replace("-", "").casefold())
    for key in keys:
        hit = _INDEX.get(key)
        if not hit:
            continue
        p = Path(hit)
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def _index_file_entry(path: Path) -> None:
    name = path.name
    uuid_m = _UUID_IN_NAME.search(name)
    keys = [name.casefold()]
    if "__" in name:
        keys.append(name.split("__", 1)[-1].casefold())
    if uuid_m:
        keys.append(uuid_m.group(1).casefold())
        keys.append(uuid_m.group(1).replace("-", "").casefold())
    _remember_index_hit(keys, path)


def _build_attach_index(roots: list[Path], *, depth: int = 6) -> None:
    """One-time walk so iMazing UUID filenames resolve after the first miss."""
    seen: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            cur, level = stack.pop()
            try:
                children = list(cur.iterdir())
            except OSError:
                continue
            for child in children:
                try:
                    if child.is_file() and (
                        child.suffix.lower() in _IMAGE_EXT
                        or child.suffix.lower()
                        in {".mp4", ".mov", ".m4v", ".m4a", ".mp3", ".pdf", ".html", ".url", ".webloc"}
                        or not child.suffix
                    ):
                        _index_file_entry(child)
                    elif child.is_dir() and level < depth:
                        stack.append((child, level + 1))
                except OSError:
                    continue
    try:
        _index_file().write_text(json.dumps(_INDEX or {}, indent=0), encoding="utf-8")
    except OSError:
        pass


def _keep_found(path: Path, filename: str) -> Path:
    _index_file_entry(path)
    return cache_put(path, filename) or path


def _find_in_zips(root: Path, name: str, uuid: str | None) -> Path | None:
    """CSV exports sometimes sit next to a zip of the same attachments."""
    try:
        if not root.is_dir():
            return None
        zips = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".zip"]
    except OSError:
        return None
    for zp in zips[:24]:
        try:
            with zipfile.ZipFile(zp) as zf:
                for inner in zf.namelist():
                    base = Path(inner).name
                    if not base or not _name_matches(base, name, uuid):
                        continue
                    dest = cache_root() / base
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.is_file() or not dest.stat().st_size:
                        dest.write_bytes(zf.read(inner))
                    if dest.is_file() and dest.stat().st_size:
                        return dest
        except (OSError, zipfile.BadZipFile, RuntimeError):
            continue
    return None


def resolve_attachment_file(
    att: dict[str, Any],
    payload: dict[str, Any] | None = None,
    *,
    build_index: bool = True,
) -> Path | None:
    mid = str(att.get("media_object_id") or "").strip()
    if mid:
        ingested = media_object_path(mid)
        if ingested is not None:
            return ingested
    raw_ref = str(att.get("source_ref") or att.get("filename") or "").strip()
    name = Path(raw_ref).name
    cached = cache_get(name) if name else None
    if cached is not None:
        return cached
    for key in ("resolved_path", "source_ref", "filename"):
        raw = str(att.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw)
        try:
            if p.is_file():
                return _keep_found(p, name or p.name)
        except OSError:
            continue
    if not name:
        return None
    if raw_ref and raw_ref not in {name}:
        for root in _search_roots(payload):
            rel = root / raw_ref.replace("\\", "/").lstrip("/")
            try:
                if rel.is_file():
                    return _keep_found(rel, name)
            except OSError:
                continue
    uuid_m = _UUID_IN_NAME.search(name)
    uuid = uuid_m.group(1) if uuid_m else None
    try:
        from memorybox.ingest.sms_export_attach import get_export_index

        export_hit = get_export_index(_search_roots(payload)).lookup_uuid_or_name(name)
        if export_hit is not None:
            return _keep_found(export_hit, name)
    except OSError:
        pass
    indexed = _lookup_index(name, uuid)
    if indexed is not None:
        return _keep_found(indexed, name)
    roots = _search_roots(payload)
    for root in roots:
        # Try known filenames even when the share folder will not list
        # (exists()/is_dir() can fail on UNC while a direct file open works).
        for hit in _dir_candidates(root, name):
            try:
                if hit.is_file():
                    return _keep_found(hit, name)
            except OSError:
                continue
        found = _walk_match(root, name, uuid, depth=6)
        if found is not None:
            return _keep_found(found, name)
        zipped = _find_in_zips(root, name, uuid)
        if zipped is not None:
            return _keep_found(zipped, name)
    if build_index:
        _build_attach_index(roots, depth=6)
        indexed = _lookup_index(name, uuid)
        if indexed is not None:
            return _keep_found(indexed, name)
    return None


def load_sms_attachment(evidence_id: str, index: int = 0) -> dict[str, Any]:
    try:
        eid = UUID(str(evidence_id).strip())
    except (ValueError, TypeError, AttributeError) as exc:
        raise SmsAttachError("evidence_id must be a UUID") from exc
    row = get_evidence(eid)
    if not row:
        raise SmsAttachError("evidence not found")
    payload = _payload(row)
    atts = _attachments(payload)
    if index < 0 or index >= len(atts):
        raise SmsAttachError("attachment index out of range")
    att = atts[index]
    path = resolve_attachment_file(att, payload)
    filename = str(att.get("filename") or (path.name if path else "attachment"))
    mime = (
        mimetypes.guess_type(filename)[0]
        or str(att.get("mime_type") or "")
        or "application/octet-stream"
    )
    kind = str(att.get("attachment_type") or "").lower()
    if kind in {"image", "jpeg", "jpg", "png", "gif", "heic"} and not mime.startswith("image/"):
        mime = "image/jpeg"
    cov = payload.get("source_coverage") or {}
    import_path = str(cov.get("import_path") or "")
    if not import_path:
        loc = str(payload.get("source_locator") or "")
        if "#row=" in loc:
            import_path = loc.split("#row=", 1)[0]
    extra = (os.environ.get("MEMORYBOX_SMS_ATTACHMENTS_DIR") or "").strip()
    return {
        "evidence_id": str(eid),
        "index": index,
        "filename": filename,
        "mime_type": mime,
        "path": str(path) if path else None,
        "bytes_present": bool(path and path.is_file()),
        "attachment": att,
        "person_ids": [str(p) for p in (payload.get("person_ids") or []) if p],
        "payload": payload,
        "import_path": import_path or None,
        "attachments_dir": extra or None,
        "search_roots": [str(p) for p in _search_roots(payload)[:16]],
    }


def read_sms_attachment_bytes(evidence_id: str, index: int = 0) -> tuple[bytes, str, str]:
    info = load_sms_attachment(evidence_id, index)
    if not info["bytes_present"] or not info["path"]:
        raise SmsAttachError(
            f"Attachment file was not ingested: {info['filename']}. "
            "Re-run ingest-sms so bytes are stored on the message "
            "(media_objects). Looked next to the SMS export and "
            "MEMORYBOX_SMS_ATTACHMENTS_DIR."
        )
    data = Path(info["path"]).read_bytes()
    if not data:
        raise SmsAttachError("attachment file is empty")
    return data, str(info["mime_type"]), str(info["filename"])


def add_sms_attachment_to_mb_library(evidence_id: str, index: int = 0) -> dict[str, Any]:
    """Copy attachment bytes into MemoryBox Artifact storage. Never writes Immich."""
    from memorybox.artifact import (
        ArtifactServiceError,
        add_evidence_ref_representation,
        add_mb_managed_representation,
        create_artifact,
    )

    info = load_sms_attachment(evidence_id, index)
    data, mime, filename = read_sms_attachment_bytes(evidence_id, index)
    kind = "photograph_of_object" if mime.startswith("image/") else "other"
    try:
        art = create_artifact(
            kind=kind,
            label=filename,
            description=f"SMS attachment from evidence {info['evidence_id']}",
            person_ids=info.get("person_ids") or None,
            actor_key="sms_to_mb_library",
        )
        add_mb_managed_representation(
            art.id,
            data=data,
            filename=filename,
            content_type=mime,
            label=filename,
        )
        add_evidence_ref_representation(
            art.id, evidence_id=info["evidence_id"], label=filename
        )
    except ArtifactServiceError as exc:
        raise SmsAttachError(str(exc)) from exc
    return {
        "ok": True,
        "immich_write": False,
        "artifact_id": art.id,
        "href": f"/artifact/ui?id={art.id}",
        "filename": filename,
        "mime_type": mime,
    }
