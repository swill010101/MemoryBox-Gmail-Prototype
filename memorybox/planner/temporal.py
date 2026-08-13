"""Composable Ask temporal resolution — seasons, holidays, year ranges.

Northern-hemisphere meteorological seasons (explicit, testable):
  Spring: Mar 1 – May 31
  Summer: Jun 1 – Aug 31
  Fall/Autumn: Sep 1 – Nov 30
  Winter: Dec 1 – Feb 28/29 (next calendar year)

Holiday windows (defaults; later Settings):
  Most holidays: holiday_date − 2 days through holiday_date + 2 days
  Christmas: Dec 11 (Christmas − 14 days) through Jan 1 (NYD) of the next year

US national (federal) holidays are included and computed per year when variable.
Recurring holiday year ranges produce one window per year (not one contiguous band).

Person observances (birthday / anniversary) are marked here; concrete dates come from
MB People facts / life events in the Ask orchestrator when recorded.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
YEAR_RANGE_RE = re.compile(
    r"\b((?:19|20)\d{2})\s*(?:through|thru|to|–|-|—)\s*((?:19|20)\d{2})\b",
    re.I,
)
MONTH_YEAR_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+((?:19|20)\d{2})\b",
    re.I,
)
SEASON_RE = re.compile(
    r"\b(spring|summer|fall|autumn|winter)\s+((?:19|20)\d{2})\b",
    re.I,
)
SEASON_ONLY_RE = re.compile(r"\b(spring|summer|fall|autumn|winter)\b", re.I)
BIRTHDAY_RE = re.compile(r"(?i)\b(birthdays?|b[\-\s]?days?|bdays?)\b")
ANNIVERSARY_RE = re.compile(r"(?i)\banniversar(?:y|ies)\b")
# Fact-style birth question — not an Explore observance window.
WHEN_BORN_RE = re.compile(r"(?i)\bwhen\s+was\b.+\bborn\b|\bbirth\s*date\b")

# Holiday aliases → canonical key (longer phrases matched first).
# Includes all current U.S. federal holidays plus common family observances.
HOLIDAY_ALIASES: dict[str, str] = {
    # Federal
    "new year's day": "nyd",
    "new years day": "nyd",
    "nyd": "nyd",
    "martin luther king jr day": "mlk_day",
    "martin luther king day": "mlk_day",
    "martin luther king jr. day": "mlk_day",
    "mlk day": "mlk_day",
    "mlk jr day": "mlk_day",
    "presidents day": "presidents_day",
    "president's day": "presidents_day",
    "presidents' day": "presidents_day",
    "washington's birthday": "presidents_day",
    "washingtons birthday": "presidents_day",
    "memorial day": "memorial_day",
    "juneteenth": "juneteenth",
    "juneteenth day": "juneteenth",
    "independence day": "july_4",
    "july 4": "july_4",
    "july 4th": "july_4",
    "july fourth": "july_4",
    "4th of july": "july_4",
    "fourth of july": "july_4",
    "labor day": "labor_day",
    "columbus day": "columbus_day",
    "indigenous peoples day": "columbus_day",
    "indigenous peoples' day": "columbus_day",
    "veterans day": "veterans_day",
    "veteran's day": "veterans_day",
    "veterans' day": "veterans_day",
    "thanksgiving": "thanksgiving",
    "thanksgiving day": "thanksgiving",
    "christmas": "christmas",
    "xmas": "christmas",
    # Common family / cultural (non-federal but expected in Ask)
    "christmas eve": "christmas_eve",
    "new year's eve": "nye",
    "new years eve": "nye",
    "nye": "nye",
    "easter": "easter",
    "easter sunday": "easter",
    "halloween": "halloween",
    "valentine's day": "valentines_day",
    "valentines day": "valentines_day",
    "valentine day": "valentines_day",
    "mother's day": "mothers_day",
    "mothers day": "mothers_day",
    "father's day": "fathers_day",
    "fathers day": "fathers_day",
}

HOLIDAY_LABELS: dict[str, str] = {
    "nyd": "New Year's Day",
    "mlk_day": "MLK Day",
    "presidents_day": "Presidents' Day",
    "memorial_day": "Memorial Day",
    "juneteenth": "Juneteenth",
    "july_4": "July 4",
    "labor_day": "Labor Day",
    "columbus_day": "Columbus Day",
    "veterans_day": "Veterans Day",
    "thanksgiving": "Thanksgiving",
    "christmas": "Christmas",
    "christmas_eve": "Christmas Eve",
    "nye": "NYE",
    "easter": "Easter",
    "halloween": "Halloween",
    "valentines_day": "Valentine's Day",
    "mothers_day": "Mother's Day",
    "fathers_day": "Father's Day",
}

# Default evidence windows (days). Christmas is special-cased.
DEFAULT_HOLIDAY_PAD_DAYS = 2
CHRISTMAS_LEAD_DAYS = 14  # through NYD (Jan 1 next year)

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class TemporalParse:
    """Normalized temporal interpretation for a shared Ask / Explore state."""

    time_start: str | None = None  # ISO date — union min (for context / band)
    time_end: str | None = None  # ISO date — union max
    windows: tuple[tuple[str, str], ...] = ()  # inclusive ISO date pairs
    label: str | None = None
    season: str | None = None
    holiday: str | None = None
    # birthday | anniversary — concrete dates filled from MB People when available
    life_event_kind: str | None = None
    life_event_years: tuple[int, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_start": self.time_start,
            "time_end": self.time_end,
            "windows": [list(w) for w in self.windows],
            "label": self.label,
            "season": self.season,
            "holiday": self.holiday,
            "life_event_kind": self.life_event_kind,
            "life_event_years": list(self.life_event_years),
            "notes": list(self.notes),
        }


def _iso(d: date) -> str:
    return d.isoformat()


def _pad_window(center: date, *, pad_days: int = DEFAULT_HOLIDAY_PAD_DAYS) -> tuple[str, str]:
    return _iso(center - timedelta(days=pad_days)), _iso(center + timedelta(days=pad_days))


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm — Western/US Easter Sunday."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month = (h + el - 7 * m + 114) // 31
    day = ((h + el - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Mon=0 … Sun=6 (datetime). n: 1-based."""
    cal = calendar.Calendar(firstweekday=0)
    days = [
        d
        for d in cal.itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    return days[n - 1]


def _last_weekday(year: int, month: int, weekday: int) -> date:
    cal = calendar.Calendar(firstweekday=0)
    days = [
        d
        for d in cal.itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    return days[-1]


def _safe_md(year: int, month: int, day: int) -> date:
    """Clamp day into month (Feb 29 → Feb 28 in non-leap years)."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def resolve_holiday_date(key: str, year: int) -> date:
    """Resolve one holiday occurrence for a calendar year (U.S. rules)."""
    if key == "christmas":
        return date(year, 12, 25)
    if key == "christmas_eve":
        return date(year, 12, 24)
    if key == "nye":
        return date(year, 12, 31)
    if key == "nyd":
        return date(year, 1, 1)
    if key == "july_4":
        return date(year, 7, 4)
    if key == "juneteenth":
        return date(year, 6, 19)
    if key == "veterans_day":
        return date(year, 11, 11)
    if key == "halloween":
        return date(year, 10, 31)
    if key == "valentines_day":
        return date(year, 2, 14)
    if key == "easter":
        return _easter_sunday(year)
    if key == "thanksgiving":
        return _nth_weekday(year, 11, 3, 4)  # 4th Thursday
    if key == "memorial_day":
        return _last_weekday(year, 5, 0)  # last Monday
    if key == "labor_day":
        return _nth_weekday(year, 9, 0, 1)  # 1st Monday
    if key == "mlk_day":
        return _nth_weekday(year, 1, 0, 3)  # 3rd Monday
    if key == "presidents_day":
        return _nth_weekday(year, 2, 0, 3)  # 3rd Monday
    if key == "columbus_day":
        return _nth_weekday(year, 10, 0, 2)  # 2nd Monday
    if key == "mothers_day":
        return _nth_weekday(year, 5, 6, 2)  # 2nd Sunday
    if key == "fathers_day":
        return _nth_weekday(year, 6, 6, 3)  # 3rd Sunday
    raise ValueError(f"unknown holiday key: {key}")


def holiday_window(key: str, year: int) -> tuple[str, str]:
    """Inclusive ISO window for one holiday occurrence."""
    if key == "christmas":
        # 2 weeks before Christmas through New Year's Day (next calendar year).
        start = date(year, 12, 25) - timedelta(days=CHRISTMAS_LEAD_DAYS)
        end = date(year + 1, 1, 1)
        return _iso(start), _iso(end)
    center = resolve_holiday_date(key, year)
    return _pad_window(center, pad_days=DEFAULT_HOLIDAY_PAD_DAYS)


def observance_window_md(
    month: int,
    day: int,
    year: int,
    *,
    pad_days: int = DEFAULT_HOLIDAY_PAD_DAYS,
) -> tuple[str, str]:
    """±pad window around month/day in a given year (birthday / anniversary)."""
    center = _safe_md(year, month, day)
    return _pad_window(center, pad_days=pad_days)


def season_window(season: str, year: int) -> tuple[str, str]:
    s = season.lower()
    if s == "autumn":
        s = "fall"
    if s == "spring":
        return f"{year}-03-01", f"{year}-05-31"
    if s == "summer":
        return f"{year}-06-01", f"{year}-08-31"
    if s == "fall":
        return f"{year}-09-01", f"{year}-11-30"
    if s == "winter":
        # Dec 1 → Feb end of next year
        end_y = year + 1
        last = 29 if calendar.isleap(end_y) else 28
        return f"{year}-12-01", f"{end_y}-02-{last:02d}"
    raise ValueError(f"unknown season: {season}")


def _find_holiday_key(text: str) -> str | None:
    q = (text or "").lower()
    # Longer phrases first
    for alias in sorted(HOLIDAY_ALIASES.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return HOLIDAY_ALIASES[alias]
    return None


def _years_in_text(text: str) -> list[int]:
    m = YEAR_RANGE_RE.search(text or "")
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        return list(range(a, b + 1))
    found = [int(y) for y in YEAR_RE.findall(text or "")]
    if not found:
        return []
    if len(found) == 1:
        return found
    # Multiple bare years without explicit range → treat as first..last inclusive
    a, b = min(found), max(found)
    return list(range(a, b + 1))


def parse_temporal(text: str) -> TemporalParse:
    """Parse WHEN from a natural-language Ask into shared temporal state."""
    q = text or ""
    notes: list[str] = []
    years = _years_in_text(q)

    # Person observances — dates filled later from MB People when present.
    # Fact questions ("when was X born") are not Explore windows.
    if BIRTHDAY_RE.search(q) and not WHEN_BORN_RE.search(q):
        label = "Birthday"
        if len(years) == 1:
            label = f"Birthday {years[0]}"
        elif len(years) > 1:
            label = f"Birthday {years[0]}–{years[-1]}"
        need = () if years else ("life_event_needs_year",)
        return TemporalParse(
            label=label,
            life_event_kind="birthday",
            life_event_years=tuple(years),
            notes=("temporal=life_event_birthday",) + need,
        )
    if ANNIVERSARY_RE.search(q):
        label = "Anniversary"
        if len(years) == 1:
            label = f"Anniversary {years[0]}"
        elif len(years) > 1:
            label = f"Anniversary {years[0]}–{years[-1]}"
        need = () if years else ("life_event_needs_year",)
        return TemporalParse(
            label=label,
            life_event_kind="anniversary",
            life_event_years=tuple(years),
            notes=("temporal=life_event_anniversary",) + need,
        )

    holiday_key = _find_holiday_key(q)

    # Month + year
    mm = MONTH_YEAR_RE.search(q)
    if mm and not holiday_key:
        month = _MONTHS[mm.group(1).lower()]
        year = int(mm.group(2))
        last = calendar.monthrange(year, month)[1]
        start, end = f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last:02d}"
        label = f"{mm.group(1).title()} {year}"
        return TemporalParse(
            time_start=start,
            time_end=end,
            windows=((start, end),),
            label=label,
            notes=("temporal=month_year",),
        )

    # Season + year
    sm = SEASON_RE.search(q)
    if sm and not holiday_key:
        season = sm.group(1).lower()
        if season == "autumn":
            season = "fall"
        year = int(sm.group(2))
        start, end = season_window(season, year)
        label = f"{season.title()} {year}"
        return TemporalParse(
            time_start=start,
            time_end=end,
            windows=((start, end),),
            label=label,
            season=season,
            notes=("temporal=season", "season_def=meteorological_nh"),
        )

    # Holiday (± window / Christmas special); multi-year → per-year windows
    if holiday_key:
        if not years:
            notes.append("holiday_missing_year")
            return TemporalParse(
                holiday=holiday_key,
                label=HOLIDAY_LABELS.get(holiday_key, holiday_key),
                notes=tuple(notes + ["temporal=holiday_needs_year"]),
            )
        windows: list[tuple[str, str]] = []
        for y in years:
            windows.append(holiday_window(holiday_key, y))
        label_base = HOLIDAY_LABELS.get(holiday_key, holiday_key)
        if len(years) == 1:
            label = f"{label_base} {years[0]}"
        else:
            label = f"{label_base} {years[0]}–{years[-1]}"
        note = "temporal=holiday_recurring" if len(years) > 1 else "temporal=holiday"
        if holiday_key == "christmas":
            notes.append("christmas_window=minus_14d_through_nyd")
        else:
            notes.append(f"holiday_pad_days={DEFAULT_HOLIDAY_PAD_DAYS}")
        return TemporalParse(
            time_start=min(w[0] for w in windows),
            time_end=max(w[1] for w in windows),
            windows=tuple(windows),
            label=label,
            holiday=holiday_key,
            notes=tuple(notes + [note]),
        )

    # Plain year / year range
    if years:
        if len(years) == 1:
            y = years[0]
            start, end = f"{y}-01-01", f"{y}-12-31"
            label = str(y)
        else:
            start, end = f"{years[0]}-01-01", f"{years[-1]}-12-31"
            label = f"{years[0]}–{years[-1]}"
        return TemporalParse(
            time_start=start,
            time_end=end,
            windows=((start, end),),
            label=label,
            notes=("temporal=year_range",),
        )

    # Season without year — ambiguous unless later context fills it
    if SEASON_ONLY_RE.search(q):
        return TemporalParse(
            notes=("temporal=season_needs_year",),
        )

    return TemporalParse()


def date_in_windows(iso_day: str | None, windows: tuple[tuple[str, str], ...] | list) -> bool:
    """True if iso_day (YYYY-MM-DD…) falls in any inclusive window."""
    if not windows:
        return True
    if not iso_day:
        return False
    d = str(iso_day)[:10]
    for start, end in windows:
        if start[:10] <= d <= end[:10]:
            return True
    return False
