import asyncio
import logging
import re
from dataclasses import dataclass
from time import monotonic
from typing import Any

import pymupdf
from google import genai
from google.genai import (
    errors,
    types,
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


DOCUMENT_SYSTEM_PROMPT = """
You are Serenya Document Intelligence, the source-grounded
document analysis layer behind Authentic AI.

You are given extracted text from selected pages of one PDF.

NON-NEGOTIABLE RULES

- Answer only from the supplied document text.
- Do not use outside knowledge to fill document gaps.
- Do not invent facts, clauses, names, amounts, dates, tables,
  policies, quotations, or page references.
- If the document does not support an answer, say:
  "The supplied document does not provide enough information
  to answer this."
- Cite factual claims using exact page citations such as
  [Page 3] or [Pages 4-5].
- Place citations directly after the supported statement.
- Never cite a page that was not supplied in the context.
- Separate direct document facts from reasonable interpretation.
- Preserve important terminology used by the document.
- Respond in the language used by the user whenever practical.
- Return clean Markdown.
- Begin directly with the answer.
- Never reveal hidden reasoning or private chain-of-thought.
""".strip()


_STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "against",
        "also",
        "and",
        "answer",
        "are",
        "before",
        "between",
        "document",
        "explain",
        "find",
        "from",
        "give",
        "have",
        "into",
        "main",
        "more",
        "most",
        "pdf",
        "please",
        "provide",
        "section",
        "show",
        "summarize",
        "summary",
        "tell",
        "that",
        "the",
        "their",
        "this",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)


class DocumentValidationError(RuntimeError):
    """Raised when an uploaded document is invalid."""


class DocumentEncryptedError(DocumentValidationError):
    """Raised when a PDF requires a password."""


class DocumentNoTextError(DocumentValidationError):
    """Raised when no usable text layer exists."""


class DocumentConfigurationError(RuntimeError):
    """Raised when the analysis provider is unavailable."""


class DocumentResponseError(RuntimeError):
    """Raised when no usable model response is produced."""


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str
    character_count: int


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    page_count: int
    pages: tuple[ExtractedPage, ...]
    extracted_characters: int
    metadata: DocumentMetadata
    repaired: bool


@dataclass(frozen=True, slots=True)
class DocumentAnalysis:
    answer: str
    model: str
    request_id: str | None
    usage: TokenUsage

    page_count: int
    extracted_characters: int
    selected_pages: tuple[int, ...]

    citations: tuple[DocumentCitation, ...]
    metadata: DocumentMetadata


def _normalize_text(
    value: str,
) -> str:
    lines: list[str] = []

    for raw_line in value.splitlines():
        normalized_line = re.sub(
            r"[ \t]+",
            " ",
            raw_line,
        ).strip()

        if normalized_line:
            lines.append(
                normalized_line
            )

    return "\n".join(lines).strip()


def _safe_metadata_value(
    value: Any,
) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    return normalized[:500]


def _query_terms(
    prompt: str,
) -> frozenset[str]:
    terms = {
        term
        for term in re.findall(
            r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}",
            prompt.lower(),
        )
        if term not in _STOP_WORDS
    }

    return frozenset(terms)


def _looks_like_broad_request(
    prompt: str,
) -> bool:
    lowered = prompt.lower()

    broad_terms = (
        "summarize",
        "summary",
        "overview",
        "main points",
        "key points",
        "entire document",
        "whole document",
        "poora document",
        "short summary",
    )

    return any(
        term in lowered
        for term in broad_terms
    )


def _page_score(
    page: ExtractedPage,
    terms: frozenset[str],
) -> float:
    if not terms:
        return 0.0

    lowered = page.text.lower()

    score = 0.0

    for term in terms:
        occurrences = lowered.count(
            term
        )

        if occurrences:
            score += min(
                occurrences,
                12,
            ) * 2.0

    first_lines = "\n".join(
        page.text.splitlines()[:8]
    ).lower()

    for term in terms:
        if term in first_lines:
            score += 4.0

    return score


def _evenly_sample(
    pages: tuple[ExtractedPage, ...],
    count: int,
) -> list[ExtractedPage]:
    if count <= 0 or not pages:
        return []

    if count >= len(pages):
        return list(pages)

    if count == 1:
        return [
            pages[0],
        ]

    last_index = len(pages) - 1

    selected_indexes = {
        round(
            position
            * last_index
            / (count - 1)
        )
        for position in range(count)
    }

    return [
        pages[index]
        for index in sorted(
            selected_indexes
        )
    ]


class DocumentService:
    provider_name = "gemini"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not gemini_settings.api_key:
            raise DocumentConfigurationError(
                "Gemini document analysis is not configured."
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
    def _extract_pdf_sync(
        pdf_bytes: bytes,
    ) -> ExtractedDocument:
        started_at = monotonic()

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

            pages: list[ExtractedPage] = []
            total_characters = 0

            for page_index in range(
                page_count
            ):
                if (
                    monotonic()
                    - started_at
                    > document_settings
                    .maximum_parse_seconds
                ):
                    raise DocumentValidationError(
                        "The PDF took too long to parse safely. "
                        "Try a smaller or optimized copy."
                    )

                try:
                    page = document.load_page(
                        page_index
                    )

                    raw_text = page.get_text(
                        "text",
                        sort=True,
                    )

                except Exception as error:
                    logger.warning(
                        "PDF page extraction failed: "
                        "page=%s type=%s",
                        page_index + 1,
                        type(error).__name__,
                    )

                    continue

                normalized_text = _normalize_text(
                    raw_text
                )

                if not normalized_text:
                    continue

                capped_text = normalized_text[
                    :document_settings
                    .maximum_scan_page_characters
                ]

                character_count = len(
                    capped_text
                )

                total_characters += (
                    character_count
                )

                pages.append(
                    ExtractedPage(
                        page_number=(
                            page_index + 1
                        ),
                        text=capped_text,
                        character_count=(
                            character_count
                        ),
                    )
                )

            if (
                total_characters
                < document_settings
                .minimum_usable_text_characters
            ):
                raise DocumentNoTextError(
                    "No usable text layer was found. "
                    "This may be a scanned PDF; OCR support "
                    "will be added in the next document phase."
                )

            return ExtractedDocument(
                page_count=page_count,
                pages=tuple(pages),
                extracted_characters=(
                    total_characters
                ),
                metadata=metadata,
                repaired=bool(
                    document.is_repaired
                ),
            )

        finally:
            document.close()

    @staticmethod
    def _hydrate_selected_pages_sync(
        pdf_bytes: bytes,
        selected_pages: tuple[
            ExtractedPage,
            ...
        ],
    ) -> tuple[
        ExtractedPage,
        ...
    ]:
        """
        Reopen the PDF and extract fuller text only
        from the pages chosen during the compact scan.
        """

        if not selected_pages:
            return ()

        preview_by_page = {
            page.page_number: page
            for page in selected_pages
        }

        try:
            document = pymupdf.open(
                stream=pdf_bytes,
                filetype="pdf",
            )

        except Exception as error:
            raise DocumentValidationError(
                "The selected PDF pages could not be reopened."
            ) from error

        try:
            if (
                document.needs_pass
                or document.is_encrypted
            ):
                raise DocumentEncryptedError(
                    "Password-protected PDFs are not supported yet."
                )

            hydrated_pages: list[
                ExtractedPage
            ] = []

            for page_number in sorted(
                preview_by_page
            ):
                preview = (
                    preview_by_page[
                        page_number
                    ]
                )

                try:
                    page = document.load_page(
                        page_number - 1
                    )

                    raw_text = page.get_text(
                        "text",
                        sort=True,
                    )

                    normalized_text = (
                        _normalize_text(
                            raw_text
                        )
                    )

                except Exception as error:
                    logger.warning(
                        "Selected PDF page hydration failed: "
                        "page=%s type=%s",
                        page_number,
                        type(error).__name__,
                    )

                    normalized_text = (
                        preview.text
                    )

                if not normalized_text:
                    normalized_text = (
                        preview.text
                    )

                detailed_text = (
                    normalized_text[
                        :document_settings
                        .maximum_page_characters
                    ]
                )

                hydrated_pages.append(
                    ExtractedPage(
                        page_number=(
                            page_number
                        ),
                        text=detailed_text,
                        character_count=len(
                            detailed_text
                        ),
                    )
                )

            return tuple(
                hydrated_pages
            )

        finally:
            document.close()

    @staticmethod
    def _select_pages(
        document: ExtractedDocument,
        prompt: str,
    ) -> tuple[ExtractedPage, ...]:
        pages = document.pages

        maximum_pages = (
            document_settings
            .maximum_selected_pages
        )

        if len(pages) <= maximum_pages:
            return pages

        broad_request = (
            _looks_like_broad_request(
                prompt
            )
        )

        terms = _query_terms(
            prompt
        )

        selected: dict[
            int,
            ExtractedPage,
        ] = {}

        def add_page(
            page: ExtractedPage,
        ) -> None:
            if (
                len(selected)
                < maximum_pages
            ):
                selected.setdefault(
                    page.page_number,
                    page,
                )

        # Cover title/introduction pages.
        for page in pages[:2]:
            add_page(page)

        if broad_request:
            for page in _evenly_sample(
                pages,
                maximum_pages,
            ):
                add_page(page)

        else:
            ranked_pages = sorted(
                pages,
                key=lambda page: (
                    _page_score(
                        page,
                        terms,
                    ),
                    page.character_count,
                ),
                reverse=True,
            )

            for page in ranked_pages:
                if (
                    _page_score(
                        page,
                        terms,
                    )
                    <= 0
                ):
                    continue

                add_page(page)

            remaining_slots = (
                maximum_pages
                - len(selected)
            )

            if remaining_slots > 0:
                for page in _evenly_sample(
                    pages,
                    remaining_slots,
                ):
                    add_page(page)

        # Include the final page when possible because
        # conclusions and signatures commonly appear there.
        if pages[-1].page_number not in selected:
            if len(selected) >= maximum_pages:
                removable_pages = [
                    page_number
                    for page_number
                    in selected
                    if page_number not in {
                        pages[0].page_number,
                        pages[1].page_number,
                    }
                ]

                if removable_pages:
                    selected.pop(
                        removable_pages[-1],
                        None,
                    )

            add_page(
                pages[-1]
            )

        return tuple(
            selected[
                page_number
            ]
            for page_number in sorted(
                selected
            )
        )

    @staticmethod
    def _build_context(
        selected_pages: tuple[
            ExtractedPage,
            ...
        ],
    ) -> str:
        sections: list[str] = []
        current_characters = 0

        for page in selected_pages:
            section = (
                f"\n===== PAGE {page.page_number} =====\n"
                f"{page.text}\n"
            )

            if (
                current_characters
                + len(section)
                > document_settings
                .maximum_context_characters
            ):
                remaining = (
                    document_settings
                    .maximum_context_characters
                    - current_characters
                )

                if remaining > 200:
                    sections.append(
                        section[:remaining]
                    )

                break

            sections.append(section)
            current_characters += len(
                section
            )

        return "".join(
            sections
        ).strip()

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
        page_count: int,
    ) -> tuple[
        DocumentCitation,
        ...
    ]:
        page_numbers: set[int] = set()

        for match in re.finditer(
            r"\[Page\s+(\d+)\]",
            answer,
            flags=re.IGNORECASE,
        ):
            page_number = int(
                match.group(1)
            )

            if (
                1
                <= page_number
                <= page_count
            ):
                page_numbers.add(
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
                if (
                    1
                    <= page_number
                    <= page_count
                ):
                    page_numbers.add(
                        page_number
                    )

        return tuple(
            DocumentCitation(
                page=page_number,
                label=f"Page {page_number}",
            )
            for page_number in sorted(
                page_numbers
            )
        )

    async def analyze(
        self,
        *,
        pdf_bytes: bytes,
        prompt: str,
    ) -> DocumentAnalysis:
        document = await asyncio.to_thread(
            self._extract_pdf_sync,
            pdf_bytes,
        )

        selected_pages = self._select_pages(
            document,
            prompt,
        )

        selected_pages = await asyncio.to_thread(
            self._hydrate_selected_pages_sync,
            pdf_bytes,
            selected_pages,
        )

        selected_page_numbers = tuple(
            page.page_number
            for page in selected_pages
        )

        context = self._build_context(
            selected_pages
        )

        request_content = f"""
USER REQUEST

{prompt}

SUPPLIED PDF CONTEXT

The context below contains extracted text from these pages only:
{", ".join(str(page) for page in selected_page_numbers)}

{context}

Answer the user request using only the supplied PDF context.
Use exact inline citations such as [Page 2] after supported claims.
""".strip()

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
                        contents=request_content,
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                DOCUMENT_SYSTEM_PROMPT
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
                        "The document model returned "
                        "an empty answer."
                    )

                citations = (
                    self._extract_citations(
                        answer,
                        document.page_count,
                    )
                )

                if not citations:
                    source_labels = ", ".join(
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
                        + "**Pages reviewed:** "
                        + source_labels
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
                    page_count=(
                        document.page_count
                    ),
                    extracted_characters=(
                        document
                        .extracted_characters
                    ),
                    selected_pages=(
                        selected_page_numbers
                    ),
                    citations=citations,
                    metadata=document.metadata,
                )

            except Exception as error:
                last_error = error

                logger.warning(
                    "Document model attempt failed: "
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
                            "Gemini document credentials "
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
                        raise DocumentResponseError(
                            "Gemini rejected the "
                            "document request."
                        ) from error

                elif not isinstance(
                    error,
                    DocumentResponseError,
                ):
                    raise DocumentResponseError(
                        "The document request could "
                        "not be completed."
                    ) from error

        raise DocumentResponseError(
            "No configured document model "
            "produced a usable answer."
        ) from last_error
