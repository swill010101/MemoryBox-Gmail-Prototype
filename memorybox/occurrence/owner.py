"""Owner confirm / unlink / reject. GRAPH-03: rejected membership is not auto-restored."""
from __future__ import annotations

from typing import Any

from memorybox.occurrence.store import get_membership, set_membership_status


def confirm_membership(
    membership_id: str, *, actor_key: str = "owner", reason: str | None = None
) -> dict[str, Any]:
    return set_membership_status(
        membership_id,
        "owner_confirmed",
        actor_key=actor_key,
        reason=reason or "owner_confirm",
    )


def reject_membership(
    membership_id: str, *, actor_key: str = "owner", reason: str | None = None
) -> dict[str, Any]:
    return set_membership_status(
        membership_id,
        "rejected",
        actor_key=actor_key,
        reason=reason or "owner_reject",
    )


def unlink_membership(
    membership_id: str, *, actor_key: str = "owner", reason: str | None = None
) -> dict[str, Any]:
    """Durable negative evidence. Reprocess must not silently restore this join."""
    return set_membership_status(
        membership_id,
        "rejected",
        actor_key=actor_key,
        reason=reason or "owner_unlink",
    )


def confirm_or_reject(membership_id: str) -> dict[str, Any] | None:
    return get_membership(membership_id)
