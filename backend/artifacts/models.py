from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias

ArtifactFormat = Literal["pdf", "docx", "pptx", "zip"]

LayoutFamily = Literal[
    "executive_report",
    "research_paper",
    "academic_textbook",
    "technical_spec",
    "proposal_document",
    "data_report",
    "case_study",
    "modern_summary",
]

BrandingMode = Literal[
    "none",
    "title_only",
    "subtle",
    "full",
]

VisualDensity = Literal[
    "compact",
    "balanced",
    "spacious",
]

HeaderMode = Literal[
    "none",
    "minimal",
    "running_section",
]

FooterMode = Literal[
    "none",
    "page_number",
    "page_number_and_title",
]


@dataclass(frozen=True, slots=True)
class ArtifactLayoutBrief:
    """Resolved document design intent used by renderers.

    The brief is deliberately deterministic and serializable. It expresses
    *how* a document should be presented without changing the source content.
    """

    family: LayoutFamily = "modern_summary"
    branding_mode: BrandingMode = "none"
    visual_density: VisualDensity = "balanced"
    header_mode: HeaderMode = "minimal"
    footer_mode: FooterMode = "page_number"
    include_table_of_contents: bool = True
    include_section_openers: bool = True
    use_landscape_for_wide_tables: bool = True
    cover_show_profile: bool = False
    cover_show_author: bool = False
    cover_show_subtitle: bool = False
    cover_show_date: bool = False
    cover_eyebrow: str | None = None
    rationale: tuple[str, ...] = field(default_factory=tuple)
    architecture_id: str = "technical_proposal_and_portfolio.accessible_reading.comprehensive"
    visual_system: str = "accessible_reading"
    architecture_mode: str = "safe_fallback"
    domain_overlay: str = "general_engineering"
    page_strategy: tuple[str, ...] = field(default_factory=tuple)
    page_limit: int | None = None


@dataclass(frozen=True, slots=True)
class ParagraphBlock:
    text: str


@dataclass(frozen=True, slots=True)
class QuoteBlock:
    text: str
    attribution: str | None = None


@dataclass(frozen=True, slots=True)
class CalloutBlock:
    title: str
    text: str
    kind: Literal[
        "info",
        "warning",
        "success",
        "assumption",
    ] = "info"


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
        "scatter",
        "area",
        "unit_circle",
        "slope_field",
    ] = "line"
    caption: str | None = None
    x_label: str | None = None
    y_label: str | None = None


@dataclass(frozen=True, slots=True)
class CodeBlock:
    code: str
    language: str = ""


@dataclass(frozen=True, slots=True)
class EquationBlock:
    expression: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class DiagramBlock:
    title: str
    steps: tuple[str, ...]
    orientation: Literal["vertical", "horizontal"] = "vertical"


@dataclass(frozen=True, slots=True)
class PageBreakBlock:
    reason: str = "author_requested"


ArtifactBlock: TypeAlias = (
    ParagraphBlock
    | QuoteBlock
    | CalloutBlock
    | BulletListBlock
    | TableBlock
    | ChartBlock
    | CodeBlock
    | EquationBlock
    | DiagramBlock
    | PageBreakBlock
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
    bundle_volume_count: int = 1
    layout_brief: ArtifactLayoutBrief = field(
        default_factory=ArtifactLayoutBrief
    )


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    format: ArtifactFormat
    path: Path
    size_bytes: int
    page_or_slide_count: int
