from __future__ import annotations

import os
from pathlib import Path

from core.artifact_settings import (
    artifact_settings,
)


def _positive_int(
    environment_name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(
        environment_name,
        str(default),
    ).strip()

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(
            (
                f"{environment_name} "
                "must be an integer."
            )
        ) from error

    if (
        value < minimum
        or value > maximum
    ):
        raise ValueError(
            (
                f"{environment_name} must "
                f"be between {minimum} "
                f"and {maximum}."
            )
        )

    return value


def _job_storage_directory() -> Path:
    configured = os.getenv(
        "ARTIFACT_JOB_STORAGE_DIRECTORY",
        "",
    ).strip()

    if configured:
        return (
            Path(configured)
            .expanduser()
            .resolve()
        )

    return (
        artifact_settings
        .storage_directory
        / "_jobs"
    ).resolve()


class ArtifactJobSettings:
    """
    Configuration for background artifact
    composition and generation jobs.
    """

    def __init__(self) -> None:
        self.storage_directory = (
            _job_storage_directory()
        )

        self.maximum_concurrent_jobs = (
            _positive_int(
                (
                    "ARTIFACT_JOB_MAXIMUM_"
                    "CONCURRENT_JOBS"
                ),
                2,
                minimum=1,
                maximum=8,
            )
        )

        self.maximum_queued_jobs = (
            _positive_int(
                (
                    "ARTIFACT_JOB_MAXIMUM_"
                    "QUEUED_JOBS"
                ),
                50,
                minimum=1,
                maximum=500,
            )
        )

        self.retention_hours = (
            _positive_int(
                (
                    "ARTIFACT_JOB_"
                    "RETENTION_HOURS"
                ),
                24,
                minimum=1,
                maximum=24 * 30,
            )
        )

        self.maximum_jobs_per_window = (
            _positive_int(
                (
                    "ARTIFACT_JOB_RATE_"
                    "LIMIT_REQUESTS"
                ),
                12,
                minimum=1,
                maximum=1_000,
            )
        )

        self.rate_limit_window_seconds = (
            _positive_int(
                (
                    "ARTIFACT_JOB_RATE_"
                    "LIMIT_WINDOW_SECONDS"
                ),
                60 * 60,
                minimum=60,
                maximum=24 * 60 * 60,
            )
        )

        self.access_token_bytes = (
            _positive_int(
                (
                    "ARTIFACT_JOB_ACCESS_"
                    "TOKEN_BYTES"
                ),
                32,
                minimum=24,
                maximum=64,
            )
        )

        self.maximum_error_characters = (
            _positive_int(
                (
                    "ARTIFACT_JOB_MAXIMUM_"
                    "ERROR_CHARACTERS"
                ),
                1_000,
                minimum=100,
                maximum=5_000,
            )
        )


artifact_job_settings = (
    ArtifactJobSettings()
)