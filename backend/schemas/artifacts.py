from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    "zip",
]

ArtifactSourceKind = Literal[
    "explicit_prompt",
    "previous_response",
    "conversation",
    "uploaded_file",
    "artifact_version",
    "project_context",
]

ArtifactDocumentType = Literal[
    "professional_report",
    "executive_brief",
    "technical_specification",
    "research_report",
    "proposal",
    "policy_document",
    "presentation",
    "general_document",
    "academic_textbook",
    "data_report",
    "case_study",
    "modern_summary",
]

ArtifactLayoutFamily = Literal[
    "auto",
    "executive_report",
    "research_paper",
    "academic_textbook",
    "technical_spec",
    "proposal_document",
    "data_report",
    "case_study",
    "modern_summary",
]

ArtifactBrandingMode = Literal[
    "none",
    "title_only",
    "subtle",
    "full",
]

ArtifactVisualDensity = Literal[
    "auto",
    "compact",
    "balanced",
    "spacious",
]

ArtifactPresentationTier = Literal[
    "auto",
    "standard",
    "professional",
    "premium",
]

ArtifactArchitectureVisualSystem = Literal[
    "auto",
    "minimal_academic",
    "classic_university",
    "modern_engineering",
    "technical_grid",
    "formal_research",
    "data_rich_analytical",
    "visual_learning",
    "code_first_technical",
    "print_optimized_monochrome",
    "accessible_reading",
]

ArtifactHeaderMode = Literal[
    "auto",
    "none",
    "minimal",
    "running_section",
]

ArtifactFooterMode = Literal[
    "none",
    "page_number",
    "page_number_and_title",
]


class ArtifactSourceSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    kind: ArtifactSourceKind = "explicit_prompt"
    summary: str = Field(
        min_length=1,
        max_length=2_000,
    )
    content: str | None = Field(
        default=None,
        max_length=(
            artifact_settings
            .maximum_source_characters
        ),
    )
    message_ids: list[str] = Field(
        default_factory=list,
        max_length=32,
    )
    attachment_names: list[str] = Field(
        default_factory=list,
        max_length=16,
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )


class ArtifactSourceReference(BaseModel):
    """Capability reference for a durable private artifact source."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    source_id: str = Field(
        min_length=32,
        max_length=32,
    )
    access_token: str = Field(
        min_length=32,
        max_length=256,
    )


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
            "Markdown-like source content used to build the artifact."
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
    )
    source_snapshot: ArtifactSourceSnapshot | None = None
    document_type: ArtifactDocumentType = "professional_report"
    purpose: str | None = Field(default=None, max_length=1_000)
    audience: str | None = Field(default=None, max_length=500)
    layout_family: ArtifactLayoutFamily = "auto"
    branding_mode: ArtifactBrandingMode = "none"
    visual_density: ArtifactVisualDensity = "auto"
    presentation_tier: ArtifactPresentationTier = "auto"
    header_mode: ArtifactHeaderMode = "auto"
    footer_mode: ArtifactFooterMode = "none"
    include_table_of_contents: bool = True
    include_section_openers: bool = True
    include_cover_date: bool = False
    include_cover_profile: bool = False
    include_document_label: bool = False
    include_cover_subtitle: bool = False
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    @field_validator("content", mode="after")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Artifact content cannot be empty.")
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


class ArtifactQualitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "passed",
        "passed_with_warnings",
        "failed",
    ] = "passed"
    page_or_slide_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    issues: list[dict[str, Any]] = Field(default_factory=list)


class ArtifactGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    access_token: str = Field(min_length=32, max_length=256)
    filename: str
    title: str
    format: ArtifactApiFormat
    media_type: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    download_url: str
    version: int = Field(ge=1)
    version_count: int = Field(ge=1)
    page_or_slide_count: int = Field(default=0, ge=0)
    validation: ArtifactQualitySummary


class ArtifactMetadataResponse(ArtifactGenerateResponse):
    model_config = ConfigDict(extra="forbid")


class ArtifactSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    version: int = Field(ge=1)
    title: str
    filename: str
    kind: ArtifactSourceKind
    summary: str = Field(min_length=1, max_length=2_000)
    content: str = Field(
        min_length=1,
        max_length=(
            artifact_settings
            .maximum_source_characters
        ),
    )
    message_ids: list[str] = Field(
        default_factory=list,
        max_length=32,
    )
    attachment_names: list[str] = Field(
        default_factory=list,
        max_length=16,
    )
    confidence: float = Field(ge=0.0, le=1.0)
    recovered_from: Literal[
        "source_snapshot",
        "artifact_version",
    ]


class ArtifactRenameRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    filename: str = Field(min_length=1, max_length=180)
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )


class ArtifactRevisionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    instruction: str = Field(
        min_length=1,
        max_length=(
            artifact_settings
            .maximum_prompt_characters
        ),
    )
    title: str | None = Field(default=None, min_length=1, max_length=240)
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )


class ArtifactExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: ArtifactApiFormat
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )


class ArtifactRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )


class ArtifactDuplicateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    filename: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
    )
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )


class ArtifactVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    filename: str
    format: ArtifactApiFormat
    media_type: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: datetime
    expires_at: datetime
    page_or_slide_count: int = Field(default=0, ge=0)
    validation: ArtifactQualitySummary
    is_current: bool
    download_url: str


class ArtifactVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    current_version: int = Field(ge=1)
    versions: list[ArtifactVersionResponse]


class ArtifactAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    timestamp: datetime
    detail: dict[str, Any] = Field(default_factory=dict)


class ArtifactAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    events: list[ArtifactAuditEvent]


class ArtifactDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    deleted: bool
