from __future__ import annotations

import math
import time
from collections import deque
from threading import RLock

from fastapi import Request

from core.artifact_job_settings import (
    artifact_job_settings,
)


class ArtifactJobRateLimitError(
    RuntimeError
):
    """
    Raised when a client creates too many
    background artifact jobs.
    """

    def __init__(
        self,
        retry_after_seconds: int,
    ) -> None:
        self.retry_after_seconds = max(
            1,
            retry_after_seconds,
        )

        super().__init__(
            (
                "Artifact job rate limit "
                "was reached."
            )
        )


class ArtifactJobRateLimiter:
    """
    Process-local sliding-window limiter for
    background artifact job creation.

    This is a baseline protection layer.
    A shared production limiter can later
    replace it without changing the API.
    """

    def __init__(
        self,
        *,
        maximum_requests: int,
        window_seconds: int,
    ) -> None:
        if maximum_requests < 1:
            raise ValueError(
                (
                    "Maximum rate-limit "
                    "requests must be positive."
                )
            )

        if window_seconds < 1:
            raise ValueError(
                (
                    "Rate-limit window "
                    "must be positive."
                )
            )

        self.maximum_requests = (
            maximum_requests
        )

        self.window_seconds = (
            window_seconds
        )

        self._buckets: dict[
            str,
            deque[float],
        ] = {}

        self._lock = RLock()

        self._last_full_cleanup = (
            time.monotonic()
        )

    def _remove_expired_entries(
        self,
        bucket: deque[float],
        *,
        now: float,
    ) -> None:
        cutoff = (
            now
            - self.window_seconds
        )

        while (
            bucket
            and bucket[0] <= cutoff
        ):
            bucket.popleft()

    def _cleanup_stale_buckets(
        self,
        *,
        now: float,
    ) -> None:
        """
        Perform a full cleanup at most once
        per minute to control memory usage.
        """

        if (
            now
            - self._last_full_cleanup
            < 60
        ):
            return

        stale_keys: list[str] = []

        for key, bucket in (
            self._buckets.items()
        ):
            self._remove_expired_entries(
                bucket,
                now=now,
            )

            if not bucket:
                stale_keys.append(
                    key
                )

        for key in stale_keys:
            self._buckets.pop(
                key,
                None,
            )

        self._last_full_cleanup = now

    def check(
        self,
        client_key: str,
    ) -> None:
        normalized_key = (
            client_key.strip()
            or "unknown-client"
        )[:160]

        now = time.monotonic()

        with self._lock:
            self._cleanup_stale_buckets(
                now=now,
            )

            bucket = (
                self._buckets
                .setdefault(
                    normalized_key,
                    deque(),
                )
            )

            self._remove_expired_entries(
                bucket,
                now=now,
            )

            if (
                len(bucket)
                >= self.maximum_requests
            ):
                oldest_request = (
                    bucket[0]
                )

                retry_after = math.ceil(
                    (
                        oldest_request
                        + self.window_seconds
                    )
                    - now
                )

                raise (
                    ArtifactJobRateLimitError(
                        retry_after
                    )
                )

            bucket.append(
                now
            )


def resolve_artifact_job_client_key(
    request: Request,
) -> str:
    """
    Resolve a stable client key without
    trusting user-controlled forwarding
    headers directly.
    """

    client = request.client

    if client is None:
        return "unknown-client"

    host = client.host.strip()

    return host or "unknown-client"


artifact_job_rate_limiter = (
    ArtifactJobRateLimiter(
        maximum_requests=(
            artifact_job_settings
            .maximum_jobs_per_window
        ),
        window_seconds=(
            artifact_job_settings
            .rate_limit_window_seconds
        ),
    )
)