from pydantic import BaseModel

from schemas.chat import TokenUsage


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

    citations: list[DocumentCitation]
    metadata: DocumentMetadata

    request_id: str | None = None
    usage: TokenUsage
