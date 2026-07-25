import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ai.model_registry import (
    get_provider_model_order,
)
from ai.model_types import StreamDelta
from ai.provider_adapter import ProviderError
from ai.response_planner import create_response_plan
from ai.task_classifier import TaskCategory
from core.cloudflare_settings import cloudflare_settings
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
Return clean Markdown.
Begin with the actual answer and avoid generic filler.
""".strip()


class CloudflareProviderAdapter:
    provider_name = "cloudflare"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def is_configured(self) -> bool:
        return bool(
            cloudflare_settings.enabled
            and cloudflare_settings.account_id
            and cloudflare_settings.api_token
        )

    def _get_client(self) -> httpx.AsyncClient:
        if not self.is_configured():
            raise ProviderError(
                "Cloudflare Workers AI is not configured.",
                provider=self.provider_name,
                code="configuration",
                retryable=True,
            )

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=cloudflare_settings.base_url,
                headers={
                    "Authorization": (
                        "Bearer "
                        f"{cloudflare_settings.api_token}"
                    ),
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(
                    cloudflare_settings.timeout_seconds
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

    @classmethod
    def _extract_answer(
        cls,
        payload: dict[str, Any],
    ) -> str:
        result = payload.get("result")

        if isinstance(result, str):
            return result.strip()

        if not isinstance(result, dict):
            return ""

        answer = cls._extract_text(
            result.get("response")
        )

        if answer:
            return answer

        answer = cls._extract_text(
            result.get("output_text")
        )

        if answer:
            return answer

        choices = result.get("choices") or []

        if choices and isinstance(
            choices[0],
            dict,
        ):
            message = (
                choices[0].get("message")
                or {}
            )

            if isinstance(message, dict):
                answer = cls._extract_text(
                    message.get("content")
                )

                if answer:
                    return answer

        collected: list[str] = []

        for output_item in (
            result.get("output")
            or []
        ):
            if not isinstance(output_item, dict):
                continue

            for content_item in (
                output_item.get("content")
                or []
            ):
                if not isinstance(content_item, dict):
                    continue

                text = content_item.get("text")

                if isinstance(text, str):
                    collected.append(text)

        return "".join(collected).strip()

    def _messages(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> list[dict[str, str]]:
        plan = create_response_plan(message)

        system = f"""
{SYSTEM_PROMPT}

Response contract:
{plan.contract}
""".strip()

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": system,
            }
        ]

        messages.extend(
            {
                "role": item.role,
                "content": item.content,
            }
            for item in history[
                -cloudflare_settings
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
                "Cloudflare Workers AI timed out.",
                provider="cloudflare",
                code="timeout",
                retryable=True,
            )

        if isinstance(
            error,
            httpx.RequestError,
        ):
            return ProviderError(
                "Could not connect to Cloudflare Workers AI.",
                provider="cloudflare",
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
                "Cloudflare Workers AI request failed.",
                provider="cloudflare",
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
            "Unexpected Cloudflare Workers AI error.",
            provider="cloudflare",
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
                    (
                        "/accounts/"
                        f"{cloudflare_settings.account_id}"
                        "/ai/run/"
                        f"{model}"
                    ),
                    json={
                        "messages": self._messages(
                            message=message,
                            history=history,
                        ),
                        "temperature": 0.2,
                        "max_tokens": 2048,
                    },
                )

                response.raise_for_status()
                payload = response.json()

                answer = self._extract_answer(
                    payload
                )

                if not answer:
                    raise ProviderError(
                        "Cloudflare returned an empty answer.",
                        provider=self.provider_name,
                        code="response",
                        retryable=True,
                    )

                result = payload.get("result") or {}
                usage_data = (
                    result.get("usage")
                    if isinstance(result, dict)
                    else {}
                ) or {}

                return ChatResponse(
                    answer=answer,
                    provider=self.provider_name,
                    model=model,
                    request_id=(
                        response.headers.get(
                            "cf-ray"
                        )
                    ),
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
                    "Cloudflare model failed: "
                    "model=%s type=%s",
                    model,
                    type(error).__name__,
                )

                translated = self._translate(error)

                if translated.code not in {
                    "request",
                    "response",
                    "connection",
                    "rate_limit",
                }:
                    raise translated from error

        raise self._translate(
            last_error
            or RuntimeError(
                "No Cloudflare model was available."
            )
        )

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> AsyncIterator[StreamDelta]:
        # Buffered fallback streaming keeps cross-provider
        # failover safe and prevents mixed partial answers.
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
