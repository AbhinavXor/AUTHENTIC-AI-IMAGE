from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from schemas.artifacts import (
    ArtifactApiFormat,
    ArtifactGenerateResponse,
)


ArtifactTone = Literal[
    "professional",
    "executive",
    "technical",
    "simple",
    "academic",
]

ArtifactLength = Literal[
    "brief",
    "standard",
    "detailed",
]


class ArtifactComposeRequest(
    BaseModel,
):
    """
    Natural-language request used to compose
    and generate a professional artifact.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    prompt: str = Field(
        min_length=1,
        max_length=8_000,
        description=(
            "Natural-language instruction describing "
            "the artifact that should be created."
        ),
    )

    format: ArtifactApiFormat = "pdf"

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=240,
    )

    subtitle: str | None = Field(
        default=None,
        max_length=500,
    )

    author: str | None = Field(
        default="Authentic AI",
        max_length=160,
    )

    filename: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
    )

    tone: ArtifactTone = "professional"

    length: ArtifactLength = "standard"

    language: str = Field(
        default="English",
        min_length=2,
        max_length=80,
    )

    include_executive_summary: bool = True

    include_table: bool = True

    include_recommendations: bool = True

    include_conclusion: bool = True

    @field_validator(
        "prompt",
        mode="after",
    )
    @classmethod
    def validate_prompt(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Artifact prompt cannot be empty."
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

    @field_validator(
        "language",
        mode="after",
    )
    @classmethod
    def validate_language(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Artifact language cannot be empty."
            )

        return normalized


class ArtifactComposeResponse(
    ArtifactGenerateResponse,
):
    """
    Generated artifact response with
    AI composition metadata.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    provider: str = Field(
        min_length=1,
        max_length=80,
    )

    model: str = Field(
        min_length=1,
        max_length=160,
    )

    request_id: str | None = None

    draft_character_count: int = Field(
        ge=1,
    )

    composition_mode: Literal[
        "ai_prompt_to_artifact"
    ] = "ai_prompt_to_artifact"