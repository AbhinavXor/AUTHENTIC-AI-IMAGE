from dataclasses import dataclass
from typing import Literal


StreamKind = Literal[
    "token",
    "done",
]


@dataclass(frozen=True, slots=True)
class StreamDelta:
    """Provider-neutral streaming response event."""

    kind: StreamKind
    content: str = ""
    provider: str = ""
    model: str = ""
