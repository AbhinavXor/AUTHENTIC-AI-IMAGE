from __future__ import annotations

import re
from dataclasses import dataclass

from artifacts.models import (
    ArtifactBlock,
    ArtifactDocument,
    ArtifactSection,
    BulletListBlock,
    CodeBlock,
    ParagraphBlock,
    TableBlock,
)


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")
_TABLE_SEPARATOR = re.compile(
    r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
)
_INTERNAL_CONTEXT = re.compile(
    r"<!--AUTHENTIC_[A-Z0-9_]+:[\s\S]*?-->"
)


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
    normalized = re.sub(
        r"-{2,}",
        "-",
        normalized,
    ).strip("-._")
    return normalized[:90] or "authentic-artifact"


def _split_table_row(line: str) -> tuple[str, ...]:
    return tuple(
        cell.strip()
        for cell in line.strip().strip("|").split("|")
    )


def _infer_title(content: str) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _HEADING.match(line)

        if heading is not None:
            return heading.group(2).strip()

        return (
            line[:100].rstrip(".:")
            or "Authentic AI Report"
        )

    return "Authentic AI Report"


def parse_artifact_document(
    content: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    author: str | None = None,
) -> ArtifactDocument:
    cleaned = _INTERNAL_CONTEXT.sub(
        "",
        content,
    ).strip()

    if not cleaned:
        raise ValueError(
            "Artifact content cannot be empty."
        )

    resolved_title = (
        title.strip()
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

        text = " ".join(
            line.strip()
            for line in paragraph_lines
            if line.strip()
        ).strip()

        paragraph_lines.clear()

        if text:
            current.blocks.append(
                ParagraphBlock(text=text)
            )

    while index < len(lines):
        line = lines[index].strip()

        if not line:
            flush_paragraph()
            index += 1
            continue

        heading = _HEADING.match(line)

        if heading is not None:
            flush_paragraph()

            heading_level = len(
                heading.group(1)
            )

            heading_text = (
                heading.group(2).strip()
            )

            if (
                heading_level == 1
                and heading_text
                == resolved_title
                and not any(
                    section.blocks
                    for section in sections
                )
            ):
                index += 1
                continue

            current = _Section(
                title=heading_text,
                level=min(
                    max(
                        heading_level - 1,
                        1,
                    ),
                    3,
                ),
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

                if (
                    candidate.strip()
                    == "```"
                ):
                    index += 1
                    break

                code_lines.append(candidate)
                index += 1

            current.blocks.append(
                CodeBlock(
                    code="\n".join(
                        code_lines
                    ),
                    language=language,
                )
            )
            continue

        if (
            index + 1 < len(lines)
            and "|" in line
            and _TABLE_SEPARATOR.match(
                lines[index + 1]
            )
        ):
            flush_paragraph()

            columns = _split_table_row(
                line
            )

            index += 2
            rows: list[
                tuple[str, ...]
            ] = []

            while index < len(lines):
                row_line = lines[index]

                if (
                    not row_line.strip()
                    or "|" not in row_line
                ):
                    break

                row = _split_table_row(
                    row_line
                )

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

        if (
            bullet is not None
            or ordered is not None
        ):
            flush_paragraph()

            is_ordered = (
                ordered is not None
            )

            items: list[str] = []

            while index < len(lines):
                candidate = (
                    lines[index].strip()
                )

                match = (
                    _ORDERED.match(
                        candidate
                    )
                    if is_ordered
                    else _BULLET.match(
                        candidate
                    )
                )

                if match is None:
                    break

                items.append(
                    match.group(1).strip()
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

    finalized = tuple(
        ArtifactSection(
            title=section.title,
            level=section.level,
            blocks=tuple(
                section.blocks
            ),
        )
        for section in sections
        if section.blocks
    )

    if not finalized:
        finalized = (
            ArtifactSection(
                title="Overview",
                level=1,
                blocks=(
                    ParagraphBlock(
                        text=cleaned
                    ),
                ),
            ),
        )

    return ArtifactDocument(
        title=resolved_title,
        subtitle=(
            subtitle.strip()
            if subtitle
            and subtitle.strip()
            else None
        ),
        author=(
            author.strip()
            if author
            and author.strip()
            else None
        ),
        sections=finalized,
    )