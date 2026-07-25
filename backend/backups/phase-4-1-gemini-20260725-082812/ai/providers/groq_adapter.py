from collections.abc import AsyncIterator

import groq

from ai.groq_service import (
    GroqChatService,
    GroqConfigurationError,
    GroqResponseError,
)
from ai.model_registry import (
    get_provider_model_order,
)
from ai.model_types import StreamDelta
from ai.provider_adapter import ProviderError
from ai.task_classifier import TaskCategory
from core.config import settings
from schemas.chat import (
    ChatMessage,
    ChatResponse,
)


class GroqProviderAdapter:
    provider_name = "groq"

    def __init__(self) -> None:
        self._service: GroqChatService | None = None

    def is_configured(self) -> bool:
        return bool(
            settings.groq_api_key
        )

    def _get_service(self) -> GroqChatService:
        if self._service is None:
            self._service = GroqChatService()

        return self._service

    @staticmethod
    def _translate_error(
        error: Exception,
    ) -> ProviderError:
        if isinstance(
            error,
            GroqConfigurationError,
        ):
            return ProviderError(
                str(error),
                provider="groq",
                code="configuration",
                retryable=False,
            )

        if isinstance(
            error,
            groq.RateLimitError,
        ):
            return ProviderError(
                "Groq rate limit or quota was reached.",
                provider="groq",
                code="rate_limit",
                retryable=True,
                status_code=getattr(
                    error,
                    "status_code",
                    429,
                ),
            )

        if isinstance(
            error,
            groq.APITimeoutError,
        ):
            return ProviderError(
                "Groq took too long to respond.",
                provider="groq",
                code="timeout",
                retryable=True,
            )

        if isinstance(
            error,
            groq.APIConnectionError,
        ):
            return ProviderError(
                "The backend could not connect to Groq.",
                provider="groq",
                code="connection",
                retryable=True,
            )

        if isinstance(
            error,
            groq.APIStatusError,
        ):
            status_code = getattr(
                error,
                "status_code",
                None,
            )

            if status_code in {
                401,
                403,
            }:
                code = "authentication"
                retryable = False

            elif status_code == 429:
                code = "rate_limit"
                retryable = True

            else:
                code = "request"
                retryable = status_code in {
                    404,
                    408,
                    500,
                    502,
                    503,
                    504,
                }

            return ProviderError(
                "Groq rejected the model request.",
                provider="groq",
                code=code,
                retryable=retryable,
                status_code=status_code,
            )

        if isinstance(
            error,
            GroqResponseError,
        ):
            return ProviderError(
                str(error),
                provider="groq",
                code="response",
                retryable=True,
            )

        return ProviderError(
            "An unexpected Groq error occurred.",
            provider="groq",
            code="unknown",
            retryable=False,
        )

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> ChatResponse:
        models = get_provider_model_order(
            self.provider_name,
            category,
        )

        try:
            return await self._get_service().answer(
                message=message,
                history=history,
                preferred_models=models,
            )

        except Exception as error:
            raise self._translate_error(
                error
            ) from error

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> AsyncIterator[StreamDelta]:
        models = get_provider_model_order(
            self.provider_name,
            category,
        )

        try:
            async for delta in (
                self
                ._get_service()
                .stream_answer(
                    message=message,
                    history=history,
                    preferred_models=models,
                )
            ):
                yield StreamDelta(
                    kind=delta.kind,
                    content=delta.content,
                    provider=self.provider_name,
                    model=delta.model,
                )

        except Exception as error:
            raise self._translate_error(
                error
            ) from error
