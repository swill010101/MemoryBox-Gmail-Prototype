"""Exclusive wall-clock stage timings for one Ask (contextvar; fail-open).

Nested provider/paging times are recorded separately and are not added again
to the exclusive total. `other_ms` is total − exclusive accounted stages.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_clock: ContextVar[dict[str, Any] | None] = ContextVar("mb_stage_clock", default=None)

_EXCLUSIVE = (
    "person_resolution_ms",
    "retrieval_ms",
    "normalization_ms",
    "preaggregation_ms",
    "observation_cache_lookup_ms",
    "rollup_ms",
    "provenance_validation_ms",
    "ask_relative_ms",
    "narrator_ms",
    "gallery_pack_assembly_ms",
)


def start() -> object:
    return _clock.set(
        {
            "t0": time.perf_counter(),
            "ms": {},
            "providers": {},
            "pages": 0,
            "depth": {},
        }
    )


def ensure() -> object | None:
    if _clock.get() is None:
        return start()
    return None


def reset(token: object) -> None:
    try:
        _clock.reset(token)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return


def _state() -> dict[str, Any] | None:
    return _clock.get()


def add(name: str, ms: int, *, provider: bool = False) -> None:
    st = _state()
    if st is None:
        return
    ms = max(0, int(ms))
    if provider:
        prov = st.setdefault("providers", {})
        prov[name] = int(prov.get(name) or 0) + ms
        return
    st["ms"][name] = int(st["ms"].get(name) or 0) + ms


def bump_pages(n: int = 1) -> None:
    st = _state()
    if st is None:
        return
    st["pages"] = int(st.get("pages") or 0) + max(0, int(n))


@contextmanager
def timed(name: str, *, provider: bool = False) -> Iterator[None]:
    st = _state()
    nested = False
    if st is not None and not provider:
        depths = st.setdefault("depth", {})
        nested = int(depths.get(name) or 0) > 0
        depths[name] = int(depths.get(name) or 0) + 1
    t0 = time.perf_counter()
    try:
        yield
    finally:
        if st is not None and not provider:
            depths = st.setdefault("depth", {})
            depths[name] = max(0, int(depths.get(name) or 0) - 1)
        if not nested:
            add(name, int((time.perf_counter() - t0) * 1000), provider=provider)


def snapshot(*, wall_total_ms: int | None = None) -> dict[str, Any]:
    st = _state() or {"t0": time.perf_counter(), "ms": {}, "providers": {}, "pages": 0}
    elapsed = int((time.perf_counter() - float(st.get("t0") or time.perf_counter())) * 1000)
    total = elapsed if wall_total_ms is None else max(0, int(wall_total_ms))
    ms = dict(st.get("ms") or {})
    exclusive = {k: int(ms.get(k) or 0) for k in _EXCLUSIVE}
    accounted = sum(exclusive.values())
    other = max(0, total - accounted)
    providers = dict(st.get("providers") or {})
    return {
        **exclusive,
        "retrieval_providers_ms": providers,
        "paging_ms": int(ms.get("paging_ms") or 0),
        "paging_pages": int(st.get("pages") or 0),
        "other_ms": other,
        "accounted_ms": accounted,
        "total_ms": total,
    }
