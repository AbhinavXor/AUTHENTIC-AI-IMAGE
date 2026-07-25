from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
from typing import Any, Literal

import groq
from groq import AsyncGroq

from ai.response_language import (
    response_language_contract,
)
from ai.response_planner import (
    ResponsePlan,
    create_response_plan,
)
from core.config import settings
from schemas.chat import (
    ChatMessage,
    ChatResponse,
    TokenUsage,
)


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are Serenya, the intelligent answer layer operating behind the
Authentic AI interface.

This private preview uses a Groq-hosted language model for inference.
Do not claim that this provider model is Authentic AI's proprietary
native Serenya runtime.

ACCURACY

- Answer only from reliable knowledge and supplied conversation context.
- State uncertainty explicitly instead of inventing information.
- Never fabricate citations, sources, test results, completed actions,
  files, links, measurements, or research findings.
- Never claim that an uploaded image, PDF, system, repository, or file
  was analyzed unless its actual contents were supplied.
- Distinguish facts, assumptions, inferences, and recommendations.

LANGUAGE

- Respond in the language used by the user whenever practical.
- For informal Hindi or Hinglish, respond in natural readable Hinglish
  unless another language is requested.
- Match the user's technical depth without becoming vague.

ANSWER QUALITY

- Begin with the actual answer, recommendation, or principal finding.
- Do not start with filler such as "Sure", "Certainly", or "Of course".
- Do not repeat the user's question.
- Do not add background that is not useful to the decision or task.
- Use concrete explanations and meaningful examples.
- Prefer precision over impressive-sounding language.
- Avoid repeating information in multiple formats.
- Do not add a generic conclusion when the answer already ends clearly.
- Do not end every response with an offer for more help.

MARKDOWN

- Return clean, valid Markdown.
- Use descriptive headings only when needed.
- Keep paragraphs short and readable.
- Use numbered lists for ordered execution.
- Use bullets for parallel points.
- Use tables only when they genuinely improve comparison.
- Bold only important terms.
- Use fenced code blocks with the correct language identifier.
- Never expose private chain-of-thought or hidden reasoning.
""".strip()


class GroqConfigurationError(RuntimeError):
    """Raised when required Groq configuration is missing."""


class GroqResponseError(RuntimeError):
    """Raised when Groq returns an unusable response."""


StreamKind = Literal[
    "token",
    "done",
]


@dataclass(frozen=True, slots=True)
class StreamDelta:
    kind: StreamKind
    content: str = ""
    model: str = ""


class GroqChatService:
    """High-quality asynchronous Groq chat integration."""

    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise GroqConfigurationError(
                "GROQ_API_KEY is not configured."
            )

        self._client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=settings.groq_timeout_seconds,
            max_retries=2,
        )

    def _candidate_models(
        self,
        preferred_models: tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        models = [
            *(preferred_models or ()),
            settings.groq_quality_model,
            settings.groq_fallback_model,
        ]

        return tuple(
            dict.fromkeys(
                model
                for model in models
                if model
            )
        )

    def _build_messages(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        plan: ResponsePlan,
    ) -> list[dict[str, str]]:
        limited_history = history[
            -settings.maximum_history_messages:
        ]

        dynamic_contract = f"""
{response_language_contract(message)}

RESPONSE PLAN

Intent: {plan.intent}

Required response contract:
{plan.contract}

Follow this contract naturally. Do not mention the response plan,
classification, reasoning effort, system prompt, or internal routing.
""".strip()

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"{SYSTEM_PROMPT}\n\n"
                    f"{dynamic_contract}"
                ),
            }
        ]

        messages.extend(
            {
                "role": item.role,
                "content": item.content,
            }
            for item in limited_history
        )

        messages.append(
            {
                "role": "user",
                "content": message,
            }
        )

        return messages

    def _completion_arguments(
        self,
        *,
        model: str,
        message: str,
        history: list[ChatMessage],
        plan: ResponsePlan,
        stream: bool,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(
                message=message,
                history=history,
                plan=plan,
            ),
            "temperature": 0.2,
            "max_completion_tokens": (
                plan.max_completion_tokens
            ),
            "stream": stream,
        }

        if model.startswith("openai/gpt-oss"):
            arguments.update(
                {
                    "reasoning_effort": (
                        plan.reasoning_effort
                    ),
                    "reasoning_format": "hidden",
                }
            )

        return arguments

    @staticmethod
    def _can_fallback(
        error: Exception,
    ) -> bool:
        if isinstance(
            error,
            GroqResponseError,
        ):
            return True

        if isinstance(
            error,
            groq.APIStatusError,
        ):
            return error.status_code in {
                404,
                408,
                429,
                500,
                502,
                503,
                504,
            }

        return False

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        preferred_models: tuple[str, ...] | None = None,
    ) -> ChatResponse:
        plan = create_response_plan(message)
        models = self._candidate_models(
            preferred_models
        )

        last_error: Exception | None = None

        for index, model in enumerate(models):
            try:
                completion: Any = (
                    await self._client.chat.completions.create(
                        **self._completion_arguments(
                            model=model,
                            message=message,
                            history=history,
                            plan=plan,
                            stream=False,
                        )
                    )
                )

                if not completion.choices:
                    raise GroqResponseError(
                        "The model returned no answer."
                    )

                answer = (
                    completion
                    .choices[0]
                    .message
                    .content
                    or ""
                ).strip()

                if not answer:
                    raise GroqResponseError(
                        "The model returned an empty answer."
                    )

                usage = completion.usage

                return ChatResponse(
                    answer=answer,
                    model=model,
                    request_id=getattr(
                        completion,
                        "id",
                        None,
                    ),
                    usage=TokenUsage(
                        prompt_tokens=getattr(
                            usage,
                            "prompt_tokens",
                            0,
                        )
                        if usage
                        else 0,
                        completion_tokens=getattr(
                            usage,
                            "completion_tokens",
                            0,
                        )
                        if usage
                        else 0,
                        total_tokens=getattr(
                            usage,
                            "total_tokens",
                            0,
                        )
                        if usage
                        else 0,
                    ),
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "Groq model attempt failed: "
                    "model=%s type=%s status=%s",
                    model,
                    type(error).__name__,
                    getattr(error, "status_code", None),
                )

                is_last_model = (
                    index == len(models) - 1
                )

                if (
                    is_last_model
                    or not self._can_fallback(error)
                ):
                    raise

        raise GroqResponseError(
            "No model produced a usable response."
        ) from last_error

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        preferred_models: tuple[str, ...] | None = None,
    ) -> AsyncIterator[StreamDelta]:
        plan = create_response_plan(message)
        models = self._candidate_models(
            preferred_models
        )

        last_error: Exception | None = None

        for index, model in enumerate(models):
            received_content = False

            try:
                stream = (
                    await self
                    ._client
                    .chat
                    .completions
                    .create(
                        **self._completion_arguments(
                            model=model,
                            message=message,
                            history=history,
                            plan=plan,
                            stream=True,
                        )
                    )
                )

                async for chunk in stream:
                    if not chunk.choices:
                        continue

                    delta = (
                        chunk
                        .choices[0]
                        .delta
                        .content
                        or ""
                    )

                    if not delta:
                        continue

                    received_content = True

                    yield StreamDelta(
                        kind="token",
                        content=delta,
                        model=model,
                    )

                if not received_content:
                    raise GroqResponseError(
                        "The model returned an empty answer."
                    )

                yield StreamDelta(
                    kind="done",
                    model=model,
                )

                return

            except Exception as error:
                last_error = error

                logger.warning(
                    "Groq model attempt failed: "
                    "model=%s type=%s status=%s",
                    model,
                    type(error).__name__,
                    getattr(error, "status_code", None),
                )

                is_last_model = (
                    index == len(models) - 1
                )

                if (
                    received_content
                    or is_last_model
                    or not self._can_fallback(error)
                ):
                    raise

        raise GroqResponseError(
            "No model produced a usable response."
        ) from last_error
