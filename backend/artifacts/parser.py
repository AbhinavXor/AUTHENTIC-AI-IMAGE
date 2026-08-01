from __future__ import annotations

import re
from dataclasses import dataclass, replace

from artifacts.models import (
    ArtifactBlock,
    ArtifactDocument,
    ArtifactSection,
    BulletListBlock,
    CalloutBlock,
    ChartBlock,
    ChartSeries,
    CodeBlock,
    DiagramBlock,
    EquationBlock,
    PageBreakBlock,
    ParagraphBlock,
    QuoteBlock,
    TableBlock,
)
from artifacts.quality import clean_inline_markdown, normalize_markdown_source
from artifacts.visualization_blocks import parse_authentic_chart_json

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")
_TABLE_SEPARATOR = re.compile(
    r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
)
_CALLOUT = re.compile(
    r"^>\s*\[!(NOTE|INFO|WARNING|SUCCESS|ASSUMPTION)\]\s*(.*?)\s*$",
    re.IGNORECASE,
)
_ASCII_DIAGRAM = re.compile(r"^[+|].*[+|]\s*$")
_PAGE_BREAK = re.compile(
    r"^(?:<!--\s*page[-_ ]?break\s*-->|\[page[-_ ]?break\])$",
    re.IGNORECASE,
)
_DISPLAY_EQUATION = re.compile(r"^\$\$(.*?)\$\$$", re.DOTALL)
_BAD_TITLE = re.compile(r"^(?:user|assistant|serenya|create(?: a)? pdf|professional pdf|final pdf generation instruction|organise this)$", re.IGNORECASE)


@dataclass(slots=True)
class _Section:
    title: str
    level: int
    blocks: list[ArtifactBlock]


def sanitize_filename(value: str) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        value.strip(),
    )
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-._")
    return normalized[:120] or "authentic-artifact"


def _split_table_row(line: str) -> tuple[str, ...]:
    return tuple(
        clean_inline_markdown(cell.strip())
        for cell in line.strip().strip("|").split("|")
    )


def _infer_title(content: str) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _HEADING.match(line)
        if heading is not None:
            candidate = clean_inline_markdown(heading.group(2).strip())
            if candidate and not _BAD_TITLE.match(candidate):
                return candidate
            continue

        candidate = clean_inline_markdown(line[:100].rstrip(".:"))
        if candidate and not _BAD_TITLE.match(candidate):
            return candidate

    return "Generated Document"


def _is_ascii_diagram_start(
    lines: list[str],
    index: int,
) -> bool:
    if index + 2 >= len(lines):
        return False

    # Markdown tables also begin with pipe characters. They must be
    # handled by the table parser rather than being interpreted as flows.
    if (
        index + 1 < len(lines)
        and _TABLE_SEPARATOR.match(lines[index + 1])
    ):
        return False
    sample = [
        lines[index + offset].rstrip()
        for offset in range(3)
    ]
    return all(
        _ASCII_DIAGRAM.match(line.strip())
        or line.strip().startswith(("|", "+"))
        for line in sample
        if line.strip()
    ) and sum(bool(line.strip()) for line in sample) >= 3



def _diagram_steps(lines: list[str]) -> tuple[str, ...]:
    candidates: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"^[+|\-\s]+|[+|\-\s]+$", "", line)
        if not line or line.casefold() in {"v", "arrow", "down"}:
            continue

        parts = re.split(r"\s*(?:--?>|→|=>|↓)\s*", line)
        for part in parts:
            normalized = clean_inline_markdown(
                re.sub(r"\s+", " ", part).strip(" [](){}")
            )
            if normalized and normalized not in candidates:
                candidates.append(normalized)

    return tuple(candidates)


def _clean_chart_block(chart: ChartBlock) -> ChartBlock:
    return replace(
        chart,
        title=clean_inline_markdown(chart.title),
        labels=tuple(
            clean_inline_markdown(label)
            for label in chart.labels
        ),
        series=tuple(
            ChartSeries(
                name=clean_inline_markdown(series.name),
                values=series.values,
            )
            for series in chart.series
        ),
        caption=(
            clean_inline_markdown(chart.caption)
            if chart.caption
            else None
        ),
        x_label=(
            clean_inline_markdown(chart.x_label)
            if chart.x_label
            else None
        ),
        y_label=(
            clean_inline_markdown(chart.y_label)
            if chart.y_label
            else None
        ),
    )

def parse_artifact_document(
    content: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    author: str | None = None,
) -> ArtifactDocument:
    cleaned = normalize_markdown_source(content)

    if not cleaned:
        raise ValueError("Artifact content cannot be empty.")

    resolved_title = (
        clean_inline_markdown(title)
        if title and title.strip()
        else _infer_title(cleaned)
    )
    sections: list[_Section] = [
        _Section(
            title="Overview",
            level=1,
            blocks=[],
        )
    ]
    current = sections[0]
    lines = cleaned.splitlines()
    paragraph_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = clean_inline_markdown(
            " ".join(
                line.strip()
                for line in paragraph_lines
                if line.strip()
            )
        )
        paragraph_lines.clear()
        if text:
            current.blocks.append(
                ParagraphBlock(text=text)
            )

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        line = re.sub(r"^[•\-*+]\s+(#{1,6}\s+)", r"\1", line)

        if not line:
            flush_paragraph()
            index += 1
            continue

        if _PAGE_BREAK.match(line):
            flush_paragraph()
            current.blocks.append(PageBreakBlock())
            index += 1
            continue

        equation = _DISPLAY_EQUATION.match(line)
        if equation is not None:
            flush_paragraph()
            expression = equation.group(1).strip()
            if expression:
                current.blocks.append(
                    EquationBlock(expression=expression)
                )
            index += 1
            continue

        if line.startswith("$$"):
            flush_paragraph()
            equation_lines = [line[2:]]
            index += 1
            closed = False
            while index < len(lines):
                candidate = lines[index].strip()
                if candidate.endswith("$$"):
                    equation_lines.append(candidate[:-2])
                    index += 1
                    closed = True
                    break
                equation_lines.append(candidate)
                index += 1
            expression = " ".join(
                part.strip()
                for part in equation_lines
                if part.strip()
            ).strip()
            if expression:
                current.blocks.append(
                    EquationBlock(expression=expression)
                )
            if not closed:
                continue
            continue

        heading = _HEADING.match(line)
        if heading is not None:
            flush_paragraph()
            heading_level = len(heading.group(1))
            heading_text = clean_inline_markdown(
                heading.group(2).strip()
            )
            if (
                heading_level == 1
                and heading_text == resolved_title
                and not any(section.blocks for section in sections)
            ):
                index += 1
                continue
            current = _Section(
                title=heading_text,
                level=min(max(heading_level - 1, 1), 3),
                blocks=[],
            )
            sections.append(current)
            index += 1
            continue

        if line.startswith("```"):
            flush_paragraph()
            language = line[3:].strip()
            index += 1
            code_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() == "```":
                    index += 1
                    break
                code_lines.append(candidate)
                index += 1
            code = "\n".join(code_lines).rstrip()
            normalized_language = language.casefold()

            if normalized_language == "authentic-chart":
                chart = parse_authentic_chart_json(code)
                if chart is not None:
                    current.blocks.append(
                        _clean_chart_block(chart)
                    )
                elif code:
                    current.blocks.append(
                        CodeBlock(code=code, language=language)
                    )
            elif normalized_language in {"diagram", "flow", "flowchart"}:
                steps = _diagram_steps(code_lines)
                if steps:
                    current.blocks.append(
                        DiagramBlock(
                            title="Process Flow",
                            steps=steps,
                        )
                    )
                elif code:
                    current.blocks.append(
                        CodeBlock(code=code, language=language)
                    )
            else:
                current.blocks.append(
                    CodeBlock(
                        code=code,
                        language=language,
                    )
                )
            continue

        if _is_ascii_diagram_start(lines, index):
            flush_paragraph()
            diagram_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index].rstrip()
                stripped = candidate.strip()
                if not stripped:
                    break
                if not (
                    stripped.startswith(("|", "+"))
                    or "-->" in stripped
                    or stripped in {"v", "V", "↓", "↑"}
                ):
                    break
                diagram_lines.append(candidate)
                index += 1
            steps = _diagram_steps(diagram_lines)
            if steps:
                current.blocks.append(
                    DiagramBlock(
                        title="Process Flow",
                        steps=steps,
                    )
                )
            continue

        callout = _CALLOUT.match(line)
        if callout is not None:
            flush_paragraph()
            kind_value = callout.group(1).lower()
            kind = "info" if kind_value == "note" else kind_value
            callout_title = clean_inline_markdown(
                callout.group(2)
            ) or kind.title()
            index += 1
            body_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate.startswith(">"):
                    break
                body_lines.append(candidate[1:].strip())
                index += 1
            current.blocks.append(
                CalloutBlock(
                    title=callout_title,
                    text=clean_inline_markdown(
                        " ".join(body_lines)
                    ),
                    kind=kind,  # type: ignore[arg-type]
                )
            )
            continue

        if line.startswith(">"):
            flush_paragraph()
            quote_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate.startswith(">"):
                    break
                quote_lines.append(candidate[1:].strip())
                index += 1
            current.blocks.append(
                QuoteBlock(
                    text=clean_inline_markdown(
                        " ".join(quote_lines)
                    )
                )
            )
            continue

        if (
            index + 1 < len(lines)
            and "|" in line
            and _TABLE_SEPARATOR.match(lines[index + 1])
        ):
            flush_paragraph()
            columns = _split_table_row(line)
            index += 2
            rows: list[tuple[str, ...]] = []
            while index < len(lines):
                row_line = lines[index]
                if not row_line.strip() or "|" not in row_line:
                    break
                row = _split_table_row(row_line)
                if len(row) == len(columns):
                    rows.append(row)
                index += 1
            current.blocks.append(
                TableBlock(
                    columns=columns,
                    rows=tuple(rows),
                )
            )
            continue

        bullet = _BULLET.match(line)
        ordered = _ORDERED.match(line)
        if bullet is not None or ordered is not None:
            flush_paragraph()
            is_ordered = ordered is not None
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                match = (
                    _ORDERED.match(candidate)
                    if is_ordered
                    else _BULLET.match(candidate)
                )
                if match is None:
                    break
                items.append(
                    clean_inline_markdown(
                        match.group(1).strip()
                    )
                )
                index += 1
            current.blocks.append(
                BulletListBlock(
                    items=tuple(items),
                    ordered=is_ordered,
                )
            )
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()

    finalized_list: list[ArtifactSection] = []
    seen_sections: set[str] = set()
    for section in sections:
        if not section.blocks:
            continue
        artifact_section = ArtifactSection(
            title=section.title,
            level=section.level,
            blocks=tuple(section.blocks),
        )
        fingerprint = re.sub(r"\W+", "", section.title.casefold()) + "|" + re.sub(
            r"\W+", "", repr(artifact_section.blocks).casefold()
        )
        if fingerprint in seen_sections:
            continue
        seen_sections.add(fingerprint)
        finalized_list.append(artifact_section)
    finalized = tuple(finalized_list)

    if not finalized:
        finalized = (
            ArtifactSection(
                title="Overview",
                level=1,
                blocks=(
                    ParagraphBlock(
                        text=clean_inline_markdown(cleaned)
                    ),
                ),
            ),
        )

    return ArtifactDocument(
        title=resolved_title,
        subtitle=(
            clean_inline_markdown(subtitle)
            if subtitle and subtitle.strip()
            else None
        ),
        author=(
            clean_inline_markdown(author)
            if author and author.strip()
            else None
        ),
        sections=finalized,
    )
