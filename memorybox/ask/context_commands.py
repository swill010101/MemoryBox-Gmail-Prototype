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
