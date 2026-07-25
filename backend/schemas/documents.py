from typing import Literal

from pydantic import BaseModel

from schemas.chat import TokenUsage


DocumentAnalysisMode = Literal[
    "text",
    "vision_ocr",
]


class DocumentMetadata(BaseModel):
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None


class DocumentCitation(BaseModel):
    page: int
    label: str


class DocumentResponse(BaseModel):
    answer: str

    provider: str
    model: str

    filename: str
    mime_type: str
    size_bytes: int

    page_count: int
    extracted_characters: int
    selected_pages: list[int]

    analysis_mode: DocumentAnalysisMode
    ocr_pages: list[int]

    citations: list[DocumentCitation]
    metadata: DocumentMetadata

    request_id: str | None = None
    usage: TokenUsage
