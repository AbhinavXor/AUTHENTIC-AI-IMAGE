from __future__ import annotations

from fastapi import Request

from core.artifact_job_rate_limit import (
    ArtifactJobRateLimitError,
    ArtifactJobRateLimiter,
)
from core.artifact_settings import artifact_settings


ArtifactOperationRateLimitError = ArtifactJobRateLimitError


artifact_operation_rate_limiter = ArtifactJobRateLimiter(
    maximum_requests=artifact_settings.maximum_operations_per_window,
    window_seconds=artifact_settings.operation_rate_limit_window_seconds,
)


def resolve_artifact_operation_client_key(request: Request) -> str:
    client = request.client
    if client is None:
        return "unknown-client"
    host = client.host.strip()
    return host or "unknown-client"
