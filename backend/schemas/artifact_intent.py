from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ArtifactIntentAction = Literal["create", "revise", "none"]
ArtifactIntentFormat = Literal["pdf", "docx", "pptx", "zip"]
ArtifactIntentSource = Literal["deterministic", "ai", "fallback"]


class ArtifactIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=12_000)
    has_attachment: bool = False
    attachment_names: list[str] = Field(default_factory=list, max_length=8)
    has_generated_artifact: bool = False

    @field_validator("message", mode="after")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Intent message cannot be empty.")
        return normalized

    @field_validator("attachment_names", mode="after")
    @classmethod
    def normalize_attachment_names(cls, values: list[str]) -> list[str]:
        return [
            normalized[:180]
            for value in values
            if (normalized := value.strip())
        ]


class ArtifactIntentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ArtifactIntentAction
    format: ArtifactIntentFormat | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=240)
    source: ArtifactIntentSource

