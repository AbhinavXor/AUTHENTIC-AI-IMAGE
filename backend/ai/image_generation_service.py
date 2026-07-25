import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)

from google import genai
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
    """Raised when no image provider is configured."""


class ImageGenerationRejectedError(
    RuntimeError
):
    """Raised when the request itself is invalid."""


class ImageGenerationQuotaError(
    RuntimeError
):
    """Raised when all configured providers have no capacity."""


class ImageGenerationResponseError(
    RuntimeError
):
    """Raised when no provider returns a usable image."""


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    image_base64: str
    mime_type: str

    width: int
    height: int

    provider: str
    model: str

    request_id: str | None
    content_sha256: str


def _status_code(
    error: Exception,
) -> int | None:
    for attribute in (
        "code",
        "status_code",
        "status",
    ):
        raw_value = getattr(
            error,
            attribute,
            None,
        )

        try:
            value = int(
                raw_value
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if 100 <= value <= 599:
            return value

    message = str(error)

    match = re.search(
        (
            r"(?:Error\s+code|HTTP|status)"
            r"\s*[:=]?\s*(\d{3})"
        ),
        message,
        flags=re.IGNORECASE,
    )

    if match:
        return int(
            match.group(1)
        )

    if (
        "too_many_requests"
        in message.lower()
        or "quota exceeded"
        in message.lower()
    ):
        return 429

    return None


def _first_environment_value(
    *names: str,
) -> str:
    for name in names:
        value = (
            os.getenv(name)
            or ""
        ).strip()

        if value:
            return value

    return ""


def _cloudflare_account_id(
) -> str:
    return _first_environment_value(
        "CLOUDFLARE_ACCOUNT_ID",
        "CF_ACCOUNT_ID",
        "CLOUDFLARE_AI_ACCOUNT_ID",
        "CLOUDFLARE_WORKERS_AI_ACCOUNT_ID",
    )


def _cloudflare_api_token(
) -> str:
    return _first_environment_value(
        "CLOUDFLARE_API_TOKEN",
        "CF_API_TOKEN",
        "CLOUDFLARE_AI_TOKEN",
        "CLOUDFLARE_WORKERS_AI_TOKEN",
        "CLOUDFLARE_AUTH_TOKEN",
        "CLOUDFLARE_TOKEN",
    )


def _decode_base64_image(
    encoded_data: Any,
) -> bytes:
    if isinstance(
        encoded_data,
        bytes,
    ):
        encoded_bytes = encoded_data

    elif isinstance(
        encoded_data,
        str,
    ):
        encoded_bytes = (
            encoded_data.encode(
                "ascii",
                errors="strict",
            )
        )

    else:
        raise ImageGenerationResponseError(
            "The provider returned invalid image data."
        )

    try:
        return base64.b64decode(
            encoded_bytes,
            validate=True,
        )

    except Exception as error:
        raise ImageGenerationResponseError(
            "The provider returned invalid Base64 image data."
        ) from error


def _decode_gemini_image(
    raw_data: Any,
) -> bytes:
    if isinstance(
        raw_data,
        str,
    ):
        return _decode_base64_image(
            raw_data
        )

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
            return _decode_base64_image(
                byte_data
            )

    raise ImageGenerationResponseError(
        "Gemini did not return readable image data."
    )


def _target_dimensions(
    *,
    aspect_ratio: str,
    image_size: str,
) -> tuple[int, int]:
    width_part, height_part = (
        aspect_ratio.split(
            ":",
            maxsplit=1,
        )
    )

    ratio = (
        int(width_part)
        / int(height_part)
    )

    longest_edge = (
        2_048
        if image_size == "2K"
        else 1_024
    )

    if ratio >= 1:
        width = longest_edge
        height = max(
            1,
            round(
                longest_edge
                / ratio
            ),
        )

    else:
        height = longest_edge
        width = max(
            1,
            round(
                longest_edge
                * ratio
            ),
        )

    return width, height


def _normalize_generated_image(
    *,
    image_bytes: bytes,
    aspect_ratio: str,
    image_size: str,
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
            "The generated image exceeds the output safety limit."
        )

    try:
        with Image.open(
            io.BytesIO(
                image_bytes
            )
        ) as opened_image:
            opened_image.load()

            if (
                opened_image.width <= 0
                or opened_image.height <= 0
            ):
                raise ImageGenerationResponseError(
                    "The generated image has invalid dimensions."
                )

            if (
                opened_image.width
                * opened_image.height
                > image_generation_settings
                .maximum_image_pixels
            ):
                raise ImageGenerationResponseError(
                    "The generated image exceeds the pixel safety limit."
                )

            image = opened_image.convert(
                "RGBA"
                if "A"
                in opened_image.getbands()
                else "RGB"
            )

    except (
        UnidentifiedImageError,
        OSError,
    ) as error:
        raise ImageGenerationResponseError(
            "The provider returned an invalid image."
        ) from error

    target_width, target_height = (
        _target_dimensions(
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    )

    source_ratio = (
        image.width
        / image.height
    )

    target_ratio = (
        target_width
        / target_height
    )

    if abs(
        source_ratio
        - target_ratio
    ) > 0.01:
        if source_ratio > target_ratio:
            crop_width = round(
                image.height
                * target_ratio
            )

            left = max(
                0,
                (
                    image.width
                    - crop_width
                )
                // 2,
            )

            image = image.crop(
                (
                    left,
                    0,
                    left + crop_width,
                    image.height,
                )
            )

        else:
            crop_height = round(
                image.width
                / target_ratio
            )

            top = max(
                0,
                (
                    image.height
                    - crop_height
                )
                // 2,
            )

            image = image.crop(
                (
                    0,
                    top,
                    image.width,
                    top + crop_height,
                )
            )

    if image.size != (
        target_width,
        target_height,
    ):
        image = image.resize(
            (
                target_width,
                target_height,
            ),
            Image.Resampling.LANCZOS,
        )

    output = io.BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    image.close()

    normalized_bytes = (
        output.getvalue()
    )

    if (
        len(normalized_bytes)
        > image_generation_settings
        .maximum_output_bytes
    ):
        raise ImageGenerationResponseError(
            "The normalized image exceeds the output safety limit."
        )

    return (
        normalized_bytes,
        target_width,
        target_height,
    )


def _build_generation_prompt(
    prompt: str,
    aspect_ratio: str,
) -> str:
    return f"""
Create exactly one finished image.

Follow the creative request precisely.
Compose the scene for a {aspect_ratio} aspect ratio.

Do not include explanatory text outside the image.
Do not add logos, signatures, captions, labels or written
text unless the user explicitly requests them.

Preserve requested composition, visual hierarchy, subject,
lighting, environment, perspective, materials and style.

USER CREATIVE REQUEST

{prompt}
""".strip()


def _cloudflare_generate_sync(
    *,
    prompt: str,
    aspect_ratio: str,
    image_size: str,
) -> GeneratedImage:
    account_id = (
        _cloudflare_account_id()
    )

    api_token = (
        _cloudflare_api_token()
    )

    if not account_id or not api_token:
        raise ImageGenerationConfigurationError(
            "Cloudflare image fallback is not configured."
        )

    model = (
        image_generation_settings
        .cloudflare_model
    )

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{model}"
    )

    cloudflare_prompt = (
        _build_generation_prompt(
            prompt,
            aspect_ratio,
        )
        [
            :image_generation_settings
            .maximum_cloudflare_prompt_characters
        ]
    )

    request_body = json.dumps(
        {
            "prompt": cloudflare_prompt,
            "steps": 4,
            "seed": random.randint(
                1,
                2_147_483_647,
            ),
        }
    ).encode(
        "utf-8"
    )

    request = Request(
        endpoint,
        data=request_body,
        headers={
            "Authorization": (
                f"Bearer {api_token}"
            ),
            "Content-Type": (
                "application/json"
            ),
            "Accept": (
                "application/json"
            ),
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=(
                image_generation_settings
                .cloudflare_timeout_seconds
            ),
        ) as response:
            response_bytes = (
                response.read()
            )

    except HTTPError as error:
        error_body = (
            error.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        logger.warning(
            "Cloudflare image request failed: "
            "status=%s message=%s",
            error.code,
            error_body[:1_000],
        )

        if error.code == 429:
            raise ImageGenerationQuotaError(
                "Cloudflare image capacity is temporarily exhausted."
            ) from error

        if error.code in {
            401,
            403,
        }:
            raise ImageGenerationConfigurationError(
                "Cloudflare image credentials are unauthorized."
            ) from error

        if error.code in {
            400,
            422,
        }:
            raise ImageGenerationRejectedError(
                "Cloudflare rejected this image request."
            ) from error

        raise ImageGenerationResponseError(
            "Cloudflare could not complete image generation."
        ) from error

    except URLError as error:
        raise ImageGenerationResponseError(
            "Cloudflare image service could not be reached."
        ) from error

    try:
        payload = json.loads(
            response_bytes
            .decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise ImageGenerationResponseError(
            "Cloudflare returned an invalid response."
        ) from error

    if (
        isinstance(
            payload,
            dict,
        )
        and payload.get(
            "success"
        ) is False
    ):
        raise ImageGenerationResponseError(
            "Cloudflare reported an unsuccessful image request."
        )

    result = (
        payload.get(
            "result",
            payload,
        )
        if isinstance(
            payload,
            dict,
        )
        else None
    )

    if not isinstance(
        result,
        dict,
    ):
        raise ImageGenerationResponseError(
            "Cloudflare response did not contain an image result."
        )

    encoded_image = (
        result.get(
            "image"
        )
    )

    image_bytes = (
        _decode_base64_image(
            encoded_image
        )
    )

    (
        normalized_bytes,
        width,
        height,
    ) = (
        _normalize_generated_image(
            image_bytes=image_bytes,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    )

    return GeneratedImage(
        image_base64=(
            base64.b64encode(
                normalized_bytes
            ).decode(
                "ascii"
            )
        ),
        mime_type="image/png",
        width=width,
        height=height,
        provider="cloudflare",
        model=model,
        request_id=None,
        content_sha256=(
            hashlib.sha256(
                normalized_bytes
            ).hexdigest()
        ),
    )


class ImageGenerationService:
    def __init__(self) -> None:
        self._gemini_client: (
            genai.Client
            | None
        ) = None

    def _get_gemini_client(
        self,
    ) -> genai.Client:
        if not gemini_settings.api_key:
            raise ImageGenerationConfigurationError(
                "Gemini image generation is not configured."
            )

        if self._gemini_client is None:
            self._gemini_client = (
                genai.Client(
                    api_key=(
                        gemini_settings
                        .api_key
                    ),
                )
            )

        if not hasattr(
            self._gemini_client,
            "interactions",
        ):
            raise ImageGenerationConfigurationError(
                "The installed Google Gen AI SDK "
                "does not support image interactions."
            )

        return self._gemini_client

    @staticmethod
    def _model_candidates(
        quality: ImageGenerationQuality,
    ) -> tuple[str, ...]:
        candidates = (
            image_generation_settings
            .gemini_quality_models
            if quality == "quality"
            else image_generation_settings
            .gemini_fast_models
        )

        return tuple(
            dict.fromkeys(
                model
                for model in candidates
                if model
            )
        )

    @staticmethod
    def _gemini_generate_sync(
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
                    "aspect_ratio": (
                        aspect_ratio
                    ),
                    "image_size": (
                        image_size
                    ),
                },
            )
        )

    async def _generate_with_gemini(
        self,
        *,
        prompt: str,
        quality: ImageGenerationQuality,
        aspect_ratio: str,
        image_size: str,
    ) -> GeneratedImage:
        client = (
            self._get_gemini_client()
        )

        request_prompt = (
            _build_generation_prompt(
                prompt,
                aspect_ratio,
            )
        )

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
                        self._gemini_generate_sync,
                        client=client,
                        model=model,
                        prompt=request_prompt,
                        aspect_ratio=aspect_ratio,
                        image_size=image_size,
                    )
                )

                output_image = getattr(
                    interaction,
                    "output_image",
                    None,
                )

                if output_image is None:
                    raise ImageGenerationResponseError(
                        "Gemini did not produce an image."
                    )

                image_bytes = (
                    _decode_gemini_image(
                        getattr(
                            output_image,
                            "data",
                            None,
                        )
                    )
                )

                (
                    normalized_bytes,
                    width,
                    height,
                ) = (
                    _normalize_generated_image(
                        image_bytes=image_bytes,
                        aspect_ratio=aspect_ratio,
                        image_size=image_size,
                    )
                )

                return GeneratedImage(
                    image_base64=(
                        base64.b64encode(
                            normalized_bytes
                        ).decode(
                            "ascii"
                        )
                    ),
                    mime_type="image/png",
                    width=width,
                    height=height,
                    provider="gemini",
                    model=model,
                    request_id=(
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
                    ),
                    content_sha256=(
                        hashlib.sha256(
                            normalized_bytes
                        ).hexdigest()
                    ),
                )

            except Exception as error:
                last_error = error
                status_code = (
                    _status_code(
                        error
                    )
                )

                logger.warning(
                    "Gemini image generation failed: "
                    "model=%s type=%s status=%s message=%s",
                    model,
                    type(error).__name__,
                    status_code,
                    str(error)[:1_000],
                )

                if status_code == 429:
                    raise ImageGenerationQuotaError(
                        "Gemini image generation has no available quota."
                    ) from error

                if status_code in {
                    401,
                    403,
                }:
                    raise ImageGenerationConfigurationError(
                        "Gemini image credentials are unauthorized."
                    ) from error

                if status_code in {
                    400,
                    422,
                }:
                    raise ImageGenerationRejectedError(
                        "Gemini rejected this image request."
                    ) from error

                if status_code in {
                    404,
                    408,
                    500,
                    502,
                    503,
                    504,
                }:
                    continue

                if isinstance(
                    error,
                    ImageGenerationResponseError,
                ):
                    continue

                continue

        raise ImageGenerationResponseError(
            "No Gemini image model produced a usable image."
        ) from last_error

    async def generate(
        self,
        *,
        prompt: str,
        quality: ImageGenerationQuality,
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

        gemini_error: (
            Exception
            | None
        ) = None

        try:
            return (
                await self
                ._generate_with_gemini(
                    prompt=normalized_prompt,
                    quality=quality,
                    aspect_ratio=(
                        aspect_ratio
                    ),
                    image_size=(
                        image_size
                    ),
                )
            )

        except (
            ImageGenerationQuotaError,
            ImageGenerationConfigurationError,
            ImageGenerationResponseError,
        ) as error:
            gemini_error = error

            logger.info(
                "Falling back to Cloudflare image generation: "
                "reason=%s",
                type(error).__name__,
            )

        try:
            return await asyncio.to_thread(
                _cloudflare_generate_sync,
                prompt=normalized_prompt,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )

        except ImageGenerationConfigurationError as error:
            if isinstance(
                gemini_error,
                ImageGenerationQuotaError,
            ):
                raise ImageGenerationQuotaError(
                    "Gemini image quota is unavailable and "
                    "Cloudflare image fallback is not configured."
                ) from error

            raise ImageGenerationConfigurationError(
                "No configured image provider is currently available."
            ) from error

        except ImageGenerationQuotaError as error:
            raise ImageGenerationQuotaError(
                "All configured image providers have exhausted capacity."
            ) from error

        except (
            ImageGenerationRejectedError,
            ImageGenerationResponseError,
        ):
            raise
