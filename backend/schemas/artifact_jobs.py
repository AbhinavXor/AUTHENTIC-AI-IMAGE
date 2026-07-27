from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from schemas.artifact_composer import (
    ArtifactComposeRequest,
    ArtifactComposeResponse,
)


ArtifactJobStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
]


class ArtifactJobCreateRequest(
    ArtifactComposeRequest
):
    """
    Request accepted by the asynchronous
    prompt-to-artifact generation endpoint.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ArtifactJobCreateResponse(BaseModel):
    """
    Initial response returned immediately
    after a background job is accepted.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    job_id: str = Field(
        min_length=32,
        max_length=32,
    )

    status: ArtifactJobStatus

    access_token: str = Field(
        min_length=32,
        max_length=256,
    )

    created_at: datetime
    expires_at: datetime

    status_url: str

    message: str = (
        "Artifact generation job accepted."
    )


class ArtifactJobStatusResponse(BaseModel):
    """
    Current background artifact job status.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    job_id: str = Field(
        min_length=32,
        max_length=32,
    )

    status: ArtifactJobStatus

    progress_percent: int = Field(
        ge=0,
        le=100,
    )

    stage: str = Field(
        min_length=1,
        max_length=160,
    )

    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    artifact: (
        ArtifactComposeResponse
        | None
    ) = None

    error: str | None = Field(
        default=None,
        max_length=5_000,
    )


class ArtifactJobDeleteResponse(BaseModel):
    """
    Response returned after a completed or
    failed background job record is removed.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    job_id: str = Field(
        min_length=32,
        max_length=32,
    )

    deleted: bool