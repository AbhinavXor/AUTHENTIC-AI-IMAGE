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

from ai.text_document_service import (
    TextDocumentConfigurationError,
    TextDocumentResponseError,
    TextDocumentService,
    TextDocumentValidationError,
)
from core.text_document_settings import (
    text_document_settings,
)
from artifacts.prompt_compiler import compact_analysis_instruction
from schemas.text_documents import (
    TextDocumentResponse,
)


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@lru_cache(maxsize=1)
def get_text_document_service(
) -> TextDocumentService:
    return TextDocumentService()


def _supported_extensions(
) -> frozenset[str]:
    return frozenset().union(
        text_document_settings
        .docx_extensions,

        text_document_settings
        .text_extensions,

        text_document_settings
        .markdown_extensions,

        text_document_settings
        .json_extensions,

        text_document_settings
        .source_code_extensions,
    )


def _validate_prompt(
    prompt: str,
) -> str:
    normalized = prompt.strip()

    if not normalized:
        return (
            "Summarize this document, identify its "
            "main points, and cite the relevant sources."
        )

    if len(normalized) > text_document_settings.maximum_prompt_characters:
        return compact_analysis_instruction(
            normalized,
            maximum_characters=text_document_settings.maximum_prompt_characters,
        )

    return normalized


@router.post(
    "/analyze-file",
    response_model=TextDocumentResponse,
)
async def analyze_text_document(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "DOCX, text, Markdown, JSON, "
                "configuration, or source-code file"
            ),
        ),
    ],
    prompt: Annotated[
        str,
        Form(),
    ] = (
        "Summarize this document, identify its "
        "main points, and cite the relevant sources."
    ),
) -> TextDocumentResponse:
    safe_filename = Path(
        file.filename
        or "document.txt"
    ).name

    extension = Path(
        safe_filename
    ).suffix.lower()

    if extension not in (
        _supported_extensions()
    ):
        await file.close()

        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "This document file type is not supported."
            ),
        )

    try:
        file_bytes = await file.read(
            text_document_settings
            .maximum_upload_bytes
            + 1
        )

    finally:
        await file.close()

    if not file_bytes:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Uploaded document is empty."
            ),
        )

    if (
        len(file_bytes)
        > text_document_settings
        .maximum_upload_bytes
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "Document exceeds the 10 MB limit."
            ),
        )

    normalized_prompt = _validate_prompt(
        prompt
    )

    try:
        result = (
            await get_text_document_service()
            .analyze(
                file_bytes=file_bytes,
                extension=extension,
                prompt=normalized_prompt,
            )
        )

    except TextDocumentValidationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except TextDocumentConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(error),
        ) from error

    except TextDocumentResponseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(error),
        ) from error

    return TextDocumentResponse(
        answer=result.answer,

        provider="gemini",
        model=result.model,

        filename=safe_filename,
        mime_type=(
            file.content_type
            or "application/octet-stream"
        ),
        size_bytes=len(
            file_bytes
        ),
        document_type=(
            result.document_type
        ),

        extracted_characters=(
            result.extracted_characters
        ),
        source_count=(
            result.source_count
        ),
        selected_sources=list(
            result.selected_sources
        ),

        citations=list(
            result.citations
        ),
        metadata=result.metadata,

        request_id=result.request_id,
        usage=result.usage,
    )
