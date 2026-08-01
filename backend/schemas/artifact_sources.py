from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.artifact_settings import artifact_settings
from schemas.artifacts import (
    ArtifactSourceKind,
    ArtifactSourceReference,
)


class ArtifactTextSourceCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    content: str = Field(
        min_length=1,
        max_length=artifact_settings.maximum_source_characters,
    )
    summary: str = Field(min_length=1, max_length=2_000)
    kind: ArtifactSourceKind = "explicit_prompt"
    message_ids: list[str] = Field(default_factory=list, max_length=32)
    attachment_names: list[str] = Field(default_factory=list, max_length=16)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ArtifactSourceCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: ArtifactSourceReference
    summary: str
    source_characters: int = Field(ge=1)
    created_at: datetime
    expires_at: datetime
