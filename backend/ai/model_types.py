from dataclasses import dataclass
from typing import Literal


StreamKind = Literal[
    "token",
    "done",
]


@dataclass(frozen=True, slots=True)
class StreamDelta:
    kind: StreamKind
    content: str = ""
    provider: str = ""
    model: str = ""
    category: str = ""
    routing_confidence: float = 0.0
