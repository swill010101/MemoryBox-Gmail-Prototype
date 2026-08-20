"""P2-I10 Cross-Source Correlation — Places, events, owner-correctable links."""

from memorybox.correlate.p2_i10_acceptance import prove_p2_i10
from memorybox.correlate.store import (
    confirm_link,
    date_conflicts,
    get_event,
    get_place,
    list_links,
    reject_link,
    upsert_event,
    upsert_link,
    upsert_place,
)

__all__ = [
    "confirm_link",
    "date_conflicts",
    "get_event",
    "get_place",
    "list_links",
    "prove_p2_i10",
    "reject_link",
    "upsert_event",
    "upsert_link",
    "upsert_place",
]
