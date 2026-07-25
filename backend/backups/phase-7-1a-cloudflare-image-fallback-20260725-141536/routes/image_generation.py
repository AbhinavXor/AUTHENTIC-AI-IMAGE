from functools import lru_cache

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from ai.image_generation_service import (
    ImageGenerationConfigurationError,
    ImageGenerationRejectedError,
    ImageGenerationResponseError,
    ImageGenerationService,
)
from schemas.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)


router = APIRouter(
    prefix="/images",
    tags=["images"],
)


@lru_cache(maxsize=1)
def get_image_generation_service(
) -> ImageGenerationService:
    return ImageGenerationService()


@router.post(
    "/generate",
    response_model=(
        ImageGenerationResponse
    ),
)
async def generate_image(
    request: ImageGenerationRequest,
) -> ImageGenerationResponse:
    try:
        result = (
            await get_image_generation_service()
            .generate(
                prompt=request.prompt,
                quality=request.quality,
                aspect_ratio=(
                    request.aspect_ratio
                ),
                image_size=(
                    request.image_size
                ),
            )
        )

    except ImageGenerationRejectedError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except ImageGenerationConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(error),
        ) from error

    except ImageGenerationResponseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(error),
        ) from error

    return ImageGenerationResponse(
        image_base64=(
            result.image_base64
        ),
        mime_type=(
            result.mime_type
        ),

        width=result.width,
        height=result.height,

        provider="gemini",
        model=result.model,

        prompt=request.prompt.strip(),
        quality=request.quality,

        aspect_ratio=(
            request.aspect_ratio
        ),
        image_size=(
            request.image_size
        ),

        content_sha256=(
            result.content_sha256
        ),

        request_id=(
            result.request_id
        ),
    )
