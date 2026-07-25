import warnings
from functools import lru_cache
from io import BytesIO
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from PIL import (
    Image,
    UnidentifiedImageError,
)

from ai.vision_service import (
    VisionConfigurationError,
    VisionResponseError,
    VisionService,
)
from core.vision_settings import vision_settings
from schemas.vision import VisionResponse


router = APIRouter(
    prefix="/vision",
    tags=["vision"],
)


_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@lru_cache(maxsize=1)
def get_vision_service() -> VisionService:
    return VisionService()


def _validate_prompt(
    prompt: str,
) -> str:
    normalized = prompt.strip()

    if not normalized:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Image prompt cannot be empty.",
        )

    if (
        len(normalized)
        > vision_settings.maximum_prompt_characters
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Image prompt is too long."
            ),
        )

    return normalized


def _inspect_image(
    image_bytes: bytes,
    declared_mime_type: str,
) -> tuple[
    str,
    str,
    int,
    int,
]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(
                BytesIO(image_bytes)
            ) as image:
                image.verify()

            with Image.open(
                BytesIO(image_bytes)
            ) as image:
                image_format = (
                    image.format
                    or ""
                ).upper()

                width, height = image.size

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "The uploaded file is not a valid "
                "supported image."
            ),
        ) from error

    detected_mime_type = (
        _FORMAT_TO_MIME.get(
            image_format
        )
    )

    if not detected_mime_type:
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Only JPEG, PNG, and WEBP "
                "images are supported."
            ),
        )

    if detected_mime_type != declared_mime_type:
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "The uploaded file content does not "
                "match its declared MIME type."
            ),
        )

    if width < 1 or height < 1:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Image dimensions are invalid.",
        )

    if (
        width * height
        > vision_settings.maximum_image_pixels
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "Image resolution exceeds the "
                "allowed pixel limit."
            ),
        )

    return (
        image_format,
        detected_mime_type,
        width,
        height,
    )


@router.post(
    "/analyze",
    response_model=VisionResponse,
)
async def analyze_image(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "JPEG, PNG, or WEBP image"
            )
        ),
    ],
    prompt: Annotated[
        str,
        Form(),
    ] = (
        "Describe this image accurately and "
        "explain the important visible details."
    ),
) -> VisionResponse:
    declared_mime_type = (
        file.content_type
        or ""
    ).lower()

    if (
        declared_mime_type
        not in vision_settings.allowed_mime_types
    ):
        await file.close()

        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Only JPEG, PNG, and WEBP "
                "images are supported."
            ),
        )

    try:
        image_bytes = await file.read(
            vision_settings.maximum_image_bytes
            + 1
        )

    finally:
        await file.close()

    if not image_bytes:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Uploaded image is empty.",
        )

    if (
        len(image_bytes)
        > vision_settings.maximum_image_bytes
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "Image exceeds the 10 MB limit."
            ),
        )

    normalized_prompt = _validate_prompt(
        prompt
    )

    (
        image_format,
        detected_mime_type,
        width,
        height,
    ) = _inspect_image(
        image_bytes,
        declared_mime_type,
    )

    try:
        (
            answer,
            model,
            request_id,
            usage,
        ) = await get_vision_service().analyze(
            image_bytes=image_bytes,
            mime_type=detected_mime_type,
            prompt=normalized_prompt,
        )

    except VisionConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(error),
        ) from error

    except VisionResponseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(error),
        ) from error

    return VisionResponse(
        answer=answer,
        provider="gemini",
        model=model,
        filename=file.filename or "image",
        mime_type=detected_mime_type,
        image_format=image_format,
        width=width,
        height=height,
        size_bytes=len(image_bytes),
        request_id=request_id,
        usage=usage,
    )
