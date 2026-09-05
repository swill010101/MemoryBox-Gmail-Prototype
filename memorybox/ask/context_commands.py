"""Explicit conversational resets; no provider seeding or processing."""
import re


def is_clear_all(text):
    return bool(re.fullmatch(r"clear\s+all[.!]?", str(text or "").strip(), re.I))


def prepare_context(store, text, session_id, resolve_person):
    clear = is_clear_all(text)
    match = re.fullmatch(r"show\s+me\s+(.+?)[.!]?", str(text or "").strip(), re.I)
    fresh = clear
    if match and not clear:
        # Only a complete MB name/alias resolves; refinements retain context.
        fresh = resolve_person(match.group(1)) is not None
    if fresh:
        if session_id:
            store.clear(session_id)
        return store.get_or_create(), True
    return store.get_or_create(session_id), False


def override_places(store, session_id, places):
    """Apply explicit Gallery place edits before planning in a fresh session.

    Omitted edits inherit normally; [] explicitly clears location and trip scope.
    Rotation prevents an older in-flight Ask from restoring the prior location.
    """
    from dataclasses import replace
    current = store.get_or_create(session_id)
    fresh = store.get_or_create()
    return store.save(replace(
        current, session_id=fresh.session_id,
        place_names=tuple(places),
        event_labels=tuple(e for e in current.event_labels if not e.lower().startswith("trip:")),
        result_selection=(),
    ))
