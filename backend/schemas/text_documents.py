from typing import Literal

from pydantic import BaseModel

from schemas.chat import TokenUsage


TextDocumentType = Literal[
    "docx",
    "text",
    "markdown",
    "json",
    "source_code",
]


TextSourceKind = Literal[
    "section",
    "table",
    "lines",
]


class TextDocumentCitation(BaseModel):
    source_id: str
    label: str
    kind: TextSourceKind


class TextDocumentMetadata(BaseModel):
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    created: str | None = None
    modified: str | None = None


class TextDocumentResponse(BaseModel):
    answer: str

    provider: str
    model: str

    filename: str
    mime_type: str
    size_bytes: int
    document_type: TextDocumentType

    extracted_characters: int
    source_count: int
    selected_sources: list[str]

    citations: list[
        TextDocumentCitation
    ]

    metadata: TextDocumentMetadata

    request_id: str | None = None
    usage: TokenUsage
