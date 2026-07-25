from collections.abc import AsyncIterator
from typing import Literal, Protocol

from ai.model_types import StreamDelta
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
    """Provider-neutral failure exposed to the model router."""

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
    """Contract implemented by every model provider."""

    provider_name: str

    def is_configured(self) -> bool:
        """Return whether required credentials are available."""

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> ChatResponse:
        """Generate one complete response."""

    def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> AsyncIterator[StreamDelta]:
        """Generate provider-neutral streaming events."""
