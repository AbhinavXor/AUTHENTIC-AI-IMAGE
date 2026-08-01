from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from core.artifact_settings import artifact_settings
from schemas.artifacts import (
    ArtifactArchitectureVisualSystem,
    ArtifactApiFormat,
    ArtifactBrandingMode,
    ArtifactDocumentType,
    ArtifactFooterMode,
    ArtifactGenerateResponse,
    ArtifactHeaderMode,
    ArtifactLayoutFamily,
    ArtifactPresentationTier,
    ArtifactSourceSnapshot,
    ArtifactSourceReference,
    ArtifactVisualDensity,
)

ArtifactPromptMode = Literal[
    "auto",
    "standard",
    "compact",
]

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


class ArtifactComposeRequest(BaseModel):
    """Natural-language request for a professional artifact."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    prompt: str = Field(
        min_length=1,
        max_length=(
            artifact_settings
            .maximum_prompt_characters
        ),
    )
    format: ArtifactApiFormat = "pdf"
    title: str | None = Field(default=None, min_length=1, max_length=240)
    subtitle: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=160)
    filename: str | None = Field(default=None, min_length=1, max_length=180)
    tone: ArtifactTone = "professional"
    length: ArtifactLength = "standard"
    language: str = Field(default="English", min_length=2, max_length=80)
    document_type: ArtifactDocumentType = "professional_report"
    purpose: str | None = Field(default=None, max_length=1_000)
    audience: str | None = Field(default=None, max_length=500)
    layout_family: ArtifactLayoutFamily = "auto"
    branding_mode: ArtifactBrandingMode = "none"
    visual_density: ArtifactVisualDensity = "auto"
    presentation_tier: ArtifactPresentationTier = "auto"
    architecture_visual_system: ArtifactArchitectureVisualSystem = "auto"
    previous_architecture_id: str | None = Field(
        default=None,
        min_length=5,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    )
    design_revision: bool = False
    header_mode: ArtifactHeaderMode = "auto"
    footer_mode: ArtifactFooterMode = "none"
    include_table_of_contents: bool = True
    include_section_openers: bool = True
    include_cover_date: bool = False
    include_cover_profile: bool = False
    include_document_label: bool = False
    include_cover_subtitle: bool = False
    source_snapshot: ArtifactSourceSnapshot | None = None
    source_ref: ArtifactSourceReference | None = None
    profile_id: str = Field(
        default="auto",
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    )
    prompt_mode: ArtifactPromptMode = "auto"
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )
    include_executive_summary: bool = True
    include_table: bool = True
    include_recommendations: bool = True
    include_conclusion: bool = True
    bundle_volume_count: int | None = Field(
        default=None,
        ge=2,
        le=(
            artifact_settings
            .maximum_pdf_bundle_volumes
        ),
    )

    @field_validator("prompt", mode="after")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Artifact prompt cannot be empty.")
        return normalized

    @field_validator(
        "title",
        "subtitle",
        "author",
        "filename",
        "purpose",
        "audience",
        "idempotency_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("language", mode="after")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Artifact language cannot be empty.")
        return normalized


class ArtifactComposeResponse(ArtifactGenerateResponse):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    request_id: str | None = None
    draft_character_count: int = Field(ge=1)
    composition_mode: Literal[
        "ai_prompt_to_artifact"
    ] = "ai_prompt_to_artifact"
