"""Increment 12A — thin Status summary (read-only; not P2 Dashboard).

Truthfulness locks: separate identity states; no Story created_at chronology;
no undated≈all videos; narrow partial labels; no health %; structured metric state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from memorybox.db import connection, ping
from memorybox.guided_capture import email_adapter_status, new_response_count

MetricState = Literal["available", "unavailable", "partial", "deferred"]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(
    key: str,
    label: str,
    *,
    value: Any = None,
    display: str | None = None,
    state: MetricState = "available",
    source: str | None = None,
    last_updated: str | None = None,
    reason: str | None = None,
    href: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    available = state == "available"
    if display is None:
        if state in ("unavailable", "deferred"):
            display = reason or "Not available"
        elif state == "partial" and value is not None:
            display = f"{value:,}" if isinstance(value, int) else str(value)
        elif value is None:
            display = "—"
        else:
            display = f"{value:,}" if isinstance(value, int) else str(value)
    # Never coerce unavailable/deferred to numeric zero
    if state in ("unavailable", "deferred") and value == 0:
        value = None
    return {
        "key": key,
        "label": label,
        "value": value,
        "display": display,
        "state": state,
        "available": available,
        "source": source,
        "last_updated": last_updated,
        "reason": reason,
        "href": href,
        "note": note,
    }


def _count(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return 0
    if isinstance(row, dict):
        return int(next(iter(row.values())))
    return int(row[0])


def _scalar(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    return next(iter(row.values())) if isinstance(row, dict) else row[0]


def _scalar_ts(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> str | None:
    v = _scalar(conn, sql, params)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _immich_photo_total(client: Any) -> tuple[int | None, str]:
    """Best-effort Immich library photo count without full asset pagination."""
    if client is None or not hasattr(client, "_request"):
        return None, "no Immich HTTP client"
    # Preferred: dedicated search statistics (accurate total)
    for body in ({}, {"type": "IMAGE"}, {"type": "image"}):
        try:
            status, data = client._request("POST", "/search/statistics", body=body)  # noqa: SLF001
            if status == 200 and isinstance(data, dict):
                for k in ("total", "photos", "count"):
                    if isinstance(data.get(k), int):
                        return int(data[k]), "immich:POST /search/statistics"
        except Exception:  # noqa: BLE001
            continue
    # Server / asset statistics
    for path in ("/server/statistics", "/assets/statistics"):
        try:
            status, data = client._request("GET", path)  # noqa: SLF001
            if status == 200 and isinstance(data, dict):
                for k in ("photos", "photo", "total", "assets"):
                    if isinstance(data.get(k), int):
                        return int(data[k]), f"immich:GET {path}"
                photos = data.get("photos")
                if isinstance(photos, dict) and isinstance(photos.get("count"), int):
                    return int(photos["count"]), f"immich:GET {path}"
        except Exception:  # noqa: BLE001
            continue
    return None, "Immich count endpoints not available to this API key"


def _count_media_root_videos() -> tuple[int | None, str]:
    """Count video files under MEMORYBOX_VIDEO_MEDIA_ROOT (filesystem; not HVRT SoT)."""
    import os
    from pathlib import Path

    raw = (os.environ.get("MEMORYBOX_VIDEO_MEDIA_ROOT") or "").strip()
    if not raw:
        return None, "MEMORYBOX_VIDEO_MEDIA_ROOT unset"
    root = Path(raw)
    if not root.is_dir():
        return None, f"media root not reachable: {raw}"
    exts = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".flv"}
    n = 0
    try:
        for path in root.rglob("*"):
            try:
                if path.is_file() and path.suffix.lower() in exts:
                    n += 1
            except OSError:
                continue
    except OSError as exc:
        return None, f"media root scan failed: {exc}"
    return n, raw


def _qdrant_point_count() -> tuple[int | None, str]:
    try:
        from memorybox.config import settings
        from memorybox.ingest.rebuild_index import _qdrant_client

        if not settings.qdrant_url or settings.qdrant_url == ":memory:":
            return None, "Qdrant not a durable network/path store for Status"
        client = _qdrant_client(settings)
        name = settings.qdrant_collection
        existing = {c.name for c in client.get_collections().collections}
        if name not in existing:
            return None, f"collection {name!r} missing"
        info = client.get_collection(name)
        # points_count attribute varies by qdrant-client version
        n = getattr(info, "points_count", None)
        if n is None and getattr(info, "points_count", None) is None:
            n = getattr(getattr(info, "result", None), "points_count", None)
        if n is None:
            # dict-like
            n = info.get("points_count") if isinstance(info, dict) else None
        if isinstance(n, int):
            return n, f"qdrant:{name}"
        return None, "points_count not exposed"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _ollama_status(calculated_at: str) -> dict[str, Any]:
    """Probe configured Ollama or common local default — do not pretend connected."""
    import urllib.request

    from memorybox.config import settings

    configured = (settings.ollama_base_url or "").strip()
    candidates: list[str] = []
    if configured:
        candidates.append(configured.rstrip("/"))
    default = "http://127.0.0.1:11434"
    if default not in candidates:
        candidates.append(default)

    last_err = "Not connected"
    for base in candidates:
        try:
            with urllib.request.urlopen(f"{base}/api/tags", timeout=2.5) as resp:
                ok = 200 <= getattr(resp, "status", 200) < 300
            if ok:
                if configured and base.rstrip("/") == configured.rstrip("/"):
                    return _metric(
                        "ollama",
                        "Ollama",
                        display="OK",
                        state="available",
                        source=f"ollama:{base}/api/tags",
                        last_updated=calculated_at,
                        note=f"Configured MEMORYBOX_OLLAMA_BASE_URL={configured}",
                    )
                return _metric(
                    "ollama",
                    "Ollama",
                    display="Reachable (not configured for MemoryBox)",
                    state="partial",
                    source=f"ollama:{base}/api/tags",
                    last_updated=calculated_at,
                    reason="Partial — daemon responds but MEMORYBOX_OLLAMA_BASE_URL is unset",
                    note=(
                        f"Set MEMORYBOX_OLLAMA_BASE_URL={base} so Ask uses Ollama "
                        "(otherwise FakeLlmProvider)"
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue
    return _metric(
        "ollama",
        "Ollama",
        display="Not connected",
        state="unavailable",
        source="MEMORYBOX_OLLAMA_BASE_URL",
        last_updated=calculated_at,
        reason="Not connected",
        note=(
            (f"Configured {configured} unreachable: {last_err}" if configured else last_err)
            + " — Ask falls back to FakeLlmProvider until Ollama is configured"
        ),
    )


def build_status_summary() -> dict[str, Any]:
    """Assemble Status payload for all tabs. Never invent unsupported counts as 0."""
    calculated_at = _iso_now()
    deferred_notes: list[str] = []

    with connection() as conn:
        people_total = _count(
            conn,
            "SELECT COUNT(*) AS c FROM people WHERE status IN ('confirmed', 'unresolved')",
        )
        people_confirmed = _count(
            conn, "SELECT COUNT(*) AS c FROM people WHERE status = 'confirmed'"
        )
        people_unresolved = _count(
            conn, "SELECT COUNT(*) AS c FROM people WHERE status = 'unresolved'"
        )
        people_named = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM people
            WHERE status IN ('confirmed', 'unresolved')
              AND display_name IS NOT NULL AND length(trim(display_name)) > 0
            """,
        )
        provider_identities = _count(conn, "SELECT COUNT(*) AS c FROM provider_identities")
        provider_identities_unlinked = _count(
            conn,
            "SELECT COUNT(*) AS c FROM provider_identities WHERE person_id IS NULL",
        )
        rel_current = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM person_relationship_assertions
            WHERE status = 'confirmed'
            """,
        )
        rel_family = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM person_relationship_assertions
            WHERE status = 'confirmed'
              AND role_kind IN (
                'parent_of', 'child_of', 'father_of', 'mother_of',
                'son_of', 'daughter_of', 'spouse_of', 'sibling_of',
                'brother_of', 'sister_of'
              )
            """,
        )
        stories = _count(conn, "SELECT COUNT(*) AS c FROM stories WHERE status = 'active'")
        stories_narrator = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM stories
            WHERE status = 'active' AND narrator_person_id IS NOT NULL
            """,
        )
        stories_with_people = _count(
            conn,
            """
            SELECT COUNT(DISTINCT s.id) AS c
            FROM stories s
            JOIN relationships r ON r.from_type = 'story' AND r.from_id = s.id
              AND r.relationship_kind = 'about_person' AND r.to_type = 'person'
            WHERE s.status = 'active'
            """,
        )
        stories_with_evidence = _count(
            conn,
            """
            SELECT COUNT(DISTINCT s.id) AS c
            FROM stories s
            JOIN relationships r ON r.from_type = 'story' AND r.from_id = s.id
              AND r.relationship_kind = 'cites_evidence' AND r.to_type = 'evidence'
            WHERE s.status = 'active'
            """,
        )
        # Stories have no life/event date field — count as undated for chronology
        stories_undated = stories
        journals = _count(
            conn, "SELECT COUNT(*) AS c FROM journal_entries WHERE status = 'active'"
        )
        journals_dated = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM journal_entries
            WHERE status = 'active'
              AND described_start_date IS NOT NULL
              AND COALESCE(described_precision, 'unknown') <> 'unknown'
            """,
        )
        journals_undated = journals - journals_dated
        gc_responses = _count(conn, "SELECT COUNT(*) AS c FROM guided_capture_responses")
        gc_new = new_response_count()
        gc_reviewed = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_responses WHERE review_status = 'reviewed'",
        )
        gc_typed = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_responses WHERE channel = 'email_text'",
        )
        gc_voice = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_responses WHERE channel = 'voice'",
        )
        gc_cred = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_responses WHERE credibility IS NOT NULL",
        )
        gc_no_cred = gc_responses - gc_cred
        gc_stt_fail = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_responses WHERE stt_status = 'failed'",
        )
        gc_stt_pending = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_responses WHERE stt_status = 'pending'",
        )
        gc_campaigns = {
            "draft": _count(
                conn,
                "SELECT COUNT(*) AS c FROM guided_capture_campaigns WHERE status = 'draft'",
            ),
            "running": _count(
                conn,
                "SELECT COUNT(*) AS c FROM guided_capture_campaigns WHERE status = 'running'",
            ),
            "paused": _count(
                conn,
                "SELECT COUNT(*) AS c FROM guided_capture_campaigns WHERE status = 'paused'",
            ),
            "outbound_complete": _count(
                conn,
                """
                SELECT COUNT(*) AS c FROM guided_capture_campaigns
                WHERE status = 'outbound_complete'
                """,
            ),
            "stopped": _count(
                conn,
                "SELECT COUNT(*) AS c FROM guided_capture_campaigns WHERE status = 'stopped'",
            ),
        }
        gc_pending_deliveries = _count(
            conn,
            "SELECT COUNT(*) AS c FROM guided_capture_deliveries WHERE status = 'pending'",
        )
        artifacts = _count(conn, "SELECT COUNT(*) AS c FROM artifacts WHERE status = 'active'")
        artifact_kinds = conn.execute(
            """
            SELECT kind, COUNT(*) AS c FROM artifacts
            WHERE status = 'active'
            GROUP BY kind
            ORDER BY kind
            """
        ).fetchall()
        art_by_kind = {
            (r["kind"] if isinstance(r, dict) else r[0]): int(
                r["c"] if isinstance(r, dict) else r[1]
            )
            for r in artifact_kinds
        }
        art_docs = art_by_kind.get("document", 0) + art_by_kind.get("letter", 0)
        art_with_story = _count(
            conn,
            """
            SELECT COUNT(DISTINCT a.id) AS c
            FROM artifacts a
            JOIN relationships r ON (
              (r.from_type = 'story' AND r.to_type = 'artifact' AND r.to_id = a.id)
              OR (r.from_type = 'artifact' AND r.to_type = 'story' AND r.from_id = a.id)
            )
            WHERE a.status = 'active'
            """,
        )
        art_with_person = _count(
            conn,
            """
            SELECT COUNT(DISTINCT a.id) AS c
            FROM artifacts a
            JOIN relationships r ON r.from_type = 'artifact' AND r.from_id = a.id
              AND r.relationship_kind = 'about_person' AND r.to_type = 'person'
            WHERE a.status = 'active'
            """,
        )
        emails = _count(
            conn, "SELECT COUNT(*) AS c FROM evidence WHERE evidence_kind = 'communication'"
        )
        calendars = _count(
            conn, "SELECT COUNT(*) AS c FROM evidence WHERE evidence_kind = 'calendar_event'"
        )
        emails_dated = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM evidence
            WHERE evidence_kind = 'communication'
              AND NULLIF(payload_json->>'sent_at', '') IS NOT NULL
            """,
        )
        calendars_dated = _count(
            conn,
            """
            SELECT COUNT(*) AS c FROM evidence
            WHERE evidence_kind = 'calendar_event'
              AND (
                NULLIF(payload_json->>'start', '') IS NOT NULL
                OR NULLIF(payload_json->>'dtstart', '') IS NOT NULL
                OR NULLIF(payload_json->>'start_at', '') IS NOT NULL
              )
            """,
        )
        jobs_error = _count(conn, "SELECT COUNT(*) AS c FROM jobs WHERE status = 'error'")
        jobs_pending = _count(
            conn, "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('pending', 'running')"
        )
        mb_audio = _count(
            conn,
            """
            SELECT (
              (SELECT COUNT(*) FROM guided_capture_responses WHERE audio_uri IS NOT NULL)
              + (SELECT COUNT(*) FROM journal_versions WHERE audio_uri IS NOT NULL)
              + (SELECT COUNT(*) FROM story_versions WHERE audio_uri IS NOT NULL)
            ) AS c
            """,
        )
        last_job = _scalar_ts(
            conn, "SELECT MAX(finished_at) AS t FROM jobs WHERE finished_at IS NOT NULL"
        )
        last_story = _scalar_ts(conn, "SELECT MAX(updated_at) AS t FROM stories")
        last_journal = _scalar_ts(conn, "SELECT MAX(updated_at) AS t FROM journal_entries")
        last_gc = _scalar_ts(conn, "SELECT MAX(received_at) AS t FROM guided_capture_responses")
        earliest_journal = _scalar_ts(
            conn,
            """
            SELECT MIN(described_start_date) AS t FROM journal_entries
            WHERE status = 'active' AND described_start_date IS NOT NULL
              AND COALESCE(described_precision, 'unknown') <> 'unknown'
            """,
        )
        latest_journal = _scalar_ts(
            conn,
            """
            SELECT MAX(described_start_date) AS t FROM journal_entries
            WHERE status = 'active' AND described_start_date IS NOT NULL
              AND COALESCE(described_precision, 'unknown') <> 'unknown'
            """,
        )
        earliest_email = _scalar_ts(
            conn,
            """
            SELECT MIN(payload_json->>'sent_at') AS t FROM evidence
            WHERE evidence_kind = 'communication'
              AND NULLIF(payload_json->>'sent_at', '') IS NOT NULL
            """,
        )
        latest_email = _scalar_ts(
            conn,
            """
            SELECT MAX(payload_json->>'sent_at') AS t FROM evidence
            WHERE evidence_kind = 'communication'
              AND NULLIF(payload_json->>'sent_at', '') IS NOT NULL
            """,
        )

    last_activity_candidates = [t for t in (last_job, last_story, last_journal, last_gc) if t]
    last_activity = max(last_activity_candidates) if last_activity_candidates else None

    # --- Providers ---
    photo_health: dict[str, Any] = {"ok": False, "detail": "not probed"}
    video_health: dict[str, Any] = {"ok": False, "detail": "not probed"}

    photos_indexed = _metric(
        "photos_indexed",
        "Photos indexed",
        state="unavailable",
        source="immich:statistics",
        last_updated=calculated_at,
        reason="Not available",
        note="Immich statistics not yet obtained",
    )
    source_videos = _metric(
        "source_videos",
        "Source videos",
        state="unavailable",
        source="hvrt:list_videos",
        last_updated=calculated_at,
        reason="Not available",
        href="/review/ui",
    )
    video_duration = _metric(
        "source_video_duration_sec",
        "Source video duration (sec)",
        state="unavailable",
        source="hvrt:list_videos.duration_sec",
        last_updated=calculated_at,
        reason="Not available",
    )
    moments = _metric(
        "searchable_moments",
        "Searchable video moments",
        state="unavailable",
        source="hvrt:list_presence_spans",
        last_updated=calculated_at,
        reason="Not available",
        href="/library/ui",
    )
    media_root_metric = _metric(
        "source_videos_media_root",
        "Video files under MEMORYBOX_VIDEO_MEDIA_ROOT",
        state="unavailable",
        source="filesystem:MEMORYBOX_VIDEO_MEDIA_ROOT",
        last_updated=calculated_at,
        reason="Not available",
        note="Will scan when MEMORYBOX_VIDEO_MEDIA_ROOT is set on this serve process",
    )
    source_video_dates = _metric(
        "source_videos_dated_undated",
        "Source videos dated / undated",
        state="unavailable",
        source="hvrt:video_date",
        last_updated=calculated_at,
        reason=(
            "Not available — provider/domain does not currently expose reliable source date"
        ),
        note="Do not infer undated from missing DTO field",
    )
    provider_clusters_unlinked = _metric(
        "provider_identity_clusters_unlinked",
        "Provider identity clusters not linked to MB Person",
        state="unavailable",
        source="provider:face_clusters",
        last_updated=calculated_at,
        reason="Not available",
        note=(
            "Exact provider cluster-not-linked state is not reliably exposed; "
            "not synthesized from Immich people list"
        ),
        href="/review/ui",
    )
    unreviewed_identity = _metric(
        "unreviewed_identity_candidates",
        "Unreviewed identity candidates",
        state="unavailable",
        source="review:identity_queue",
        last_updated=calculated_at,
        reason="Not available",
        note=(
            "Status metric deferred — no durable unreviewed-identity queue distinct from "
            "unresolved MB People"
        ),
        href="/review/ui",
    )
    leverage_tasks: list[dict[str, Any]] = []

    try:
        from memorybox.ask.deps import build_photo, build_video

        photo = build_photo()
        ph = photo.health()
        photo_health = {"ok": bool(ph.ok), "detail": ph.detail, "provider": ph.provider_key}
        if ph.ok:
            client = getattr(photo, "_client", None)
            total_photos, photo_src = _immich_photo_total(client)
            if total_photos is not None:
                photos_indexed = _metric(
                    "photos_indexed",
                    "Photos indexed",
                    value=int(total_photos),
                    state="available",
                    source=photo_src,
                    last_updated=calculated_at,
                    href="/library/ui",
                )
            else:
                photos_indexed = _metric(
                    "photos_indexed",
                    "Photos indexed",
                    state="deferred",
                    source="immich:search/statistics|server/statistics",
                    last_updated=calculated_at,
                    reason="Not available",
                    note=(
                        f"{photo_src}. Immich is healthy (ping OK) but this API key "
                        "cannot read library totals — grant statistics/search.statistics "
                        "or use a key with asset.read + statistics access"
                    ),
                )
                deferred_notes.append("photos_indexed — Immich statistics permission")
        else:
            photos_indexed = _metric(
                "photos_indexed",
                "Photos indexed",
                state="unavailable",
                source="immich:health",
                last_updated=calculated_at,
                reason="Provider unavailable",
                note=ph.detail,
            )

        video = build_video()
        vh = video.health()
        video_health = {
            "ok": bool(vh.ok),
            "detail": vh.detail,
            "provider": vh.provider_key,
        }
        media_n, media_detail = _count_media_root_videos()
        media_root_metric = (
            _metric(
                "source_videos_media_root",
                "Video files under MEMORYBOX_VIDEO_MEDIA_ROOT",
                value=media_n,
                state="partial",
                source="filesystem:MEMORYBOX_VIDEO_MEDIA_ROOT",
                last_updated=calculated_at,
                reason="Partial — filesystem scan of configured media root",
                note=(
                    f"Recursive count under {media_detail}. "
                    "This is the family-video library on disk — not the same as "
                    "HVRT worker inventory unless the worker is pointed at this root."
                ),
            )
            if media_n is not None
            else _metric(
                "source_videos_media_root",
                "Video files under MEMORYBOX_VIDEO_MEDIA_ROOT",
                state="unavailable",
                source="filesystem:MEMORYBOX_VIDEO_MEDIA_ROOT",
                last_updated=calculated_at,
                reason="Not available",
                note=media_detail,
            )
        )

        if (vh.provider_key or "").startswith("fake"):
            # Do not present synthetic fake clips as the real Home Videos archive
            source_videos = _metric(
                "source_videos",
                "Source videos (via video provider)",
                state="unavailable",
                source="MEMORYBOX_VIDEO_PROVIDER",
                last_updated=calculated_at,
                reason="Not available — serve is using FakeVideoProvider",
                note=(
                    "Status/Ask are not talking to the HVRT video worker. "
                    "Set MEMORYBOX_VIDEO_PROVIDER=hvrt and MEMORYBOX_VIDEO_WORKER_URL "
                    "(e.g. http://127.0.0.1:8791), run `python -m memorybox.video_worker` "
                    "with MEMORYBOX_VIDEO_MEDIA_ROOT pointing at your Home Videos share, "
                    "then restart serve. Review needs the same worker for real inventory."
                ),
                href="/review/ui",
            )
            moments = _metric(
                "searchable_moments",
                "Searchable video moments",
                state="unavailable",
                source="MEMORYBOX_VIDEO_PROVIDER",
                last_updated=calculated_at,
                reason="Not available — FakeVideoProvider (synthetic spans only)",
                note="Start HVRT worker for real presence spans",
                href="/library/ui",
            )
            video_duration = _metric(
                "source_video_duration_sec",
                "Source video duration (sec)",
                state="unavailable",
                source="MEMORYBOX_VIDEO_PROVIDER",
                last_updated=calculated_at,
                reason="Not available — FakeVideoProvider",
            )
        elif vh.ok:
            try:
                vids = video.list_videos(limit=5000)
                n_vids = len(vids)
                bounded = n_vids >= 5000
                dur = 0.0
                dur_known = 0
                for v in vids:
                    if v.duration_sec is not None:
                        dur += float(v.duration_sec)
                        dur_known += 1
                source_videos = _metric(
                    "source_videos",
                    "Source videos (via video provider)",
                    value=n_vids,
                    display=f"{n_vids:,}{'+' if bounded else ''}",
                    state="partial" if bounded else "available",
                    source="hvrt:list_videos",
                    last_updated=calculated_at,
                    href="/review/ui",
                    note=(
                        f"Provider={vh.provider_key}. Bounded list ≤5000."
                        + (" Count may be incomplete." if bounded else "")
                    ),
                    reason="Bounded list" if bounded else None,
                )
                if dur_known > 0:
                    video_duration = _metric(
                        "source_video_duration_sec",
                        "Source video duration (sec)",
                        value=int(dur),
                        state="partial",
                        source="hvrt:list_videos.duration_sec",
                        last_updated=calculated_at,
                        reason=f"Summed from {dur_known}/{n_vids} videos with duration",
                        note=f"Partial — {dur_known}/{n_vids} videos expose duration_sec",
                    )
                else:
                    video_duration = _metric(
                        "source_video_duration_sec",
                        "Source video duration (sec)",
                        state="unavailable",
                        source="hvrt:list_videos.duration_sec",
                        last_updated=calculated_at,
                        reason="Not available",
                    )
                source_video_dates = _metric(
                    "source_videos_dated_undated",
                    "Source videos dated / undated",
                    state="unavailable",
                    source="hvrt:video_date",
                    last_updated=calculated_at,
                    reason=(
                        "Not available — provider/domain does not currently expose "
                        "reliable source date"
                    ),
                )
                spans = video.list_presence_spans(limit=5000)
                n_mom = len(spans)
                mom_bounded = n_mom >= 5000
                moments = _metric(
                    "searchable_moments",
                    "Searchable video moments",
                    value=n_mom,
                    display=f"{n_mom:,}{'+' if mom_bounded else ''}",
                    state="partial" if mom_bounded else "available",
                    source="hvrt:list_presence_spans",
                    last_updated=calculated_at,
                    href="/library/ui",
                    note=(
                        "Derived presence spans (rebuildable). Bounded ≤5000. "
                        "Not the same inventory as source videos."
                    ),
                    reason="Bounded list" if mom_bounded else None,
                )
            except Exception as exc:  # noqa: BLE001
                source_videos = _metric(
                    "source_videos",
                    "Source videos (via video provider)",
                    state="unavailable",
                    source="hvrt:list_videos",
                    last_updated=calculated_at,
                    reason="Not available",
                    note=str(exc),
                )
                moments = _metric(
                    "searchable_moments",
                    "Searchable video moments",
                    state="unavailable",
                    source="hvrt:list_presence_spans",
                    last_updated=calculated_at,
                    reason="Not available",
                    note=str(exc),
                )
        else:
            source_videos = _metric(
                "source_videos",
                "Source videos (via video provider)",
                state="unavailable",
                source="hvrt:health",
                last_updated=calculated_at,
                reason="Provider unavailable",
                note=vh.detail,
            )
            moments = _metric(
                "searchable_moments",
                "Searchable video moments",
                state="unavailable",
                source="hvrt:health",
                last_updated=calculated_at,
                reason="Provider unavailable",
                note=vh.detail,
            )
            source_video_dates = _metric(
                "source_videos_dated_undated",
                "Source videos dated / undated",
                state="unavailable",
                source="hvrt:video_date",
                last_updated=calculated_at,
                reason=(
                    "Not available — provider/domain does not currently expose "
                    "reliable source date"
                ),
            )
    except Exception as exc:  # noqa: BLE001
        photo_health = {"ok": False, "detail": str(exc)}
        video_health = {"ok": False, "detail": str(exc)}
        media_root_metric = _metric(
            "source_videos_media_root",
            "Video files under MEMORYBOX_VIDEO_MEDIA_ROOT",
            state="unavailable",
            source="filesystem:MEMORYBOX_VIDEO_MEDIA_ROOT",
            last_updated=calculated_at,
            reason="Not available",
            note=str(exc),
        )

    try:
        email_st = email_adapter_status()
    except Exception as exc:  # noqa: BLE001
        email_st = {"ok": False, "detail": str(exc)}

    db_ok = False
    try:
        db_ok = bool(ping())
    except Exception:  # noqa: BLE001
        db_ok = False

    from memorybox.config import settings

    qdrant_detail = settings.qdrant_url or "unset"
    qdrant_n, qdrant_src = _qdrant_point_count()
    ollama_metric = _ollama_status(calculated_at)

    # Archive Health tasks from real attention signals only (no dating approx)
    if people_unresolved > 0:
        n = min(5, people_unresolved)
        leverage_tasks.append(
            {
                "text": f"Identify up to {n} unresolved People when you're ready.",
                "href": "/people/ui",
                "kind": "attention",
            }
        )
    if gc_new > 0:
        n = min(5, gc_new)
        leverage_tasks.append(
            {
                "text": f"Review {n} new Guided Capture response{'s' if n != 1 else ''}.",
                "href": "/guided-capture/ui",
                "kind": "attention",
            }
        )
    if artifacts - art_with_story > 0:
        n = min(3, artifacts - art_with_story)
        leverage_tasks.append(
            {
                "text": (
                    f"Add Story/context to {n} Artifact{'s' if n != 1 else ''} "
                    "(optional — Artifacts are valid without Person links)."
                ),
                "href": "/artifact/ui",
                "kind": "attention",
            }
        )
    if journals_undated > 0:
        n = min(5, journals_undated)
        leverage_tasks.append(
            {
                "text": (
                    f"Review {n} Journal entr{'ies' if n != 1 else 'y'} "
                    "missing meaningful described dates."
                ),
                "href": "/journal/ui",
                "kind": "attention",
            }
        )
    if jobs_error > 0:
        leverage_tasks.append(
            {
                "text": f"{jobs_error} processing job(s) failed — check Processing tab.",
                "href": None,
                "kind": "failed",
            }
        )
    leverage_tasks = leverage_tasks[:5]

    deferred_notes.extend(
        [
            "Photo date/location/favorites/duplicates/blur — deferred",
            "Videos awaiting analysis queue — deferred",
            "Documents awaiting OCR — deferred",
            "Photo/video % linked to known People — deferred",
            "Provider face-cluster-not-linked exact count — unavailable (not synthesized)",
            "SMS ingest — Not connected in P1",
            "Source video dated/undated — unavailable until reliable date exposed",
            "High-leverage video dating task — omitted until source→moment dates computable",
        ]
    )

    pg = "postgresql"
    tabs = {
        "archive_summary": {
            "title": "Archive Summary",
            "sections": [
                {
                    "title": "Knowledge",
                    "metrics": [
                        _metric(
                            "people",
                            "People",
                            value=people_total,
                            state="available",
                            source=f"{pg}:people",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "stories",
                            "Stories",
                            value=stories,
                            state="available",
                            source=f"{pg}:stories",
                            last_updated=calculated_at,
                            href="/story/ui",
                        ),
                        _metric(
                            "journals",
                            "Journal Entries",
                            value=journals,
                            state="available",
                            source=f"{pg}:journal_entries",
                            last_updated=calculated_at,
                            href="/journal/ui",
                        ),
                        _metric(
                            "gc_responses",
                            "Guided Capture Responses",
                            value=gc_responses,
                            state="available",
                            source=f"{pg}:guided_capture_responses",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "artifacts",
                            "Artifacts / Keepsakes",
                            value=artifacts,
                            state="available",
                            source=f"{pg}:artifacts",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                        ),
                    ],
                },
                {
                    "title": "Media / Evidence",
                    "metrics": [
                        source_videos,
                        media_root_metric,
                        moments,
                        _metric(
                            "mb_managed_audio",
                            "MemoryBox-managed audio recordings",
                            value=mb_audio,
                            state="partial",
                            source=f"{pg}:audio_uri columns",
                            last_updated=calculated_at,
                            reason="Partial — MB-stored audio_uri rows only",
                            note=(
                                "Counts Guided Capture / Journal / Story audio_uri values "
                                "MemoryBox retains — not Immich/HVRT audio libraries"
                            ),
                        ),
                        _metric(
                            "emails",
                            "Emails indexed in MemoryBox Evidence (PostgreSQL)",
                            value=emails,
                            state="available",
                            source=f"{pg}:evidence.communication",
                            last_updated=calculated_at,
                            note=(
                                "This is the MemoryBox Evidence row count — not a Gmail "
                                "mailbox total. If a prior mbox ingest was ~94k messages but "
                                "this shows far fewer, those messages are not present as "
                                "communication Evidence in this database (re-ingest or check "
                                "which DB/serve host was used)."
                            ),
                        ),
                        (
                            _metric(
                                "emails_qdrant",
                                "Qdrant evidence points (all kinds)",
                                value=qdrant_n,
                                state="partial",
                                source=qdrant_src,
                                last_updated=calculated_at,
                                reason="Partial — includes all indexed evidence kinds, not email-only",
                                note="Compare to PG Evidence if index was rebuilt from a larger corpus",
                            )
                            if qdrant_n is not None
                            else _metric(
                                "emails_qdrant",
                                "Qdrant evidence points (all kinds)",
                                state="unavailable",
                                source="qdrant",
                                last_updated=calculated_at,
                                reason="Not available",
                                note=qdrant_src,
                            )
                        ),
                        _metric(
                            "calendar",
                            "Calendar events",
                            value=calendars,
                            state="available",
                            source=f"{pg}:evidence.calendar_event",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "sms",
                            "SMS / Text Messages",
                            state="unavailable",
                            source="sms:ingest",
                            last_updated=calculated_at,
                            reason="Not yet connected",
                            note="P1 does not ingest SMS",
                        ),
                        _metric(
                            "artifact_documents",
                            "Artifact-backed documents / letters",
                            value=art_docs,
                            state="partial",
                            source=f"{pg}:artifacts.kind in (document, letter)",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                            reason="Partial — Artifact kinds only",
                            note="Does not include Immich documents or a full scan OCR corpus",
                        ),
                    ],
                },
                {
                    "title": "Processing / attention",
                    "metrics": [
                        provider_clusters_unlinked,
                        _metric(
                            "people_unresolved",
                            "Unresolved MB People",
                            value=people_unresolved,
                            state="available",
                            source=f"{pg}:people.status=unresolved",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        unreviewed_identity,
                        _metric(
                            "gc_new",
                            "New Guided Capture responses",
                            value=gc_new,
                            state="available",
                            source=f"{pg}:guided_capture_responses.review_status=new",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "videos_awaiting_analysis",
                            "Videos awaiting analysis",
                            state="deferred",
                            source="hvrt:pending_analysis",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — no durable pending-analysis queue",
                        ),
                        _metric(
                            "audio_awaiting_stt",
                            "GC audio awaiting / failed transcription",
                            value=gc_stt_pending + gc_stt_fail,
                            state="partial",
                            source=f"{pg}:guided_capture_responses.stt_status",
                            last_updated=calculated_at,
                            reason=f"pending={gc_stt_pending} failed={gc_stt_fail}",
                            href="/guided-capture/ui",
                            note="Guided Capture STT states only",
                        ),
                        _metric(
                            "ocr_pending",
                            "Documents awaiting OCR",
                            state="deferred",
                            source="ocr:queue",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "jobs_error",
                            "Processing errors (jobs)",
                            value=jobs_error,
                            state="available",
                            source=f"{pg}:jobs.status=error",
                            last_updated=calculated_at,
                        ),
                    ],
                },
                {
                    "title": "Last activity",
                    "metrics": [
                        _metric(
                            "last_activity",
                            "Last ingest / domain update",
                            display=last_activity or "Unknown",
                            state="available" if last_activity else "unavailable",
                            source=f"{pg}:max(jobs/stories/journals/gc)",
                            last_updated=calculated_at,
                            reason="Unknown" if not last_activity else None,
                            note="Record/activity timestamps — not archive life chronology",
                        ),
                    ],
                },
            ],
        },
        "people": {
            "title": "People & Identity",
            "sections": [
                {
                    "title": "People (states kept separate)",
                    "metrics": [
                        _metric(
                            "people_named",
                            "Known / named People",
                            value=people_named,
                            state="available",
                            source=f"{pg}:people",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "people_confirmed",
                            "Owner-confirmed People",
                            value=people_confirmed,
                            state="available",
                            source=f"{pg}:people.status=confirmed",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "people_unresolved",
                            "Unresolved MB People",
                            value=people_unresolved,
                            state="available",
                            source=f"{pg}:people.status=unresolved",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "provider_identities",
                            "Provider identity mappings",
                            value=provider_identities,
                            state="available",
                            source=f"{pg}:provider_identities",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "provider_identities_unlinked",
                            "Provider identities without linked MB Person",
                            value=provider_identities_unlinked,
                            state="available",
                            source=f"{pg}:provider_identities.person_id IS NULL",
                            last_updated=calculated_at,
                            href="/people/ui",
                            note="MB mapping rows only — not Immich face-cluster census",
                        ),
                        provider_clusters_unlinked,
                        unreviewed_identity,
                        _metric(
                            "relationships",
                            "Relationships recorded (current)",
                            value=rel_current,
                            state="available",
                            source=f"{pg}:person_relationship_assertions",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "family_relationships",
                            "Direct family relationships (thin vocab)",
                            value=rel_family,
                            state="partial",
                            source=f"{pg}:person_relationship_assertions.role_kind",
                            last_updated=calculated_at,
                            href="/people/ui",
                            reason="Partial — thin P1 role vocabulary only",
                        ),
                        _metric(
                            "photo_link_pct",
                            "Photos linked to known People",
                            state="deferred",
                            source="immich×people",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — expensive Immich corpus join",
                        ),
                        _metric(
                            "video_link_pct",
                            "Video moments linked to known People",
                            state="deferred",
                            source="hvrt×people",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — requires full span×identity census",
                        ),
                    ],
                }
            ],
        },
        "photos": {
            "title": "Photos",
            "sections": [
                {
                    "title": "Inventory",
                    "metrics": [
                        photos_indexed,
                        _metric(
                            "photo_dates",
                            "Photos with reliable dates",
                            state="deferred",
                            source="immich:asset_dates",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_location",
                            "Photos with location",
                            state="deferred",
                            source="immich:asset_location",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_favorites",
                            "Favorites",
                            state="deferred",
                            source="immich:favorites",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_duplicates",
                            "Potential duplicates",
                            state="deferred",
                            source="immich:duplicates",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_blur",
                            "Low-quality / blurred",
                            state="deferred",
                            source="image_quality",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — no image-quality engine in P1",
                        ),
                    ],
                }
            ],
        },
        "video": {
            "title": "Video",
            "sections": [
                {
                    "title": "SOURCE VIDEOS (preserved files)",
                    "metrics": [
                        source_videos,
                        media_root_metric,
                        video_duration,
                        source_video_dates,
                        _metric(
                            "videos_with_transcripts",
                            "Videos with transcripts",
                            state="deferred",
                            source="hvrt:transcripts",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "videos_awaiting_analysis",
                            "Videos pending analysis",
                            state="deferred",
                            source="hvrt:pending_analysis",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — no durable pending-analysis queue",
                        ),
                    ],
                },
                {
                    "title": "SEARCHABLE VIDEO MOMENTS (derived)",
                    "metrics": [
                        moments,
                        _metric(
                            "moments_note",
                            "Note",
                            display="Source videos ≠ searchable moments",
                            state="available",
                            source="product_rule",
                            last_updated=calculated_at,
                            note="Moments/spans are rebuildable; not a second film archive",
                        ),
                    ],
                },
                {
                    "title": "High-leverage cleanup",
                    "metrics": [],
                    "intro": (
                        "Dating leverage appears only when source→moment dates are "
                        "computable from real relationships."
                    ),
                    "tasks": [t for t in leverage_tasks if t.get("kind") == "high_leverage"],
                },
            ],
        },
        "stories_knowledge": {
            "title": "Stories & Knowledge",
            "sections": [
                {
                    "title": "Stories",
                    "metrics": [
                        _metric(
                            "stories",
                            "Story count",
                            value=stories,
                            state="available",
                            source=f"{pg}:stories",
                            last_updated=calculated_at,
                            href="/story/ui",
                        ),
                        _metric(
                            "stories_narrator",
                            "Stories with narrator identified",
                            value=stories_narrator,
                            state="available",
                            source=f"{pg}:stories.narrator_person_id",
                            last_updated=calculated_at,
                            href="/story/ui",
                        ),
                        _metric(
                            "stories_people",
                            "Stories linked to People",
                            value=stories_with_people,
                            state="available",
                            source=f"{pg}:relationships.about_person",
                            last_updated=calculated_at,
                            href="/story/ui",
                        ),
                        _metric(
                            "stories_evidence",
                            "Stories linked to Evidence",
                            value=stories_with_evidence,
                            state="available",
                            source=f"{pg}:relationships.cites_evidence",
                            last_updated=calculated_at,
                            href="/story/ui",
                        ),
                        _metric(
                            "stories_undated",
                            "Stories without life/event date (undated)",
                            value=stories_undated,
                            state="available",
                            source=f"{pg}:stories (no event date field)",
                            last_updated=calculated_at,
                            note=(
                                "Stories have no life/event date; created_at is record metadata "
                                "only and is not used as archive chronology"
                            ),
                        ),
                    ],
                },
                {
                    "title": "Journal",
                    "metrics": [
                        _metric(
                            "journals",
                            "Journal Entry count",
                            value=journals,
                            state="available",
                            source=f"{pg}:journal_entries",
                            last_updated=calculated_at,
                            href="/journal/ui",
                        ),
                        _metric(
                            "journals_dated",
                            "Entries with described/effective dates",
                            value=journals_dated,
                            state="available",
                            source=f"{pg}:journal_entries.described_start_date",
                            last_updated=calculated_at,
                            href="/journal/ui",
                        ),
                        _metric(
                            "journals_undated",
                            "Entries missing meaningful dates",
                            value=journals_undated,
                            state="available",
                            source=f"{pg}:journal_entries",
                            last_updated=calculated_at,
                            href="/journal/ui",
                        ),
                    ],
                },
                {
                    "title": "Guided Capture Responses",
                    "metrics": [
                        _metric(
                            "gc_responses",
                            "Total Responses",
                            value=gc_responses,
                            state="available",
                            source=f"{pg}:guided_capture_responses",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_new",
                            "New / unreviewed",
                            value=gc_new,
                            state="available",
                            source=f"{pg}:review_status=new",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_reviewed",
                            "Reviewed",
                            value=gc_reviewed,
                            state="available",
                            source=f"{pg}:review_status=reviewed",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_typed",
                            "Typed responses",
                            value=gc_typed,
                            state="available",
                            source=f"{pg}:channel=email_text",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "gc_voice",
                            "Voice responses",
                            value=gc_voice,
                            state="available",
                            source=f"{pg}:channel=voice",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "gc_cred",
                            "Credibility rated",
                            value=gc_cred,
                            state="available",
                            source=f"{pg}:credibility",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "gc_no_cred",
                            "Not rated",
                            value=gc_no_cred,
                            state="available",
                            source=f"{pg}:credibility IS NULL",
                            last_updated=calculated_at,
                        ),
                    ],
                },
            ],
        },
        "artifacts": {
            "title": "Artifacts",
            "sections": [
                {
                    "title": "Inventory",
                    "metrics": [
                        _metric(
                            "artifacts",
                            "Total Artifacts",
                            value=artifacts,
                            state="available",
                            source=f"{pg}:artifacts",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                        ),
                        *[
                            _metric(
                                f"artifact_kind_{k}",
                                f"Kind: {k}",
                                value=v,
                                state="available",
                                source=f"{pg}:artifacts.kind",
                                last_updated=calculated_at,
                                href="/artifact/ui",
                            )
                            for k, v in sorted(art_by_kind.items())
                        ],
                        _metric(
                            "art_with_story",
                            "Artifacts with Story/context link",
                            value=art_with_story,
                            state="available",
                            source=f"{pg}:relationships",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                        ),
                        _metric(
                            "art_without_story",
                            "Artifacts missing Story/context",
                            value=max(0, artifacts - art_with_story),
                            state="available",
                            source=f"{pg}:artifacts",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                            note="Not an error — context is optional enrichment",
                        ),
                        _metric(
                            "art_with_person",
                            "Artifacts linked to People",
                            value=art_with_person,
                            state="available",
                            source=f"{pg}:relationships.about_person",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                        ),
                        _metric(
                            "art_without_person",
                            "Artifacts not linked to People",
                            value=max(0, artifacts - art_with_person),
                            state="available",
                            source=f"{pg}:artifacts",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                            note="Valid without Person — not an error",
                        ),
                    ],
                }
            ],
        },
        "communications": {
            "title": "Communications",
            "sections": [
                {
                    "title": "Email",
                    "metrics": [
                        _metric(
                            "emails",
                            "Email messages indexed in MemoryBox Evidence (PostgreSQL)",
                            value=emails,
                            state="available",
                            source=f"{pg}:evidence.communication",
                            last_updated=calculated_at,
                            note=(
                                "PG Evidence count only. A historical ~94k Gmail/mbox ingest "
                                "is not reflected here unless those rows exist in this database."
                            ),
                        ),
                        _metric(
                            "email_correspondents",
                            "Recognized correspondents",
                            state="deferred",
                            source="comms:correspondents",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — no durable correspondent SoT census",
                        ),
                    ],
                },
                {
                    "title": "Guided Capture campaigns",
                    "metrics": [
                        _metric(
                            "gc_draft",
                            "Draft",
                            value=gc_campaigns["draft"],
                            state="available",
                            source=f"{pg}:guided_capture_campaigns",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_running",
                            "Running",
                            value=gc_campaigns["running"],
                            state="available",
                            source=f"{pg}:guided_capture_campaigns",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_paused",
                            "Paused",
                            value=gc_campaigns["paused"],
                            state="available",
                            source=f"{pg}:guided_capture_campaigns",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_complete",
                            "Completed / exhausted (outbound_complete)",
                            value=gc_campaigns["outbound_complete"],
                            state="available",
                            source=f"{pg}:guided_capture_campaigns",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_stopped",
                            "Stopped",
                            value=gc_campaigns["stopped"],
                            state="available",
                            source=f"{pg}:guided_capture_campaigns",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_pending_q",
                            "Questions waiting to send",
                            value=gc_pending_deliveries,
                            state="available",
                            source=f"{pg}:guided_capture_deliveries.pending",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_new",
                            "New responses",
                            value=gc_new,
                            state="available",
                            source=f"{pg}:guided_capture_responses",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                    ],
                },
                {
                    "title": "SMS",
                    "metrics": [
                        _metric(
                            "sms",
                            "SMS / Text Messages",
                            state="unavailable",
                            source="sms:ingest",
                            last_updated=calculated_at,
                            reason="Not yet connected",
                        ),
                    ],
                },
            ],
        },
        "timeline": {
            "title": "Timeline",
            "sections": [
                {
                    "title": "Coverage (honest, modality-aware)",
                    "metrics": [
                        _metric(
                            "earliest_journal",
                            "Earliest Journal described date",
                            display=earliest_journal or "Unknown",
                            state="available" if earliest_journal else "unavailable",
                            source=f"{pg}:journal_entries.described_start_date",
                            last_updated=calculated_at,
                            reason="Unknown" if not earliest_journal else None,
                            href="/library/ui",
                            note="Uses described/effective date, not capture-only",
                        ),
                        _metric(
                            "latest_journal",
                            "Latest Journal described date",
                            display=latest_journal or "Unknown",
                            state="available" if latest_journal else "unavailable",
                            source=f"{pg}:journal_entries.described_start_date",
                            last_updated=calculated_at,
                            reason="Unknown" if not latest_journal else None,
                            href="/library/ui",
                        ),
                        _metric(
                            "earliest_email",
                            "Earliest email sent_at",
                            display=earliest_email or "Unknown",
                            state="available" if earliest_email else "unavailable",
                            source=f"{pg}:evidence.payload_json.sent_at",
                            last_updated=calculated_at,
                            reason="Unknown" if not earliest_email else None,
                            note="Genuine communication event date",
                        ),
                        _metric(
                            "latest_email",
                            "Latest email sent_at",
                            display=latest_email or "Unknown",
                            state="available" if latest_email else "unavailable",
                            source=f"{pg}:evidence.payload_json.sent_at",
                            last_updated=calculated_at,
                            reason="Unknown" if not latest_email else None,
                        ),
                        _metric(
                            "journals_dated",
                            "Journal entries with reliable described date",
                            value=journals_dated,
                            state="available",
                            source=f"{pg}:journal_entries",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "journals_undated",
                            "Journal entries undated / unknown precision",
                            value=journals_undated,
                            state="available",
                            source=f"{pg}:journal_entries",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "emails_dated",
                            "Emails with sent_at",
                            value=emails_dated,
                            state="available",
                            source=f"{pg}:evidence.communication",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "calendars_dated",
                            "Calendar events with start date",
                            value=calendars_dated,
                            state="partial",
                            source=f"{pg}:evidence.calendar_event payload start fields",
                            last_updated=calculated_at,
                            reason="Partial — depends on ICS payload fields present",
                        ),
                        _metric(
                            "stories_undated",
                            "Stories undated (no life/event date)",
                            value=stories_undated,
                            state="available",
                            source=f"{pg}:stories",
                            last_updated=calculated_at,
                            note=(
                                "Story created_at is record creation only — not used as "
                                "archive chronology"
                            ),
                        ),
                        source_video_dates,
                        _metric(
                            "year_coverage",
                            "Strongest / weakest coverage years",
                            state="deferred",
                            source="timeline:year_histogram",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — avoid false precision in thin Status",
                        ),
                    ],
                }
            ],
        },
        "sources": {
            "title": "Sources & Providers",
            "sections": [
                {
                    "title": "Dependencies",
                    "metrics": [
                        _metric(
                            "postgres",
                            "PostgreSQL",
                            display="OK" if db_ok else "unavailable",
                            state="available" if db_ok else "unavailable",
                            source="memorybox.db.ping",
                            last_updated=calculated_at,
                            reason=None if db_ok else "unavailable",
                        ),
                        _metric(
                            "qdrant",
                            "Qdrant",
                            display=qdrant_detail,
                            state="partial" if settings.qdrant_url else "unavailable",
                            source="MEMORYBOX_QDRANT_URL",
                            last_updated=calculated_at,
                            reason="Not connected" if not settings.qdrant_url else "Configured URL shown",
                            note="Live ping not required for thin Status",
                        ),
                        ollama_metric,
                        _metric(
                            "immich",
                            "Immich",
                            display="OK" if photo_health.get("ok") else "unavailable",
                            state="available" if photo_health.get("ok") else "unavailable",
                            source="immich:health",
                            last_updated=calculated_at,
                            reason=None if photo_health.get("ok") else "unavailable",
                            note=str(photo_health.get("detail") or ""),
                        ),
                        _metric(
                            "hvrt",
                            "HVRT / Video worker",
                            display="OK" if video_health.get("ok") else "unavailable",
                            state="available" if video_health.get("ok") else "unavailable",
                            source="hvrt:health",
                            last_updated=calculated_at,
                            reason=None if video_health.get("ok") else "unavailable",
                            note=str(video_health.get("detail") or ""),
                        ),
                        _metric(
                            "gmail",
                            "Gmail / Guided Capture email",
                            display="OK" if email_st.get("ok") else "degraded / unavailable",
                            state="available" if email_st.get("ok") else "unavailable",
                            source="guided_capture:email_adapter_status",
                            last_updated=calculated_at,
                            note=str(email_st.get("detail") or email_st),
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "calendar_source",
                            "Calendar (ICS evidence)",
                            value=calendars,
                            state="available",
                            source=f"{pg}:evidence.calendar_event",
                            last_updated=calculated_at,
                            note="Indexed calendar_event evidence rows",
                        ),
                        _metric(
                            "artifact_storage",
                            "Artifact storage",
                            display="Configured via MEMORYBOX_ARTIFACT_MEDIA_ROOT",
                            state="partial",
                            source="MEMORYBOX_ARTIFACT_MEDIA_ROOT",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                            reason="Partial — path configured; live disk probe not required",
                        ),
                    ],
                }
            ],
        },
        "processing": {
            "title": "Processing",
            "sections": [
                {
                    "title": "Queues / jobs (distinct states)",
                    "metrics": [
                        _metric(
                            "jobs_pending",
                            "Pending / running jobs",
                            value=jobs_pending,
                            state="available",
                            source=f"{pg}:jobs",
                            last_updated=calculated_at,
                            note="Pending ≠ Unreviewed ≠ Unknown ≠ Failed",
                        ),
                        _metric(
                            "jobs_error",
                            "Failed processing jobs",
                            value=jobs_error,
                            state="available",
                            source=f"{pg}:jobs.status=error",
                            last_updated=calculated_at,
                        ),
                        _metric(
                            "gc_new",
                            "Unreviewed Guided Capture (attention, not failure)",
                            value=gc_new,
                            state="available",
                            source=f"{pg}:guided_capture_responses",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "people_unresolved",
                            "Unresolved MB People (attention, not failure)",
                            value=people_unresolved,
                            state="available",
                            source=f"{pg}:people",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "gc_stt",
                            "GC audio STT pending / failed",
                            display=f"pending={gc_stt_pending} failed={gc_stt_fail}",
                            state="partial",
                            source=f"{pg}:guided_capture_responses.stt_status",
                            last_updated=calculated_at,
                            reason=f"pending={gc_stt_pending} failed={gc_stt_fail}",
                        ),
                        _metric(
                            "ocr",
                            "Documents awaiting OCR",
                            state="deferred",
                            source="ocr:queue",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "video_pending",
                            "Videos awaiting analysis",
                            state="deferred",
                            source="hvrt:pending_analysis",
                            last_updated=calculated_at,
                            reason="Not available",
                            note="Status metric deferred — no durable pending-analysis queue",
                        ),
                    ],
                }
            ],
        },
        "archive_health": {
            "title": "Archive Health",
            "sections": [
                {
                    "title": "Strong coverage",
                    "intro": "No universal archive-health percentage is computed or displayed.",
                    "metrics": [
                        _metric(
                            "people",
                            "People",
                            value=people_total,
                            state="available",
                            source=f"{pg}:people",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "emails",
                            "Emails in Evidence (PG)",
                            value=emails,
                            state="available",
                            source=f"{pg}:evidence",
                            last_updated=calculated_at,
                            note="PostgreSQL Evidence communication rows — not Gmail mailbox total",
                        ),
                        _metric(
                            "calendar",
                            "Calendar events",
                            value=calendars,
                            state="available",
                            source=f"{pg}:evidence",
                            last_updated=calculated_at,
                        ),
                        photos_indexed,
                    ],
                },
                {
                    "title": "Needs attention",
                    "metrics": [
                        _metric(
                            "people_unresolved",
                            "Unresolved MB People",
                            value=people_unresolved,
                            state="available",
                            source=f"{pg}:people",
                            last_updated=calculated_at,
                            href="/people/ui",
                        ),
                        _metric(
                            "gc_new",
                            "New Guided Capture responses",
                            value=gc_new,
                            state="available",
                            source=f"{pg}:guided_capture_responses",
                            last_updated=calculated_at,
                            href="/guided-capture/ui",
                        ),
                        source_video_dates,
                        _metric(
                            "art_without_story",
                            "Artifacts without Story/context",
                            value=max(0, artifacts - art_with_story),
                            state="available",
                            source=f"{pg}:artifacts",
                            last_updated=calculated_at,
                            href="/artifact/ui",
                            note="Optional enrichment — not broken",
                        ),
                    ],
                },
                {
                    "title": "HIGH-LEVERAGE HELP",
                    "metrics": [],
                    "intro": "When you're ready, I can help.",
                    "tasks": leverage_tasks,
                },
            ],
        },
    }

    return {
        "ok": True,
        "calculated_at": calculated_at,
        "default_tab": "archive_summary",
        "metric_contract": {
            "fields": [
                "key",
                "label",
                "value",
                "display",
                "state",
                "available",
                "source",
                "last_updated",
                "reason",
                "href",
                "note",
            ],
            "states": ["available", "unavailable", "partial", "deferred"],
            "rule": "Client must not interpret unavailable/deferred as zero",
        },
        "tabs": tabs,
        "deferred_notes": deferred_notes,
        "nav": [
            {"id": "archive_summary", "label": "Archive Summary"},
            {"id": "people", "label": "People & Identity"},
            {"id": "photos", "label": "Photos"},
            {"id": "video", "label": "Video"},
            {"id": "stories_knowledge", "label": "Stories & Knowledge"},
            {"id": "artifacts", "label": "Artifacts"},
            {"id": "communications", "label": "Communications"},
            {"id": "timeline", "label": "Timeline"},
            {"id": "sources", "label": "Sources & Providers"},
            {"id": "processing", "label": "Processing"},
            {"id": "archive_health", "label": "Archive Health"},
        ],
        "links": {
            "people": "/people/ui",
            "review": "/review/ui",
            "story": "/story/ui",
            "journal": "/journal/ui",
            "artifact": "/artifact/ui",
            "guided_capture": "/guided-capture/ui",
            "library": "/library/ui",
            "ask": "/ask/ui",
            "export": "/export/ui",
            "status": "/status/ui",
        },
    }
