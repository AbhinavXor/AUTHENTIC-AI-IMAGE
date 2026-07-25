import logging
from typing import Any

from google import genai
from google.genai import (
    errors,
    types,
)

from core.gemini_settings import gemini_settings
from schemas.chat import TokenUsage


logger = logging.getLogger(__name__)


VISION_SYSTEM_PROMPT = """
You are Serenya Vision, the image-understanding layer behind
Authentic AI.

Analyze only what is actually visible in the supplied image.

Rules:

- Never invent hidden objects, text, people, measurements, events,
  locations, identities, or context.
- Clearly distinguish visible facts from reasonable inference.
- Mention uncertainty when visual evidence is insufficient.
- Transcribe visible text carefully when the user asks for OCR.
- For charts, diagrams, interfaces, documents, and screenshots,
  preserve their structure and explain relationships clearly.
- Do not identify real people.
- Respond in the language used by the user whenever practical.
- Return clean Markdown.
- Begin directly with the answer.
- Never expose hidden reasoning or private chain-of-thought.
""".strip()


class VisionConfigurationError(RuntimeError):
    """Raised when vision provider configuration is missing."""


class VisionResponseError(RuntimeError):
    """Raised when no usable vision answer is produced."""


class VisionService:
    """Gemini-backed image-understanding service."""

    provider_name = "gemini"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not gemini_settings.api_key:
            raise VisionConfigurationError(
                "Gemini is not configured."
            )

        if self._client is None:
            self._client = genai.Client(
                api_key=gemini_settings.api_key,
                http_options=types.HttpOptions(
                    timeout=int(
                        gemini_settings.timeout_seconds
                        * 1000
                    ),
                ),
            )

        return self._client

    @staticmethod
    def _model_candidates() -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                model
                for model in (
                    gemini_settings.quality_model,
                    gemini_settings.fallback_model,
                    gemini_settings.preview_model,
                    gemini_settings.fast_model,
                )
                if model
            )
        )

    @staticmethod
    def _response_text(
        response: Any,
    ) -> str:
        try:
            return (
                getattr(
                    response,
                    "text",
                    "",
                )
                or ""
            ).strip()

        except Exception:
            return ""

    @staticmethod
    def _usage(
        response: Any,
    ) -> TokenUsage:
        metadata = getattr(
            response,
            "usage_metadata",
            None,
        )

        if metadata is None:
            return TokenUsage()

        prompt_tokens = int(
            getattr(
                metadata,
                "prompt_token_count",
                0,
            )
            or 0
        )

        completion_tokens = int(
            getattr(
                metadata,
                "candidates_token_count",
                0,
            )
            or getattr(
                metadata,
                "output_token_count",
                0,
            )
            or 0
        )

        total_tokens = int(
            getattr(
                metadata,
                "total_token_count",
                0,
            )
            or (
                prompt_tokens
                + completion_tokens
            )
        )

        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _status_code(
        error: Exception,
    ) -> int | None:
        raw_code = getattr(
            error,
            "code",
            None,
        )

        try:
            return int(raw_code)

        except (
            TypeError,
            ValueError,
        ):
            return None

    async def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
    ) -> tuple[
        str,
        str,
        str | None,
        TokenUsage,
    ]:
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type,
        )

        last_error: Exception | None = None

        for model in self._model_candidates():
            try:
                response = (
                    await self
                    ._get_client()
                    .aio
                    .models
                    .generate_content(
                        model=model,
                        contents=[
                            image_part,
                            prompt,
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                VISION_SYSTEM_PROMPT
                            ),
                            temperature=0.2,
                            max_output_tokens=2_048,
                        ),
                    )
                )

                answer = self._response_text(
                    response
                )

                if not answer:
                    raise VisionResponseError(
                        "The vision model returned "
                        "an empty answer."
                    )

                return (
                    answer,
                    model,
                    getattr(
                        response,
                        "response_id",
                        None,
                    ),
                    self._usage(response),
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "Vision model attempt failed: "
                    "model=%s type=%s status=%s",
                    model,
                    type(error).__name__,
                    self._status_code(error),
                )

                if isinstance(
                    error,
                    errors.APIError,
                ):
                    status_code = (
                        self._status_code(error)
                    )

                    if status_code in {
                        401,
                        403,
                    }:
                        raise VisionConfigurationError(
                            "Gemini vision credentials "
                            "are invalid or unauthorized."
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
                        raise VisionResponseError(
                            "Gemini rejected the "
                            "vision request."
                        ) from error

                elif not isinstance(
                    error,
                    VisionResponseError,
                ):
                    raise VisionResponseError(
                        "The vision request could "
                        "not be completed."
                    ) from error

        raise VisionResponseError(
            "No configured vision model "
            "produced a usable answer."
        ) from last_error
