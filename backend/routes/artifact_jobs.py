from __future__ import annotations

import asyncio
from functools import lru_cache

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)

from artifacts.job_runner import (
    ArtifactJobRunner,
)
from artifacts.job_store import (
    ArtifactJobAccessError,
    ArtifactJobCapacityError,
    ArtifactJobConflictError,
    ArtifactJobExpiredError,
    ArtifactJobNotFoundError,
    ArtifactJobStorageError,
    ArtifactJobStore,
)
from core.artifact_job_rate_limit import (
    ArtifactJobRateLimitError,
    artifact_job_rate_limiter,
    resolve_artifact_job_client_key,
)
from routes.artifacts import (
    get_artifact_storage,
)
from routes.chat import (
    get_model_router,
)
from schemas.artifact_jobs import (
    ArtifactJobCreateRequest,
    ArtifactJobCreateResponse,
    ArtifactJobDeleteResponse,
    ArtifactJobStatusResponse,
)


router = APIRouter(
    prefix="/artifacts/jobs",
    tags=["artifact-jobs"],
)


_ACCESS_TOKEN_HEADER = (
    "X-Artifact-Job-Token"
)


@lru_cache(maxsize=1)
def get_artifact_job_store() -> (
    ArtifactJobStore
):
    return ArtifactJobStore()


@lru_cache(maxsize=1)
def get_artifact_job_runner() -> (
    ArtifactJobRunner
):
    return ArtifactJobRunner(
        job_store=(
            get_artifact_job_store()
        ),
        model_router=get_model_router(),
        artifact_storage=(
            get_artifact_storage()
        ),
    )


def _set_private_headers(
    response: Response,
) -> None:
    response.headers[
        "Cache-Control"
    ] = "private, no-store, max-age=0"

    response.headers[
        "Pragma"
    ] = "no-cache"

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"


def _require_access_token(
    access_token: str | None,
) -> str:
    if access_token is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Artifact job access token "
                "is required."
            ),
            headers={
                "WWW-Authenticate": (
                    "ArtifactJobToken"
                ),
            },
        )

    normalized = access_token.strip()

    if not normalized:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Artifact job access token "
                "is required."
            ),
            headers={
                "WWW-Authenticate": (
                    "ArtifactJobToken"
                ),
            },
        )

    return normalized


def _raise_job_lookup_error(
    error: Exception,
) -> None:
    if isinstance(
        error,
        ArtifactJobExpiredError,
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Artifact job has expired."
            ),
        ) from error

    if isinstance(
        error,
        ArtifactJobAccessError,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Artifact job access "
                "was denied."
            ),
        ) from error

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            "Artifact job was not found."
        ),
    ) from error


def _status_response(
    *,
    job_id: str,
    status_value: str,
    progress_percent: int,
    stage: str,
    created_at: object,
    updated_at: object,
    expires_at: object,
    artifact: object,
    error: str | None,
) -> ArtifactJobStatusResponse:
    return ArtifactJobStatusResponse(
        job_id=job_id,
        status=status_value,
        progress_percent=progress_percent,
        stage=stage,
        created_at=created_at,
        updated_at=updated_at,
        expires_at=expires_at,
        artifact=artifact,
        error=error,
    )


@router.post(
    "",
    response_model=ArtifactJobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_artifact_job(
    payload: ArtifactJobCreateRequest,
    request: Request,
    response: Response,
) -> ArtifactJobCreateResponse:
    client_key = (
        resolve_artifact_job_client_key(
            request
        )
    )

    try:
        artifact_job_rate_limiter.check(
            client_key
        )

    except ArtifactJobRateLimitError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Too many artifact jobs were "
                "created. Try again later."
            ),
            headers={
                "Retry-After": str(
                    error
                    .retry_after_seconds
                ),
            },
        ) from error

    job_store = (
        get_artifact_job_store()
    )

    try:
        job, access_token = (
            await asyncio.to_thread(
                job_store.create,
                payload,
            )
        )

    except ArtifactJobCapacityError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "The artifact generation "
                "queue is currently full."
            ),
            headers={
                "Retry-After": "60",
            },
        ) from error

    except ArtifactJobStorageError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The artifact job could "
                "not be created."
            ),
        ) from error

    try:
        get_artifact_job_runner().submit(
            job.job_id
        )

    except RuntimeError as error:
        try:
            await asyncio.to_thread(
                job_store.update,
                job.job_id,
                status="failed",
                progress_percent=100,
                stage=(
                    "Generation could "
                    "not be started"
                ),
                error=(
                    "The server could not "
                    "start the background "
                    "artifact task."
                ),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The artifact job could "
                "not be started."
            ),
        ) from error

    _set_private_headers(
        response
    )

    return ArtifactJobCreateResponse(
        job_id=job.job_id,
        status=job.status,
        access_token=access_token,
        created_at=job.created_at,
        expires_at=job.expires_at,
        status_url=(
            f"/api/v1/artifacts/jobs/"
            f"{job.job_id}"
        ),
        message=(
            "Artifact generation "
            "job accepted."
        ),
    )


@router.get(
    "/{job_id}",
    response_model=ArtifactJobStatusResponse,
)
async def get_artifact_job_status(
    job_id: str,
    response: Response,
    access_token: str | None = Header(
        default=None,
        alias=_ACCESS_TOKEN_HEADER,
    ),
) -> ArtifactJobStatusResponse:
    token = _require_access_token(
        access_token
    )

    try:
        job = await asyncio.to_thread(
            get_artifact_job_store().get,
            job_id,
            token,
        )

    except (
        ArtifactJobNotFoundError,
        ArtifactJobExpiredError,
        ArtifactJobAccessError,
    ) as error:
        _raise_job_lookup_error(
            error
        )

    except ArtifactJobStorageError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Artifact job status "
                "could not be read."
            ),
        ) from error

    _set_private_headers(
        response
    )

    return _status_response(
        job_id=job.job_id,
        status_value=job.status,
        progress_percent=(
            job.progress_percent
        ),
        stage=job.stage,
        created_at=job.created_at,
        updated_at=job.updated_at,
        expires_at=job.expires_at,
        artifact=job.artifact,
        error=job.error,
    )


@router.delete(
    "/{job_id}",
    response_model=ArtifactJobDeleteResponse,
)
async def delete_artifact_job(
    job_id: str,
    response: Response,
    access_token: str | None = Header(
        default=None,
        alias=_ACCESS_TOKEN_HEADER,
    ),
) -> ArtifactJobDeleteResponse:
    token = _require_access_token(
        access_token
    )

    try:
        deleted = await asyncio.to_thread(
            get_artifact_job_store().delete,
            job_id,
            token,
        )

    except ArtifactJobConflictError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "An active artifact job "
                "cannot be deleted."
            ),
        ) from error

    except (
        ArtifactJobNotFoundError,
        ArtifactJobExpiredError,
        ArtifactJobAccessError,
    ) as error:
        _raise_job_lookup_error(
            error
        )

    except ArtifactJobStorageError as error:
        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Artifact job could "
                "not be deleted."
            ),
        ) from error

    _set_private_headers(
        response
    )

    return ArtifactJobDeleteResponse(
        job_id=job_id,
        deleted=deleted,
    )


def recover_interrupted_artifact_jobs(
) -> int:
    """
    Mark jobs left active by a previous
    application process as interrupted.
    """

    return (
        get_artifact_job_store()
        .recover_interrupted_jobs()
    )


async def shutdown_artifact_job_runner(
) -> None:
    """
    Stop active in-process artifact tasks
    during application shutdown.
    """

    await (
        get_artifact_job_runner()
        .shutdown()
    )