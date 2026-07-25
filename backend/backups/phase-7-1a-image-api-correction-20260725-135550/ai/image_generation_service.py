import asyncio
import base64
import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import errors
from PIL import (
    Image,
    UnidentifiedImageError,
)

from core.gemini_settings import (
    gemini_settings,
)
from core.image_generation_settings import (
    image_generation_settings,
)
from schemas.image_generation import (
    ImageGenerationAspectRatio,
    ImageGenerationQuality,
    ImageGenerationSize,
)


logger = logging.getLogger(__name__)


class ImageGenerationConfigurationError(
    RuntimeError
):
    """Raised when image generation is unavailable."""


class ImageGenerationRejectedError(
    RuntimeError
):
    """Raised when a generation request is rejected."""


class ImageGenerationResponseError(
    RuntimeError
):
    """Raised when no safe image is returned."""


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    image_base64: str
    mime_type: str

    width: int
    height: int

    model: str
    request_id: str | None

    content_sha256: str


def _status_code(
    error: Exception,
) -> int | None:
    raw_code = getattr(
        error,
        "code",
        None,
    )

    try:
        return int(
            raw_code
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _decode_output_data(
    raw_data: Any,
) -> bytes:
    if isinstance(
        raw_data,
        str,
    ):
        try:
            return base64.b64decode(
                raw_data,
                validate=True,
            )

        except Exception as error:
            raise ImageGenerationResponseError(
                "The image provider returned "
                "invalid encoded image data."
            ) from error

    if isinstance(
        raw_data,
        (
            bytes,
            bytearray,
        ),
    ):
        byte_data = bytes(
            raw_data
        )

        try:
            with Image.open(
                io.BytesIO(
                    byte_data
                )
            ):
                return byte_data

        except Exception:
            try:
                return base64.b64decode(
                    byte_data,
                    validate=True,
                )

            except Exception as error:
                raise ImageGenerationResponseError(
                    "The image provider returned "
                    "unreadable image data."
                ) from error

    raise ImageGenerationResponseError(
        "The image provider did not return image data."
    )


def _normalize_generated_image(
    image_bytes: bytes,
) -> tuple[
    bytes,
    int,
    int,
]:
    if not image_bytes:
        raise ImageGenerationResponseError(
            "The generated image is empty."
        )

    if (
        len(image_bytes)
        > image_generation_settings
        .maximum_output_bytes
    ):
        raise ImageGenerationResponseError(
            "The generated image exceeds "
            "the output safety limit."
        )

    try:
        with Image.open(
            io.BytesIO(
                image_bytes
            )
        ) as image:
            image.load()

            width, height = (
                image.size
            )

            if (
                width <= 0
                or height <= 0
            ):
                raise ImageGenerationResponseError(
                    "The generated image has "
                    "invalid dimensions."
                )

            if (
                width * height
                > image_generation_settings
                .maximum_image_pixels
            ):
                raise ImageGenerationResponseError(
                    "The generated image exceeds "
                    "the pixel safety limit."
                )

            if image.mode not in {
                "RGB",
                "RGBA",
            }:
                if (
                    "A"
                    in image.getbands()
                ):
                    normalized = (
                        image.convert(
                            "RGBA"
                        )
                    )

                else:
                    normalized = (
                        image.convert(
                            "RGB"
                        )
                    )

            else:
                normalized = (
                    image.copy()
                )

    except (
        UnidentifiedImageError,
        OSError,
    ) as error:
        raise ImageGenerationResponseError(
            "The image provider returned "
            "an invalid image."
        ) from error

    output = io.BytesIO()

    normalized.save(
        output,
        format="PNG",
        optimize=True,
    )

    normalized.close()

    normalized_bytes = (
        output.getvalue()
    )

    if (
        len(normalized_bytes)
        > image_generation_settings
        .maximum_output_bytes
    ):
        raise ImageGenerationResponseError(
            "The normalized image exceeds "
            "the output safety limit."
        )

    return (
        normalized_bytes,
        width,
        height,
    )


class ImageGenerationService:
    provider_name = "gemini"

    def __init__(self) -> None:
        self._client: (
            genai.Client
            | None
        ) = None

    def _get_client(
        self,
    ) -> genai.Client:
        if not gemini_settings.api_key:
            raise ImageGenerationConfigurationError(
                "Gemini image generation "
                "is not configured."
            )

        if self._client is None:
            self._client = genai.Client(
                api_key=(
                    gemini_settings
                    .api_key
                ),
            )

        if not hasattr(
            self._client,
            "interactions",
        ):
            raise ImageGenerationConfigurationError(
                "The installed Google Gen AI SDK "
                "does not support image interactions."
            )

        return self._client

    @staticmethod
    def _model_candidates(
        quality: (
            ImageGenerationQuality
        ),
    ) -> tuple[str, ...]:
        if quality == "quality":
            return (
                image_generation_settings
                .quality_model,

                image_generation_settings
                .fast_model,
            )

        return (
            image_generation_settings
            .fast_model,
        )

    @staticmethod
    def _build_prompt(
        prompt: str,
    ) -> str:
        return f"""
Create exactly one finished image.

Follow the user's creative request precisely.

Do not include explanatory text outside the image.
Do not add logos, signatures, labels, captions or written
text unless the user explicitly requests them.

Preserve requested composition, visual hierarchy, subject,
lighting, environment, camera perspective, material,
typography and style.

USER CREATIVE REQUEST

{prompt}
""".strip()

    @staticmethod
    def _create_interaction(
        *,
        client: genai.Client,
        model: str,
        prompt: str,
        aspect_ratio: str,
        image_size: str,
    ) -> Any:
        return (
            client
            .interactions
            .create(
                model=model,
                input=prompt,
                response_format={
                    "type": "image",
                    "mime_type": (
                        "image/png"
                    ),
                    "aspect_ratio": (
                        aspect_ratio
                    ),
                    "image_size": (
                        image_size
                    ),
                },
            )
        )

    async def generate(
        self,
        *,
        prompt: str,
        quality: (
            ImageGenerationQuality
        ),
        aspect_ratio: (
            ImageGenerationAspectRatio
        ),
        image_size: (
            ImageGenerationSize
        ),
    ) -> GeneratedImage:
        normalized_prompt = (
            prompt.strip()
        )

        if not normalized_prompt:
            raise ImageGenerationRejectedError(
                "Image prompt cannot be empty."
            )

        if (
            len(normalized_prompt)
            > image_generation_settings
            .maximum_prompt_characters
        ):
            raise ImageGenerationRejectedError(
                "Image prompt is too long."
            )

        if (
            aspect_ratio
            not in image_generation_settings
            .allowed_aspect_ratios
        ):
            raise ImageGenerationRejectedError(
                "Unsupported image aspect ratio."
            )

        if (
            image_size
            not in image_generation_settings
            .allowed_image_sizes
        ):
            raise ImageGenerationRejectedError(
                "Unsupported image size."
            )

        request_prompt = (
            self._build_prompt(
                normalized_prompt
            )
        )

        client = self._get_client()

        last_error: (
            Exception
            | None
        ) = None

        for model in (
            self._model_candidates(
                quality
            )
        ):
            try:
                interaction = (
                    await asyncio.to_thread(
                        self._create_interaction,
                        client=client,
                        model=model,
                        prompt=(
                            request_prompt
                        ),
                        aspect_ratio=(
                            aspect_ratio
                        ),
                        image_size=(
                            image_size
                        ),
                    )
                )

                output_image = getattr(
                    interaction,
                    "output_image",
                    None,
                )

                if output_image is None:
                    raise ImageGenerationResponseError(
                        "The image model did not "
                        "produce an image."
                    )

                raw_data = getattr(
                    output_image,
                    "data",
                    None,
                )

                decoded_bytes = (
                    _decode_output_data(
                        raw_data
                    )
                )

                (
                    normalized_bytes,
                    width,
                    height,
                ) = (
                    _normalize_generated_image(
                        decoded_bytes
                    )
                )

                encoded_image = (
                    base64.b64encode(
                        normalized_bytes
                    ).decode(
                        "ascii"
                    )
                )

                content_sha256 = (
                    hashlib.sha256(
                        normalized_bytes
                    ).hexdigest()
                )

                request_id = (
                    getattr(
                        interaction,
                        "id",
                        None,
                    )
                    or getattr(
                        interaction,
                        "interaction_id",
                        None,
                    )
                )

                return GeneratedImage(
                    image_base64=(
                        encoded_image
                    ),
                    mime_type=(
                        "image/png"
                    ),
                    width=width,
                    height=height,
                    model=model,
                    request_id=(
                        request_id
                    ),
                    content_sha256=(
                        content_sha256
                    ),
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "Image generation failed: "
                    "model=%s type=%s status=%s",
                    model,
                    type(error).__name__,
                    _status_code(
                        error
                    ),
                )

                if isinstance(
                    error,
                    errors.APIError,
                ):
                    status_code = (
                        _status_code(
                            error
                        )
                    )

                    if status_code in {
                        401,
                        403,
                    }:
                        raise ImageGenerationConfigurationError(
                            "Gemini image credentials "
                            "are invalid or unauthorized."
                        ) from error

                    if status_code in {
                        400,
                        422,
                    }:
                        raise ImageGenerationRejectedError(
                            "The image provider rejected "
                            "this generation request."
                        ) from error

                    if status_code not in {
                        404,
                        408,
                        429,
                        500,
                        502,
                        503,
                        504,
                    }:
                        raise ImageGenerationResponseError(
                            "The image provider could "
                            "not complete the request."
                        ) from error

                elif isinstance(
                    error,
                    ImageGenerationConfigurationError,
                ):
                    raise

                elif isinstance(
                    error,
                    ImageGenerationRejectedError,
                ):
                    raise

                elif not isinstance(
                    error,
                    ImageGenerationResponseError,
                ):
                    raise ImageGenerationResponseError(
                        "Image generation could "
                        "not be completed."
                    ) from error

        raise ImageGenerationResponseError(
            "No configured image model produced "
            "a usable image."
        ) from last_error
