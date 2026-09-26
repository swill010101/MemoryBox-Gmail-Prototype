"""Ask package — Evidence-backed Ask + orchestrator (Increment 4)."""
from __future__ import annotations

from typing import Any

__all__ = ["AskOrchestrator", "AskResult"]


def __getattr__(name: str) -> Any:
    if name in {"AskOrchestrator", "AskResult"}:
        from memorybox.ask.orchestrator import AskOrchestrator, AskResult

        return AskOrchestrator if name == "AskOrchestrator" else AskResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
