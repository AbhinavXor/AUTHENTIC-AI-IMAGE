from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


ImageGenerationQuality = Literal[
    "fast",
    "quality",
]


ImageGenerationSize = Literal[
    "1K",
    "2K",
]


ImageGenerationAspectRatio = Literal[
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "5:4",
    "4:5",
    "21:9",
]


class ImageGenerationRequest(
    BaseModel
):
    prompt: str = Field(
        min_length=1,
        max_length=4_000,
    )

    quality: (
        ImageGenerationQuality
    ) = "fast"

    aspect_ratio: (
        ImageGenerationAspectRatio
    ) = "1:1"

    image_size: (
        ImageGenerationSize
    ) = "1K"


class ImageGenerationResponse(
    BaseModel
):
    image_base64: str
    mime_type: str

    width: int
    height: int

    provider: str
    model: str

    prompt: str
    quality: (
        ImageGenerationQuality
    )

    aspect_ratio: (
        ImageGenerationAspectRatio
    )

    image_size: (
        ImageGenerationSize
    )

    content_sha256: str

    request_id: str | None = None
