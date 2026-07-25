import asyncio
import logging
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pymupdf
from google import genai
from google.genai import (
    errors,
    types,
)
from PIL import Image

from ai.document_service import (
    DocumentAnalysis,
    DocumentConfigurationError,
    DocumentEncryptedError,
    DocumentResponseError,
    DocumentValidationError,
)
from core.document_settings import (
    document_settings,
)
from core.gemini_settings import (
    gemini_settings,
)
from schemas.chat import TokenUsage
from schemas.documents import (
    DocumentCitation,
    DocumentMetadata,
)


logger = logging.getLogger(__name__)


SCANNED_DOCUMENT_SYSTEM_PROMPT = """
You are Serenya Scanned Document Intelligence, the source-grounded
visual document analysis layer behind Authentic AI.

You are given images rendered from selected pages of one PDF.

NON-NEGOTIABLE RULES

- Read only the visible content in the supplied page images.
- Answer only from those supplied pages.
- Do not use outside knowledge to fill document gaps.
- Do not invent text, names, amounts, dates, clauses, tables,
  signatures, stamps, policies, or page references.
- Preserve important wording used by the document.
- If text is unclear, state that it is unclear.
- If the supplied pages do not support an answer, say:
  "The supplied document pages do not provide enough information
  to answer this."
- Cite factual claims using exact citations such as [Page 2].
- Never cite a page that was not supplied.
- Separate visible document facts from interpretation.
- Respond in the language used by the user whenever practical.
- Return clean Markdown.
- Begin directly with the answer.
- Never expose hidden reasoning or private chain-of-thought.
""".strip()


@dataclass(frozen=True, slots=True)
class RenderedPdfPage:
    page_number: int
    image_bytes: bytes


def _safe_metadata_value(
    value: Any,
) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    return normalized[:500]


def _even_page_numbers(
    page_count: int,
    maximum_pages: int,
) -> tuple[int, ...]:
    if page_count < 1:
        return ()

    if page_count <= maximum_pages:
        return tuple(
            range(
                1,
                page_count + 1,
            )
        )

    if maximum_pages <= 1:
        return (1,)

    final_index = page_count - 1

    zero_based_indexes = {
        round(
            position
            * final_index
            / (maximum_pages - 1)
        )
        for position in range(
            maximum_pages
        )
    }

    return tuple(
        index + 1
        for index in sorted(
            zero_based_indexes
        )
    )


class ScannedPdfService:
    provider_name = "gemini"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not gemini_settings.api_key:
            raise DocumentConfigurationError(
                "Gemini scanned-document analysis "
                "is not configured."
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
    def _render_pdf_sync(
        pdf_bytes: bytes,
    ) -> tuple[
        tuple[RenderedPdfPage, ...],
        int,
        DocumentMetadata,
    ]:
        try:
            document = pymupdf.open(
                stream=pdf_bytes,
                filetype="pdf",
            )

        except Exception as error:
            raise DocumentValidationError(
                "The uploaded file is not a readable PDF."
            ) from error

        try:
            if not document.is_pdf:
                raise DocumentValidationError(
                    "The uploaded file is not a valid PDF."
                )

            if (
                document.needs_pass
                or document.is_encrypted
            ):
                raise DocumentEncryptedError(
                    "Password-protected PDFs are not supported yet."
                )

            page_count = int(
                document.page_count
            )

            if page_count < 1:
                raise DocumentValidationError(
                    "The PDF does not contain any pages."
                )

            if (
                page_count
                > document_settings.maximum_pdf_pages
            ):
                raise DocumentValidationError(
                    "The PDF exceeds the "
                    f"{document_settings.maximum_pdf_pages:,}-page "
                    "safety limit."
                )

            raw_metadata = (
                document.metadata
                if isinstance(
                    document.metadata,
                    dict,
                )
                else {}
            )

            metadata = DocumentMetadata(
                title=_safe_metadata_value(
                    raw_metadata.get("title")
                ),
                author=_safe_metadata_value(
                    raw_metadata.get("author")
                ),
                subject=_safe_metadata_value(
                    raw_metadata.get("subject")
                ),
                creator=_safe_metadata_value(
                    raw_metadata.get("creator")
                ),
                producer=_safe_metadata_value(
                    raw_metadata.get("producer")
                ),
            )

            selected_page_numbers = (
                _even_page_numbers(
                    page_count,
                    document_settings
                    .maximum_ocr_pages,
                )
            )

            rendered_pages: list[
                RenderedPdfPage
            ] = []

            total_rendered_bytes = 0

            for page_number in (
                selected_page_numbers
            ):
                page = document.load_page(
                    page_number - 1
                )

                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(
                        1.6,
                        1.6,
                    ),
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )

                png_bytes = pixmap.tobytes(
                    "png"
                )

                with Image.open(
                    BytesIO(png_bytes)
                ) as image:
                    normalized = image.convert(
                        "RGB"
                    )

                    normalized.thumbnail(
                        (
                            1_700,
                            2_400,
                        ),
                        Image.Resampling.LANCZOS,
                    )

                    output = BytesIO()

                    normalized.save(
                        output,
                        format="JPEG",
                        quality=84,
                        optimize=True,
                    )

                    image_bytes = (
                        output.getvalue()
                    )

                if (
                    len(image_bytes)
                    > document_settings
                    .maximum_ocr_page_bytes
                ):
                    with Image.open(
                        BytesIO(
                            image_bytes
                        )
                    ) as image:
                        reduced = image.convert(
                            "RGB"
                        )

                        reduced.thumbnail(
                            (
                                1_300,
                                1_850,
                            ),
                            Image.Resampling.LANCZOS,
                        )

                        output = BytesIO()

                        reduced.save(
                            output,
                            format="JPEG",
                            quality=72,
                            optimize=True,
                        )

                        image_bytes = (
                            output.getvalue()
                        )

                if (
                    len(image_bytes)
                    > document_settings
                    .maximum_ocr_page_bytes
                ):
                    logger.warning(
                        "Scanned PDF page skipped because "
                        "rendered image remained too large: "
                        "page=%s bytes=%s",
                        page_number,
                        len(image_bytes),
                    )

                    continue

                if (
                    total_rendered_bytes
                    + len(image_bytes)
                    > document_settings
                    .maximum_ocr_total_bytes
                ):
                    break

                total_rendered_bytes += len(
                    image_bytes
                )

                rendered_pages.append(
                    RenderedPdfPage(
                        page_number=page_number,
                        image_bytes=image_bytes,
                    )
                )

            if not rendered_pages:
                raise DocumentValidationError(
                    "The scanned PDF pages could not "
                    "be rendered safely."
                )

            return (
                tuple(rendered_pages),
                page_count,
                metadata,
            )

        finally:
            document.close()

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
            completion_tokens=(
                completion_tokens
            ),
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

    @staticmethod
    def _extract_citations(
        answer: str,
        available_pages: tuple[int, ...],
    ) -> tuple[
        DocumentCitation,
        ...
    ]:
        available = set(
            available_pages
        )

        cited_pages: set[int] = set()

        for match in re.finditer(
            r"\[Page\s+(\d+)\]",
            answer,
            flags=re.IGNORECASE,
        ):
            page_number = int(
                match.group(1)
            )

            if page_number in available:
                cited_pages.add(
                    page_number
                )

        for match in re.finditer(
            r"\[Pages\s+(\d+)\s*[-–]\s*(\d+)\]",
            answer,
            flags=re.IGNORECASE,
        ):
            first_page = int(
                match.group(1)
            )

            final_page = int(
                match.group(2)
            )

            if first_page > final_page:
                first_page, final_page = (
                    final_page,
                    first_page,
                )

            for page_number in range(
                first_page,
                final_page + 1,
            ):
                if page_number in available:
                    cited_pages.add(
                        page_number
                    )

        return tuple(
            DocumentCitation(
                page=page_number,
                label=f"Page {page_number}",
            )
            for page_number in sorted(
                cited_pages
            )
        )

    async def analyze(
        self,
        *,
        pdf_bytes: bytes,
        prompt: str,
    ) -> DocumentAnalysis:
        (
            rendered_pages,
            page_count,
            metadata,
        ) = await asyncio.to_thread(
            self._render_pdf_sync,
            pdf_bytes,
        )

        selected_page_numbers = tuple(
            page.page_number
            for page in rendered_pages
        )

        content_parts: list[
            str | types.Part
        ] = [
            (
                "USER REQUEST\n\n"
                f"{prompt}\n\n"
                "SCANNED PDF PAGE IMAGES\n\n"
                "The page labels below are exact PDF "
                "page numbers. Read visible text from "
                "the page images and answer only from "
                "those pages. Cite claims using "
                "[Page N]."
            )
        ]

        for page in rendered_pages:
            content_parts.append(
                (
                    "\n\n"
                    f"===== PAGE {page.page_number} ====="
                )
            )

            content_parts.append(
                types.Part.from_bytes(
                    data=page.image_bytes,
                    mime_type="image/jpeg",
                )
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
                        contents=content_parts,
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                SCANNED_DOCUMENT_SYSTEM_PROMPT
                            ),
                            temperature=0.1,
                            max_output_tokens=3_000,
                        ),
                    )
                )

                answer = self._response_text(
                    response
                )

                if not answer:
                    raise DocumentResponseError(
                        "The scanned-document model "
                        "returned an empty answer."
                    )

                citations = (
                    self._extract_citations(
                        answer,
                        selected_page_numbers,
                    )
                )

                if not citations:
                    reviewed = ", ".join(
                        f"[Page {page}]"
                        for page in (
                            selected_page_numbers[
                                :6
                            ]
                        )
                    )

                    answer = (
                        answer.rstrip()
                        + "\n\n"
                        + "**Scanned pages reviewed:** "
                        + reviewed
                    )

                    citations = tuple(
                        DocumentCitation(
                            page=page,
                            label=(
                                f"Page {page}"
                            ),
                        )
                        for page in (
                            selected_page_numbers[
                                :6
                            ]
                        )
                    )

                return DocumentAnalysis(
                    answer=answer,
                    model=model,
                    request_id=getattr(
                        response,
                        "response_id",
                        None,
                    ),
                    usage=self._usage(
                        response
                    ),
                    page_count=page_count,
                    extracted_characters=0,
                    selected_pages=(
                        selected_page_numbers
                    ),
                    citations=citations,
                    metadata=metadata,
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "Scanned PDF model attempt failed: "
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
                        self._status_code(
                            error
                        )
                    )

                    if status_code in {
                        401,
                        403,
                    }:
                        raise DocumentConfigurationError(
                            "Gemini scanned-document "
                            "credentials are invalid."
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
                        raise DocumentResponseError(
                            "Gemini rejected the "
                            "scanned-document request."
                        ) from error

                elif not isinstance(
                    error,
                    DocumentResponseError,
                ):
                    raise DocumentResponseError(
                        "The scanned-document request "
                        "could not be completed."
                    ) from error

        raise DocumentResponseError(
            "No configured model produced a usable "
            "scanned-document answer."
        ) from last_error
