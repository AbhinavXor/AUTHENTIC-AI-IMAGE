from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from artifacts.models import (
    ArtifactDocument,
    ArtifactSection,
    BulletListBlock,
    CalloutBlock,
    ChartBlock,
    CodeBlock,
    DiagramBlock,
    EquationBlock,
    PageBreakBlock,
    ParagraphBlock,
    QuoteBlock,
    TableBlock,
)
from artifacts.pdf_renderer import render_pdf
from artifacts.parser import sanitize_filename


def _block_weight(block: object) -> int:
    if isinstance(block, ParagraphBlock):
        return len(block.text)
    if isinstance(block, QuoteBlock):
        return len(block.text) + len(block.attribution or "")
    if isinstance(block, CalloutBlock):
        return len(block.title) + len(block.text)
    if isinstance(block, BulletListBlock):
        return sum(len(item) for item in block.items)
    if isinstance(block, TableBlock):
        return sum(len(cell) for cell in block.columns) + sum(
            len(cell)
            for row in block.rows
            for cell in row
        )
    if isinstance(block, ChartBlock):
        return 1_500 + len(block.title) + sum(len(label) for label in block.labels)
    if isinstance(block, CodeBlock):
        return len(block.code)
    if isinstance(block, EquationBlock):
        return max(250, len(block.expression) * 5)
    if isinstance(block, DiagramBlock):
        return 1_000 + sum(len(step) for step in block.steps)
    if isinstance(block, PageBreakBlock):
        return 100
    return 100


def _section_weight(section: ArtifactSection) -> int:
    return len(section.title) + sum(
        _block_weight(block)
        for block in section.blocks
    )


def _balanced_section_groups(
    sections: tuple[ArtifactSection, ...],
    volume_count: int,
) -> list[list[ArtifactSection]]:
    if volume_count <= 1 or len(sections) <= 1:
        return [list(sections)]

    volume_count = min(volume_count, len(sections))
    total_weight = sum(_section_weight(section) for section in sections)
    target_weight = max(1, total_weight // volume_count)

    groups: list[list[ArtifactSection]] = []
    current: list[ArtifactSection] = []
    current_weight = 0

    for index, section in enumerate(sections):
        remaining_sections = len(sections) - index
        remaining_groups = volume_count - len(groups)
        should_close = (
            current
            and current_weight >= target_weight
            and remaining_sections >= remaining_groups
            and len(groups) < volume_count - 1
        )
        if should_close:
            groups.append(current)
            current = []
            current_weight = 0

        current.append(section)
        current_weight += _section_weight(section)

    if current:
        groups.append(current)

    while len(groups) < volume_count:
        largest_index = max(
            range(len(groups)),
            key=lambda i: len(groups[i]),
        )
        largest = groups[largest_index]
        if len(largest) < 2:
            break
        split_at = len(largest) // 2
        groups[largest_index:largest_index + 1] = [
            largest[:split_at],
            largest[split_at:],
        ]

    return groups


def render_pdf_bundle(
    document: ArtifactDocument,
    output_path: Path,
) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    requested_volumes = max(2, document.bundle_volume_count)
    groups = _balanced_section_groups(
        document.sections,
        requested_volumes,
    )
    total_volumes = len(groups)
    safe_stem = sanitize_filename(document.title) or "document"

    manifest: dict[str, object] = {
        "schema_version": 1,
        "title": document.title,
        "bundle_type": "multi_volume_pdf",
        "volume_count": total_volumes,
        "files": [],
    }

    with TemporaryDirectory(
        prefix="artifact-pdf-bundle-",
        dir=output_path.parent,
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        generated_files: list[Path] = []

        for index, section_group in enumerate(groups, start=1):
            volume_title = (
                f"{document.title} - Volume {index} of {total_volumes}"
            )
            volume_document = replace(
                document,
                title=volume_title,
                subtitle=(
                    document.subtitle
                    or f"Multi-volume PDF bundle - Volume {index}"
                ),
                sections=tuple(section_group),
                bundle_volume_count=1,
            )
            filename = (
                f"{safe_stem}-Volume-{index:02d}-of-{total_volumes:02d}.pdf"
            )
            rendered = render_pdf(
                volume_document,
                temporary_root / filename,
            )
            generated_files.append(rendered)
            manifest["files"].append(
                {
                    "filename": filename,
                    "volume": index,
                    "section_count": len(section_group),
                    "first_section": section_group[0].title,
                    "last_section": section_group[-1].title,
                }
            )

        manifest_path = temporary_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        with ZipFile(
            output_path,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            archive.write(manifest_path, arcname="manifest.json")
            for generated in generated_files:
                archive.write(generated, arcname=generated.name)

    return output_path
