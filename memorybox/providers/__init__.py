"""Capability provider adapters (MBBS Increment 2).

Domain / orchestration code depends on protocols + DTOs only.
Immich / Ollama / mbox POC clients are wrapped here — never as domain Person PKs.
"""

from memorybox.providers.email_read.protocol import EmailReadProvider
from memorybox.providers.llm.protocol import LlmProvider
from memorybox.providers.photo.protocol import PhotoProvider

__all__ = ["EmailReadProvider", "LlmProvider", "PhotoProvider"]
