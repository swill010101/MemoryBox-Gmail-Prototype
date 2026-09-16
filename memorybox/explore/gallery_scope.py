"""Ask-date scope for Gallery (all media + prepared communications).

Communications join the same date buckets as photos/videos/Stories.
The 80-row bound is only for thread-detail retrieval, never for counts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PAGING_LANGUAGE = re.compile(
    r"(80 of|page 80|reachable email|page size|ask token|keyset|load older|"
    r"retrieval window|browser window|processing/window)",
    re.I,
)


@dataclass(frozen=True)
class CommsAskScope:
    date_from: str | None
    date_to: str | None
    grain: str
    calendar_year: int | None

    @property
    def dated(self) -> bool:
        return bool(self.date_from and self.date_to)


def comms_ask_scope(time_start: Any = None, time_end: Any = None) -> CommsAskScope:
    start = str(time_start or "").strip()[:10] or None
    end = str(time_end or "").strip()[:10] or None
    if start and len(start) == 4:
        start = start + "-01-01"
    if end and len(end) == 4:
        end = end + "-12-31"
    if start and end and start[:4] == end[:4] and start[:4].isdigit():
        return CommsAskScope(start, end, "month", int(start[:4]))
    if start and end:
        return CommsAskScope(start, end, "year", None)
    return CommsAskScope(None, None, "year", None)


SENTINEL_DATE_PREFIX = "1970-01-01"


def is_sentinel_date(raw: Any) -> bool:
    text = str(raw or "").strip()
    return text.startswith(SENTINEL_DATE_PREFIX)


def item_in_ask_window(item: dict[str, Any], scope: CommsAskScope) -> bool:
    if not scope.dated:
        return True
    if item.get("undated") or is_sentinel_date(item.get("date")):
        return False
    raw = str(item.get("date") or "").strip()
    if not raw:
        return False
    start, end = scope.date_from or "", scope.date_to or ""
    if len(raw) >= 10:
        day = raw[:10]
        return start <= day <= end
    if len(raw) >= 7 and raw[4] == "-":
        return start[:7] <= raw[:7] <= end[:7]
    if len(raw) >= 4 and raw[:4].isdigit():
        return start[:4] <= raw[:4] <= end[:4]
    return False


def restrict_items_to_ask_dates(
    items: list[dict[str, Any]],
    *,
    time_start: Any = None,
    time_end: Any = None,
) -> list[dict[str, Any]]:
    scope = comms_ask_scope(time_start, time_end)
    if not scope.dated:
        return list(items)
    return [i for i in items if item_in_ask_window(i, scope)]


def curator_gallery_sentence(
    *,
    person_label: str,
    year: int | None,
    photo_n: int = 0,
    video_n: int = 0,
    sms_n: int = 0,
    thread_n: int = 0,
    story_n: int = 0,
    artifact_n: int = 0,
    calendar_n: int = 0,
    loading_comms: bool = False,
    loading_sms: bool = False,
) -> str:
    who = (person_label or "this person").strip() or "this person"
    when = f" during {year}" if year else ""
    parts: list[str] = []
    if photo_n:
        parts.append(f"{photo_n} photo{'s' if photo_n != 1 else ''}")
    if video_n:
        parts.append(f"{video_n} video{'s' if video_n != 1 else ''}")
    if sms_n:
        parts.append(f"{sms_n} text message{'s' if sms_n != 1 else ''}")
    if story_n:
        parts.append(f"{story_n} Stor{'y' if story_n == 1 else 'ies'}")
    if artifact_n:
        parts.append(f"{artifact_n} Artifact{'s' if artifact_n != 1 else ''}")
    if calendar_n:
        parts.append(f"{calendar_n} calendar event{'s' if calendar_n != 1 else ''}")
    if thread_n:
        parts.append(f"{thread_n} email thread{'s' if thread_n != 1 else ''}")
    if not parts:
        if loading_comms or loading_sms:
            return f"I am gathering conversations involving {who}{when}."
        if year:
            return f"I did not find dated memories involving {who}{when}."
        return f"I did not find memories involving {who}."
    if len(parts) == 1:
        found = parts[0]
    elif len(parts) == 2:
        found = f"{parts[0]} and {parts[1]}"
    else:
        found = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    extra = ""
    if loading_comms and thread_n == 0:
        extra = " Email threads are still gathering."
    if loading_sms and sms_n == 0:
        extra += " Text messages are still gathering."
    return f"I found {found} involving {who}{when}.{extra}"


def curator_language_ok(text: str) -> bool:
    return not bool(PAGING_LANGUAGE.search(str(text or "")))


def empty_prepared_body_notice() -> str:
    return "Prepared text unavailable—open original."


def attachment_state_copy(
    *,
    action: str | None,
    available: bool,
    mime: str = "",
    filename: str = "",
) -> str:
    act = str(action or "").strip().lower()
    if not available:
        return "Original file unavailable. The record is kept but is not viewable."
    if act in {"blocked", "unsafe"}:
        return "Blocked as unsafe."
    if act == "record_only":
        return "Attachment metadata only — this file type is not viewable here."
    if act == "view_image":
        return "Image preview"
    if act == "open_pdf":
        return "Open PDF (this opens the attached file, not the email thread)"
    if act == "open_document":
        return "Open document (this opens the attached file, not the email thread)"
    blob = f"{filename} {mime}".lower()
    if any(x in blob for x in ("jpeg", "jpg", "png", "gif", "webp", "image/")):
        return "Preview unavailable."
    return "Preview unavailable."


def ask_calendar_year(time_start: Any = None, time_end: Any = None) -> int | None:
    scope = comms_ask_scope(time_start, time_end)
    return scope.calendar_year


def scoped_counts(
    *,
    photo_n: int = 0,
    video_n: int = 0,
    sms_n: int = 0,
    email_threads: int = 0,
    story_n: int = 0,
    artifact_n: int = 0,
    calendar_n: int = 0,
) -> dict[str, int]:
    """One count object for Curator, pills, cards, buckets, and modal totals."""
    photos = max(0, int(photo_n or 0))
    videos = max(0, int(video_n or 0))
    sms = max(0, int(sms_n or 0))
    threads = max(0, int(email_threads or 0))
    stories = max(0, int(story_n or 0))
    artifacts = max(0, int(artifact_n or 0))
    calendar = max(0, int(calendar_n or 0))
    return {
        "photos": photos,
        "videos": videos,
        "sms": sms,
        "email_threads": threads,
        "stories": stories,
        "artifacts": artifacts,
        "calendar": calendar,
        "communications": sms + threads,
    }
