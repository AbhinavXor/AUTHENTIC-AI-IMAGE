import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from google import genai
from google.genai import (
    errors,
    types,
)

from ai.model_registry import (
    get_provider_model_order,
)
from ai.model_types import StreamDelta
from ai.provider_adapter import ProviderError
from ai.response_language import (
    response_language_contract,
)
from ai.response_planner import (
    ResponsePlan,
    create_response_plan,
)
from ai.task_classifier import TaskCategory
from core.gemini_settings import gemini_settings
from schemas.chat import (
    ChatMessage,
    ChatResponse,
    TokenUsage,
)


logger = logging.getLogger(__name__)


GEMINI_SYSTEM_PROMPT = """
You are Serenya, the intelligent answer layer operating behind the
Authentic AI interface.

This request uses an external provider model for inference. Never claim
that the provider model is Authentic AI's proprietary native Serenya
runtime.

ACCURACY

- Answer from reliable knowledge and supplied conversation context.
- State uncertainty instead of inventing information.
- Never fabricate citations, files, links, actions, measurements,
  test results, or research findings.
- Distinguish facts, assumptions, inferences, and recommendations.
- Never expose hidden reasoning or private chain-of-thought.

LANGUAGE

- Respond in the language used by the user whenever practical.
- For Hindi or Hinglish, use natural readable Hinglish unless another
  language is requested.

ANSWER QUALITY

- Begin with the answer, recommendation, or principal finding.
- Do not begin with filler.
- Do not repeat the question.
- Use concrete explanations and meaningful examples.
- Return clean valid Markdown.
- Do not add a generic conclusion or routine offer for more help.
""".strip()


class GeminiResponseError(RuntimeError):
    """Raised when Gemini returns no usable text."""


class GeminiProviderAdapter:
    provider_name = "gemini"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def is_configured(self) -> bool:
        return bool(
            gemini_settings.api_key
        )

    def _get_client(self) -> genai.Client:
        if not self.is_configured():
            raise ProviderError(
                "GEMINI_API_KEY is not configured.",
                provider=self.provider_name,
                code="configuration",
                retryable=False,
            )

        if self._client is None:
            self._client = genai.Client(
                api_key=gemini_settings.api_key,
                http_options=types.HttpOptions(
                    timeout=int(
                        gemini_settings.timeout_seconds
                        * 1000
                    ),
                ),
            )

        return self._client

    @staticmethod
    def _status_code(
        error: Exception,
    ) -> int | None:
        raw_code = getattr(
            error,
            "code",
            None,
        )

        try:
            return int(raw_code)
        except (
            TypeError,
            ValueError,
        ):
            return None

    @classmethod
    def _can_try_next_model(
        cls,
        error: Exception,
    ) -> bool:
        if isinstance(
            error,
            GeminiResponseError,
        ):
            return True

        if not isinstance(
            error,
            errors.APIError,
        ):
            return False

        status_code = cls._status_code(
            error
        )

        if status_code in {
            404,
            408,
            429,
            500,
            502,
            503,
            504,
        }:
            return True

        if status_code == 403:
            message = str(
                getattr(
                    error,
                    "message",
                    "",
                )
            ).lower()

            return (
                "model" in message
                and "api key" not in message
            )

        return False

    @classmethod
    def _translate_error(
        cls,
        error: Exception,
    ) -> ProviderError:
        if isinstance(
            error,
            ProviderError,
        ):
            return error

        if isinstance(
            error,
            GeminiResponseError,
        ):
            return ProviderError(
                str(error),
                provider="gemini",
                code="response",
                retryable=True,
            )

        if isinstance(
            error,
            (
                asyncio.TimeoutError,
                TimeoutError,
                httpx.TimeoutException,
            ),
        ):
            return ProviderError(
                "Gemini took too long to respond.",
                provider="gemini",
                code="timeout",
                retryable=True,
            )

        if isinstance(
            error,
            httpx.HTTPError,
        ):
            return ProviderError(
                "The backend could not connect to Gemini.",
                provider="gemini",
                code="connection",
                retryable=True,
            )

        if isinstance(
            error,
            errors.APIError,
        ):
            status_code = cls._status_code(
                error
            )

            message = str(
                getattr(
                    error,
                    "message",
                    "",
                )
                or error
            ).lower()

            if (
                status_code in {
                    401,
                    403,
                }
                or (
                    status_code == 400
                    and "api key" in message
                )
            ):
                return ProviderError(
                    "Gemini credentials are invalid "
                    "or do not have permission.",
                    provider="gemini",
                    code="authentication",

                    # Allows the central router to continue
                    # safely to Groq.
                    retryable=True,
                    status_code=status_code,
                )

            if status_code == 429:
                return ProviderError(
                    "Gemini quota or rate limit was reached.",
                    provider="gemini",
                    code="rate_limit",
                    retryable=True,
                    status_code=status_code,
                )

            if status_code in {
                408,
                500,
                502,
                503,
                504,
            }:
                return ProviderError(
                    "Gemini is temporarily unavailable.",
                    provider="gemini",
                    code="connection",
                    retryable=True,
                    status_code=status_code,
                )

            if status_code == 404:
                return ProviderError(
                    "No configured Gemini model "
                    "was available.",
                    provider="gemini",
                    code="request",
                    retryable=True,
                    status_code=status_code,
                )

            return ProviderError(
                "Gemini rejected the request.",
                provider="gemini",
                code="request",
                retryable=False,
                status_code=status_code,
            )

        return ProviderError(
            "An unexpected Gemini error occurred.",
            provider="gemini",
            code="unknown",
            retryable=True,
        )

    @staticmethod
    def _build_system_instruction(
        plan: ResponsePlan,
        message: str,
    ) -> str:
        return f"""
{GEMINI_SYSTEM_PROMPT}

{response_language_contract(message)}

RESPONSE PLAN

Intent: {plan.intent}

Required response contract:
{plan.contract}

Follow the contract naturally. Never mention the response plan,
classification, provider routing, or system instruction.
""".strip()

    @staticmethod
    def _text_part(
        text: str,
    ) -> types.Part:
        return types.Part.from_text(
            text=text
        )

    def _build_contents(
        self,
        *,
        message: str,
        history: list[ChatMessage],
    ) -> list[types.Content]:
        limited_history = history[
            -gemini_settings.maximum_history_messages:
        ]

        contents: list[types.Content] = []

        for item in limited_history:
            role = (
                "model"
                if item.role == "assistant"
                else "user"
            )

            contents.append(
                types.Content(
                    role=role,
                    parts=[
                        self._text_part(
                            item.content
                        )
                    ],
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=[
                    self._text_part(
                        message
                    )
                ],
            )
        )

        return contents

    def _generation_config(
        self,
        plan: ResponsePlan,
        message: str,
    ) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=(
                self._build_system_instruction(
                    plan,
                    message,
                )
            ),
            temperature=0.2,
            max_output_tokens=(
                plan.max_completion_tokens
            ),
        )

    @staticmethod
    def _response_text(
        response: Any,
    ) -> str:
        try:
            return (
                getattr(
                    response,
                    "text",
                    "",
                )
                or ""
            ).strip()
        except Exception:
            return ""

    @staticmethod
    def _token_usage(
        response: Any,
    ) -> TokenUsage:
        metadata = getattr(
            response,
            "usage_metadata",
            None,
        )

        if metadata is None:
            return TokenUsage()

        prompt_tokens = (
            getattr(
                metadata,
                "prompt_token_count",
                0,
            )
            or 0
        )

        completion_tokens = (
            getattr(
                metadata,
                "candidates_token_count",
                0,
            )
            or getattr(
                metadata,
                "output_token_count",
                0,
            )
            or 0
        )

        total_tokens = (
            getattr(
                metadata,
                "total_token_count",
                0,
            )
            or (
                prompt_tokens
                + completion_tokens
            )
        )

        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> ChatResponse:
        plan = create_response_plan(
            message
        )

        models = get_provider_model_order(
            self.provider_name,
            category,
        )

        last_error: Exception | None = None

        for index, model in enumerate(models):
            try:
                response = (
                    await self
                    ._get_client()
                    .aio
                    .models
                    .generate_content(
                        model=model,
                        contents=self._build_contents(
                            message=message,
                            history=history,
                        ),
                        config=self._generation_config(
                            plan,
                            message,
                        ),
                    )
                )

                answer = self._response_text(
                    response
                )

                if not answer:
                    raise GeminiResponseError(
                        "Gemini returned an empty answer."
                    )

                return ChatResponse(
                    answer=answer,
                    provider=self.provider_name,
                    model=model,
                    request_id=getattr(
                        response,
                        "response_id",
                        None,
                    ),
                    usage=self._token_usage(
                        response
                    ),
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "Gemini model attempt failed: "
                    "model=%s type=%s status=%s",
                    model,
                    type(error).__name__,
                    self._status_code(error),
                )

                is_last_model = (
                    index == len(models) - 1
                )

                if (
                    is_last_model
                    or not self._can_try_next_model(
                        error
                    )
                ):
                    raise self._translate_error(
                        error
                    ) from error

        raise ProviderError(
            "No Gemini model produced an answer.",
            provider=self.provider_name,
            code="response",
            retryable=True,
        ) from last_error

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> AsyncIterator[StreamDelta]:
        plan = create_response_plan(
            message
        )

        models = get_provider_model_order(
            self.provider_name,
            category,
        )

        last_error: Exception | None = None

        for index, model in enumerate(models):
            received_content = False

            try:
                stream = (
                    await self
                    ._get_client()
                    .aio
                    .models
                    .generate_content_stream(
                        model=model,
                        contents=self._build_contents(
                            message=message,
                            history=history,
                        ),
                        config=self._generation_config(
                            plan,
                            message,
                        ),
                    )
                )

                async for chunk in stream:
                    content = self._response_text(
                        chunk
                    )

                    if not content:
                        continue

                    received_content = True

                    yield StreamDelta(
                        kind="token",
                        content=content,
                        provider=self.provider_name,
                        model=model,
                    )

                if not received_content:
                    raise GeminiResponseError(
                        "Gemini returned an empty stream."
                    )

                yield StreamDelta(
                    kind="done",
                    provider=self.provider_name,
                    model=model,
                )

                return

            except Exception as error:
                last_error = error

                logger.warning(
                    "Gemini streaming attempt failed: "
                    "model=%s type=%s status=%s "
                    "content_started=%s",
                    model,
                    type(error).__name__,
                    self._status_code(error),
                    received_content,
                )

                is_last_model = (
                    index == len(models) - 1
                )

                if (
                    received_content
                    or is_last_model
                    or not self._can_try_next_model(
                        error
                    )
                ):
                    raise self._translate_error(
                        error
                    ) from error

        raise ProviderError(
            "No Gemini model produced a stream.",
            provider=self.provider_name,
            code="response",
            retryable=True,
        ) from last_error
