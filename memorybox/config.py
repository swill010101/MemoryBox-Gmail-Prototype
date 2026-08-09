"""Configuration for the MemoryBox monolith (env-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


@dataclass(frozen=True)
class Settings:
    """Runtime settings. No provider credentials in Increment 1."""

    database_url: str
    host: str
    port: int
    migrations_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parent
        default_url = "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox"
        return cls(
            database_url=_env("MEMORYBOX_DATABASE_URL", default_url) or default_url,
            host=_env("MEMORYBOX_HOST", "127.0.0.1") or "127.0.0.1",
            port=int(_env("MEMORYBOX_PORT", "8790") or "8790"),
            migrations_dir=root / "migrations",
        )


settings = Settings.from_env()
