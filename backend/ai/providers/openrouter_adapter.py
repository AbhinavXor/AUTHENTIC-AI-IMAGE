import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ai.model_registry import get_provider_model_order
from ai.model_types import StreamDelta
from ai.provider_adapter import ProviderError
from ai.response_language import (
    response_language_contract,
)
from ai.response_planner import create_response_plan
from ai.task_classifier import TaskCategory
from core.openrouter_settings import openrouter_settings
from schemas.chat import (
    ChatMessage,
    ChatResponse,
    TokenUsage,
)


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are Serenya, the intelligent answer layer behind Authentic AI.

This request uses an external provider model. Never claim that the
provider model is Authentic AI's proprietary native Serenya runtime.

Answer accurately from reliable knowledge and supplied context.
State uncertainty instead of inventing information.
Never fabricate citations, files, links, actions, or test results.
Never reveal hidden reasoning.
Respond in the user's language.
Return clean Markdown and begin with the actual answer.
""".strip()


_BLOCKED_MODEL_TERMS = (
    "safety",
    "moderation",
    "guard",
    "content-safety",
    "embedding",
    "rerank",
    "classifier",
)


class OpenRouterProviderAdapter:
    provider_name = "openrouter"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def is_configured(self) -> bool:
        return bool(
            openrouter_settings.enabled
            and openrouter_settings.api_key
        )

    def _get_client(self) -> httpx.AsyncClient:
        if not self.is_configured():
            raise ProviderError(
                "OpenRouter is not configured.",
                provider=self.provider_name,
                code="configuration",
                retryable=True,
            )

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=openrouter_settings.base_url,
                headers={
                    "Authorization": (
                        "Bearer "
                        f"{openrouter_settings.api_key}"
                    ),
                    "Content-Type": "application/json",
                    "X-Title": "Authentic AI",
                },
                timeout=httpx.Timeout(
                    openrouter_settings.timeout_seconds
                ),
            )

        return self._client

    @staticmethod
    def _extract_text(
        value: Any,
    ) -> str:
        if isinstance(value, str):
            return value.strip()

        if not isinstance(value, list):
            return ""

        parts: list[str] = []

        for item in value:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                text = item.get("text")

                if isinstance(text, str):
                    parts.append(text)

        return "".join(parts).strip()

    def _messages(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> list[dict[str, str]]:
        plan = create_response_plan(message)

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"{SYSTEM_PROMPT}\n\n"
                    f"{response_language_contract(message)}\n\n"
                    f"Response contract:\n{plan.contract}"
                ),
            }
        ]

        messages.extend(
            {
                "role": item.role,
                "content": item.content,
            }
            for item in history[
                -openrouter_settings
                .maximum_history_messages:
            ]
        )

        messages.append(
            {
                "role": "user",
                "content": message,
            }
        )

        return messages

    @staticmethod
    def _translate(
        error: Exception,
    ) -> ProviderError:
        if isinstance(
            error,
            ProviderError,
        ):
            return error

        if isinstance(
            error,
            httpx.TimeoutException,
        ):
            return ProviderError(
                "OpenRouter timed out.",
                provider="openrouter",
                code="timeout",
                retryable=True,
            )

        if isinstance(
            error,
            httpx.RequestError,
        ):
            return ProviderError(
                "Could not connect to OpenRouter.",
                provider="openrouter",
                code="connection",
                retryable=True,
            )

        if isinstance(
            error,
            httpx.HTTPStatusError,
        ):
            status_code = error.response.status_code

            if status_code in {
                401,
                403,
            }:
                code = "authentication"

            elif status_code == 402:
                code = "billing"

            elif status_code == 429:
                code = "rate_limit"

            elif status_code in {
                408,
                500,
                502,
                503,
                504,
            }:
                code = "connection"

            else:
                code = "request"

            return ProviderError(
                "OpenRouter request failed.",
                provider="openrouter",
                code=code,
                retryable=code in {
                    "billing",
                    "rate_limit",
                    "timeout",
                    "connection",
                },
                status_code=status_code,
            )

        return ProviderError(
            "Unexpected OpenRouter error.",
            provider="openrouter",
            code="unknown",
            retryable=True,
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

        last_error: Exception | None = None

        for model in models:
            try:
                response = await self._get_client().post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": self._messages(
                            message=message,
                            history=history,
                        ),
                        "temperature": 0.2,
                        "max_tokens": 2048,
                        "stream": False,
                    },
                )

                response.raise_for_status()
                payload = response.json()

                choices = payload.get("choices") or []

                if not choices:
                    raise ProviderError(
                        "OpenRouter returned no choices.",
                        provider=self.provider_name,
                        code="response",
                        retryable=True,
                    )

                message_data = (
                    choices[0].get("message")
                    or {}
                )

                answer = self._extract_text(
                    message_data.get("content")
                )

                returned_model = str(
                    payload.get("model")
                    or model
                )

                combined = (
                    returned_model.lower()
                    + " "
                    + answer.lower()
                )

                if (
                    not answer
                    or answer.lower().startswith(
                        "user safety:"
                    )
                    or any(
                        term in combined
                        for term in _BLOCKED_MODEL_TERMS
                    )
                ):
                    raise ProviderError(
                        "OpenRouter selected a non-chat "
                        "or unusable model.",
                        provider=self.provider_name,
                        code="response",
                        retryable=True,
                    )

                usage_data = payload.get("usage") or {}

                return ChatResponse(
                    answer=answer,
                    provider=self.provider_name,
                    model=returned_model,
                    request_id=payload.get("id"),
                    usage=TokenUsage(
                        prompt_tokens=int(
                            usage_data.get(
                                "prompt_tokens",
                                0,
                            )
                            or 0
                        ),
                        completion_tokens=int(
                            usage_data.get(
                                "completion_tokens",
                                0,
                            )
                            or 0
                        ),
                        total_tokens=int(
                            usage_data.get(
                                "total_tokens",
                                0,
                            )
                            or 0
                        ),
                    ),
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "OpenRouter model failed: "
                    "model=%s type=%s",
                    model,
                    type(error).__name__,
                )

                translated = self._translate(error)

                if translated.code not in {
                    "request",
                    "response",
                    "connection",
                }:
                    raise translated from error

        raise self._translate(
            last_error
            or RuntimeError(
                "No OpenRouter model was available."
            )
        )

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> AsyncIterator[StreamDelta]:
        response = await self.answer(
            message=message,
            history=history,
            category=category,
        )

        yield StreamDelta(
            kind="token",
            content=response.answer,
            provider=self.provider_name,
            model=response.model,
        )

        yield StreamDelta(
            kind="done",
            provider=self.provider_name,
            model=response.model,
        )
