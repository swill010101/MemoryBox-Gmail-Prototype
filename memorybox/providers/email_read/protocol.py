"""EmailReadProvider protocol."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from memorybox.providers.base import ProviderHealth
from memorybox.providers.email_read.dto import EmailMessageDto, EmailSourceRef


class EmailReadProvider(Protocol):
    provider_key: str

    def health(self) -> ProviderHealth: ...

    def iter_messages(
        self, source: EmailSourceRef, *, limit: int | None = None
    ) -> Iterator[EmailMessageDto]: ...
