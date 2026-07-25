import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from ai.pdf_page_request import (
    ExplicitPageRequestError,
    build_explicit_page_prompt,
    parse_explicit_page_request,
    prepare_explicit_pdf_subset,
    remap_answer_page_references,
    remap_page_numbers,
)
from ai.document_service import (
    DocumentConfigurationError,
    DocumentEncryptedError,
    DocumentNoTextError,
    DocumentResponseError,
    DocumentService,
    DocumentValidationError,
)
from ai.scanned_pdf_service import (
    ScannedPdfService,
)
from core.document_settings import (
    document_settings,
)
from schemas.documents import (
    DocumentAnalysisMode,
    DocumentResponse,
)


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@lru_cache(maxsize=1)
def get_document_service() -> DocumentService:
    return DocumentService()


@lru_cache(maxsize=1)
def get_scanned_pdf_service() -> ScannedPdfService:
    return ScannedPdfService()


def _validate_prompt(
    prompt: str,
) -> str:
    normalized = prompt.strip()

    if not normalized:
        return (
            "Summarize this PDF, identify its main points, "
            "and cite the relevant pages."
        )

    if (
        len(normalized)
        > document_settings
        .maximum_prompt_characters
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Document prompt is too long."
            ),
        )

    return normalized


@router.post(
    "/analyze",
    response_model=DocumentResponse,
)
async def analyze_document(
    file: Annotated[
        UploadFile,
        File(
            description="PDF document",
        ),
    ],
    prompt: Annotated[
        str,
        Form(),
    ] = (
        "Summarize this PDF, identify its main points, "
        "and cite the relevant pages."
    ),
) -> DocumentResponse:
    declared_mime_type = (
        file.content_type
        or ""
    ).lower()

    if (
        declared_mime_type
        not in document_settings
        .allowed_mime_types
    ):
        await file.close()

        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Only PDF documents are supported "
                "by this endpoint."
            ),
        )

    try:
        pdf_bytes = await file.read(
            document_settings
            .maximum_pdf_bytes
            + 1
        )

    finally:
        await file.close()

    if not pdf_bytes:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Uploaded PDF is empty."
            ),
        )

    if (
        len(pdf_bytes)
        > document_settings
        .maximum_pdf_bytes
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "PDF exceeds the 20 MB limit."
            ),
        )

    if not pdf_bytes.startswith(
        b"%PDF-"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "The uploaded file content is not a PDF."
            ),
        )

    normalized_prompt = _validate_prompt(
        prompt
    )

    explicit_page_request = (
        parse_explicit_page_request(
            normalized_prompt
        )
    )

    prepared_explicit_pdf = None
    analysis_pdf_bytes = file_bytes
    analysis_prompt = normalized_prompt

    if explicit_page_request is not None:
        try:
            prepared_explicit_pdf = (
                await asyncio.to_thread(
                    prepare_explicit_pdf_subset,
                    pdf_bytes=analysis_pdf_bytes,
                    request=explicit_page_request,
                )
            )

        except ExplicitPageRequestError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=str(error),
            ) from error

        analysis_pdf_bytes = (
            prepared_explicit_pdf
            .pdf_bytes
        )

        analysis_prompt = (
            build_explicit_page_prompt(
                user_prompt=analysis_prompt,
                prepared=(
                    prepared_explicit_pdf
                ),
            )
        )


    safe_filename = Path(
        file.filename
        or "document.pdf"
    ).name

    analysis_mode: DocumentAnalysisMode = (
        "text"
    )

    ocr_pages: list[int] = []

    try:
        try:
            result = (
                await get_document_service()
                .analyze(
                    pdf_bytes=pdf_bytes,
                    prompt=analysis_prompt,
                )
            )

        except DocumentNoTextError:
            analysis_mode = "vision_ocr"

            result = (
                await get_scanned_pdf_service()
                .analyze(
                    pdf_bytes=pdf_bytes,
                    prompt=analysis_prompt,
                )
            )

            ocr_pages = list(
                result.selected_pages
            )

    except DocumentEncryptedError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except DocumentValidationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except DocumentConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(error),
        ) from error

    except DocumentResponseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(error),
        ) from error

    response_answer = result.answer
    response_page_count = result.page_count

    response_selected_pages = list(
        result.selected_pages
    )

    response_ocr_pages = list(
        ocr_pages
    )

    response_citations = list(
        result.citations
    )

    if prepared_explicit_pdf is not None:
        page_map = (
            prepared_explicit_pdf
            .page_map
        )

        response_answer = (
            remap_answer_page_references(
                result.answer,
                page_map,
            )
        )

        response_page_count = (
            prepared_explicit_pdf
            .original_page_count
        )

        response_selected_pages = list(
            remap_page_numbers(
                result.selected_pages,
                page_map,
            )
        )

        response_ocr_pages = list(
            remap_page_numbers(
                ocr_pages,
                page_map,
            )
        )

        mapped_citations = []
        seen_citation_pages = set()

        for citation in result.citations:
            mapped_pages = (
                remap_page_numbers(
                    (
                        citation.page,
                    ),
                    page_map,
                )
            )

            if not mapped_pages:
                continue

            original_page = (
                mapped_pages[0]
            )

            if (
                original_page
                in seen_citation_pages
            ):
                continue

            seen_citation_pages.add(
                original_page
            )

            mapped_citations.append(
                citation.model_copy(
                    update={
                        "page": original_page,
                        "label": (
                            f"Page {original_page}"
                        ),
                    }
                )
            )

        response_citations = (
            mapped_citations
        )

    return DocumentResponse(
        answer=response_answer,

        provider="gemini",
        model=result.model,

        filename=safe_filename,
        mime_type="application/pdf",
        size_bytes=len(pdf_bytes),

        page_count=response_page_count,
        extracted_characters=(
            result.extracted_characters
        ),
        selected_pages=response_selected_pages,

        analysis_mode=analysis_mode,
        ocr_pages=response_ocr_pages,

        citations=response_citations,
        metadata=result.metadata,

        request_id=result.request_id,
        usage=result.usage,
    )
