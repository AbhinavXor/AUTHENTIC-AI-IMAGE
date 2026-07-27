from __future__ import annotations

import asyncio
from functools import lru_cache

from fastapi import (
    APIRouter,
    HTTPException,
    Response,
    status,
)
from fastapi.responses import FileResponse

from artifacts.engine import (
    ArtifactGenerationError,
    ArtifactValidationError,
)
from artifacts.parser import (
    parse_artifact_document,
)
from artifacts.storage import (
    ArtifactExpiredError,
    ArtifactNotFoundError,
    ArtifactStorage,
    ArtifactStorageError,
    StoredArtifact,
)
from schemas.artifacts import (
    ArtifactDeleteResponse,
    ArtifactGenerateRequest,
    ArtifactGenerateResponse,
    ArtifactMetadataResponse,
)


router = APIRouter(
    prefix="/artifacts",
    tags=["artifacts"],
)


@lru_cache(maxsize=1)
def get_artifact_storage() -> ArtifactStorage:
    return ArtifactStorage()


def _artifact_response(
    stored: StoredArtifact,
) -> ArtifactGenerateResponse:
    return ArtifactGenerateResponse(
        artifact_id=stored.artifact_id,
        filename=stored.filename,
        format=stored.format,
        media_type=stored.media_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        created_at=stored.created_at,
        expires_at=stored.expires_at,
        download_url=(
            f"/api/v1/artifacts/"
            f"{stored.artifact_id}/download"
        ),
    )


def _raise_lookup_error(
    error: Exception,
) -> None:
    if isinstance(
        error,
        ArtifactExpiredError,
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Artifact has expired.",
        ) from error

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Artifact was not found.",
    ) from error


@router.post(
    "/generate",
    response_model=ArtifactGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_artifact_file(
    request: ArtifactGenerateRequest,
) -> ArtifactGenerateResponse:
    try:
        artifact = parse_artifact_document(
            request.content,
            title=request.title,
            subtitle=request.subtitle,
            author=request.author,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    storage = get_artifact_storage()

    try:
        await asyncio.to_thread(
            storage.cleanup_expired
        )

        stored = await asyncio.to_thread(
            storage.create,
            artifact,
            format=request.format,
            filename=request.filename,
        )

    except ArtifactValidationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except (
        ArtifactGenerationError,
        ArtifactStorageError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Artifact generation failed."
            ),
        ) from error

    return _artifact_response(
        stored
    )


@router.get(
    "/{artifact_id}",
    response_model=ArtifactMetadataResponse,
)
async def get_artifact_metadata(
    artifact_id: str,
) -> ArtifactMetadataResponse:
    storage = get_artifact_storage()

    try:
        stored = await asyncio.to_thread(
            storage.get,
            artifact_id,
        )

    except (
        ArtifactExpiredError,
        ArtifactNotFoundError,
    ) as error:
        _raise_lookup_error(
            error
        )

    except ArtifactStorageError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Artifact metadata could not be read."
            ),
        ) from error

    return ArtifactMetadataResponse(
        **_artifact_response(
            stored
        ).model_dump()
    )


@router.get(
    "/{artifact_id}/download",
    response_class=FileResponse,
)
async def download_artifact(
    artifact_id: str,
) -> FileResponse:
    storage = get_artifact_storage()

    try:
        stored = await asyncio.to_thread(
            storage.get,
            artifact_id,
        )

    except (
        ArtifactExpiredError,
        ArtifactNotFoundError,
    ) as error:
        _raise_lookup_error(
            error
        )

    except ArtifactStorageError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Artifact file could not be read."
            ),
        ) from error

    return FileResponse(
        path=stored.path,
        media_type=stored.media_type,
        filename=stored.filename,
        headers={
            "Cache-Control": (
                "private, no-store, max-age=0"
            ),
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Artifact-SHA256": stored.sha256,
        },
    )


@router.delete(
    "/{artifact_id}",
    response_model=ArtifactDeleteResponse,
)
async def delete_artifact(
    artifact_id: str,
    response: Response,
) -> ArtifactDeleteResponse:
    storage = get_artifact_storage()

    try:
        deleted = await asyncio.to_thread(
            storage.delete,
            artifact_id,
        )

    except ArtifactNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact was not found.",
        ) from error

    except ArtifactStorageError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Artifact could not be deleted."
            ),
        ) from error

    response.headers[
        "Cache-Control"
    ] = "no-store"

    return ArtifactDeleteResponse(
        artifact_id=artifact_id,
        deleted=deleted,
    )