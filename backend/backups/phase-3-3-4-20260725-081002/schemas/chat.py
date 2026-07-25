from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class ChatMessage(BaseModel):
    role: Literal[
        "user",
        "assistant",
    ]

    content: str = Field(
        min_length=1,
        max_length=8_000,
    )

    @field_validator("content")
    @classmethod
    def normalize_content(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Message content cannot be empty."
            )

        return normalized


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=8_000,
    )

    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=16,
    )

    @field_validator("message")
    @classmethod
    def normalize_message(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Question cannot be empty."
            )

        return normalized


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    answer: str

    provider: str = Field(
        default="groq",
        min_length=1,
        max_length=40,
    )

    model: str
    request_id: str | None = None
    usage: TokenUsage
