import logging
from collections.abc import (
    AsyncIterator,
    Iterable,
)

from ai.model_types import StreamDelta
from ai.provider_adapter import (
    ProviderAdapter,
    ProviderError,
)
from ai.provider_health import (
    ProviderHealthManager,
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
    """
    Provider-neutral execution router with health tracking,
    cooldowns, circuit breaking, and safe fallback.
    """

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

        self._health = ProviderHealthManager(
            adapter.provider_name
            for adapter in self._adapters
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
        health_by_provider = {
            item["provider"]: item
            for item in self._health.snapshot()
        }

        return [
            {
                "provider": adapter.provider_name,
                "configured": adapter.is_configured(),
                "health": health_by_provider.get(
                    adapter.provider_name,
                    {},
                ),
            }
            for adapter in self._adapters
        ]

    @staticmethod
    def _availability_error() -> ProviderError:
        return ProviderError(
            (
                "All configured AI providers are "
                "temporarily unavailable."
            ),
            provider="router",
            code="availability",
            retryable=False,
        )

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
        attempted_provider = False

        for adapter in adapters:
            if not self._health.acquire_attempt(
                adapter.provider_name
            ):
                logger.info(
                    "Skipping unavailable provider: %s",
                    adapter.provider_name,
                )
                continue

            attempted_provider = True

            try:
                response = await adapter.answer(
                    message=message,
                    history=history,
                )

                self._health.record_success(
                    adapter.provider_name
                )

                return response

            except ProviderError as error:
                last_error = error

                self._health.record_failure(
                    adapter.provider_name,
                    error,
                )

                logger.warning(
                    "Provider attempt failed: "
                    "provider=%s code=%s status=%s "
                    "retryable=%s",
                    error.provider,
                    error.code,
                    error.status_code,
                    error.retryable,
                )

                if not error.retryable:
                    raise

        if not attempted_provider:
            raise self._availability_error()

        if last_error is not None:
            raise last_error

        raise self._availability_error()

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
        attempted_provider = False

        for adapter in adapters:
            if not self._health.acquire_attempt(
                adapter.provider_name
            ):
                logger.info(
                    "Skipping unavailable streaming "
                    "provider: %s",
                    adapter.provider_name,
                )
                continue

            attempted_provider = True
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

                self._health.record_success(
                    adapter.provider_name
                )

                return

            except ProviderError as error:
                last_error = error

                self._health.record_failure(
                    adapter.provider_name,
                    error,
                )

                logger.warning(
                    "Streaming provider attempt failed: "
                    "provider=%s code=%s status=%s "
                    "retryable=%s content_started=%s",
                    error.provider,
                    error.code,
                    error.status_code,
                    error.retryable,
                    received_content,
                )

                # Never combine partial responses generated
                # by different providers.
                if (
                    received_content
                    or not error.retryable
                ):
                    raise

        if not attempted_provider:
            raise self._availability_error()

        if last_error is not None:
            raise last_error

        raise self._availability_error()
