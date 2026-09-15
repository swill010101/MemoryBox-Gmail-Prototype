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


def item_in_ask_window(item: dict[str, Any], scope: CommsAskScope) -> bool:
    if not scope.dated:
        return True
    if item.get("undated"):
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
    story_n: int = 0,
    thread_n: int = 0,
    loading_comms: bool = False,
) -> str:
    who = (person_label or "this person").strip() or "this person"
    when = f" during {year}" if year else ""
    kinds: list[str] = []
    if photo_n:
        kinds.append("photos")
    if video_n:
        kinds.append("videos")
    if story_n:
        kinds.append("Stories")
    if thread_n:
        kinds.append("conversations")
    if not kinds:
        if loading_comms:
            return (
                f"MemoryBox is gathering conversations involving {who}{when}. "
                "Photos and videos already in Gallery stay visible."
            )
        if year:
            return f"MemoryBox did not find dated memories involving {who}{when}."
        return f"MemoryBox is ready to show memories involving {who}."
    if len(kinds) == 1:
        found = kinds[0]
    elif len(kinds) == 2:
        found = f"{kinds[0]} and {kinds[1]}"
    else:
        found = ", ".join(kinds[:-1]) + f", and {kinds[-1]}"
    extra = ""
    if loading_comms and "conversations" not in kinds:
        extra = " Conversations are still gathering."
    return f"MemoryBox found {found} involving {who}{when}.{extra}"


def curator_language_ok(text: str) -> bool:
    return not bool(PAGING_LANGUAGE.search(text or ""))
