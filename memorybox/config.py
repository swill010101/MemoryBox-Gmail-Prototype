"""Configuration for the MemoryBox monolith — host-portable (D7).

No product-host names, drive letters, or credentials are baked into logic.
Set MEMORYBOX_* per host. MEMORYBOX_ALLOW_DEV_DEFAULTS=1 enables local desktop
defaults for development/prove only — never use that as the P1 runtime deploy path.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


def _truthy(name: str) -> bool:
    return (_env(name, "0") or "0").lower() in ("1", "true", "yes", "on")


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
# P1 runtime hostname — cloud/desktop agents probe this after loopback.
FLIGHTSIM_OLLAMA_BASE_URL = "http://flightsim:11434"
OLLAMA_AUTODETECT_URLS = (DEFAULT_OLLAMA_BASE_URL, FLIGHTSIM_OLLAMA_BASE_URL)


def _resolve_ollama_base_url(configured: str | None) -> str | None:
    """Honor MEMORYBOX_OLLAMA_BASE_URL; otherwise use the first Ollama that answers."""
    explicit = (configured or "").strip() or None
    if explicit:
        return explicit
    try:
        from memorybox.providers.llm._ollama_http import ollama_reachable

        for url in OLLAMA_AUTODETECT_URLS:
            if ollama_reachable(url):
                return url
    except Exception:
        return None
    return None


@dataclass(frozen=True)
class Settings:
    database_url: str
    host: str
    port: int
    migrations_dir: Path
    qdrant_url: str
    qdrant_collection: str
    ollama_base_url: str | None
    ollama_embed_model: str
    ollama_chat_model: str
    smoke_mbox_uri: str | None
    smoke_ics_uri: str | None
    allow_dev_defaults: bool

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parent
        allow_dev = _truthy("MEMORYBOX_ALLOW_DEV_DEFAULTS")
        db_default = (
            "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
            if allow_dev
            else None
        )
        database_url = _env("MEMORYBOX_DATABASE_URL", db_default)
        if not database_url:
            raise RuntimeError(
                "MEMORYBOX_DATABASE_URL is required "
                "(or set MEMORYBOX_ALLOW_DEV_DEFAULTS=1 for local desktop defaults only)"
            )
        qdrant_default = ":memory:" if allow_dev else None
        # FlightSim/P1 serve uses localhost Qdrant. After the gate clears
        # ALLOW_DEV, Settings must not require a missing MEMORYBOX_QDRANT_URL.
        if not qdrant_default and _truthy("MEMORYBOX_P1_RUNTIME_HOST"):
            qdrant_default = "http://127.0.0.1:6333"
        qdrant_url = _env("MEMORYBOX_QDRANT_URL", qdrant_default)
        if not qdrant_url:
            raise RuntimeError(
                "MEMORYBOX_QDRANT_URL is required "
                "(network URL on the P1 runtime host; :memory: or path:... on desktop prove)"
            )
        return cls(
            database_url=database_url,
            host=_env("MEMORYBOX_HOST", "0.0.0.0") or "0.0.0.0",
            port=int(_env("MEMORYBOX_PORT", "8790") or "8790"),
            migrations_dir=root / "migrations",
            qdrant_url=qdrant_url,
            qdrant_collection=_env("MEMORYBOX_QDRANT_COLLECTION", "memorybox_evidence")
            or "memorybox_evidence",
            ollama_base_url=_resolve_ollama_base_url(_env("MEMORYBOX_OLLAMA_BASE_URL")),
            ollama_embed_model=_env("MEMORYBOX_OLLAMA_EMBED_MODEL", "nomic-embed-text")
            or "nomic-embed-text",
            ollama_chat_model=_env("MEMORYBOX_OLLAMA_CHAT_MODEL", "llama3.2") or "llama3.2",
            smoke_mbox_uri=_env("MEMORYBOX_SMOKE_MBOX_URI"),
            smoke_ics_uri=_env("MEMORYBOX_SMOKE_ICS_URI"),
            allow_dev_defaults=allow_dev,
        )


class _SettingsProxy:
    """Lazy settings so importing the package does not require env until first use."""

    _cached: Settings | None = None

    def reload(self) -> Settings:
        self._cached = Settings.from_env()
        return self._cached

    def _get(self) -> Settings:
        if self._cached is None:
            self._cached = Settings.from_env()
        return self._cached

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


settings = _SettingsProxy()  # type: ignore[assignment]
