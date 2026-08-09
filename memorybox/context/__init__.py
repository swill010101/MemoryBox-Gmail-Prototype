"""Ask session context contract (Increment 4).

In-memory for I4; persistence can implement the same ContextStore protocol later
without redesigning Ask / planner / orchestrator APIs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4


@dataclass(frozen=True)
class AskContext:
    """Inherited conversational context for EF-02 basic follow-ups.

    Fields are generalized (no demo-entity hardcoding). Empty/None means unset.
    """

    session_id: str
    person_names: tuple[str, ...] = ()
    place_names: tuple[str, ...] = ()
    event_labels: tuple[str, ...] = ()
    time_start: str | None = None  # ISO-8601 or year string
    time_end: str | None = None
    result_selection: tuple[str, ...] = ()  # evidence ids / photo external ids
    modalities_active: tuple[str, ...] = ()  # visual|still|photo|video|communication|calendar_event
    last_ask: str | None = None
    updated_at: str | None = None

    def breadcrumb(self) -> list[dict[str, str]]:
        """UI-facing crumbs; no family content required in empty state."""
        crumbs: list[dict[str, str]] = []
        if self.person_names:
            crumbs.append({"kind": "person", "value": ", ".join(self.person_names)})
        if self.place_names:
            crumbs.append({"kind": "place", "value": ", ".join(self.place_names)})
        if self.event_labels:
            crumbs.append({"kind": "event", "value": ", ".join(self.event_labels)})
        if self.time_start or self.time_end:
            crumbs.append(
                {
                    "kind": "time",
                    "value": f"{self.time_start or '…'} → {self.time_end or '…'}",
                }
            )
        if self.result_selection:
            crumbs.append(
                {"kind": "selection", "value": f"{len(self.result_selection)} item(s)"}
            )
        if self.modalities_active:
            crumbs.append(
                {"kind": "modality", "value": ", ".join(self.modalities_active)}
            )
        return crumbs

    def is_empty(self) -> bool:
        return not (
            self.person_names
            or self.place_names
            or self.event_labels
            or self.time_start
            or self.time_end
            or self.result_selection
            or self.modalities_active
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["breadcrumb"] = self.breadcrumb()
        d["empty"] = self.is_empty()
        return d

    @classmethod
    def empty(cls, session_id: str | None = None) -> "AskContext":
        return cls(session_id=session_id or str(uuid4()))


@dataclass
class ContextPatch:
    """Partial update — None means leave unchanged; empty tuple clears a list field."""

    person_names: tuple[str, ...] | None = None
    place_names: tuple[str, ...] | None = None
    event_labels: tuple[str, ...] | None = None
    time_start: str | None | object = field(default_factory=lambda: _UNSET)
    time_end: str | None | object = field(default_factory=lambda: _UNSET)
    result_selection: tuple[str, ...] | None = None
    modalities_active: tuple[str, ...] | None = None
    last_ask: str | None | object = field(default_factory=lambda: _UNSET)


_UNSET = object()


def apply_patch(ctx: AskContext, patch: ContextPatch) -> AskContext:
    kwargs: dict[str, Any] = {"updated_at": datetime.utcnow().isoformat() + "Z"}
    if patch.person_names is not None:
        kwargs["person_names"] = tuple(patch.person_names)
    if patch.place_names is not None:
        kwargs["place_names"] = tuple(patch.place_names)
    if patch.event_labels is not None:
        kwargs["event_labels"] = tuple(patch.event_labels)
    if patch.time_start is not _UNSET:
        kwargs["time_start"] = patch.time_start
    if patch.time_end is not _UNSET:
        kwargs["time_end"] = patch.time_end
    if patch.result_selection is not None:
        kwargs["result_selection"] = tuple(patch.result_selection)
    if patch.modalities_active is not None:
        kwargs["modalities_active"] = tuple(patch.modalities_active)
    if patch.last_ask is not _UNSET:
        kwargs["last_ask"] = patch.last_ask
    return replace(ctx, **kwargs)


class ContextStore(Protocol):
    """Persistence-agnostic session context API (I4: in-memory)."""

    def get_or_create(self, session_id: str | None = None) -> AskContext: ...

    def get(self, session_id: str) -> AskContext | None: ...

    def save(self, ctx: AskContext) -> AskContext: ...

    def clear(self, session_id: str) -> AskContext: ...

    def patch(self, session_id: str, patch: ContextPatch) -> AskContext: ...


class InMemoryContextStore:
    """Process-session store. Replace with durable backend later via ContextStore."""

    def __init__(self) -> None:
        self._sessions: dict[str, AskContext] = {}

    def get_or_create(self, session_id: str | None = None) -> AskContext:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        ctx = AskContext.empty(session_id)
        self._sessions[ctx.session_id] = ctx
        return ctx

    def get(self, session_id: str) -> AskContext | None:
        return self._sessions.get(session_id)

    def save(self, ctx: AskContext) -> AskContext:
        stamped = replace(
            ctx, updated_at=datetime.utcnow().isoformat() + "Z"
        )
        self._sessions[stamped.session_id] = stamped
        return stamped

    def clear(self, session_id: str) -> AskContext:
        ctx = AskContext.empty(session_id)
        self._sessions[session_id] = ctx
        return ctx

    def patch(self, session_id: str, patch: ContextPatch) -> AskContext:
        current = self.get_or_create(session_id)
        updated = apply_patch(current, patch)
        return self.save(updated)


# Process-global default store (thin UX + CLI share this for I4).
default_context_store = InMemoryContextStore()
