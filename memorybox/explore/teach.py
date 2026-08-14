"""Owner teach from Explore/Person viewer — map identity and kick recognition."""
from __future__ import annotations

import threading
from typing import Any
from urllib.parse import unquote
from uuid import UUID


def _is_uuid(raw: str) -> bool:
    try:
        UUID(str(raw).strip())
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def resolve_teach_person(
    *,
    person_id: str | None,
    person_key: str | None,
    display_name: str | None,
) -> dict[str, Any]:
    """Resolve picker selection to an MB Person (lazy-teach Immich when needed)."""
    from memorybox.ask.deps import build_photo
    from memorybox.person import get_person, teach_provider_person

    pid = (person_id or "").strip()
    key = (person_key or "").strip()
    if not pid and key.startswith("mb:"):
        pid = key[3:].strip()
    if pid and _is_uuid(pid):
        view = get_person(pid)
        if not view:
            raise ValueError("person not found")
        return {"created": False, "person": view.to_dict()}
    if key.startswith("immich:"):
        rest = key[len("immich:") :]
        i = rest.find(":")
        if i < 0:
            raise ValueError("invalid Immich person key")
        ext = unquote(rest[:i])
        name = unquote(rest[i + 1 :]).strip() or (display_name or "").strip()
        if not ext or len(name) < 2:
            raise ValueError("Immich person needs external_id and display_name")
        view = teach_provider_person(
            display_name=name,
            provider_key="immich",
            external_id=ext,
            label=name,
            photo=build_photo(),
        )
        return {"created": True, "person": view.to_dict()}
    raise ValueError("person_id or person_key required")


def kick_recognition_background(person_id: str) -> None:
    """Enqueue eligible videos and process a batch without blocking the viewer."""

    def _run() -> None:
        try:
            from memorybox.ask.deps import build_video
            from memorybox.recognition.process import process_queue
            from memorybox.recognition.queue import enqueue_full_eligible_archive

            video = build_video()
            listed: list[dict[str, Any]] = []
            try:
                rows = video.list_videos(limit=5000) or []
            except Exception:  # noqa: BLE001
                rows = []
            vpk = getattr(video, "provider_key", None) or "hvrt"
            for v in rows:
                veid = getattr(v, "external_id", None) or (
                    v.get("external_id") if isinstance(v, dict) else None
                )
                if not veid:
                    continue
                listed.append(
                    {
                        "video_provider_key": vpk,
                        "video_external_id": str(veid),
                    }
                )
            enqueue_full_eligible_archive(
                person_id=person_id,
                videos=listed,
                enqueue_reason="owner_teach",
            )
            process_queue(video_provider=video, person_id=person_id, max_items=40)
        except Exception:  # noqa: BLE001 — background; viewer already saved
            return

    threading.Thread(target=_run, daemon=True, name="mb-teach-recognition").start()


def teach_face_from_viewer(
    *,
    person_id: str | None = None,
    person_key: str | None = None,
    display_name: str | None = None,
    provider_key: str = "immich",
    asset_external_id: str | None = None,
    video_external_id: str | None = None,
    start_sec: float = 0.0,
    face_external_id: str | None = None,
    person_external_id: str | None = None,
    face_box: dict[str, Any] | None = None,
    media_type: str = "video",
) -> dict[str, Any]:
    """Map selected face → MB Person, store evidence, start recognition in background."""
    from memorybox.person import map_provider_identity
    from memorybox.person.face_evidence import owner_confirm_or_correct
    from memorybox.recognition.process import owner_correct_appearance

    resolved = resolve_teach_person(
        person_id=person_id,
        person_key=person_key,
        display_name=display_name,
    )
    person = resolved["person"]
    pid = str(person["id"])
    label = (display_name or person.get("display_name") or "Person").strip() or "Person"
    pk = (provider_key or "immich").strip() or "immich"
    mapped = None
    immich_person = (person_external_id or "").strip()
    if pk in {"immich", "fake_photo"} and immich_person:
        mapped = map_provider_identity(
            person_id=pid,
            provider_key=pk if pk != "fake_photo" else "immich",
            external_id=immich_person,
            label=label,
        ).to_dict()

    fe = owner_confirm_or_correct(
        person_id=pid,
        provider_key=pk,
        method="owner_correct",
        external_face_id=(face_external_id or immich_person or None),
        source_asset_id=(asset_external_id or video_external_id or None),
        bbox=face_box if isinstance(face_box, dict) else None,
        meta={
            "media_type": media_type,
            "video_external_id": video_external_id,
            "start_sec": start_sec,
            "person_external_id": immich_person or None,
        },
    )

    appearance = None
    vid = (video_external_id or "").strip()
    if vid and str(media_type or "").lower() == "video":
        appearance = owner_correct_appearance(
            person_id=pid,
            video_provider_key=pk if pk in {"hvrt", "fake_video", "immich"} else "hvrt",
            video_external_id=vid,
            start_sec=float(start_sec or 0),
            end_sec=None,
            face_external_id=(face_external_id or immich_person or None),
        )

    kick_recognition_background(pid)
    return {
        "ok": True,
        "person": mapped or person,
        "face_evidence": fe,
        "appearance": appearance,
        "recognition_started": True,
        "created": resolved.get("created"),
        "note": (
            "Face saved. Photo identity uses the Immich mapping immediately; "
            "video appearance search is running in the background."
        ),
    }
