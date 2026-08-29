"""Photo package."""

from memorybox.providers.photo.protocol import PhotoProvider

__all__ = ["PhotoProvider", "build_photo"]


def __getattr__(name: str):
    # build_photo lives in ask.deps (process singleton). Keep a lazy alias so
    # `from memorybox.providers.photo import build_photo` does not 500.
    if name == "build_photo":
        from memorybox.ask.deps import build_photo as _build_photo

        return _build_photo
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
