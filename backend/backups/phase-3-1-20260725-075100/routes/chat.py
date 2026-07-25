import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import groq
from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse

from ai.groq_service import (
    GroqChatService,
    GroqConfigurationError,
    GroqResponseError,
)
from schemas.chat import (
    ChatRequest,
    ChatResponse,
)


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@lru_cache(maxsize=1)
def get_groq_service() -> GroqChatService:
    return GroqChatService()


def _provider_error_message(
    error: Exception,
) -> str:
    if isinstance(
        error,
        groq.RateLimitError,
    ):
        return (
            "The AI service rate limit was reached. "
            "Please wait briefly and try again."
        )

    if isinstance(
        error,
        groq.APITimeoutError,
    ):
        return (
            "The AI service took too long to respond."
        )

    if isinstance(
        error,
        groq.APIConnectionError,
    ):
        return (
            "The backend could not connect to "
            "the AI service."
        )

    if isinstance(
        error,
        groq.APIStatusError,
    ):
        if error.status_code in {
            401,
            403,
        }:
            return (
                "The AI service credentials are invalid "
                "or do not have permission."
            )

        return (
            "The AI provider rejected the request."
        )

    if isinstance(
        error,
        GroqResponseError,
    ):
        return str(error)

    return (
        "The AI response could not be completed."
    )


def _sse_event(
    event: str,
    payload: dict[str, Any],
) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
    )

    return (
        f"event: {event}\n"
        f"data: {serialized}\n\n"
    )


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def create_chat_completion(
    payload: ChatRequest,
) -> ChatResponse:
    try:
        service = get_groq_service()

        return await service.answer(
            message=payload.message,
            history=payload.history,
        )

    except GroqConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Groq is not configured "
                "on the backend."
            ),
        ) from error

    except groq.RateLimitError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=_provider_error_message(error),
        ) from error

    except groq.APITimeoutError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_504_GATEWAY_TIMEOUT
            ),
            detail=_provider_error_message(error),
        ) from error

    except (
        groq.APIConnectionError,
        groq.APIStatusError,
        GroqResponseError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=_provider_error_message(error),
        ) from error


@router.post("/stream")
async def create_streaming_chat_completion(
    payload: ChatRequest,
) -> StreamingResponse:
    try:
        service = get_groq_service()

    except GroqConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Groq is not configured "
                "on the backend."
            ),
        ) from error

    async def generate_events() -> AsyncIterator[str]:
        try:
            async for delta in service.stream_answer(
                message=payload.message,
                history=payload.history,
            ):
                if delta.kind == "token":
                    yield _sse_event(
                        "token",
                        {
                            "content": delta.content,
                        },
                    )

                elif delta.kind == "done":
                    yield _sse_event(
                        "done",
                        {
                            "model": delta.model,
                        },
                    )

        except (
            groq.RateLimitError,
            groq.APITimeoutError,
            groq.APIConnectionError,
            groq.APIStatusError,
            GroqResponseError,
        ) as error:
            yield _sse_event(
                "error",
                {
                    "detail": (
                        _provider_error_message(
                            error
                        )
                    ),
                },
            )

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
