"""Increment 12A — thin Status summary (read-only; not P2 Dashboard)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from memorybox.db import connection, ping
from memorybox.guided_capture import email_adapter_status, new_response_count


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(
    key: str,
    label: str,
    *,
    value: Any = None,
    display: str | None = None,
    available: bool = True,
    href: str | None = None,
    reason: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if display is None:
        if not available:
            display = reason or "Not available"
        elif value is None:
            display = "—"
        else:
            display = f"{value:,}" if isinstance(value, int) else str(value)
    return {
        "key": key,
        "label": label,
        "value": value,
        "display": display,
        "available": available,
        "href": href,
        "reason": reason,
        "note": note,
    }


def _count(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return 0
    # dict_row or tuple
    if isinstance(row, dict):
        return int(next(iter(row.values())))
    return int(row[0])


def _scalar_ts(conn: Any, sql: str) -> str | None:
    row = conn.execute(sql).fetchone()
    if not row:
        return None
    v = next(iter(row.values())) if isinstance(row, dict) else row[0]
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def build_status_summary() -> dict[str, Any]:
    """Assemble Status payload for all tabs. Never invent unsupported counts as 0."""
    calculated_at = _iso_now()
    deferred: list[str] = []

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
        jobs_error = _count(conn, "SELECT COUNT(*) AS c FROM jobs WHERE status = 'error'")
        jobs_pending = _count(
            conn, "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('pending', 'running')"
        )
        audio_uris = _count(
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

    last_activity_candidates = [t for t in (last_job, last_story, last_journal, last_gc) if t]
    last_activity = max(last_activity_candidates) if last_activity_candidates else None

    # --- Providers (bounded; down ≠ zero) ---
    photo_health = {"ok": False, "detail": "not probed"}
    video_health = {"ok": False, "detail": "not probed"}
    photos_indexed = _metric(
        "photos_indexed",
        "Photos indexed",
        available=False,
        reason="Not available",
        note="Status metric deferred — Immich statistics not wrapped; provider probe below",
    )
    immich_people = _metric(
        "immich_face_people",
        "Immich people / face clusters (provider)",
        available=False,
        reason="Not available",
        href="/review/ui",
    )
    source_videos = _metric(
        "source_videos",
        "Source videos",
        available=False,
        reason="Not available",
        href="/review/ui",
    )
    video_duration = _metric(
        "source_video_duration_sec",
        "Source video duration (sec, partial)",
        available=False,
        reason="Not available",
    )
    moments = _metric(
        "searchable_moments",
        "Searchable video moments",
        available=False,
        reason="Not available",
        href="/library/ui",
    )
    leverage_tasks: list[dict[str, Any]] = []

    try:
        from memorybox.ask.deps import build_photo, build_video

        photo = build_photo()
        ph = photo.health()
        photo_health = {"ok": bool(ph.ok), "detail": ph.detail, "provider": ph.provider_key}
        if ph.ok:
            try:
                people_refs = photo.list_people(limit=500)
                immich_people = _metric(
                    "immich_face_people",
                    "Immich people / face clusters (provider)",
                    value=len(people_refs),
                    href="/people/ui",
                    note="Bounded list (≤500); not a full Immich census",
                )
                # Try Immich statistics without making Status SoT
                client = getattr(photo, "_client", None)
                total_photos = None
                if client is not None and hasattr(client, "_request"):
                    for path in ("/server/statistics", "/assets/statistics"):
                        try:
                            status, body = client._request("GET", path)  # noqa: SLF001
                            if status == 200 and isinstance(body, dict):
                                for k in ("photos", "photo", "total", "assets"):
                                    if isinstance(body.get(k), int):
                                        total_photos = int(body[k])
                                        break
                                usage = body.get("usageByUser") or body.get("usage")
                                if total_photos is None and isinstance(body.get("photos"), dict):
                                    total_photos = body["photos"].get("count")
                                if total_photos is not None:
                                    break
                        except Exception:  # noqa: BLE001
                            continue
                if total_photos is not None:
                    photos_indexed = _metric(
                        "photos_indexed",
                        "Photos indexed",
                        value=int(total_photos),
                        href="/library/ui",
                        note="From Immich statistics endpoint",
                    )
                else:
                    photos_indexed = _metric(
                        "photos_indexed",
                        "Photos indexed",
                        available=False,
                        reason="Not available",
                        note="Status metric deferred — Immich statistics endpoint not available to this key",
                    )
                    deferred.append("photos_indexed — Immich statistics")
            except Exception as exc:  # noqa: BLE001
                photos_indexed = _metric(
                    "photos_indexed",
                    "Photos indexed",
                    available=False,
                    reason="Not available",
                    note=str(exc),
                )
        else:
            photos_indexed = _metric(
                "photos_indexed",
                "Photos indexed",
                available=False,
                reason="Provider unavailable",
                note=ph.detail,
            )
            immich_people = _metric(
                "immich_face_people",
                "Immich people / face clusters (provider)",
                available=False,
                reason="Provider unavailable",
                note=ph.detail,
                href="/review/ui",
            )

        video = build_video()
        vh = video.health()
        video_health = {"ok": bool(vh.ok), "detail": vh.detail, "provider": vh.provider_key}
        if vh.ok:
            try:
                vids = video.list_videos(limit=500)
                n_vids = len(vids)
                bounded = n_vids >= 500
                dur = 0.0
                dur_known = 0
                for v in vids:
                    if v.duration_sec is not None:
                        dur += float(v.duration_sec)
                        dur_known += 1
                source_videos = _metric(
                    "source_videos",
                    "Source videos",
                    value=n_vids,
                    display=f"{n_vids:,}{'+' if bounded else ''}",
                    href="/review/ui",
                    note="Preserved source files (HVRT). Bounded list ≤500."
                    + (" Count may be incomplete." if bounded else ""),
                )
                video_duration = _metric(
                    "source_video_duration_sec",
                    "Source video duration (sec)",
                    value=int(dur) if dur_known else None,
                    available=dur_known > 0,
                    reason="Not available" if dur_known == 0 else None,
                    note=f"Summed from {dur_known}/{n_vids} videos with duration",
                )
                # Library treats video browse dates as undated today
                undated_sources = _metric(
                    "source_videos_undated",
                    "Source videos with missing / uncertain dates",
                    value=n_vids,
                    note="Video DTOs do not yet carry calendar dates; Library treats source video browse as undated",
                    href="/library/ui",
                )
                spans = video.list_presence_spans(limit=500)
                n_mom = len(spans)
                mom_bounded = n_mom >= 500
                moments = _metric(
                    "searchable_moments",
                    "Searchable video moments",
                    value=n_mom,
                    display=f"{n_mom:,}{'+' if mom_bounded else ''}",
                    href="/library/ui",
                    note="Derived presence spans (rebuildable). Bounded ≤500. Not the same inventory as source videos.",
                )
                if n_vids > 0 and n_mom > 0:
                    leverage_tasks.append(
                        {
                            "text": (
                                f"Dating source videos could place {n_mom:,} searchable moments "
                                f"on the timeline (all listed sources currently lack calendar dates)."
                            ),
                            "href": "/library/ui",
                            "kind": "high_leverage",
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                source_videos = _metric(
                    "source_videos",
                    "Source videos",
                    available=False,
                    reason="Not available",
                    note=str(exc),
                )
                moments = _metric(
                    "searchable_moments",
                    "Searchable video moments",
                    available=False,
                    reason="Not available",
                    note=str(exc),
                )
        else:
            source_videos = _metric(
                "source_videos",
                "Source videos",
                available=False,
                reason="Provider unavailable",
                note=vh.detail,
            )
            moments = _metric(
                "searchable_moments",
                "Searchable video moments",
                available=False,
                reason="Provider unavailable",
                note=vh.detail,
            )
    except Exception as exc:  # noqa: BLE001
        photo_health = {"ok": False, "detail": str(exc)}
        video_health = {"ok": False, "detail": str(exc)}

    # Email adapter / capture / db / qdrant / ollama
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
    ollama_detail = settings.ollama_base_url or "Not connected"

    # High-leverage Archive Health tasks from real attention signals
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
                "text": f"Add Story/context to {n} Artifact{'s' if n != 1 else ''} (optional — Artifacts are valid without Person links).",
                "href": "/artifact/ui",
                "kind": "attention",
            }
        )
    if journals_undated > 0:
        n = min(5, journals_undated)
        leverage_tasks.append(
            {
                "text": f"Review {n} Journal entr{'ies' if n != 1 else 'y'} missing meaningful described dates.",
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

    deferred.extend(
        [
            "Photo date/location/favorites/duplicates/blur — Status metric deferred — source capability not yet available",
            "Videos awaiting analysis queue — Status metric deferred — no durable pending-analysis table",
            "Documents awaiting OCR — Status metric deferred — source capability not yet available",
            "Photo/video % linked to known People — Status metric deferred — expensive corpus join",
            "SMS ingest — Not connected in P1",
        ]
    )

    undated_sources_metric = locals().get("undated_sources")
    if undated_sources_metric is None:
        undated_sources_metric = _metric(
            "source_videos_undated",
            "Source videos with missing / uncertain dates",
            available=False,
            reason="Not available",
        )

    tabs = {
        "archive_summary": {
            "title": "Archive Summary",
            "sections": [
                {
                    "title": "Knowledge",
                    "metrics": [
                        _metric("people", "People", value=people_total, href="/people/ui"),
                        _metric("stories", "Stories", value=stories, href="/story/ui"),
                        _metric(
                            "journals", "Journal Entries", value=journals, href="/journal/ui"
                        ),
                        _metric(
                            "gc_responses",
                            "Guided Capture Responses",
                            value=gc_responses,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "artifacts",
                            "Artifacts / Keepsakes",
                            value=artifacts,
                            href="/artifact/ui",
                        ),
                    ],
                },
                {
                    "title": "Media / Evidence",
                    "metrics": [
                        photos_indexed,
                        source_videos,
                        moments,
                        _metric(
                            "audio_recordings",
                            "Audio recordings (MB-preserved refs)",
                            value=audio_uris,
                            note="Counts GC/Journal/Story audio_uri rows MemoryBox retained",
                        ),
                        _metric("emails", "Emails indexed", value=emails),
                        _metric("calendar", "Calendar events", value=calendars),
                        _metric(
                            "sms",
                            "SMS / Text Messages",
                            available=False,
                            reason="Not yet connected",
                            note="P1 does not ingest SMS",
                        ),
                        _metric(
                            "documents",
                            "Documents / letters (Artifacts)",
                            value=art_by_kind.get("document", 0) + art_by_kind.get("letter", 0),
                            href="/artifact/ui",
                        ),
                    ],
                },
                {
                    "title": "Processing / attention",
                    "metrics": [
                        immich_people,
                        _metric(
                            "people_unresolved",
                            "Unresolved Person candidates",
                            value=people_unresolved,
                            href="/people/ui",
                        ),
                        _metric(
                            "gc_new",
                            "New Guided Capture responses",
                            value=gc_new,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "videos_awaiting_analysis",
                            "Videos awaiting analysis",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — no durable pending-analysis queue",
                        ),
                        _metric(
                            "audio_awaiting_stt",
                            "Audio awaiting / failed transcription (GC)",
                            value=gc_stt_pending + gc_stt_fail,
                            note=f"pending={gc_stt_pending} failed={gc_stt_fail}",
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "ocr_pending",
                            "Documents awaiting OCR",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "jobs_error",
                            "Processing errors (jobs)",
                            value=jobs_error,
                        ),
                    ],
                },
                {
                    "title": "Last activity",
                    "metrics": [
                        _metric(
                            "last_activity",
                            "Last ingest / domain update",
                            value=None,
                            display=last_activity or "Unknown",
                            available=bool(last_activity),
                            reason="Unknown" if not last_activity else None,
                        ),
                    ],
                },
            ],
        },
        "people": {
            "title": "People & Identity",
            "sections": [
                {
                    "title": "People",
                    "metrics": [
                        _metric(
                            "people_named",
                            "Known / named People",
                            value=people_named,
                            href="/people/ui",
                        ),
                        _metric(
                            "people_confirmed",
                            "Owner-confirmed People",
                            value=people_confirmed,
                            href="/people/ui",
                        ),
                        _metric(
                            "people_unresolved",
                            "Unresolved / provisional People",
                            value=people_unresolved,
                            href="/people/ui",
                        ),
                        _metric(
                            "provider_identities",
                            "Provider identity mappings",
                            value=provider_identities,
                            href="/people/ui",
                        ),
                        immich_people,
                        _metric(
                            "relationships",
                            "Relationships recorded (current)",
                            value=rel_current,
                            href="/people/ui",
                        ),
                        _metric(
                            "family_relationships",
                            "Direct family relationships (thin vocab)",
                            value=rel_family,
                            href="/people/ui",
                        ),
                        _metric(
                            "photo_link_pct",
                            "Photos linked to known People",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — expensive Immich corpus join",
                        ),
                        _metric(
                            "video_link_pct",
                            "Video moments linked to known People",
                            available=False,
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
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_location",
                            "Photos with location",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_favorites",
                            "Favorites",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_duplicates",
                            "Potential duplicates",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "photo_blur",
                            "Low-quality / blurred",
                            available=False,
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
                        video_duration,
                        undated_sources_metric,
                        _metric(
                            "videos_with_transcripts",
                            "Videos with transcripts",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "videos_awaiting_analysis",
                            "Videos pending analysis",
                            available=False,
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
                            value=None,
                            display="Source videos ≠ searchable moments",
                            available=True,
                            note="Moments/spans are rebuildable; do not treat as a second film archive",
                        ),
                    ],
                },
                {
                    "title": "High-leverage cleanup",
                    "metrics": [],
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
                        _metric("stories", "Story count", value=stories, href="/story/ui"),
                        _metric(
                            "stories_narrator",
                            "Stories with narrator identified",
                            value=stories_narrator,
                            href="/story/ui",
                        ),
                        _metric(
                            "stories_people",
                            "Stories linked to People",
                            value=stories_with_people,
                            href="/story/ui",
                        ),
                        _metric(
                            "stories_evidence",
                            "Stories linked to Evidence",
                            value=stories_with_evidence,
                            href="/story/ui",
                        ),
                    ],
                },
                {
                    "title": "Journal",
                    "metrics": [
                        _metric("journals", "Journal Entry count", value=journals, href="/journal/ui"),
                        _metric(
                            "journals_dated",
                            "Entries with described/effective dates",
                            value=journals_dated,
                            href="/journal/ui",
                        ),
                        _metric(
                            "journals_undated",
                            "Entries missing meaningful dates",
                            value=journals_undated,
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
                            href="/guided-capture/ui",
                        ),
                        _metric("gc_new", "New / unreviewed", value=gc_new, href="/guided-capture/ui"),
                        _metric(
                            "gc_reviewed",
                            "Reviewed",
                            value=gc_reviewed,
                            href="/guided-capture/ui",
                        ),
                        _metric("gc_typed", "Typed responses", value=gc_typed),
                        _metric("gc_voice", "Voice responses", value=gc_voice),
                        _metric("gc_cred", "Credibility rated", value=gc_cred),
                        _metric("gc_no_cred", "Not rated", value=gc_no_cred),
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
                            "artifacts", "Total Artifacts", value=artifacts, href="/artifact/ui"
                        ),
                        *[
                            _metric(
                                f"artifact_kind_{k}",
                                f"Kind: {k}",
                                value=v,
                                href="/artifact/ui",
                            )
                            for k, v in sorted(art_by_kind.items())
                        ],
                        _metric(
                            "art_with_story",
                            "Artifacts with Story/context link",
                            value=art_with_story,
                            href="/artifact/ui",
                        ),
                        _metric(
                            "art_without_story",
                            "Artifacts missing Story/context",
                            value=max(0, artifacts - art_with_story),
                            href="/artifact/ui",
                            note="Not an error — context is optional enrichment",
                        ),
                        _metric(
                            "art_with_person",
                            "Artifacts linked to People",
                            value=art_with_person,
                            href="/artifact/ui",
                        ),
                        _metric(
                            "art_without_person",
                            "Artifacts not linked to People",
                            value=max(0, artifacts - art_with_person),
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
                        _metric("emails", "Email messages indexed", value=emails),
                        _metric(
                            "email_correspondents",
                            "Recognized correspondents",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — no durable correspondent SoT census",
                        ),
                    ],
                },
                {
                    "title": "Guided Capture campaigns",
                    "metrics": [
                        _metric("gc_draft", "Draft", value=gc_campaigns["draft"], href="/guided-capture/ui"),
                        _metric(
                            "gc_running", "Running", value=gc_campaigns["running"], href="/guided-capture/ui"
                        ),
                        _metric(
                            "gc_paused", "Paused", value=gc_campaigns["paused"], href="/guided-capture/ui"
                        ),
                        _metric(
                            "gc_complete",
                            "Completed / exhausted (outbound_complete)",
                            value=gc_campaigns["outbound_complete"],
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "gc_stopped", "Stopped", value=gc_campaigns["stopped"], href="/guided-capture/ui"
                        ),
                        _metric(
                            "gc_pending_q",
                            "Questions waiting to send",
                            value=gc_pending_deliveries,
                            href="/guided-capture/ui",
                        ),
                        _metric("gc_new", "New responses", value=gc_new, href="/guided-capture/ui"),
                    ],
                },
                {
                    "title": "SMS",
                    "metrics": [
                        _metric(
                            "sms",
                            "SMS / Text Messages",
                            available=False,
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
                            available=bool(earliest_journal),
                            reason="Unknown" if not earliest_journal else None,
                            href="/library/ui",
                            note="Uses Journal described/effective date, not capture-only",
                        ),
                        _metric(
                            "latest_journal",
                            "Latest Journal described date",
                            display=latest_journal or "Unknown",
                            available=bool(latest_journal),
                            reason="Unknown" if not latest_journal else None,
                            href="/library/ui",
                        ),
                        _metric(
                            "journals_dated",
                            "Journal entries with reliable described date",
                            value=journals_dated,
                        ),
                        _metric(
                            "journals_undated",
                            "Journal entries undated / unknown precision",
                            value=journals_undated,
                        ),
                        undated_sources_metric,
                        _metric(
                            "year_coverage",
                            "Strongest / weakest coverage years",
                            available=False,
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
                            available=db_ok,
                            reason=None if db_ok else "unavailable",
                        ),
                        _metric(
                            "qdrant",
                            "Qdrant",
                            display=qdrant_detail,
                            available=bool(settings.qdrant_url),
                            reason="Not connected" if not settings.qdrant_url else None,
                            note="Configured URL shown; live ping not required for thin Status",
                        ),
                        _metric(
                            "ollama",
                            "Ollama",
                            display=ollama_detail if settings.ollama_base_url else "Not connected",
                            available=bool(settings.ollama_base_url),
                            reason="Not connected" if not settings.ollama_base_url else None,
                        ),
                        _metric(
                            "immich",
                            "Immich",
                            display="OK" if photo_health.get("ok") else "unavailable",
                            available=bool(photo_health.get("ok")),
                            reason=None if photo_health.get("ok") else "unavailable",
                            note=str(photo_health.get("detail") or ""),
                        ),
                        _metric(
                            "hvrt",
                            "HVRT / Video worker",
                            display="OK" if video_health.get("ok") else "unavailable",
                            available=bool(video_health.get("ok")),
                            reason=None if video_health.get("ok") else "unavailable",
                            note=str(video_health.get("detail") or ""),
                        ),
                        _metric(
                            "gmail",
                            "Gmail / Guided Capture email",
                            display="OK" if email_st.get("ok") else "degraded / unavailable",
                            available=bool(email_st.get("ok")),
                            note=str(email_st.get("detail") or email_st),
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "calendar_source",
                            "Calendar (ICS evidence)",
                            value=calendars,
                            note="Indexed calendar_event evidence rows",
                        ),
                        _metric(
                            "artifact_storage",
                            "Artifact storage",
                            display="Configured via MEMORYBOX_ARTIFACT_MEDIA_ROOT",
                            available=True,
                            href="/artifact/ui",
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
                            note="Pending ≠ Unreviewed ≠ Unknown ≠ Failed",
                        ),
                        _metric(
                            "jobs_error",
                            "Failed processing jobs",
                            value=jobs_error,
                        ),
                        _metric(
                            "gc_new",
                            "Unreviewed Guided Capture (attention, not failure)",
                            value=gc_new,
                            href="/guided-capture/ui",
                        ),
                        _metric(
                            "people_unresolved",
                            "Unknown / unresolved People (attention, not failure)",
                            value=people_unresolved,
                            href="/people/ui",
                        ),
                        _metric(
                            "gc_stt",
                            "GC audio STT pending / failed",
                            display=f"pending={gc_stt_pending} failed={gc_stt_fail}",
                            available=True,
                        ),
                        _metric(
                            "ocr",
                            "Documents awaiting OCR",
                            available=False,
                            reason="Not available",
                            note="Status metric deferred — source capability not yet available",
                        ),
                        _metric(
                            "video_pending",
                            "Videos awaiting analysis",
                            available=False,
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
                    "metrics": [
                        _metric("people", "People", value=people_total, href="/people/ui"),
                        _metric("emails", "Emails indexed", value=emails),
                        _metric("calendar", "Calendar events", value=calendars),
                        photos_indexed,
                    ],
                },
                {
                    "title": "Needs attention",
                    "metrics": [
                        _metric(
                            "people_unresolved",
                            "Unresolved People",
                            value=people_unresolved,
                            href="/people/ui",
                        ),
                        _metric("gc_new", "New Guided Capture responses", value=gc_new, href="/guided-capture/ui"),
                        undated_sources_metric,
                        _metric(
                            "art_without_story",
                            "Artifacts without Story/context",
                            value=max(0, artifacts - art_with_story),
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
        "tabs": tabs,
        "deferred_notes": deferred,
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
