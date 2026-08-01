from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from core.artifact_settings import artifact_settings
from schemas.artifact_composer import ArtifactComposeRequest


_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_TITLE_CLEANUP = re.compile(
    r"\b(?:create|make|generate|prepare|produce|export|convert|pdf|docx|pptx|document|file|please|professional|polished|bana\s*do|banado|banao)\b",
    re.IGNORECASE,
)

_COMMAND_TITLE = re.compile(
    r"\b(?:add|create|make|generate|rename|convert|revise|update|new\s+version|professionally\s+organise|pdf\s+bana)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LargeSourcePlan:
    source_text: str
    chunks: tuple[str, ...]
    inferred_title: str
    source_character_count: int
    estimated_page_count: int
    use_multi_pass: bool
    bundle_volume_count: int | None


def authoritative_source_text(
    request: ArtifactComposeRequest,
) -> str:
    snapshot = request.source_snapshot
    if snapshot is not None and snapshot.content:
        # Instructions and source are separate channels. A verbose redesign
        # brief must never displace the uploaded or durable source merely
        # because the instruction happens to contain more characters.
        return snapshot.content.strip()
    return request.prompt.strip()


def _paragraph_units(text: str) -> Iterable[str]:
    """Yield paragraphs while keeping fenced blocks intact."""

    cursor = 0
    for match in _FENCE.finditer(text):
        prefix = text[cursor:match.start()]
        for paragraph in re.split(r"\n\s*\n", prefix):
            normalized = paragraph.strip()
            if normalized:
                yield normalized
        block = match.group(0).strip()
        if block:
            yield block
        cursor = match.end()

    suffix = text[cursor:]
    for paragraph in re.split(r"\n\s*\n", suffix):
        normalized = paragraph.strip()
        if normalized:
            yield normalized


def split_large_source(
    text: str,
    *,
    target_characters: int | None = None,
) -> tuple[str, ...]:
    target = (
        target_characters
        if target_characters is not None
        else artifact_settings.large_source_chunk_characters
    )
    hard_limit = max(target + 2_000, int(target * 1.35))

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    def flush() -> None:
        nonlocal current, current_size
        if current:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_size = 0

    for unit in _paragraph_units(text):
        if len(unit) > hard_limit and not unit.startswith("```"):
            flush()
            start = 0
            while start < len(unit):
                end = min(start + target, len(unit))
                if end < len(unit):
                    boundary = unit.rfind("\n", start, end)
                    if boundary <= start:
                        boundary = unit.rfind(". ", start, end)
                        if boundary > start:
                            boundary += 1
                    if boundary > start + target // 2:
                        end = boundary
                piece = unit[start:end].strip()
                if piece:
                    chunks.append(piece)
                start = end
            continue

        added = len(unit) + (2 if current else 0)
        if current and current_size + added > target:
            flush()

        current.append(unit)
        current_size += added

        if current_size >= hard_limit:
            flush()

    flush()
    return tuple(chunk for chunk in chunks if chunk)


def infer_large_source_title(
    request: ArtifactComposeRequest,
    source_text: str,
) -> str:
    if request.title and not _COMMAND_TITLE.search(request.title):
        return request.title.strip()[:240]

    heading = _HEADING.search(source_text[:20_000])
    if heading:
        candidate = heading.group(1)
    else:
        candidate = next(
            (
                line.strip()
                for line in source_text.splitlines()
                if 4 <= len(line.strip()) <= 240
            ),
            "Professional Document",
        )

    candidate = _TITLE_CLEANUP.sub(" ", candidate)
    candidate = re.sub(r"[`*_#>|\[\](){}]", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,:;-_")

    if len(candidate) < 4:
        return "Professional Document"
    return candidate[:240]


def estimate_pdf_pages(source_text: str) -> int:
    words = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", source_text))
    headings = len(_HEADING.findall(source_text))
    charts = source_text.casefold().count("```authentic-chart")
    tables = sum(
        1
        for line in source_text.splitlines()
        if line.strip().startswith("|") and line.count("|") >= 2
    ) // 3
    equations = len(
        re.findall(
            r"(?:\$\$[\s\S]*?\$\$|^\s*[^\n]{0,180}(?:=|∫|√|≤|≥|lim\b|d/dx|dy/dx)[^\n]{0,180}\s*$)",
            source_text,
            re.MULTILINE,
        )
    )

    base = math.ceil(
        words
        / artifact_settings.pdf_target_words_per_page
    )
    visual_allowance = math.ceil(charts * 0.55 + tables * 0.16 + equations * 0.035)
    structural_allowance = math.ceil(headings / 11) + 3
    return max(1, base + visual_allowance + structural_allowance)


def _bundle_volume_count(
    source_characters: int,
    estimated_pages: int,
) -> int | None:
    character_threshold = artifact_settings.pdf_bundle_source_characters
    page_threshold = artifact_settings.maximum_single_pdf_pages
    if (
        source_characters <= character_threshold
        and (
            not artifact_settings.enforce_single_pdf_page_limit
            or estimated_pages <= page_threshold
        )
    ):
        return None

    count_by_characters = math.ceil(
        source_characters / character_threshold
    )
    count_by_pages = (
        math.ceil(estimated_pages / page_threshold)
        if artifact_settings.enforce_single_pdf_page_limit
        else 1
    )
    count = max(2, count_by_characters, count_by_pages)
    return min(
        count,
        artifact_settings.maximum_pdf_bundle_volumes,
    )


def plan_large_source(
    request: ArtifactComposeRequest,
) -> LargeSourcePlan:
    source_text = authoritative_source_text(request)
    chunks = split_large_source(source_text)
    source_characters = len(source_text)
    estimated_pages = estimate_pdf_pages(source_text)
    use_multi_pass = len(chunks) > 1
    bundle_volume_count = (
        _bundle_volume_count(
            source_characters,
            estimated_pages,
        )
        if request.format == "pdf"
        else None
    )

    return LargeSourcePlan(
        source_text=source_text,
        chunks=chunks or (source_text,),
        inferred_title=infer_large_source_title(
            request,
            source_text,
        ),
        source_character_count=source_characters,
        estimated_page_count=estimated_pages,
        use_multi_pass=use_multi_pass,
        bundle_volume_count=bundle_volume_count,
    )
