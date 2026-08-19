"""P2-I3 Archive Health helpers — three-way concepts + Work on these now."""
from __future__ import annotations

from typing import Any

WORK_ON_NOW_TARGET = 5
WORK_ON_NOW_CEILING = 7


def _metric(
    key: str,
    label: str,
    *,
    value: Any = None,
    display: str | None = None,
    state: str = "available",
    source: str | None = None,
    last_updated: str | None = None,
    reason: str | None = None,
    href: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    from memorybox.status.summary import _metric as base_metric

    return base_metric(
        key,
        label,
        value=value,
        display=display,
        state=state,  # type: ignore[arg-type]
        source=source,
        last_updated=last_updated,
        reason=reason,
        href=href,
        note=note,
    )


def _with_return(href: str) -> str:
    if not href:
        return href
    sep = "&" if "?" in href else "?"
    if "mb_return=" in href:
        return href
    return f"{href}{sep}mb_return=1"


def _db_counts() -> dict[str, int]:
    from memorybox.db import connection

    out: dict[str, int] = {
        "face_appearance_moments": 0,
        "face_evidence": 0,
        "video_face_observations": 0,
        "i8b_native_ranges": 0,
        "i1_hvrt_ranges": 0,
        "people_unresolved": 0,
        "journals_undated": 0,
        "artifacts_without_story": 0,
        "gc_new": 0,
    }
    try:
        with connection() as conn:
            def c(sql: str) -> int:
                row = conn.execute(sql).fetchone()
                if not row:
                    return 0
                return int(next(iter(row.values())) if isinstance(row, dict) else row[0])

            try:
                out["face_appearance_moments"] = c(
                    "SELECT COUNT(*) AS n FROM face_appearance_moments"
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                out["video_face_observations"] = c(
                    "SELECT COUNT(*) AS n FROM video_face_observations"
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                out["i8b_native_ranges"] = c(
                    "SELECT COUNT(*) AS n FROM face_appearance_moments "
                    "WHERE COALESCE(evidence_lineage, '') = 'mb_native_i8b'"
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                out["i1_hvrt_ranges"] = c(
                    "SELECT COUNT(*) AS n FROM face_appearance_moments "
                    "WHERE COALESCE(evidence_lineage, method, '') IN ('i1_hvrt', 'auto_associate')"
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                out["face_evidence"] = c("SELECT COUNT(*) AS n FROM face_evidence")
            except Exception:  # noqa: BLE001
                pass
            out["people_unresolved"] = c(
                "SELECT COUNT(*) AS n FROM people WHERE status = 'unresolved'"
            )
            out["journals_undated"] = c(
                """
                SELECT COUNT(*) AS n FROM journal_entries
                WHERE status = 'active'
                  AND (
                    described_start_date IS NULL
                    OR COALESCE(described_precision, 'unknown') = 'unknown'
                  )
                """
            )
            # Artifacts-without-story exact join is schema-sensitive; omit from auto counts.
            out["artifacts_without_story"] = 0
            try:
                from memorybox.guided_capture import new_response_count

                out["gc_new"] = int(new_response_count())
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    return out


def _sync_and_queue() -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, Any]]]:
    sync: dict[str, Any] | None = None
    queue: dict[str, Any] = {"by_status": {}, "total": 0}
    failed_items: list[dict[str, Any]] = []
    try:
        from memorybox.person.immich_sync import latest_sync_run

        sync = latest_sync_run("immich")
    except Exception:  # noqa: BLE001
        sync = None
    try:
        from memorybox.recognition.queue import list_queue_items, queue_summary

        queue = queue_summary()
        failed_items = list_queue_items(status="failed", limit=5)
    except Exception:  # noqa: BLE001
        pass
    return sync, queue, failed_items


def build_work_on_these_now(
    *,
    calculated_at: str,
    photo_health: dict[str, Any],
    video_health: dict[str, Any],
    jobs_error: int = 0,
) -> list[dict[str, Any]]:
    """Ranked high-leverage actions — target ~5, hard ceiling 7."""
    counts = _db_counts()
    sync, queue, failed_items = _sync_and_queue()
    by = queue.get("by_status") or {}
    queued_n = int(by.get("queued") or 0)
    running_n = int(by.get("running") or 0)
    failed_n = int(by.get("failed") or 0)
    deferred_n = int(by.get("deferred") or 0)

    candidates: list[tuple[int, dict[str, Any]]] = []

    # High leverage: failed recognition on source videos (propagates to moments)
    if failed_n > 0:
        vid = ""
        if failed_items:
            vid = str(failed_items[0].get("video_external_id") or "")
        href = f"/review/ui?video={vid}" if vid else "/review/ui"
        candidates.append(
            (
                100,
                {
                    "id": "recognition_failed",
                    "priority": 100,
                    "kind": "high_leverage",
                    "concept": "processing",
                    "text": (
                        f"Review {min(failed_n, 7)} failed recognition video"
                        f"{'s' if failed_n != 1 else ''} "
                        "(corrections can unlock searchable moments)."
                    ),
                    "action_label": "Work on this now",
                    "href": _with_return(href),
                    "return_href": "/status/ui",
                },
            )
        )

    # High leverage: large recognition backlog (processing propagates broadly)
    if queued_n + running_n >= 10:
        candidates.append(
            (
                90,
                {
                    "id": "recognition_backlog",
                    "priority": 90,
                    "kind": "high_leverage",
                    "concept": "processing",
                    "text": (
                        f"Recognition backlog: {queued_n} queued"
                        + (f", {running_n} running" if running_n else "")
                        + ". Continue processing so new People appear in video moments."
                    ),
                    "action_label": "Work on this now",
                    "href": _with_return("/people/ui"),
                    "return_href": "/status/ui",
                    "note": "Open People → Sync / queue controls; return here to see counts update.",
                },
            )
        )

    # Provider unhealthy — route to Settings entry (not mature Settings rebuild)
    if not photo_health.get("ok"):
        candidates.append(
            (
                85,
                {
                    "id": "immich_unhealthy",
                    "priority": 85,
                    "kind": "high_leverage",
                    "concept": "provider",
                    "text": (
                        "Immich photo provider is unavailable or degraded — "
                        "Photos available cannot be trusted until the source recovers."
                    ),
                    "action_label": "Work on this now",
                    "href": _with_return("/settings/ui"),
                    "return_href": "/status/ui",
                },
            )
        )
    if not video_health.get("ok"):
        candidates.append(
            (
                80,
                {
                    "id": "hvrt_unhealthy",
                    "priority": 80,
                    "kind": "high_leverage",
                    "concept": "provider",
                    "text": (
                        "Video provider is unavailable or degraded — "
                        "Source videos and searchable moments may be incomplete."
                    ),
                    "action_label": "Work on this now",
                    "href": _with_return("/settings/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    # Stale / never synced Immich people
    if sync is None:
        candidates.append(
            (
                75,
                {
                    "id": "immich_never_synced",
                    "priority": 75,
                    "kind": "high_leverage",
                    "concept": "processing",
                    "text": "Immich People have not been synced yet — run Sync so known People appear.",
                    "action_label": "Work on this now",
                    "href": _with_return("/people/ui"),
                    "return_href": "/status/ui",
                },
            )
        )
    elif str(sync.get("status") or "") in ("failed", "error"):
        candidates.append(
            (
                78,
                {
                    "id": "immich_sync_failed",
                    "priority": 78,
                    "kind": "high_leverage",
                    "concept": "processing",
                    "text": "Last Immich People sync failed — retry Sync on People.",
                    "action_label": "Work on this now",
                    "href": _with_return("/people/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    if deferred_n > 0:
        candidates.append(
            (
                70,
                {
                    "id": "recognition_deferred",
                    "priority": 70,
                    "kind": "attention",
                    "concept": "processing",
                    "text": f"{deferred_n} recognition item(s) deferred — review exclusions on People/Review.",
                    "action_label": "Work on this now",
                    "href": _with_return("/people/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    if counts["people_unresolved"] > 0:
        n = min(5, counts["people_unresolved"])
        candidates.append(
            (
                60,
                {
                    "id": "people_unresolved",
                    "priority": 60,
                    "kind": "attention",
                    "concept": "knowledge_gap",
                    "text": f"Identify up to {n} unresolved People when you're ready.",
                    "action_label": "Work on this now",
                    "href": _with_return("/people/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    if counts["gc_new"] > 0:
        n = min(5, counts["gc_new"])
        candidates.append(
            (
                50,
                {
                    "id": "gc_new",
                    "priority": 50,
                    "kind": "attention",
                    "concept": "knowledge_gap",
                    "text": f"Review {n} new Guided Capture response{'s' if n != 1 else ''}.",
                    "action_label": "Work on this now",
                    "href": _with_return("/guided-capture/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    if counts["journals_undated"] > 0:
        n = min(5, counts["journals_undated"])
        candidates.append(
            (
                40,
                {
                    "id": "journals_undated",
                    "priority": 40,
                    "kind": "attention",
                    "concept": "knowledge_gap",
                    "text": (
                        f"Review {n} Journal entr{'ies' if n != 1 else 'y'} "
                        "missing meaningful described dates."
                    ),
                    "action_label": "Work on this now",
                    "href": _with_return("/journal/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    if counts["artifacts_without_story"] > 0:
        n = min(3, counts["artifacts_without_story"])
        candidates.append(
            (
                30,
                {
                    "id": "artifacts_without_story",
                    "priority": 30,
                    "kind": "attention",
                    "concept": "knowledge_gap",
                    "text": (
                        f"Add Story/context to {n} Artifact{'s' if n != 1 else ''} "
                        "(optional enrichment)."
                    ),
                    "action_label": "Work on this now",
                    "href": _with_return("/artifact/ui"),
                    "return_href": "/status/ui",
                },
            )
        )

    if jobs_error > 0:
        candidates.append(
            (
                55,
                {
                    "id": "jobs_error",
                    "priority": 55,
                    "kind": "attention",
                    "concept": "processing",
                    "text": f"{jobs_error} processing job(s) failed — check Processing details.",
                    "action_label": "Work on this now",
                    "href": _with_return("/status/ui"),
                    "return_href": "/status/ui",
                    "note": "Open the Processing tab below.",
                },
            )
        )

    # Stable sort by priority desc, then id
    candidates.sort(key=lambda x: (-x[0], x[1].get("id") or ""))
    # Prefer high_leverage in the visible window when present
    high = [t for _, t in candidates if t.get("kind") == "high_leverage"]
    rest = [t for _, t in candidates if t.get("kind") != "high_leverage"]
    ordered = high + rest
    return ordered[:WORK_ON_NOW_CEILING]


def build_concept_panels(
    *,
    calculated_at: str,
    photo_health: dict[str, Any],
    video_health: dict[str, Any],
    photos_metric: dict[str, Any],
    source_videos: dict[str, Any],
    moments: dict[str, Any],
    people_total: int,
    people_unresolved: int,
    stories: int,
    journals: int,
    emails: int,
) -> dict[str, Any]:
    sync, queue, _failed = _sync_and_queue()
    counts = _db_counts()
    by = queue.get("by_status") or {}

    # Prefer durable MB moments when present; keep provider span metric too
    durable_moments = counts["face_appearance_moments"]
    if durable_moments > 0:
        moments_metric = _metric(
            "searchable_video_moments",
            "Searchable video moments",
            value=durable_moments,
            state="available",
            source="postgresql:face_appearance_moments",
            last_updated=calculated_at,
            href="/library/ui",
            note=(
                "Durable face-appearance moments in MemoryBox "
                "(not the same as source video file count)."
            ),
        )
    else:
        # Relabel existing moments metric key for clarity
        moments_metric = dict(moments)
        moments_metric["key"] = "searchable_video_moments"
        moments_metric["label"] = "Searchable video moments"

    photos = dict(photos_metric)
    photos["key"] = "photos_available"
    photos["label"] = "Photos available"
    if photos.get("state") == "available" and not (photos.get("note") or "").startswith("Immich"):
        photos["note"] = (photos.get("note") or "") + (
            " Immich library total when authorized — not MB completeness."
        )

    sv = dict(source_videos)
    sv["label"] = "Source videos"
    if "via video provider" in (sv.get("label") or ""):
        sv["label"] = "Source videos"

    ph_ok = bool(photo_health.get("ok"))
    vh_ok = bool(video_health.get("ok"))

    provider_metrics = [
        _metric(
            "immich_provider_health",
            "Immich (photos) — can MemoryBox reach this source?",
            value=1 if ph_ok else None,
            display="Healthy" if ph_ok else "Unavailable",
            state="available" if ph_ok else "unavailable",
            source="immich:health",
            last_updated=calculated_at,
            reason=None if ph_ok else (photo_health.get("detail") or "Provider unavailable"),
            note="Provider health is not archive completeness.",
            href="/settings/ui",
        ),
        _metric(
            "hvrt_provider_health",
            "HVRT / video worker — can MemoryBox reach this source?",
            value=1 if vh_ok else None,
            display="Healthy" if vh_ok else "Unavailable",
            state="available" if vh_ok else "unavailable",
            source="hvrt:health",
            last_updated=calculated_at,
            reason=None if vh_ok else (video_health.get("detail") or "Provider unavailable"),
            note="Provider health is not archive completeness.",
            href="/settings/ui",
        ),
        photos,
        sv,
    ]

    if sync:
        sync_disp = (
            f"{sync.get('status')} · {sync.get('finished_at') or sync.get('started_at') or '—'}"
        )
        processing_sync = _metric(
            "immich_last_sync",
            "Last Immich People sync",
            display=sync_disp,
            state="available" if sync.get("status") == "ok" else "partial",
            source="postgresql:provider_person_sync_runs",
            last_updated=calculated_at,
            reason=None if sync.get("status") == "ok" else f"status={sync.get('status')}",
            note=(
                f"created={sync.get('created_count')} mapped={sync.get('mapped_count')} "
                f"skipped={sync.get('skipped_count')} conflicts={sync.get('conflict_count')}"
            ),
            href="/people/ui",
        )
    else:
        processing_sync = _metric(
            "immich_last_sync",
            "Last Immich People sync",
            state="unavailable",
            source="postgresql:provider_person_sync_runs",
            last_updated=calculated_at,
            reason="No Immich sync run recorded yet",
            href="/people/ui",
        )

    def _q(status: str) -> dict[str, Any]:
        n = int(by.get(status) or 0)
        return _metric(
            f"recognition_{status}",
            f"Recognition queue — {status}",
            value=n,
            state="available",
            source="postgresql:recognition_queue_items",
            last_updated=calculated_at,
            href="/people/ui",
        )

    processing_metrics = [
        processing_sync,
        _q("queued"),
        _q("running"),
        _q("completed"),
        _q("failed"),
        _q("deferred"),
        _metric(
            "recognition_total",
            "Recognition queue — total items",
            value=int(queue.get("total") or 0),
            state="available",
            source="postgresql:recognition_queue_items",
            last_updated=calculated_at,
            note="I1 queue plus I8B run_kind (provider_seeded / owner_learned / incremental / correction).",
        ),
    ]

    knowledge_metrics = [
        moments_metric,
        _metric(
            "known_people",
            "Known People",
            value=people_total,
            state="available",
            source="postgresql:people",
            last_updated=calculated_at,
            href="/people/ui",
            note="Confirmed + unresolved MB People (not Immich-only).",
        ),
        _metric(
            "unresolved_people",
            "Unresolved People (knowledge gap)",
            value=people_unresolved,
            state="available",
            source="postgresql:people",
            last_updated=calculated_at,
            href="/people/ui",
        ),
        _metric(
            "face_evidence",
            "Face evidence records",
            value=counts["face_evidence"],
            state="available",
            source="postgresql:face_evidence",
            last_updated=calculated_at,
            href="/review/ui",
        ),
        _metric(
            "stories",
            "Stories",
            value=stories,
            state="available",
            source="postgresql:stories",
            last_updated=calculated_at,
            href="/story/ui",
        ),
        _metric(
            "journal_entries",
            "Journal entries",
            value=journals,
            state="available",
            source="postgresql:journal_entries",
            last_updated=calculated_at,
            href="/journal/ui",
        ),
        _metric(
            "communications",
            "Communications (email evidence in MemoryBox)",
            value=emails,
            state="available",
            source="postgresql:evidence.communication",
            last_updated=calculated_at,
            note="PG Evidence only — not full mailbox completeness.",
        ),
    ]

    return {
        "disclaimer": (
            "Healthy providers do not mean the archive is complete. "
            "Counts show what MemoryBox can currently see or has already learned."
        ),
        "provider_health": {
            "title": "Source / provider health",
            "intro": "Can MemoryBox currently reach and use each source?",
            "metrics": provider_metrics,
        },
        "processing_state": {
            "title": "Processing state",
            "intro": "Queued, running, completed, failed, deferred, or stale work.",
            "metrics": processing_metrics,
        },
        "knowledge_gaps": {
            "title": "Archive knowledge",
            "intro": "What MemoryBox already knows — and gaps that remain.",
            "metrics": knowledge_metrics,
        },
    }


def enrich_status_for_p2_i3(payload: dict[str, Any]) -> dict[str, Any]:
    """Overlay P2-I3 Archive Health structure onto the Status summary payload."""
    calculated_at = payload.get("calculated_at") or ""
    tabs = payload.get("tabs") or {}

    # Pull live health from Sources tab metrics if present; else re-probe lightly
    photo_health = {"ok": False, "detail": "unknown"}
    video_health = {"ok": False, "detail": "unknown"}
    try:
        from memorybox.ask.deps import build_photo, build_video

        ph = build_photo().health()
        photo_health = {"ok": bool(ph.ok), "detail": ph.detail}
        vh = build_video().health()
        video_health = {"ok": bool(vh.ok), "detail": vh.detail}
    except Exception as exc:  # noqa: BLE001
        photo_health = {"ok": False, "detail": str(exc)}
        video_health = {"ok": False, "detail": str(exc)}

    # Locate existing metrics from tabs
    def _find_metric(key: str) -> dict[str, Any] | None:
        for tab in tabs.values():
            for sec in tab.get("sections") or []:
                for m in sec.get("metrics") or []:
                    if m.get("key") == key:
                        return m
        return None

    photos_m = _find_metric("photos_available") or _find_metric("photos_indexed") or _metric(
        "photos_available",
        "Photos available",
        state="unavailable",
        reason="Not available",
        last_updated=calculated_at,
    )
    # Relabel everywhere
    for tab in tabs.values():
        for sec in tab.get("sections") or []:
            for m in sec.get("metrics") or []:
                if m.get("key") in ("photos_indexed", "photos_available"):
                    m["key"] = "photos_available"
                    m["label"] = "Photos available"
                if m.get("key") == "searchable_moments":
                    m["label"] = "Searchable video moments"
                if m.get("key") == "source_videos":
                    m["label"] = "Source videos"

    source_videos = _find_metric("source_videos") or _metric(
        "source_videos",
        "Source videos",
        state="unavailable",
        reason="Not available",
        last_updated=calculated_at,
    )
    moments = _find_metric("searchable_moments") or _find_metric(
        "searchable_video_moments"
    ) or _metric(
        "searchable_video_moments",
        "Searchable video moments",
        state="unavailable",
        reason="Not available",
        last_updated=calculated_at,
    )

    # People / stories / journals / emails from archive_summary if present
    people_total = 0
    people_unresolved = 0
    stories = 0
    journals = 0
    emails = 0
    jobs_error = 0
    pm = _find_metric("people")
    if pm and isinstance(pm.get("value"), int):
        people_total = pm["value"]
    pu = _find_metric("people_unresolved")
    if pu and isinstance(pu.get("value"), int):
        people_unresolved = pu["value"]
    sm = _find_metric("stories")
    if sm and isinstance(sm.get("value"), int):
        stories = sm["value"]
    jm = _find_metric("journals")
    if jm and isinstance(jm.get("value"), int):
        journals = jm["value"]
    em = _find_metric("emails")
    if em and isinstance(em.get("value"), int):
        emails = em["value"]
    je = _find_metric("jobs_error")
    if je and isinstance(je.get("value"), int):
        jobs_error = je["value"]

    concepts = build_concept_panels(
        calculated_at=calculated_at,
        photo_health=photo_health,
        video_health=video_health,
        photos_metric=photos_m,
        source_videos=source_videos,
        moments=moments,
        people_total=people_total,
        people_unresolved=people_unresolved,
        stories=stories,
        journals=journals,
        emails=emails,
    )
    work = build_work_on_these_now(
        calculated_at=calculated_at,
        photo_health=photo_health,
        video_health=video_health,
        jobs_error=jobs_error,
    )

    # Rewrite archive_health tab as three-way + work now
    tabs["archive_health"] = {
        "title": "Archive Health",
        "sections": [
            {
                "title": concepts["provider_health"]["title"],
                "intro": concepts["provider_health"]["intro"],
                "concept": "provider_health",
                "metrics": concepts["provider_health"]["metrics"],
            },
            {
                "title": concepts["processing_state"]["title"],
                "intro": concepts["processing_state"]["intro"],
                "concept": "processing_state",
                "metrics": concepts["processing_state"]["metrics"],
            },
            {
                "title": concepts["knowledge_gaps"]["title"],
                "intro": concepts["knowledge_gaps"]["intro"],
                "concept": "knowledge_gaps",
                "metrics": concepts["knowledge_gaps"]["metrics"],
            },
            {
                "title": "Work on these now",
                "intro": (
                    "About five high-leverage next steps (never a giant backlog). "
                    "Complete one, return here, and counts update."
                ),
                "concept": "work_on_these_now",
                "metrics": [],
                "tasks": work,
            },
            {
                "title": "Completeness",
                "intro": concepts["disclaimer"],
                "metrics": [],
            },
        ],
    }

    # Default to Archive Health overview
    payload["default_tab"] = "archive_health"
    payload["product"] = "archive_health"
    payload["increment"] = "P2-I3"
    payload["concepts"] = concepts
    payload["work_on_these_now"] = work
    payload["work_on_these_now_meta"] = {
        "target": WORK_ON_NOW_TARGET,
        "ceiling": WORK_ON_NOW_CEILING,
        "visible": len(work),
    }
    payload["honesty"] = {
        "rule": "unavailable_or_deferred_never_equals_zero",
        "completeness": (
            "Provider healthy does not imply archive complete"
        ),
    }

    nav = payload.get("nav") or []
    # Put Archive Health first
    rest = [n for n in nav if n.get("id") != "archive_health"]
    payload["nav"] = [{"id": "archive_health", "label": "Archive Health"}] + [
        n for n in rest if n.get("id") != "archive_summary"
    ] + (
        [{"id": "archive_summary", "label": "Archive Summary (detail)"}]
        if any(n.get("id") == "archive_summary" for n in nav)
        else []
    )
    # Avoid duplicating archive_summary if already appended
    seen: set[str] = set()
    deduped = []
    for n in payload["nav"]:
        i = n.get("id")
        if i in seen:
            continue
        seen.add(i)
        deduped.append(n)
    payload["nav"] = deduped

    links = payload.setdefault("links", {})
    links["status"] = "/status/ui"
    links["settings"] = "/settings/ui"
    links["archive_health"] = "/status/ui"

    # Replace leverage tasks inside old archive_health tasks already done
    payload["tabs"] = tabs
    return payload
