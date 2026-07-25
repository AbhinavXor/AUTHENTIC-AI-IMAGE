import logging
from collections.abc import (
    AsyncIterator,
    Iterable,
)

from ai.model_registry import (
    get_provider_priority,
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
from ai.task_classifier import (
    TaskCategory,
    classify_task,
)
from schemas.chat import (
    ChatMessage,
    ChatResponse,
)


logger = logging.getLogger(__name__)


class ModelRouter:
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

    def _ordered_adapters(
        self,
        category: TaskCategory,
    ) -> tuple[ProviderAdapter, ...]:
        priority = get_provider_priority(
            category
        )

        positions = {
            provider: index
            for index, provider in enumerate(
                priority
            )
        }

        return tuple(
            sorted(
                self._configured_adapters(),
                key=lambda adapter: positions.get(
                    adapter.provider_name,
                    len(positions),
                ),
            )
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
        classification = classify_task(
            message
        )

        adapters = self._ordered_adapters(
            classification.category
        )

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
                continue

            attempted_provider = True

            try:
                response = await adapter.answer(
                    message=message,
                    history=history,
                    category=classification.category,
                )

                self._health.record_success(
                    adapter.provider_name
                )

                return response.model_copy(
                    update={
                        "category": (
                            classification.category
                        ),
                        "routing_confidence": (
                            classification.confidence
                        ),
                    }
                )

            except ProviderError as error:
                last_error = error

                self._health.record_failure(
                    adapter.provider_name,
                    error,
                )

                logger.warning(
                    "Provider failed: provider=%s "
                    "category=%s code=%s status=%s",
                    error.provider,
                    classification.category,
                    error.code,
                    error.status_code,
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
        classification = classify_task(
            message
        )

        adapters = self._ordered_adapters(
            classification.category
        )

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
                continue

            attempted_provider = True
            received_content = False

            try:
                async for delta in adapter.stream_answer(
                    message=message,
                    history=history,
                    category=classification.category,
                ):
                    if (
                        delta.kind == "token"
                        and delta.content
                    ):
                        received_content = True

                    yield StreamDelta(
                        kind=delta.kind,
                        content=delta.content,
                        provider=delta.provider,
                        model=delta.model,
                        category=(
                            classification.category
                        ),
                        routing_confidence=(
                            classification.confidence
                        ),
                    )

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
