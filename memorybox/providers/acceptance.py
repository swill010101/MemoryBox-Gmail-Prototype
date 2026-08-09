"""Increment 2 acceptance: providers return MB DTOs; Immich ids never become Person PKs."""
from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.providers.email_read.dto import EmailSourceRef
from memorybox.providers.email_read.mbox import MboxEmailReadProvider
from memorybox.providers.llm.dto import ChatMessage
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.dto import PhotoPersonRef, PhotoSearchQuery
from memorybox.providers.photo.fake import FakePhotoProvider


FORBIDDEN_PERSON_PK_FIELDS = frozenset(
    {
        "person_id",
        "immich_person_id",
        "mb_person_id",
        "people_id",
    }
)


def _dto_field_names(cls: type) -> set[str]:
    return {f.name for f in fields(cls)}


def _assert_no_person_pk_fields() -> list[str]:
    problems: list[str] = []
    for name in _dto_field_names(PhotoPersonRef):
        if name in FORBIDDEN_PERSON_PK_FIELDS:
            problems.append(f"PhotoPersonRef.{name} looks like a domain Person PK field")
    # Immich external ids must be named external_id
    if "external_id" not in _dto_field_names(PhotoPersonRef):
        problems.append("PhotoPersonRef missing external_id")
    if "provider_key" not in _dto_field_names(PhotoPersonRef):
        problems.append("PhotoPersonRef missing provider_key")
    return problems


def _domain_never_uses_immich_as_person_pk(immich_external_id: str) -> dict[str, Any]:
    """Insert provider_identities mapping; people.id must remain a distinct MB UUID."""
    with connection() as conn:
        person = conn.execute(
            """
            INSERT INTO people (display_name, status, notes, attributes_json)
            VALUES ('I2 Provider Map Person', 'confirmed', 'Inc 2 acceptance',
                    '{"fixture":"i2_provider"}'::jsonb)
            RETURNING id
            """
        ).fetchone()
        assert person is not None
        mb_id = person["id"]
        conn.execute(
            """
            INSERT INTO provider_identities (
                person_id, provider_key, identity_kind, external_id, label, metadata_json
            )
            VALUES (%s, 'immich', 'face', %s, 'mapped Immich person',
                    '{"fixture":"i2_provider"}'::jsonb)
            ON CONFLICT (provider_key, identity_kind, external_id)
            DO UPDATE SET person_id = EXCLUDED.person_id
            """,
            (mb_id, immich_external_id),
        )
        row = conn.execute(
            """
            SELECT p.id AS mb_person_id, pi.external_id
            FROM people p
            JOIN provider_identities pi ON pi.person_id = p.id
            WHERE pi.provider_key = 'immich' AND pi.external_id = %s
            """,
            (immich_external_id,),
        ).fetchone()
    assert row is not None
    mb_person_id = row["mb_person_id"]
    ok = (
        str(mb_person_id) != immich_external_id
        and isinstance(mb_person_id, UUID)
    )
    return {
        "ok": ok,
        "mb_person_id": str(mb_person_id),
        "immich_external_id": immich_external_id,
        "ids_differ": str(mb_person_id) != immich_external_id,
    }


def _write_tiny_mbox(path: Path) -> None:
    path.write_text(
        "From me@example.com Sat Aug 09 12:00:00 2026\n"
        "From: tester@example.com\n"
        "To: owner@example.com\n"
        "Subject: I2 synthetic\n"
        "Message-ID: <i2-synthetic@memorybox.test>\n"
        "Date: Sat, 09 Aug 2026 12:00:00 -0500\n"
        "\n"
        "Hello from Increment 2 email-read fixture.\n"
        "\n",
        encoding="utf-8",
    )


def prove_increment_2() -> dict[str, Any]:
    problems = _assert_no_person_pk_fields()
    photo = FakePhotoProvider()
    llm = FakeLlmProvider()
    email = MboxEmailReadProvider()

    people = photo.list_people(query="Grandpa")
    assets = photo.search_assets(
        PhotoSearchQuery(person_external_ids=(people[0].external_id,))
    )
    preview = photo.fetch_preview(assets[0].external_id)
    emb = llm.embed("grandpa christmas", purpose="query")
    chat = llm.chat(
        [ChatMessage(role="user", content="Summarize without inventing facts.")]
    )

    mbox_path = Path(__file__).resolve().parent / "_fixtures" / "i2_synthetic.mbox"
    mbox_path.parent.mkdir(parents=True, exist_ok=True)
    _write_tiny_mbox(mbox_path)
    messages = list(
        email.iter_messages(
            EmailSourceRef(provider_key="mbox", uri=str(mbox_path)), limit=5
        )
    )

    # Domain mapping rule
    map_check = _domain_never_uses_immich_as_person_pk(people[0].external_id)

    # Call sites must go through provider objects (duck-typed protocols)
    photo_methods = {"health", "list_people", "search_assets", "get_asset", "fetch_preview"}
    llm_methods = {"health", "embed", "chat"}
    email_methods = {"health", "iter_messages"}
    for required, obj in (
        (photo_methods, photo),
        (llm_methods, llm),
        (email_methods, email),
    ):
        missing = required - {n for n, _ in inspect.getmembers(obj, predicate=callable)}
        if missing:
            problems.append(f"{type(obj).__name__} missing methods: {sorted(missing)}")

    checks = {
        "dto_no_person_pk_fields": not problems,
        "photo_health": photo.health().ok,
        "llm_health": llm.health().ok,
        "email_health": email.health().ok,
        "photo_people_via_external_id": bool(people)
        and people[0].external_id
        and not hasattr(people[0], "person_id"),
        "photo_search_returns_asset": bool(assets),
        "photo_preview_bytes": len(preview.data) > 0,
        "llm_embed": len(emb.vector) > 0,
        "llm_chat": bool(chat.content),
        "email_message_read": bool(messages)
        and messages[0].subject == "I2 synthetic",
        "domain_person_pk_not_immich": map_check["ok"],
    }
    ok = all(checks.values()) and map_check["ok"] and not problems
    return {
        "ok": ok,
        "increment": 2,
        "checks": checks,
        "problems": problems,
        "domain_mapping": map_check,
        "sample": {
            "photo_person_external_id": people[0].external_id if people else None,
            "photo_asset_external_id": assets[0].external_id if assets else None,
            "email_message_id": messages[0].external_id if messages else None,
            "llm_chat_preview": chat.content[:80],
        },
    }
