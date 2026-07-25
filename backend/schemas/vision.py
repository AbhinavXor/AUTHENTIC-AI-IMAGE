from pydantic import BaseModel

from schemas.chat import TokenUsage


class VisionResponse(BaseModel):
    answer: str
    provider: str
    model: str

    filename: str
    mime_type: str
    image_format: str
    width: int
    height: int
    size_bytes: int

    request_id: str | None = None
    usage: TokenUsage
