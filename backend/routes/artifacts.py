from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai.provider_adapter import ProviderError
from artifacts.composer import ArtifactCompositionError
from artifacts.engine import (
    ArtifactGenerationError,
    ArtifactValidationError,
)
from artifacts.repository import (
    ArtifactAccessError,
    ArtifactConflictError,
    ArtifactRepository,
    ArtifactRepositoryError,
)
from artifacts.responses import artifact_response_payload
from artifacts.service import ArtifactLifecycleService
from artifacts.source_fidelity import (
    is_canonical_artifact_markdown,
    recovered_source_contamination,
    sanitize_recovered_source_payload,
)
from artifacts.storage import (
    ArtifactExpiredError,
    ArtifactNotFoundError,
    ArtifactStorage,
    ArtifactStorageError,
)
from core.artifact_operation_rate_limit import (
    ArtifactOperationRateLimitError,
    artifact_operation_rate_limiter,
    resolve_artifact_operation_client_key,
)
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.artifacts import (
    ArtifactAuditEvent,
    ArtifactAuditResponse,
    ArtifactDeleteResponse,
    ArtifactDuplicateRequest,
    ArtifactExportRequest,
    ArtifactGenerateRequest,
    ArtifactGenerateResponse,
    ArtifactMetadataResponse,
    ArtifactSourceResponse,
    ArtifactRenameRequest,
    ArtifactRestoreRequest,
    ArtifactRevisionRequest,
    ArtifactVersionListResponse,
    ArtifactVersionResponse,
)

router = APIRouter(
    prefix="/artifacts",
    tags=["artifacts"],
)

_ARTIFACT_TOKEN_HEADER = "X-Artifact-Token"
_IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

_RequestModel = TypeVar("_RequestModel", bound=BaseModel)


def _with_idempotency_key(
    request: _RequestModel,
    header_value: str | None,
) -> _RequestModel:
    header_key = (header_value or "").strip() or None
    body_key = getattr(request, "idempotency_key", None)

    if header_key and body_key and header_key != body_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Idempotency-Key header does not match "
                "the request body idempotency_key."
            ),
        )

    resolved = header_key or body_key
    if not resolved or resolved == body_key:
        return request

    return request.model_copy(
        update={"idempotency_key": resolved}
    )


@lru_cache(maxsize=1)
def get_artifact_storage() -> ArtifactStorage:
    return ArtifactStorage()


@lru_cache(maxsize=1)
def get_artifact_repository() -> ArtifactRepository:
    return ArtifactRepository(
        get_artifact_storage()
    )


def _get_model_router():
    from routes.chat import get_model_router

    return get_model_router()


@lru_cache(maxsize=1)
def get_artifact_lifecycle_service() -> ArtifactLifecycleService:
    from routes.artifact_sources import get_artifact_source_vault

    return ArtifactLifecycleService(
        artifact_storage=get_artifact_storage(),
        artifact_repository=get_artifact_repository(),
        model_router=_get_model_router(),
        source_vault=get_artifact_source_vault(),
    )


def _set_private_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"


def _check_operation_rate_limit(request: Request) -> None:
    try:
        artifact_operation_rate_limiter.check(
            resolve_artifact_operation_client_key(request)
        )
    except ArtifactOperationRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many artifact operations were requested. Try again later.",
            headers={
                "Retry-After": str(error.retry_after_seconds),
            },
        ) from error


def _require_token(value: str | None) -> str:
    if value is None or not value.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Artifact access token is required.",
            headers={"WWW-Authenticate": "ArtifactToken"},
        )
    return value.strip()


def _raise_repository_error(error: Exception) -> None:
    if isinstance(error, ArtifactAccessError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Artifact access was denied.",
        ) from error
    if isinstance(error, ArtifactExpiredError):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Artifact has expired.",
        ) from error
    if isinstance(error, ArtifactNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact was not found.",
        ) from error
    if isinstance(error, ArtifactConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Artifact metadata could not be processed.",
    ) from error


def _version_download_name(
    display_name: str,
    *,
    format: str,
    version: int,
    current_version: int,
) -> str:
    if version == current_version:
        return display_name

    return (
        f"{Path(display_name).stem}-v{version}."
        f"{format}"
    )


def _creation_http_error(error: Exception) -> HTTPException:
    if isinstance(error, ProviderError):
        provider_status = {
            "rate_limit": status.HTTP_429_TOO_MANY_REQUESTS,
            "timeout": status.HTTP_504_GATEWAY_TIMEOUT,
            "configuration": status.HTTP_503_SERVICE_UNAVAILABLE,
            "authentication": status.HTTP_503_SERVICE_UNAVAILABLE,
            "billing": status.HTTP_503_SERVICE_UNAVAILABLE,
            "availability": status.HTTP_503_SERVICE_UNAVAILABLE,
        }.get(error.code, status.HTTP_502_BAD_GATEWAY)
        return HTTPException(
            status_code=provider_status,
            detail="The artifact composition provider could not complete the request.",
        )
    if isinstance(error, (ArtifactValidationError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )
    if isinstance(error, ArtifactCompositionError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )
    if isinstance(
        error,
        (
            ArtifactGenerationError,
            ArtifactStorageError,
            ArtifactRepositoryError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Artifact generation or persistence failed.",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Artifact operation failed unexpectedly.",
    )


def _compose_request_from_generate(
    request: ArtifactGenerateRequest,
) -> ArtifactComposeRequest:
    return ArtifactComposeRequest(
        prompt=(
            request.purpose
            or "Render the supplied artifact content."
        ),
        format=request.format,
        title=request.title,
        subtitle=request.subtitle,
        author=request.author,
        filename=request.filename,
        document_type=request.document_type,
        purpose=request.purpose,
        audience=request.audience,
        layout_family=request.layout_family,
        branding_mode=request.branding_mode,
        visual_density=request.visual_density,
        presentation_tier=request.presentation_tier,
        header_mode=request.header_mode,
        footer_mode=request.footer_mode,
        include_table_of_contents=request.include_table_of_contents,
        include_section_openers=request.include_section_openers,
        include_cover_date=request.include_cover_date,
        include_cover_profile=request.include_cover_profile,
        include_document_label=request.include_document_label,
        include_cover_subtitle=request.include_cover_subtitle,
        source_snapshot=request.source_snapshot,
        idempotency_key=request.idempotency_key,
    )


@router.post(
    "/generate",
    response_model=ArtifactGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_artifact_file(
    request: ArtifactGenerateRequest,
    response: Response,
    client_request: Request,
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactGenerateResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    _check_operation_rate_limit(client_request)
    service = get_artifact_lifecycle_service()

    try:
        result = await asyncio.to_thread(
            service.create_from_markdown,
            _compose_request_from_generate(request),
            source_content=request.content,
        )
    except Exception as error:
        raise _creation_http_error(error) from error

    token = result.view.access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Artifact access token was not created.",
        )

    _set_private_headers(response)
    return ArtifactGenerateResponse(
        **artifact_response_payload(
            result.view,
            access_token=token,
        )
    )


@router.get(
    "/{artifact_id}",
    response_model=ArtifactMetadataResponse,
)
async def get_artifact_metadata(
    artifact_id: str,
    response: Response,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
) -> ArtifactMetadataResponse:
    token = _require_token(access_token)

    try:
        view = await asyncio.to_thread(
            get_artifact_repository().get,
            artifact_id,
            token,
        )
    except Exception as error:
        _raise_repository_error(error)

    _set_private_headers(response)
    return ArtifactMetadataResponse(
        **artifact_response_payload(
            view,
            access_token=token,
        )
    )


@router.get(
    "/{artifact_id}/source",
    response_model=ArtifactSourceResponse,
)
async def get_artifact_source(
    artifact_id: str,
    response: Response,
    version: int | None = Query(
        default=None,
        ge=1,
    ),
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
) -> ArtifactSourceResponse:
    """Return the private authoritative source for source continuity.

    The capability token is mandatory. The original source snapshot is
    preferred. When an older conversation retained only a compact preview,
    the canonical source of the requested artifact version is returned.
    """
    token = _require_token(access_token)

    try:
        view = await asyncio.to_thread(
            get_artifact_repository().get,
            artifact_id,
            token,
            version=version,
        )
    except Exception as error:
        _raise_repository_error(error)

    snapshot = dict(
        view.record.source_snapshot
        or {}
    )
    snapshot_content = str(
        snapshot.get("content")
        or ""
    ).strip()
    version_content = (
        view.version.source_content
        or ""
    ).strip()

    clean_snapshot = sanitize_recovered_source_payload(
        snapshot_content
    ) if snapshot_content else ""
    clean_version = sanitize_recovered_source_payload(
        version_content
    ) if version_content else ""

    snapshot_issues = recovered_source_contamination(
        snapshot_content
    ) if snapshot_content else ()
    version_issues = recovered_source_contamination(
        version_content
    ) if version_content else ()

    use_snapshot = bool(
        clean_snapshot
        and not snapshot_issues
    )
    if use_snapshot:
        content = clean_snapshot
        kind = str(
            snapshot.get("kind")
            or "conversation"
        )
        recovered_from = "source_snapshot"
    elif clean_version:
        content = clean_version
        kind = "artifact_version"
        recovered_from = "artifact_version"
    elif clean_snapshot:
        content = clean_snapshot
        kind = str(
            snapshot.get("kind")
            or "conversation"
        )
        recovered_from = "source_snapshot"
    else:
        content = ""
        kind = "artifact_version"
        recovered_from = "artifact_version"

    # A clean canonical version is safer than a contaminated snapshot even
    # when the snapshot happens to be longer.
    if (
        clean_version
        and is_canonical_artifact_markdown(clean_version)
        and snapshot_issues
    ):
        content = clean_version
        kind = "artifact_version"
        recovered_from = "artifact_version"

    if not content:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "The artifact does not contain "
                "a recoverable source."
            ),
        )

    if kind not in {
        "explicit_prompt",
        "previous_response",
        "conversation",
        "uploaded_file",
        "artifact_version",
        "project_context",
    }:
        kind = "artifact_version"

    _set_private_headers(response)
    return ArtifactSourceResponse(
        artifact_id=view.record.artifact_id,
        version=view.version.version,
        title=view.record.title,
        filename=view.version.filename,
        kind=kind,
        summary=str(
            snapshot.get("summary")
            or view.record.title
        )[:2_000],
        content=content,
        message_ids=[
            str(item)
            for item in snapshot.get(
                "message_ids",
                [],
            )
        ][:32],
        attachment_names=[
            str(item)
            for item in snapshot.get(
                "attachment_names",
                [],
            )
        ][:16],
        confidence=float(
            snapshot.get("confidence")
            or (0.98 if recovered_from == "source_snapshot" else 0.92)
        ),
        recovered_from=recovered_from,
    )


@router.patch(
    "/{artifact_id}",
    response_model=ArtifactMetadataResponse,
)
async def rename_artifact(
    artifact_id: str,
    request: ArtifactRenameRequest,
    response: Response,
    client_request: Request,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactMetadataResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    _check_operation_rate_limit(client_request)
    token = _require_token(access_token)

    try:
        view = await asyncio.to_thread(
            get_artifact_repository().rename,
            artifact_id,
            token,
            display_name=request.filename,
            expected_version=request.expected_version,
            idempotency_key=request.idempotency_key,
        )
    except Exception as error:
        _raise_repository_error(error)

    _set_private_headers(response)
    return ArtifactMetadataResponse(
        **artifact_response_payload(
            view,
            access_token=token,
        )
    )


@router.post(
    "/{artifact_id}/revisions",
    response_model=ArtifactGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def revise_artifact(
    artifact_id: str,
    request: ArtifactRevisionRequest,
    response: Response,
    client_request: Request,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactGenerateResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    _check_operation_rate_limit(client_request)
    token = _require_token(access_token)

    try:
        result = await get_artifact_lifecycle_service().revise(
            artifact_id,
            token,
            request,
        )
    except (
        ArtifactAccessError,
        ArtifactConflictError,
        ArtifactNotFoundError,
        ArtifactExpiredError,
    ) as error:
        _raise_repository_error(error)
    except Exception as error:
        raise _creation_http_error(error) from error

    _set_private_headers(response)
    return ArtifactGenerateResponse(
        **artifact_response_payload(
            result.view,
            access_token=token,
        )
    )


@router.post(
    "/{artifact_id}/exports",
    response_model=ArtifactGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_artifact(
    artifact_id: str,
    request: ArtifactExportRequest,
    response: Response,
    client_request: Request,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactGenerateResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    _check_operation_rate_limit(client_request)
    token = _require_token(access_token)

    try:
        result = await asyncio.to_thread(
            get_artifact_lifecycle_service().export,
            artifact_id,
            token,
            format=request.format,
            expected_version=request.expected_version,
            idempotency_key=request.idempotency_key,
        )
    except (
        ArtifactAccessError,
        ArtifactConflictError,
        ArtifactNotFoundError,
        ArtifactExpiredError,
    ) as error:
        _raise_repository_error(error)
    except Exception as error:
        raise _creation_http_error(error) from error

    _set_private_headers(response)
    return ArtifactGenerateResponse(
        **artifact_response_payload(
            result.view,
            access_token=token,
        )
    )


@router.post(
    "/{artifact_id}/duplicate",
    response_model=ArtifactGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_artifact(
    artifact_id: str,
    request: ArtifactDuplicateRequest,
    response: Response,
    client_request: Request,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactGenerateResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    _check_operation_rate_limit(client_request)
    token = _require_token(access_token)

    try:
        result = await asyncio.to_thread(
            get_artifact_lifecycle_service().duplicate,
            artifact_id,
            token,
            request=request,
        )
    except (
        ArtifactAccessError,
        ArtifactNotFoundError,
        ArtifactExpiredError,
    ) as error:
        _raise_repository_error(error)
    except Exception as error:
        raise _creation_http_error(error) from error

    new_token = result.view.access_token
    if not new_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Duplicated artifact token was not created.",
        )

    _set_private_headers(response)
    return ArtifactGenerateResponse(
        **artifact_response_payload(
            result.view,
            access_token=new_token,
        )
    )


@router.post(
    "/{artifact_id}/restore",
    response_model=ArtifactGenerateResponse,
)
async def restore_artifact(
    artifact_id: str,
    request: ArtifactRestoreRequest,
    response: Response,
    client_request: Request,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
    idempotency_key_header: str | None = Header(
        default=None,
        alias=_IDEMPOTENCY_KEY_HEADER,
    ),
) -> ArtifactGenerateResponse:
    request = _with_idempotency_key(
        request,
        idempotency_key_header,
    )
    _check_operation_rate_limit(client_request)
    token = _require_token(access_token)

    try:
        view = await asyncio.to_thread(
            get_artifact_repository().restore,
            artifact_id,
            token,
            version=request.version,
            expected_version=request.expected_version,
            idempotency_key=request.idempotency_key,
        )
    except Exception as error:
        _raise_repository_error(error)

    _set_private_headers(response)
    return ArtifactGenerateResponse(
        **artifact_response_payload(
            view,
            access_token=token,
        )
    )


@router.get(
    "/{artifact_id}/versions",
    response_model=ArtifactVersionListResponse,
)
async def list_artifact_versions(
    artifact_id: str,
    response: Response,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
) -> ArtifactVersionListResponse:
    token = _require_token(access_token)

    try:
        view = await asyncio.to_thread(
            get_artifact_repository().get,
            artifact_id,
            token,
        )
        versions = await asyncio.to_thread(
            get_artifact_repository().list_versions,
            artifact_id,
            token,
        )
    except Exception as error:
        _raise_repository_error(error)

    _set_private_headers(response)
    return ArtifactVersionListResponse(
        artifact_id=artifact_id,
        current_version=view.record.current_version,
        versions=[
            ArtifactVersionResponse(
                version=version.version,
                filename=_version_download_name(
                    view.record.display_name,
                    format=version.format,
                    version=version.version,
                    current_version=view.record.current_version,
                ),
                format=version.format,
                media_type=version.media_type,
                size_bytes=version.size_bytes,
                sha256=version.sha256,
                created_at=version.created_at,
                expires_at=version.expires_at,
                page_or_slide_count=(
                    version.page_or_slide_count
                ),
                validation=version.validation,
                is_current=(
                    version.version
                    == view.record.current_version
                ),
                download_url=(
                    f"/api/v1/artifacts/{artifact_id}/download"
                    f"?version={version.version}"
                ),
            )
            for version in versions
        ],
    )


@router.get(
    "/{artifact_id}/audit",
    response_model=ArtifactAuditResponse,
)
async def get_artifact_audit(
    artifact_id: str,
    response: Response,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
) -> ArtifactAuditResponse:
    token = _require_token(access_token)
    try:
        events = await asyncio.to_thread(
            get_artifact_repository().list_audit_events,
            artifact_id,
            token,
        )
    except Exception as error:
        _raise_repository_error(error)

    _set_private_headers(response)
    return ArtifactAuditResponse(
        artifact_id=artifact_id,
        events=[
            ArtifactAuditEvent.model_validate(event)
            for event in events
        ],
    )


@router.get(
    "/{artifact_id}/download",
    response_class=FileResponse,
)
async def download_artifact(
    artifact_id: str,
    version: int | None = Query(
        default=None,
        ge=1,
    ),
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
) -> FileResponse:
    token = _require_token(access_token)

    try:
        view = await asyncio.to_thread(
            get_artifact_repository().get,
            artifact_id,
            token,
            version=version,
        )
    except Exception as error:
        _raise_repository_error(error)

    download_name = _version_download_name(
        view.record.display_name,
        format=view.version.format,
        version=view.version.version,
        current_version=view.record.current_version,
    )

    return FileResponse(
        path=view.stored.path,
        media_type=view.version.media_type,
        filename=download_name,
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Artifact-SHA256": view.version.sha256,
            "X-Artifact-Version": str(
                view.version.version
            ),
        },
    )


@router.delete(
    "/{artifact_id}",
    response_model=ArtifactDeleteResponse,
)
async def delete_artifact(
    artifact_id: str,
    response: Response,
    client_request: Request,
    access_token: str | None = Header(
        default=None,
        alias=_ARTIFACT_TOKEN_HEADER,
    ),
) -> ArtifactDeleteResponse:
    _check_operation_rate_limit(client_request)
    token = _require_token(access_token)

    try:
        deleted = await asyncio.to_thread(
            get_artifact_repository().delete,
            artifact_id,
            token,
        )
    except Exception as error:
        _raise_repository_error(error)

    _set_private_headers(response)
    return ArtifactDeleteResponse(
        artifact_id=artifact_id,
        deleted=deleted,
    )
