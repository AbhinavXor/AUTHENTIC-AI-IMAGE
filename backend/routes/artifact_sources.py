from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import pymupdf
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    status,
)

from artifacts.source_vault import ArtifactSourceVault
from core.artifact_settings import artifact_settings
from core.document_settings import document_settings
from schemas.artifact_sources import (
    ArtifactSourceCreateResponse,
    ArtifactTextSourceCreateRequest,
)
from schemas.artifacts import ArtifactSourceSnapshot


router = APIRouter(
    prefix="/artifact-sources",
    tags=["artifact-sources"],
)


@lru_cache(maxsize=1)
def get_artifact_source_vault() -> ArtifactSourceVault:
    return ArtifactSourceVault(
        root_directory=artifact_settings.source_storage_directory,
        retention_hours=artifact_settings.retention_hours,
    )


def _normalize_pdf_text(value: str) -> str:
    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in value.replace("\r", "\n").splitlines()
    ]
    output: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if output and not previous_blank:
                output.append("")
            previous_blank = True
            continue
        output.append(line)
        previous_blank = False
    return "\n".join(output).strip()


def extract_pdf_source(
    pdf_bytes: bytes,
) -> tuple[str, str | None, int]:
    try:
        document = pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf",
        )
    except Exception as error:
        raise ValueError(
            "The uploaded file is not a readable PDF."
        ) from error

    try:
        if document.needs_pass or document.is_encrypted:
            raise ValueError(
                "Password-protected PDFs cannot be used as artifact sources."
            )
        pages: list[str] = []
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            text = _normalize_pdf_text(page.get_text("text"))
            if text:
                pages.append(text)
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        title = str(metadata.get("title") or "").strip() or None
        return "\n\n".join(pages).strip(), title, int(document.page_count)
    finally:
        document.close()


def _response(
    snapshot: ArtifactSourceSnapshot,
) -> ArtifactSourceCreateResponse:
    reference, record = get_artifact_source_vault().create(snapshot)
    return ArtifactSourceCreateResponse(
        reference=reference,
        summary=snapshot.summary,
        source_characters=len(snapshot.content or ""),
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


@router.post(
    "/text",
    response_model=ArtifactSourceCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_text_artifact_source(
    request: ArtifactTextSourceCreateRequest,
) -> ArtifactSourceCreateResponse:
    return _response(
        ArtifactSourceSnapshot(
            kind=request.kind,
            summary=request.summary,
            content=request.content,
            message_ids=request.message_ids,
            attachment_names=request.attachment_names,
            confidence=request.confidence,
        )
    )


@router.post(
    "/upload",
    response_model=ArtifactSourceCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_uploaded_artifact_source(
    file: Annotated[UploadFile, File()],
) -> ArtifactSourceCreateResponse:
    declared_type = (file.content_type or "").casefold()
    filename = Path(file.filename or "source.pdf").name
    if declared_type != "application/pdf" and not filename.casefold().endswith(".pdf"):
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported by the durable artifact-source endpoint.",
        )
    try:
        pdf_bytes = await file.read(document_settings.maximum_pdf_bytes + 1)
    finally:
        await file.close()
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded PDF is empty.",
        )
    if len(pdf_bytes) > document_settings.maximum_pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded PDF exceeds the configured byte-size safety limit.",
        )
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file content is not a PDF.",
        )
    try:
        content, metadata_title, page_count = extract_pdf_source(pdf_bytes)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The PDF does not contain extractable text. Use an OCR-enabled copy "
                "before requesting a lossless redesign."
            ),
        )
    if len(content) > artifact_settings.maximum_prompt_characters:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The extracted source exceeds the configured source-storage limit.",
        )
    summary_title = metadata_title or Path(filename).stem
    return _response(
        ArtifactSourceSnapshot(
            kind="uploaded_file",
            summary=f"{summary_title} — {page_count} source pages",
            content=content,
            message_ids=[],
            attachment_names=[filename],
            confidence=1.0,
        )
    )
