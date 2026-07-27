from __future__ import annotations

import os
from pathlib import Path

from core.config import BASE_DIR


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
            f"{environment_name} must be an integer."
        ) from error

    if value < minimum or value > maximum:
        raise ValueError(
            f"{environment_name} must be between "
            f"{minimum} and {maximum}."
        )

    return value


def _storage_directory() -> Path:
    configured = os.getenv(
        "ARTIFACT_STORAGE_DIRECTORY",
        "",
    ).strip()

    if configured:
        return Path(configured).expanduser().resolve()

    return (
        BASE_DIR
        / "data"
        / "generated_artifacts"
    ).resolve()


class ArtifactSettings:
    """Artifact API limits and private storage configuration."""

    def __init__(self) -> None:
        self.storage_directory = (
            _storage_directory()
        )

        self.maximum_request_bytes = (
            _positive_int(
                "ARTIFACT_MAXIMUM_REQUEST_BYTES",
                2 * 1024 * 1024,
                minimum=16 * 1024,
                maximum=20 * 1024 * 1024,
            )
        )

        self.maximum_content_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_CONTENT_CHARACTERS",
                500_000,
                minimum=1_000,
                maximum=2_000_000,
            )
        )

        self.maximum_title_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_TITLE_CHARACTERS",
                240,
                minimum=20,
                maximum=500,
            )
        )

        self.maximum_subtitle_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_SUBTITLE_CHARACTERS",
                500,
                minimum=20,
                maximum=2_000,
            )
        )

        self.maximum_author_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_AUTHOR_CHARACTERS",
                160,
                minimum=20,
                maximum=500,
            )
        )

        self.retention_hours = (
            _positive_int(
                "ARTIFACT_RETENTION_HOURS",
                24,
                minimum=1,
                maximum=24 * 30,
            )
        )

        self.maximum_generated_file_bytes = (
            _positive_int(
                "ARTIFACT_MAXIMUM_GENERATED_FILE_BYTES",
                50 * 1024 * 1024,
                minimum=1 * 1024 * 1024,
                maximum=250 * 1024 * 1024,
            )
        )


artifact_settings = ArtifactSettings()