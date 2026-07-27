from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from core.artifact_settings import artifact_settings


ArtifactApiFormat = Literal[
    "pdf",
    "docx",
    "pptx",
]


class ArtifactGenerateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    content: str = Field(
        min_length=1,
        max_length=(
            artifact_settings
            .maximum_content_characters
        ),
        description=(
            "Markdown-like source content used to "
            "build the artifact."
        ),
    )

    format: ArtifactApiFormat

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=(
            artifact_settings
            .maximum_title_characters
        ),
    )

    subtitle: str | None = Field(
        default=None,
        max_length=(
            artifact_settings
            .maximum_subtitle_characters
        ),
    )

    author: str | None = Field(
        default=None,
        max_length=(
            artifact_settings
            .maximum_author_characters
        ),
    )

    filename: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
        description=(
            "Optional preferred filename. The backend "
            "sanitizes it and applies the requested extension."
        ),
    )

    @field_validator(
        "content",
        mode="after",
    )
    @classmethod
    def validate_content(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Artifact content cannot be empty."
            )

        return normalized

    @field_validator(
        "title",
        "subtitle",
        "author",
        "filename",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            return value

        normalized = value.strip()

        return normalized or None


class ArtifactGenerateResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    artifact_id: str

    filename: str
    format: ArtifactApiFormat
    media_type: str

    size_bytes: int = Field(
        ge=1,
    )

    sha256: str = Field(
        min_length=64,
        max_length=64,
    )

    created_at: datetime
    expires_at: datetime

    download_url: str


class ArtifactMetadataResponse(
    ArtifactGenerateResponse
):
    model_config = ConfigDict(
        extra="forbid",
    )


class ArtifactDeleteResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    artifact_id: str
    deleted: bool