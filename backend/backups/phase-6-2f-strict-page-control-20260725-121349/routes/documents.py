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
                    prompt=normalized_prompt,
                )
            )

        except DocumentNoTextError:
            analysis_mode = "vision_ocr"

            result = (
                await get_scanned_pdf_service()
                .analyze(
                    pdf_bytes=pdf_bytes,
                    prompt=normalized_prompt,
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

    return DocumentResponse(
        answer=result.answer,

        provider="gemini",
        model=result.model,

        filename=safe_filename,
        mime_type="application/pdf",
        size_bytes=len(pdf_bytes),

        page_count=result.page_count,
        extracted_characters=(
            result.extracted_characters
        ),
        selected_pages=list(
            result.selected_pages
        ),

        analysis_mode=analysis_mode,
        ocr_pages=ocr_pages,

        citations=list(
            result.citations
        ),
        metadata=result.metadata,

        request_id=result.request_id,
        usage=result.usage,
    )
