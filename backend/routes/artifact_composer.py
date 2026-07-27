from __future__ import annotations

import asyncio

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from ai.model_router import ModelRouter
from ai.provider_adapter import ProviderError
from artifacts.composer import (
    ArtifactCompositionError,
    compose_artifact_draft,
)
from artifacts.engine import (
    ArtifactGenerationError,
    ArtifactValidationError,
)
from artifacts.parser import (
    parse_artifact_document,
)
from artifacts.storage import (
    ArtifactStorageError,
    StoredArtifact,
)
from routes.artifacts import (
    get_artifact_storage,
)
from routes.chat import (
    get_model_router,
)
from schemas.artifact_composer import (
    ArtifactComposeRequest,
    ArtifactComposeResponse,
)


router = APIRouter(
    prefix="/artifacts",
    tags=["artifacts"],
)


def _provider_error_message(
    error: ProviderError,
) -> str:
    messages = {
        "configuration": (
            "No AI provider is configured "
            "for artifact composition."
        ),
        "authentication": (
            "AI provider credentials are invalid."
        ),
        "billing": (
            "The selected AI provider has no "
            "available credits or billing access."
        ),
        "rate_limit": (
            "Available AI quota or rate limit "
            "was reached."
        ),
        "timeout": (
            "The artifact composition service "
            "took too long."
        ),
        "connection": (
            "Could not connect to the AI "
            "composition service."
        ),
        "request": (
            "The AI provider rejected the "
            "artifact request."
        ),
        "response": (
            "The AI provider returned an "
            "unusable artifact draft."
        ),
        "availability": (
            "All configured AI providers are "
            "temporarily unavailable."
        ),
        "unknown": (
            "The artifact draft could not "
            "be composed."
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
        return (
            status.HTTP_429_TOO_MANY_REQUESTS
        )

    if error.code == "timeout":
        return (
            status.HTTP_504_GATEWAY_TIMEOUT
        )

    if error.code in {
        "configuration",
        "authentication",
        "billing",
        "availability",
    }:
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return status.HTTP_502_BAD_GATEWAY


def _compose_response(
    *,
    stored: StoredArtifact,
    provider: str,
    model: str,
    request_id: str | None,
    draft_character_count: int,
) -> ArtifactComposeResponse:
    return ArtifactComposeResponse(
        artifact_id=stored.artifact_id,
        filename=stored.filename,
        format=stored.format,
        media_type=stored.media_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        created_at=stored.created_at,
        expires_at=stored.expires_at,
        download_url=(
            f"/api/v1/artifacts/"
            f"{stored.artifact_id}/download"
        ),
        provider=provider,
        model=model,
        request_id=request_id,
        draft_character_count=(
            draft_character_count
        ),
        composition_mode=(
            "ai_prompt_to_artifact"
        ),
    )


@router.post(
    "/compose",
    response_model=ArtifactComposeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def compose_and_generate_artifact(
    request: ArtifactComposeRequest,
) -> ArtifactComposeResponse:
    model_router: ModelRouter = (
        get_model_router()
    )

    try:
        draft = await compose_artifact_draft(
            request,
            model_router=model_router,
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

    except ArtifactCompositionError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(error),
        ) from error

    try:
        artifact = parse_artifact_document(
            draft.content,
            title=request.title,
            subtitle=request.subtitle,
            author=request.author,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    storage = get_artifact_storage()

    try:
        await asyncio.to_thread(
            storage.cleanup_expired
        )

        stored = await asyncio.to_thread(
            storage.create,
            artifact,
            format=request.format,
            filename=request.filename,
        )

    except ArtifactValidationError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except (
        ArtifactGenerationError,
        ArtifactStorageError,
    ) as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The composed artifact could "
                "not be generated."
            ),
        ) from error

    return _compose_response(
        stored=stored,
        provider=draft.provider,
        model=draft.model,
        request_id=draft.request_id,
        draft_character_count=len(
            draft.content
        ),
    )