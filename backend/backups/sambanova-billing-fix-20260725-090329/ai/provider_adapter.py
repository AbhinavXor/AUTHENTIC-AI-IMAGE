from collections.abc import AsyncIterator
from typing import Literal, Protocol

from ai.model_types import StreamDelta
from ai.task_classifier import TaskCategory
from schemas.chat import (
    ChatMessage,
    ChatResponse,
)


ProviderErrorCode = Literal[
    "configuration",
    "authentication",
    "rate_limit",
    "timeout",
    "connection",
    "request",
    "response",
    "availability",
    "unknown",
]


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        code: ProviderErrorCode,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)

        self.provider = provider
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class ProviderAdapter(Protocol):
    provider_name: str

    def is_configured(self) -> bool:
        """Return whether provider credentials exist."""

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> ChatResponse:
        """Generate one complete response."""

    def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> AsyncIterator[StreamDelta]:
        """Generate streaming response events."""
