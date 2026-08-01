from __future__ import annotations

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)

from ai.provider_adapter import ProviderError
from artifacts.composer import ArtifactCompositionError
from artifacts.engine import (
    ArtifactGenerationError,
    ArtifactValidationError,
)
from artifacts.repository import ArtifactRepositoryError
from artifacts.responses import artifact_response_payload
from core.artifact_operation_rate_limit import (
    ArtifactOperationRateLimitError,
    artifact_operation_rate_limiter,
    resolve_artifact_operation_client_key,
)
from artifacts.storage import ArtifactStorageError
from routes.artifacts import (
    _IDEMPOTENCY_KEY_HEADER,
    _with_idempotency_key,
    get_artifact_lifecycle_service,
)
from schemas.artifact_composer import (
    ArtifactComposeRequest,
    ArtifactComposeResponse,
)

router = APIRouter(
    prefix="/artifacts",
    tags=["artifacts"],
)


def _provider_error_message(error: ProviderError) -> str:
    return {
        "configuration": "No AI provider is configured for artifact composition.",
        "authentication": "AI provider credentials are invalid.",
        "billing": "The selected AI provider has no available credits or billing access.",
        "rate_limit": "Available AI quota or rate limit was reached.",
        "timeout": "The artifact composition service took too long.",
        "connection": "Could not connect to the AI composition service.",
        "request": "The AI provider rejected the artifact request.",
        "response": "The AI provider returned an unusable artifact draft.",
        "availability": "All configured AI providers are temporarily unavailable.",
        "unknown": "The artifact draft could not be composed.",
    }.get(error.code, "The artifact draft could not be composed.")


def _provider_http_status(error: ProviderError) -> int:
    if error.code == "rate_limit":
        return status.HTTP_429_TOO_MANY_REQUESTS
    if error.code == "timeout":
        return status.HTTP_504_GATEWAY_TIMEOUT
    if error.code in {
        "configuration",
        "authentication",
        "billing",
        "availability",
    }:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_502_BAD_GATEWAY


@router.post(
    "/compose",
    response_model=ArtifactComposeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def compose_and_generate_artifact(
    request: ArtifactComposeRequest,
    response: Response,
    client_request: Request,
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactComposeResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    try:
        artifact_operation_rate_limiter.check(
            resolve_artifact_operation_client_key(client_request)
        )
    except ArtifactOperationRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many artifact operations were requested. Try again later.",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error

    try:
        result = await get_artifact_lifecycle_service().compose_and_create(
            request
        )
    except ProviderError as error:
        raise HTTPException(
            status_code=_provider_http_status(error),
            detail=_provider_error_message(error),
        ) from error
    except ArtifactCompositionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (ArtifactValidationError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (
        ArtifactGenerationError,
        ArtifactStorageError,
        ArtifactRepositoryError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The composed artifact could not be generated.",
        ) from error

    token = result.view.access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Artifact access token was not created.",
        )

    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return ArtifactComposeResponse(
        **artifact_response_payload(
            result.view,
            access_token=token,
        ),
        provider=result.provider or "unknown",
        model=result.model or "unknown",
        request_id=result.request_id,
        draft_character_count=result.draft_character_count,
        composition_mode="ai_prompt_to_artifact",
    )
