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


def _boolean(
    environment_name: str,
    default: bool,
) -> bool:
    raw_value = os.getenv(
        environment_name,
        "true" if default else "false",
    ).strip().casefold()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{environment_name} must be a boolean value."
    )


class ArtifactSettings:
    """Artifact API limits and private storage configuration."""

    def __init__(self) -> None:
        self.storage_directory = (
            _storage_directory()
        )

        self.source_storage_directory = (
            self.storage_directory.parent
            / "artifact_sources"
        ).resolve()

        self.maximum_request_bytes = (
            _positive_int(
                "ARTIFACT_MAXIMUM_REQUEST_BYTES",
                64 * 1024 * 1024,
                minimum=16 * 1024,
                maximum=256 * 1024 * 1024,
            )
        )

        self.maximum_prompt_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_PROMPT_CHARACTERS",
                4_000_000,
                minimum=8_000,
                maximum=8_000_000,
            )
        )

        # Durable sources use a separate budget so page-rich uploads are not
        # forced into the much smaller instruction/provider prompt channel.
        # Sources beyond the single-document threshold are handled by the
        # existing multi-volume PDF planner instead of being rejected early.
        self.maximum_source_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_SOURCE_CHARACTERS",
                16_000_000,
                minimum=50_000,
                maximum=64_000_000,
            )
        )

        # Provider prompts are deliberately much smaller than accepted
        # source payloads. Large sources live in the source vault and are
        # streamed through bounded composition passes instead of being
        # duplicated inside one model request.
        self.provider_prompt_budget_characters = (
            _positive_int(
                "ARTIFACT_PROVIDER_PROMPT_BUDGET_CHARACTERS",
                24_000,
                minimum=6_000,
                maximum=120_000,
            )
        )

        self.compact_prompt_budget_characters = (
            _positive_int(
                "ARTIFACT_COMPACT_PROMPT_BUDGET_CHARACTERS",
                12_000,
                minimum=4_000,
                maximum=48_000,
            )
        )

        self.maximum_compiled_instruction_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_COMPILED_INSTRUCTION_CHARACTERS",
                2_400,
                minimum=600,
                maximum=12_000,
            )
        )

        self.large_source_chunk_characters = (
            _positive_int(
                "ARTIFACT_LARGE_SOURCE_CHUNK_CHARACTERS",
                9_000,
                minimum=2_000,
                maximum=24_000,
            )
        )

        self.pdf_bundle_source_characters = (
            _positive_int(
                "ARTIFACT_PDF_BUNDLE_SOURCE_CHARACTERS",
                4_000_000,
                minimum=50_000,
                maximum=8_000_000,
            )
        )

        self.maximum_pdf_bundle_volumes = (
            _positive_int(
                "ARTIFACT_MAXIMUM_PDF_BUNDLE_VOLUMES",
                12,
                minimum=2,
                maximum=24,
            )
        )

        self.maximum_content_characters = (
            _positive_int(
                "ARTIFACT_MAXIMUM_CONTENT_CHARACTERS",
                16_000_000,
                minimum=1_000,
                maximum=64_000_000,
            )
        )

        self.maximum_single_pdf_pages = (
            _positive_int(
                "ARTIFACT_MAXIMUM_SINGLE_PDF_PAGES",
                320,
                minimum=50,
                maximum=1_000,
            )
        )

        # Disabled by default: document length follows source content. The
        # value above remains available as an opt-in operational safety
        # threshold for constrained deployments, not a product page cap.
        self.enforce_single_pdf_page_limit = _boolean(
            "ARTIFACT_ENFORCE_SINGLE_PDF_PAGE_LIMIT",
            False,
        )

        self.pdf_target_words_per_page = (
            _positive_int(
                "ARTIFACT_PDF_TARGET_WORDS_PER_PAGE",
                285,
                minimum=180,
                maximum=500,
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

        self.cleanup_interval_seconds = (
            _positive_int(
                "ARTIFACT_CLEANUP_INTERVAL_SECONDS",
                15 * 60,
                minimum=60,
                maximum=24 * 60 * 60,
            )
        )

        self.maximum_operations_per_window = (
            _positive_int(
                "ARTIFACT_OPERATION_RATE_LIMIT_REQUESTS",
                120,
                minimum=1,
                maximum=10_000,
            )
        )

        self.operation_rate_limit_window_seconds = (
            _positive_int(
                "ARTIFACT_OPERATION_RATE_LIMIT_WINDOW_SECONDS",
                60 * 60,
                minimum=60,
                maximum=24 * 60 * 60,
            )
        )

        self.maximum_generated_file_bytes = (
            _positive_int(
                "ARTIFACT_MAXIMUM_GENERATED_FILE_BYTES",
                512 * 1024 * 1024,
                minimum=1 * 1024 * 1024,
                maximum=1024 * 1024 * 1024,
            )
        )


artifact_settings = ArtifactSettings()
