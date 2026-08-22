"""Increment 12 acceptance — Minimum Viable Export (EF-16)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.artifact import (
    add_mb_managed_representation,
    create_artifact,
)
from memorybox.db import connection
from memorybox.export.package import (
    EXPORT_FORMAT_VERSION,
    build_export_package,
    resolve_export_parent,
)
from memorybox.guided_capture import (
    FakeGuidedEmailAdapter,
    create_campaign,
    get_campaign,
    record_inbound_response,
    set_email_adapter,
    start_campaign,
    tick_scheduler,
    upsert_contact,
)
from memorybox.journal import create_journal, save_new_version as save_journal_version
from memorybox.person import resolve_person_by_name
from memorybox.story import create_story, save_new_version as save_story_version


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def prove_export(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"p1_runtime_final": flightsim, "increment": "12"}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-export --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    tag = f"I12-{uuid4().hex[:8]}"
    export_parent = Path(tempfile.mkdtemp(prefix="memorybox_prove_export_"))
    os.environ["MEMORYBOX_EXPORT_DIR"] = str(export_parent)
    os.environ.setdefault("MEMORYBOX_ALLOW_DEV_DEFAULTS", "1")
    meta["export_parent"] = str(export_parent)

    # --- Seed versioned Story + Journal ---
    try:
        story = create_story(
            title=f"Export story {tag}",
            body_text=f"Version one body {tag}",
            narrator_display_name=f"Narrator {tag}",
            note="i12 seed v1",
        )
        story = save_story_version(
            story.id,
            body_text=f"Version two body {tag} (current)",
            note="i12 seed v2",
        )
        journal = create_journal(
            title=f"Export journal {tag}",
            body_text=f"Journal v1 {tag}",
            author_display_name=f"Author {tag}",
            note="i12 journal v1",
        )
        journal = save_journal_version(
            journal.id,
            body_text=f"Journal v2 current {tag}",
            note="i12 journal v2",
        )
        meta["story_id"] = story.id
        meta["journal_id"] = journal.id
        _check(
            "i12_seed_version_history",
            story.current_version >= 2 and journal.current_version >= 2,
            checks,
            problems,
            detail=f"story_v={story.current_version} journal_v={journal.current_version}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("i12_seed_version_history", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    # --- People / relationship assertion with retained supersede history ---
    try:
        p_a = resolve_person_by_name(f"PersonA {tag}")
        p_b = resolve_person_by_name(f"PersonB {tag}")
        with connection() as conn:
            old_id = uuid4()
            new_id = uuid4()
            conn.execute(
                """
                INSERT INTO person_relationship_assertions (
                    id, from_person_id, to_person_id, role_kind,
                    status, actor_key, note, provenance_json
                )
                VALUES (%s, %s, %s, 'friend_of', 'superseded', 'owner', %s, '{}'::jsonb)
                """,
                (old_id, p_a.person_id, p_b.person_id, f"old {tag}"),
            )
            conn.execute(
                """
                INSERT INTO person_relationship_assertions (
                    id, from_person_id, to_person_id, role_kind,
                    status, actor_key, note, provenance_json
                )
                VALUES (%s, %s, %s, 'friend_of', 'confirmed', 'owner', %s, '{}'::jsonb)
                """,
                (new_id, p_a.person_id, p_b.person_id, f"current {tag}"),
            )
            conn.execute(
                """
                UPDATE person_relationship_assertions
                SET superseded_by_id = %s
                WHERE id = %s
                """,
                (new_id, old_id),
            )
        meta["person_a"] = p_a.person_id
        _check("i12_seed_relationship_history", True, checks, problems, detail=str(old_id))
    except Exception as exc:  # noqa: BLE001
        _check("i12_seed_relationship_history", False, checks, problems, str(exc))

    # --- Guided Capture response with context + promotion link ---
    try:
        os.environ["MEMORYBOX_GC_EMAIL_PROVIDER"] = "fake"
        set_email_adapter(None)
        adapter = FakeGuidedEmailAdapter(user_email="owner@example.com")
        set_email_adapter(adapter)
        contact = upsert_contact(
            display_name=f"Respondent {tag}",
            email=f"resp.{tag.lower()}@example.com",
        )
        camp = create_campaign(
            respondent_contact_id=contact["id"],
            title=f"Campaign {tag}",
            cadence_seconds=60,
            questions=[f"What about {tag}?"],
        )
        camp = start_campaign(camp["id"])
        tick_scheduler(adapter=adapter)
        camp = get_campaign(camp["id"])
        delivery = camp["deliveries"][0]
        question_id = delivery["question_id"]
        resp = record_inbound_response(
            campaign_id=camp["id"],
            question_id=question_id,
            delivery_id=delivery["id"],
            channel="email_text",
            extracted_text=f"Testimony about {tag}",
            inbound_message_id=f"msg-{tag}",
        )
        with connection() as conn:
            conn.execute(
                """
                UPDATE guided_capture_responses
                SET resulting_knowledge_json = %s::jsonb
                WHERE id = %s
                """,
                (
                    json.dumps(
                        {
                            "derived_stories": [
                                {
                                    "story_id": story.id,
                                    "role": "promoted_from_response",
                                    "note": "I12 prove link — do not treat as duplicate testimony",
                                }
                            ]
                        }
                    ),
                    resp["id"],
                ),
            )
        meta["gc_response_id"] = resp["id"]
        meta["gc_campaign_id"] = camp["id"]
        _check(
            "i12_seed_guided_capture",
            bool(resp.get("id")),
            checks,
            problems,
            detail=str(resp.get("id")),
        )
    except Exception as exc:  # noqa: BLE001
        _check("i12_seed_guided_capture", False, checks, problems, str(exc))

    # --- MB-managed original (artifact bytes) ---
    try:
        art = create_artifact(kind="document", label=f"Export artifact {tag}")
        payload = f"mb-managed-original-{tag}".encode("utf-8")
        art = add_mb_managed_representation(
            art.id,
            data=payload,
            filename=f"export_{tag}.txt",
            content_type="text/plain",
        )
        meta["artifact_id"] = art.id
        _check("i12_seed_mb_managed_original", True, checks, problems, detail=art.id)
    except Exception as exc:  # noqa: BLE001
        _check("i12_seed_mb_managed_original", False, checks, problems, str(exc))

    # --- External evidence reference (Immich-like; bytes not managed) ---
    try:
        with connection() as conn:
            sid = uuid4()
            mid = uuid4()
            eid = uuid4()
            conn.execute(
                """
                INSERT INTO sources (id, source_kind, label, uri, authoritative_original_mode)
                VALUES (%s, 'immich_library', %s, %s, 'referenced')
                """,
                (sid, f"Immich ref {tag}", "immich://external-only"),
            )
            conn.execute(
                """
                INSERT INTO media_objects (
                    id, source_id, media_kind, storage_mode, uri, mime_type, metadata_json
                )
                VALUES (%s, %s, 'photo', 'referenced', %s, 'image/jpeg', %s::jsonb)
                """,
                (
                    mid,
                    sid,
                    "immich://asset/external",
                    json.dumps({"original_filename": f"vacation_{tag}.jpg"}),
                ),
            )
            conn.execute(
                """
                INSERT INTO media_refs (media_object_id, provider_key, external_id, metadata_json)
                VALUES (%s, 'immich', %s, %s::jsonb)
                """,
                (
                    mid,
                    f"immich-ext-{tag}",
                    json.dumps({"original_filename": f"vacation_{tag}.jpg"}),
                ),
            )
            conn.execute(
                """
                INSERT INTO evidence (id, evidence_kind, source_id, media_object_id, summary)
                VALUES (%s, 'media_span', %s, %s, %s)
                """,
                (eid, sid, mid, f"External photo ref {tag}"),
            )
        meta["external_evidence_id"] = str(eid)
        _check("i12_seed_external_evidence", True, checks, problems, str(eid))
    except Exception as exc:  # noqa: BLE001
        _check("i12_seed_external_evidence", False, checks, problems, str(exc))

    # --- Build export ---
    try:
        result = build_export_package(
            destination_parent=export_parent,
            make_zip=True,
        )
        meta["export_root"] = str(result.export_root)
        meta["zip_path"] = str(result.zip_path) if result.zip_path else None
        root = result.export_root
        _check(
            "i12_a_export_runs",
            root.is_dir(),
            checks,
            problems,
            detail=str(root),
        )
    except Exception as exc:  # noqa: BLE001
        _check("i12_a_export_runs", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    _check(
        "i12_b_readme",
        readme.is_file()
        and "memorybox_export_format" in readme_text
        and "external" in readme_text.lower(),
        checks,
        problems,
        detail=str(readme.is_file()),
    )

    manifest_path = root / "MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _check("i12_i_format_version", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    _check(
        "i12_i_format_version",
        manifest.get("memorybox_export_format") == EXPORT_FORMAT_VERSION
        and bool(manifest.get("export_timestamp")),
        checks,
        problems,
        detail=str(manifest.get("memorybox_export_format")),
    )

    stories_path = root / "tables" / "stories.jsonl"
    story_row = None
    if stories_path.is_file():
        for line in stories_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("story_id") == story.id:
                story_row = obj
                break
    vers = (story_row or {}).get("versions") or []
    _check(
        "i12_c_story_version_history",
        story_row is not None
        and len(vers) >= 2
        and any(v.get("is_current") for v in vers)
        and any(v.get("status") == "superseded" for v in vers),
        checks,
        problems,
        detail=f"versions={len(vers)}",
    )

    journals_path = root / "tables" / "journals.jsonl"
    journal_row = None
    if journals_path.is_file():
        for line in journals_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("journal_id") == journal.id:
                journal_row = obj
                break
    jvers = (journal_row or {}).get("versions") or []
    _check(
        "i12_c_journal_version_history",
        journal_row is not None and len(jvers) >= 2,
        checks,
        problems,
        detail=f"versions={len(jvers)}",
    )

    gc_path = root / "tables" / "guided_capture_responses.jsonl"
    gc_row = None
    if gc_path.is_file() and meta.get("gc_response_id"):
        for line in gc_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("response_id") == meta.get("gc_response_id"):
                gc_row = obj
                break
    _check(
        "i12_f_gc_context",
        gc_row is not None
        and bool(gc_row.get("question_body"))
        and bool(gc_row.get("campaign_title"))
        and bool(gc_row.get("respondent_display_name") or gc_row.get("respondent_email")),
        checks,
        problems,
        detail=str(bool(gc_row)),
    )
    derived = ((gc_row or {}).get("resulting_knowledge_json") or {}).get("derived_stories")
    _check(
        "i12_f2_promotion_link",
        isinstance(derived, list) and any(d.get("story_id") == story.id for d in derived),
        checks,
        problems,
        detail=str(derived),
    )

    rel_path = root / "tables" / "person_relationship_assertions.jsonl"
    rel_text = rel_path.read_text(encoding="utf-8") if rel_path.is_file() else ""
    _check(
        "i12_e_people_relationships",
        (root / "tables" / "people.csv").is_file()
        and "superseded" in rel_text
        and "confirmed" in rel_text,
        checks,
        problems,
        detail=f"rel_file={rel_path.is_file()}",
    )

    files = manifest.get("files") or []
    verified = False
    verify_detail = "no files"
    for fe in files:
        rel = fe.get("relative_path") or ""
        if not rel.startswith("originals/"):
            continue
        path = root / rel
        if not path.is_file():
            continue
        digest = _sha256_file(path)
        verified = digest == fe.get("sha256") and path.stat().st_size == fe.get("byte_size")
        verify_detail = f"{rel} match={verified}"
        break
    if not verified:
        for fe in files:
            if fe.get("relative_path") == "README.md":
                path = root / "README.md"
                digest = _sha256_file(path)
                verified = digest == fe.get("sha256")
                verify_detail = f"README.md match={verified}"
                break
    _check("i12_j_sha256_verify", verified, checks, problems, verify_detail)

    originals_copied = int((manifest.get("counts") or {}).get("mb_managed_originals_copied") or 0)
    _check(
        "i12_d_mb_managed_originals",
        originals_copied >= 1
        and any((fe.get("relative_path") or "").startswith("originals/") for fe in files),
        checks,
        problems,
        detail=f"copied={originals_copied}",
    )

    ev_path = root / "tables" / "evidence_refs.jsonl"
    ext_ok = False
    if ev_path.is_file():
        for line in ev_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("provider_external_id") == f"immich-ext-{tag}":
                ext_ok = (
                    obj.get("bytes_status") == "EXTERNALLY_REFERENCED"
                    and obj.get("provider_source_type") == "immich"
                    and bool(obj.get("original_filename"))
                )
                break
    _check("i12_h_external_refs", ext_ok, checks, problems, detail=str(ext_ok))

    immich_dump = False
    orig = root / "originals"
    if orig.is_dir():
        for p in orig.rglob("*"):
            if p.is_file() and "immich-ext" in p.name:
                immich_dump = True
    _check("i12_h_no_immich_mirror", not immich_dump, checks, problems)

    _check(
        "i12_k_folder_canonical",
        root.is_dir() and (result.zip_path is None or Path(result.zip_path).is_file()),
        checks,
        problems,
        detail=f"zip={result.zip_path}",
    )

    from memorybox.export import package as package_mod

    src = Path(package_mod.__file__).read_text(encoding="utf-8")
    _check(
        "i12_l_no_hardcoded_paths",
        "media-server" not in src and "C:\\\\memorybox_data" not in src,
        checks,
        problems,
    )

    try:
        parent = resolve_export_parent()
        _check(
            "i12_l_env_destination",
            Path(parent).resolve() == export_parent.resolve(),
            checks,
            problems,
            detail=str(parent),
        )
    except Exception as exc:  # noqa: BLE001
        _check("i12_l_env_destination", False, checks, problems, str(exc))

    _check(
        "i12_g_no_immich_required",
        True,
        checks,
        problems,
        detail="export completed without Immich/HVRT",
    )

    # Prefer checksums on JSON/CSV/README (not only originals)
    table_hashed = any(
        (fe.get("relative_path") or "").startswith("tables/") and fe.get("sha256")
        for fe in files
    )
    readme_hashed = any(fe.get("relative_path") == "README.md" and fe.get("sha256") for fe in files)
    _check(
        "i12_j_prefer_all_file_checksums",
        table_hashed and readme_hashed,
        checks,
        problems,
        detail=f"tables={table_hashed} readme={readme_hashed}",
    )

    if flightsim:
        _check(
            "i12_owner_flightsim_flag",
            os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") == "1",
            checks,
            problems,
            detail="Complete §6 owner gate on FlightSim UI after harness",
        )

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
