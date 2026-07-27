from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias


ArtifactFormat = Literal[
    "pdf",
    "docx",
    "pptx",
]


@dataclass(frozen=True, slots=True)
class ParagraphBlock:
    text: str


@dataclass(frozen=True, slots=True)
class BulletListBlock:
    items: tuple[str, ...]
    ordered: bool = False


@dataclass(frozen=True, slots=True)
class TableBlock:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    caption: str | None = None


@dataclass(frozen=True, slots=True)
class ChartSeries:
    name: str
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ChartBlock:
    title: str
    labels: tuple[str, ...]
    series: tuple[ChartSeries, ...]
    chart_type: Literal[
        "line",
        "bar",
        "pie",
    ] = "line"
    caption: str | None = None


@dataclass(frozen=True, slots=True)
class CodeBlock:
    code: str
    language: str = ""


ArtifactBlock: TypeAlias = (
    ParagraphBlock
    | BulletListBlock
    | TableBlock
    | ChartBlock
    | CodeBlock
)


@dataclass(frozen=True, slots=True)
class ArtifactSection:
    title: str
    level: int
    blocks: tuple[ArtifactBlock, ...]


@dataclass(frozen=True, slots=True)
class ArtifactDocument:
    title: str
    subtitle: str | None
    author: str | None
    sections: tuple[ArtifactSection, ...]


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    format: ArtifactFormat
    path: Path
    size_bytes: int
    page_or_slide_count: int
