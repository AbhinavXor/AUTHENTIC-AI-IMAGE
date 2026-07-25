import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse

from ai.model_router import ModelRouter
from ai.provider_adapter import ProviderError
from schemas.chat import (
    ChatRequest,
    ChatResponse,
)


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@lru_cache(maxsize=1)
def get_model_router() -> ModelRouter:
    return ModelRouter()


def _provider_error_message(
    error: ProviderError,
) -> str:
    messages = {
        "configuration": (
            "No AI provider is configured "
            "on the backend."
        ),
        "authentication": (
            "The AI provider credentials are invalid "
            "or do not have permission."
        ),
        "rate_limit": (
            "The available AI service quota or "
            "rate limit was reached."
        ),
        "timeout": (
            "The AI service took too long to respond."
        ),
        "connection": (
            "The backend could not connect "
            "to the AI service."
        ),
        "request": (
            "The AI provider rejected the request."
        ),
        "response": (
            "The AI provider returned "
            "an unusable response."
        ),
        "availability": (
            "All configured AI providers are "
            "temporarily unavailable."
        ),
        "unknown": (
            "The AI response could not be completed."
        ),
    }

    return messages.get(
        error.code,
        messages["unknown"],
    )


def _provider_http_status(
    error: ProviderError,
) -> int:
    if error.code == "rate_limit":
        return status.HTTP_429_TOO_MANY_REQUESTS

    if error.code == "timeout":
        return status.HTTP_504_GATEWAY_TIMEOUT

    if error.code in {
        "configuration",
        "authentication",
        "availability",
    }:
        return status.HTTP_503_SERVICE_UNAVAILABLE

    return status.HTTP_502_BAD_GATEWAY


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
        model_router = get_model_router()

        return await model_router.answer(
            message=payload.message,
            history=payload.history,
        )

    except ProviderError as error:
        raise HTTPException(
            status_code=_provider_http_status(
                error
            ),
            detail=_provider_error_message(
                error
            ),
        ) from error


@router.post("/stream")
async def create_streaming_chat_completion(
    payload: ChatRequest,
) -> StreamingResponse:
    model_router = get_model_router()

    if not model_router.is_configured():
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "No AI provider is configured "
                "on the backend."
            ),
        )

    async def generate_events() -> AsyncIterator[str]:
        try:
            async for delta in (
                model_router.stream_answer(
                    message=payload.message,
                    history=payload.history,
                )
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
                            "provider": delta.provider,
                            "model": delta.model,
                        },
                    )

        except ProviderError as error:
            yield _sse_event(
                "error",
                {
                    "detail": (
                        _provider_error_message(
                            error
                        )
                    ),
                    "provider": error.provider,
                    "code": error.code,
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
