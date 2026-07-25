import logging
from collections.abc import AsyncIterator, Iterable

from ai.model_types import StreamDelta
from ai.provider_adapter import (
    ProviderAdapter,
    ProviderError,
)
from ai.providers.groq_adapter import (
    GroqProviderAdapter,
)
from schemas.chat import (
    ChatMessage,
    ChatResponse,
)


logger = logging.getLogger(__name__)


class ModelRouter:
    """Provider-neutral model execution and fallback router."""

    def __init__(
        self,
        adapters: Iterable[ProviderAdapter] | None = None,
    ) -> None:
        self._adapters = tuple(
            adapters
            if adapters is not None
            else (
                GroqProviderAdapter(),
            )
        )

    def _configured_adapters(
        self,
    ) -> tuple[ProviderAdapter, ...]:
        return tuple(
            adapter
            for adapter in self._adapters
            if adapter.is_configured()
        )

    def is_configured(self) -> bool:
        return bool(
            self._configured_adapters()
        )

    def status(self) -> list[dict[str, object]]:
        return [
            {
                "provider": adapter.provider_name,
                "configured": adapter.is_configured(),
            }
            for adapter in self._adapters
        ]

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> ChatResponse:
        adapters = self._configured_adapters()

        if not adapters:
            raise ProviderError(
                "No AI provider is configured.",
                provider="router",
                code="configuration",
                retryable=False,
            )

        last_error: ProviderError | None = None

        for index, adapter in enumerate(adapters):
            try:
                return await adapter.answer(
                    message=message,
                    history=history,
                )

            except ProviderError as error:
                last_error = error

                logger.warning(
                    "Provider attempt failed: "
                    "provider=%s code=%s status=%s",
                    error.provider,
                    error.code,
                    error.status_code,
                )

                is_last_provider = (
                    index == len(adapters) - 1
                )

                if (
                    is_last_provider
                    or not error.retryable
                ):
                    raise

        if last_error is not None:
            raise last_error

        raise ProviderError(
            "No provider produced a response.",
            provider="router",
            code="response",
            retryable=False,
        )

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> AsyncIterator[StreamDelta]:
        adapters = self._configured_adapters()

        if not adapters:
            raise ProviderError(
                "No AI provider is configured.",
                provider="router",
                code="configuration",
                retryable=False,
            )

        last_error: ProviderError | None = None

        for index, adapter in enumerate(adapters):
            received_content = False

            try:
                async for delta in adapter.stream_answer(
                    message=message,
                    history=history,
                ):
                    if (
                        delta.kind == "token"
                        and delta.content
                    ):
                        received_content = True

                    yield delta

                return

            except ProviderError as error:
                last_error = error

                logger.warning(
                    "Streaming provider attempt failed: "
                    "provider=%s code=%s status=%s",
                    error.provider,
                    error.code,
                    error.status_code,
                )

                is_last_provider = (
                    index == len(adapters) - 1
                )

                if (
                    received_content
                    or is_last_provider
                    or not error.retryable
                ):
                    raise

        if last_error is not None:
            raise last_error

        raise ProviderError(
            "No provider produced a streaming response.",
            provider="router",
            code="response",
            retryable=False,
        )
