"""P2-I4 Mixed-Media Find — demo fixture (not product hard-code).

Load via GET /explore/demo/peggy-christmas for UX prove only.
"""
from __future__ import annotations

from typing import Any


def peggy_christmas_fixture() -> dict[str, Any]:
    """Deterministic Mixed-Media Find fixture for I4 acceptance demo."""
    items: list[dict[str, Any]] = [
        {
            "id": "ph-01",
            "kind": "photo",
            "title": "Peggy at the tree",
            "date": "1998-12-24",
            "people": ["Peggy"],
            "place": "Oak Street",
            "excerpt": "Christmas Eve living room",
        },
        {
            "id": "ph-02",
            "kind": "photo",
            "title": "Stockings hung",
            "date": "1999-12-24",
            "people": ["Peggy", "Rick"],
            "excerpt": "Mantle before midnight",
        },
        {
            "id": "vid-01",
            "kind": "video",
            "title": "Peggy opens gifts",
            "date": "2001-12-25",
            "people": ["Peggy"],
            "duration_sec": 42,
            "t": 18.5,
            "video_external_id": "vid-demo-peggy-gifts",
            "excerpt": "Moment @ 18.5s",
        },
        {
            "id": "em-01",
            "kind": "email",
            "title": "Re: Christmas plans",
            "date": "2003-12-10",
            "people": ["Peggy", "Rick"],
            "from": "rick@example.com",
            "to": "peggy@example.com",
            "excerpt": "Can you bring the fudge recipe again?",
        },
        {
            "id": "ph-03",
            "kind": "photo",
            "title": "Kitchen morning",
            "date": "2004-12-25",
            "people": ["Peggy"],
            "excerpt": "Coffee and wrapping scraps",
        },
        {
            "id": "art-01",
            "kind": "artifact",
            "title": "Hand-carved nativity",
            "date": "2005-12-01",
            "people": ["Peggy"],
            "excerpt": "Gift from Mom — still on the mantel",
        },
        {
            "id": "st-01",
            "kind": "story",
            "title": "Rick remembers the blackout Christmas",
            "date": "2005-12-26",
            "people": ["Rick", "Peggy"],
            "excerpt": "Candles, Monopoly, and the last of the fudge",
        },
        {
            "id": "ph-04",
            "kind": "photo",
            "title": "Snow on Oak Street",
            "date": "2006-12-23",
            "people": ["Peggy"],
            "place": "Oak Street",
        },
        {
            "id": "vid-02",
            "kind": "video",
            "title": "Caroling in the hall",
            "date": "2007-12-24",
            "people": ["Peggy", "Rick"],
            "duration_sec": 95,
            "t": 40.0,
            "video_external_id": "vid-demo-caroling",
            "excerpt": "Moment @ 40s",
        },
        {
            "id": "em-02",
            "kind": "email",
            "title": "Travel for Christmas",
            "date": "2008-11-28",
            "people": ["Peggy"],
            "from": "peggy@example.com",
            "excerpt": "Arriving Thursday — save me the end seat.",
        },
        {
            "id": "ph-05",
            "kind": "photo",
            "title": "Table set for twelve",
            "date": "2009-12-25",
            "people": ["Peggy"],
        },
        {
            "id": "ph-06",
            "kind": "photo",
            "title": "Peggy and the red scarf",
            "date": "2010-12-24",
            "people": ["Peggy"],
        },
        {
            "id": "art-02",
            "kind": "artifact",
            "title": "Recipe card — fudge",
            "date": "2011-12-20",
            "people": ["Peggy"],
            "excerpt": "Stained, folded, still used",
        },
        {
            "id": "ph-07",
            "kind": "photo",
            "title": "Fireplace glow",
            "date": "2012-12-24",
            "people": ["Peggy", "Rick"],
        },
        {
            "id": "em-03",
            "kind": "email",
            "title": "Photo from last year",
            "date": "2013-12-15",
            "people": ["Peggy"],
            "excerpt": "Attached the oak-street snow shot",
        },
        {
            "id": "ph-08",
            "kind": "photo",
            "title": "Kids at the tree",
            "date": "2014-12-25",
            "people": ["Peggy"],
        },
        {
            "id": "ph-09",
            "kind": "photo",
            "title": "Morning light, living room",
            "date": "2015-12-25",
            "people": ["Peggy"],
        },
        {
            "id": "st-02",
            "kind": "story",
            "title": "Why we always hang the glass bird",
            "date": "2016-12-24",
            "people": ["Peggy"],
            "excerpt": "Mom’s ornament — unbroken since ’82",
        },
        {
            "id": "ph-10",
            "kind": "photo",
            "title": "Peggy laughing",
            "date": "2017-12-24",
            "people": ["Peggy"],
        },
        {
            "id": "ph-11",
            "kind": "photo",
            "title": "Porch lights",
            "date": "2018-12-23",
            "people": ["Peggy"],
            "place": "Oak Street",
        },
        {
            "id": "ph-12",
            "kind": "photo",
            "title": "Quiet Christmas morning",
            "date": "2019-12-25",
            "people": ["Peggy"],
        },
        {
            "id": "ph-13",
            "kind": "photo",
            "title": "Zoom Christmas still",
            "date": "2020-12-25",
            "people": ["Peggy", "Rick"],
            "excerpt": "Distance, same jokes",
        },
        {
            "id": "ph-14",
            "kind": "photo",
            "title": "Together again",
            "date": "2021-12-24",
            "people": ["Peggy", "Rick"],
        },
        {
            "id": "ph-undated",
            "kind": "photo",
            "title": "Peggy at Christmas (scan, undated)",
            "date": None,
            "undated": True,
            "people": ["Peggy"],
            "excerpt": "Box of prints — year unknown",
            "face_identity": "Unknown",
            "teachable": True,
        },
        {
            "id": "em-04",
            "kind": "email",
            "title": "Next year at Oak Street",
            "date": "2021-12-28",
            "people": ["Peggy"],
            "excerpt": "Same house. Same tree corner.",
        },
    ]

    # Enrich a dated photo for visible I1 Teach proof in demo.
    for it in items:
        if it["id"] == "ph-01":
            it["teachable"] = True
            it["face_identity"] = "Unknown"
            it["face_box"] = {"x": 0.28, "y": 0.18, "w": 0.22, "h": 0.28}
        if it["id"] == "vid-01":
            it["teachable"] = True
            it["face_identity"] = "Unknown"
            it["paused_frame"] = True
            it["face_box"] = {"x": 0.35, "y": 0.2, "w": 0.2, "h": 0.3}

    counts = {
        "photo": sum(1 for i in items if i["kind"] == "photo"),
        "video": sum(1 for i in items if i["kind"] == "video"),
        "email": sum(1 for i in items if i["kind"] == "email"),
        "artifact": sum(1 for i in items if i["kind"] == "artifact"),
        "story": sum(1 for i in items if i["kind"] == "story"),
        "undated": sum(1 for i in items if i.get("undated") or not i.get("date")),
    }
    story_bit = (
        f"and a story Rick told"
        if counts["story"] == 1
        else f"and {counts['story']} stories"
    )
    return {
        "ok": True,
        "demo": True,
        "fixture_id": "peggy-christmas",
        "query": "Tell me about Peggy around Christmas",
        "title": "Peggy around Christmas",
        "curator": (
            f"I found {len(items)} memories of Peggy around Christmas, including "
            f"{counts['photo']} photos, {counts['video']} video moments, "
            f"{counts['email']} emails, {counts['artifact']} artifacts, "
            f"{story_bit}."
        ),
        "chips": [
            {"kind": "person", "label": "Peggy"},
            {"kind": "event", "label": "Christmas"},
            {"kind": "range", "label": "1998–2021"},
        ],
        "range": {"start": "1998-01-01", "end": "2021-12-31"},
        "items": items,
        "counts": counts,
    }
