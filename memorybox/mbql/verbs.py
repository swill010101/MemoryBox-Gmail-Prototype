"""Shared MBQL command verbs — Explore and server must use the same ids.

Client may apply refine instantly (Q2). Prove checks these ids exist in explore.js.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Act = Literal["refine", "navigate"]


@dataclass(frozen=True)
class CommandSpec:
    verb: str
    act: Act
    pattern: re.Pattern[str]
    gallery_show_sms: bool | None = None
    visual_scope: str | None = None


def _rx(src: str) -> re.Pattern[str]:
    return re.compile(src, re.IGNORECASE)


# FlightSim phrase list + I4/I7 refine verbs. Keep in sync with explore.js MBQL_VERBS.
COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("clear_filters", "refine", _rx(r"^clear filters\.?$")),
    CommandSpec("show_everything", "refine", _rx(r"^show everything\.?$")),
    CommandSpec("only_undated", "refine", _rx(r"^only undated\.?$|^undated\.?$|^show undated\.?$")),
    CommandSpec("clear_undated", "refine", _rx(r"^clear undated\.?$|^include dated\.?$")),
    CommandSpec("show_map", "refine", _rx(r"^show map\.?$|^map view\.?$|^on the map\.?$")),
    CommandSpec("show_gallery", "refine", _rx(r"^show gallery\.?$|^gallery view\.?$|^list view\.?$")),
    CommandSpec("clear_place", "refine", _rx(r"^clear location\.?$|^clear place\.?$|^clear map selection\.?$")),
    CommandSpec("clear_time", "refine", _rx(r"^clear date\.?$|^clear time\.?$|^clear timeline\.?$")),
    CommandSpec("reset", "refine", _rx(r"^reset\.?$")),
    CommandSpec("reset_timeline", "refine", _rx(r"^reset timeline\.?$|^full result range\.?$|^reset range\.?$")),
    CommandSpec(
        "only_photos",
        "refine",
        _rx(r"^only photos?\.?$|^photos?\.?$"),
        visual_scope="still_only",
    ),
    CommandSpec(
        "only_video",
        "refine",
        _rx(r"^only videos?\.?$"),
        visual_scope="video_only",
    ),
    CommandSpec("add_video", "refine", _rx(r"^add video\.?$"), visual_scope="broad"),
    CommandSpec(
        "add_texts",
        "refine",
        _rx(r"^(add|include)\s+(texts?|sms|imessage|i-?message)s?\.?$|^add texts?\.?$"),
        gallery_show_sms=True,
    ),
    CommandSpec(
        "only_texts",
        "refine",
        _rx(r"^only (email|emails|texts?|sms|imessage)\b"),
        gallery_show_sms=True,
    ),
    CommandSpec("only_artifacts", "refine", _rx(r"^only artifacts?\.?$")),
    CommandSpec("only_stories", "refine", _rx(r"^only stories?\.?$")),
    CommandSpec("go_to_people", "navigate", _rx(r"clear context.*people|go to people")),
    CommandSpec(
        "go_to_person",
        "navigate",
        _rx(r"^(?:go to\s+(.+?)\s+instead|select\s+(.+?)|switch to\s+(.+?))\.?$"),
    ),
)

VERB_IDS = tuple(c.verb for c in COMMANDS)


def match_command(text: str) -> CommandSpec | None:
    q = (text or "").strip()
    if not q:
        return None
    for spec in COMMANDS:
        if spec.pattern.search(q):
            return spec
    return None


def navigate_target(text: str, spec: CommandSpec) -> str | None:
    if spec.verb != "go_to_person":
        return None
    m = spec.pattern.search((text or "").strip())
    if not m:
        return None
    who = ""
    for g in m.groups():
        if g and str(g).strip():
            who = str(g).replace(".", "").strip()
            break
    return who or None
