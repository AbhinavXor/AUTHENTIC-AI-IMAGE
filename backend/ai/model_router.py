import logging
from collections.abc import (
    AsyncIterator,
    Iterable,
)

from ai.conversation_context import (
    resolve_contextual_request,
)
from ai.deterministic_math import (
    build_deterministic_math_answer,
)
from ai.deterministic_visualization import (
    attach_deterministic_visualization,
    build_deterministic_visualization,
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
from ai.product_identity import (
    resolve_product_identity_response,
)
from ai.providers.groq_adapter import (
    GroqProviderAdapter,
)
from ai.providers.gemini_adapter import (
    GeminiProviderAdapter,
)
from ai.providers.cloudflare_adapter import (
    CloudflareProviderAdapter,
)
from ai.providers.openrouter_adapter import (
    OpenRouterProviderAdapter,
)
from ai.providers.sambanova_adapter import (
    SambaNovaProviderAdapter,
)
from ai.task_classifier import (
    TaskCategory,
    classify_task,
)
from schemas.chat import (
    ChatMessage,
    ChatResponse,
    TokenUsage,
)


logger = logging.getLogger(__name__)

_DETERMINISTIC_PROVIDER = "deterministic"
_DETERMINISTIC_MODEL = "native-visualization-v1"
_DETERMINISTIC_MATH_MODEL = "native-math-v1"
_PRODUCT_IDENTITY_MODEL = "native-product-identity-v1"

_DETERMINISTIC_FALLBACK_TEXT = (
    "The AI explanation is temporarily unavailable. "
    "The visualization below was generated directly "
    "from the data or equation in your request."
)


def _deterministic_fallback_answer(
    message: str,
) -> str:
    return attach_deterministic_visualization(
        message=message,
        provider_answer=(
            _DETERMINISTIC_FALLBACK_TEXT
        ),
    )


def _deterministic_chat_response(
    *,
    message: str,
    category: str,
    routing_confidence: float,
) -> ChatResponse:
    return ChatResponse(
        answer=(
            _deterministic_fallback_answer(
                message
            )
        ),
        provider=_DETERMINISTIC_PROVIDER,
        model=_DETERMINISTIC_MODEL,
        category=category,
        routing_confidence=(
            routing_confidence
        ),
        request_id=None,
        usage=TokenUsage(),
    )



def _deterministic_math_chat_response(
    *,
    answer: str,
    category: str,
    routing_confidence: float,
) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        provider=_DETERMINISTIC_PROVIDER,
        model=_DETERMINISTIC_MATH_MODEL,
        category=category,
        routing_confidence=routing_confidence,
        request_id=None,
        usage=TokenUsage(),
    )


def _product_identity_chat_response(
    answer: str,
) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        provider=_DETERMINISTIC_PROVIDER,
        model=_PRODUCT_IDENTITY_MODEL,
        category="fast_chat",
        routing_confidence=1.0,
        request_id=None,
        usage=TokenUsage(),
    )


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
                GeminiProviderAdapter(),
                CloudflareProviderAdapter(),
                SambaNovaProviderAdapter(),
                OpenRouterProviderAdapter(),
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
        identity_answer = resolve_product_identity_response(
            message
        )
        if identity_answer is not None:
            return _product_identity_chat_response(
                identity_answer
            )

        effective_message = (
            resolve_contextual_request(
                message,
                history,
            )
        )

        classification = classify_task(
            effective_message
        )

        deterministic_visualization = (
            build_deterministic_visualization(
                effective_message
            )
        )

        deterministic_math_answer = (
            build_deterministic_math_answer(
                effective_message
            )
        )

        if deterministic_math_answer is not None:
            answer = deterministic_math_answer

            if deterministic_visualization is not None:
                answer = (
                    attach_deterministic_visualization(
                        message=effective_message,
                        provider_answer=answer,
                    )
                )

            return _deterministic_math_chat_response(
                answer=answer,
                category=classification.category,
                routing_confidence=(
                    classification.confidence
                ),
            )

        adapters = self._ordered_adapters(
            classification.category
        )

        if not adapters:
            if deterministic_visualization is not None:
                return _deterministic_chat_response(
                    message=effective_message,
                    category=(
                        classification.category
                    ),
                    routing_confidence=(
                        classification.confidence
                    ),
                )

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
                    message=effective_message,
                    history=history,
                    category=classification.category,
                )

                self._health.record_success(
                    adapter.provider_name
                )

                answer = response.answer

                if deterministic_visualization is not None:
                    answer = (
                        attach_deterministic_visualization(
                            message=effective_message,
                            provider_answer=answer,
                        )
                    )

                return response.model_copy(
                    update={
                        "answer": answer,
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

                continue

        if deterministic_visualization is not None:
            return _deterministic_chat_response(
                message=effective_message,
                category=(
                    classification.category
                ),
                routing_confidence=(
                    classification.confidence
                ),
            )

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
        identity_answer = resolve_product_identity_response(
            message
        )
        if identity_answer is not None:
            yield StreamDelta(
                kind="token",
                content=identity_answer,
                provider=_DETERMINISTIC_PROVIDER,
                model=_PRODUCT_IDENTITY_MODEL,
                category="fast_chat",
                routing_confidence=1.0,
            )
            yield StreamDelta(
                kind="done",
                provider=_DETERMINISTIC_PROVIDER,
                model=_PRODUCT_IDENTITY_MODEL,
                category="fast_chat",
                routing_confidence=1.0,
            )
            return

        effective_message = (
            resolve_contextual_request(
                message,
                history,
            )
        )

        classification = classify_task(
            effective_message
        )

        deterministic_visualization = (
            build_deterministic_visualization(
                effective_message
            )
        )

        deterministic_math_answer = (
            build_deterministic_math_answer(
                effective_message
            )
        )

        if deterministic_math_answer is not None:
            answer = deterministic_math_answer

            if deterministic_visualization is not None:
                answer = (
                    attach_deterministic_visualization(
                        message=effective_message,
                        provider_answer=answer,
                    )
                )

            yield StreamDelta(
                kind="token",
                content=answer,
                provider=_DETERMINISTIC_PROVIDER,
                model=_DETERMINISTIC_MATH_MODEL,
                category=classification.category,
                routing_confidence=(
                    classification.confidence
                ),
            )

            yield StreamDelta(
                kind="done",
                provider=_DETERMINISTIC_PROVIDER,
                model=_DETERMINISTIC_MATH_MODEL,
                category=classification.category,
                routing_confidence=(
                    classification.confidence
                ),
            )

            return

        adapters = self._ordered_adapters(
            classification.category
        )

        if not adapters:
            if deterministic_visualization is not None:
                yield StreamDelta(
                    kind="token",
                    content=(
                        _deterministic_fallback_answer(
                            message
                        )
                    ),
                    provider=(
                        _DETERMINISTIC_PROVIDER
                    ),
                    model=_DETERMINISTIC_MODEL,
                    category=(
                        classification.category
                    ),
                    routing_confidence=(
                        classification.confidence
                    ),
                )

                yield StreamDelta(
                    kind="done",
                    provider=(
                        _DETERMINISTIC_PROVIDER
                    ),
                    model=_DETERMINISTIC_MODEL,
                    category=(
                        classification.category
                    ),
                    routing_confidence=(
                        classification.confidence
                    ),
                )

                return

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

            buffered_content: list[str] = []

            final_provider = (
                adapter.provider_name
            )

            final_model = ""

            try:
                async for delta in adapter.stream_answer(
                    message=effective_message,
                    history=history,
                    category=classification.category,
                ):
                    if delta.provider:
                        final_provider = (
                            delta.provider
                        )

                    if delta.model:
                        final_model = delta.model

                    if (
                        delta.kind == "token"
                        and delta.content
                    ):
                        received_content = True

                        if (
                            deterministic_visualization
                            is not None
                        ):
                            buffered_content.append(
                                delta.content
                            )

                    if deterministic_visualization is None:
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

                if deterministic_visualization is not None:
                    provider_answer = "".join(
                        buffered_content
                    ).strip()

                    if not provider_answer:
                        provider_answer = (
                            _DETERMINISTIC_FALLBACK_TEXT
                        )

                    merged_answer = (
                        attach_deterministic_visualization(
                            message=effective_message,
                            provider_answer=(
                                provider_answer
                            ),
                        )
                    )

                    yield StreamDelta(
                        kind="token",
                        content=merged_answer,
                        provider=final_provider,
                        model=(
                            final_model
                            or _DETERMINISTIC_MODEL
                        ),
                        category=(
                            classification.category
                        ),
                        routing_confidence=(
                            classification.confidence
                        ),
                    )

                    yield StreamDelta(
                        kind="done",
                        provider=final_provider,
                        model=(
                            final_model
                            or _DETERMINISTIC_MODEL
                        ),
                        category=(
                            classification.category
                        ),
                        routing_confidence=(
                            classification.confidence
                        ),
                    )

                return

            except ProviderError as error:
                last_error = error

                self._health.record_failure(
                    adapter.provider_name,
                    error,
                )

                logger.warning(
                    "Streaming provider failed: "
                    "provider=%s category=%s "
                    "code=%s status=%s",
                    error.provider,
                    classification.category,
                    error.code,
                    error.status_code,
                )

                if (
                    deterministic_visualization
                    is not None
                    and received_content
                ):
                    partial_answer = "".join(
                        buffered_content
                    ).strip()

                    if partial_answer:
                        partial_answer = (
                            f"{partial_answer}\n\n"
                            "The explanation may be incomplete "
                            "because the provider response ended early."
                        )
                    else:
                        partial_answer = (
                            _DETERMINISTIC_FALLBACK_TEXT
                        )

                    yield StreamDelta(
                        kind="token",
                        content=(
                            attach_deterministic_visualization(
                                message=effective_message,
                                provider_answer=(
                                    partial_answer
                                ),
                            )
                        ),
                        provider=final_provider,
                        model=(
                            final_model
                            or _DETERMINISTIC_MODEL
                        ),
                        category=(
                            classification.category
                        ),
                        routing_confidence=(
                            classification.confidence
                        ),
                    )

                    yield StreamDelta(
                        kind="done",
                        provider=final_provider,
                        model=(
                            final_model
                            or _DETERMINISTIC_MODEL
                        ),
                        category=(
                            classification.category
                        ),
                        routing_confidence=(
                            classification.confidence
                        ),
                    )

                    return

                continue

        if deterministic_visualization is not None:
            yield StreamDelta(
                kind="token",
                content=(
                    _deterministic_fallback_answer(
                        message
                    )
                ),
                provider=_DETERMINISTIC_PROVIDER,
                model=_DETERMINISTIC_MODEL,
                category=classification.category,
                routing_confidence=(
                    classification.confidence
                ),
            )

            yield StreamDelta(
                kind="done",
                provider=_DETERMINISTIC_PROVIDER,
                model=_DETERMINISTIC_MODEL,
                category=classification.category,
                routing_confidence=(
                    classification.confidence
                ),
            )

            return

        if not attempted_provider:
            raise self._availability_error()

        if last_error is not None:
            raise last_error

        raise self._availability_error()
