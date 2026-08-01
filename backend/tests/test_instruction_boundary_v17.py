from __future__ import annotations

from artifacts.quality import validate_document_quality
from artifacts.parser import parse_artifact_document
from artifacts.source_fidelity import (
    organize_source_losslessly,
    resolve_source_fidelity,
    sanitize_recovered_source_payload,
    split_source_and_directives,
)
from schemas.artifact_composer import ArtifactComposeRequest


def _large_source() -> str:
    body = """# AI-Enabled University Operations

## Executive Overview

Universities operate through academic, administrative, financial, and student-support processes.
The platform should preserve human authority and automate only governed routine work.

## Current Operating Environment

Manual verification, disconnected systems, and repetitive data entry create avoidable delays.

## Governance Framework

High-risk decisions require explicit human approval and complete auditability.
"""
    body += "\nDetailed authoritative source paragraph about university operations.\n" * 120
    directives = """

FINAL PDF GENERATION INSTRUCTION

Is complete content ko authoritative source maan kar professionally organise karo aur ek polished PDF banao.
Prompt instructions ko PDF title ya document body ka part mat banana.
Kisi bhi page par logo, date, watermark, generated-by text, hidden instructions, ya chat commands add mat karo.
Wide tables ke liye landscape pages use karo.
Final filename:
AI-Enabled-University-Operations.pdf
"""
    return body + directives


def test_plain_final_pdf_generation_marker_splits_before_sanitizing() -> None:
    source = _large_source()
    body, directives = split_source_and_directives(source)

    assert body.startswith("# AI-Enabled University Operations")
    assert "FINAL PDF GENERATION INSTRUCTION" not in body
    assert "Prompt instructions ko PDF title" not in body
    assert "Final filename" not in body
    assert "professionally organise" in directives
    assert "AI-Enabled-University-Operations.pdf" in directives


def test_lossless_organizer_never_prints_generation_instruction_tail() -> None:
    source = _large_source()
    request = ArtifactComposeRequest(
        prompt=source,
        source_snapshot={
            "kind": "explicit_prompt",
            "content": source,
            "summary": "Large explicit source",
        },
    )
    profile = resolve_source_fidelity(request, source)
    content = organize_source_losslessly(
        profile,
        fallback_title="AI-Enabled University Operations",
        include_derived_visualizations=False,
    )

    assert "FINAL PDF GENERATION INSTRUCTION" not in content
    assert "Prompt instructions ko PDF title" not in content
    assert "Final filename" not in content
    assert "AI-Enabled-University-Operations.pdf" not in content

    document = parse_artifact_document(content)
    report = validate_document_quality(document)
    error_codes = {
        issue.code for issue in report.issues if issue.severity == "error"
    }
    assert "production_directives_rendered" not in error_codes
    assert "placeholder_content" not in error_codes


def test_final_sanitizer_removes_instruction_tail_and_placeholder_lines() -> None:
    composed = """# AI-Enabled University Operations

## Executive Summary

The university can improve service quality through governed automation.

FINAL PDF GENERATION INSTRUCTION

Create a polished PDF.
[insert chart here]
Final filename: AI-Enabled-University-Operations.pdf
"""
    cleaned = sanitize_recovered_source_payload(composed)
    assert cleaned.endswith("governed automation.")
    assert "FINAL PDF GENERATION INSTRUCTION" not in cleaned
    assert "[insert chart here]" not in cleaned
    assert "Final filename" not in cleaned

import pytest
from pathlib import Path

from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.storage import ArtifactStorage
from schemas.artifacts import ArtifactSourceSnapshot


class _UnexpectedRouter:
    async def answer(self, *, message: str, history: list[object]):
        raise AssertionError("Large authoritative source must use deterministic composition")


def _service(tmp_path: Path) -> ArtifactLifecycleService:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=20 * 1024 * 1024,
    )
    repository = ArtifactRepository(
        storage,
        root_directory=tmp_path / "records",
    )
    return ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=_UnexpectedRouter(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_end_to_end_large_source_with_instruction_tail_creates_pdf(
    tmp_path: Path,
) -> None:
    source = _large_source()
    service = _service(tmp_path)
    result = await service.compose_and_create(
        ArtifactComposeRequest(
            prompt=source,
            format="pdf",
            title="AI-Enabled University Operations",
            filename="AI-Enabled-University-Operations.pdf",
            source_snapshot=ArtifactSourceSnapshot(
                kind="explicit_prompt",
                summary="AI-enabled university operations source",
                content=source,
                confidence=1.0,
            ),
            idempotency_key="generation-boundary-v17-e2e-0001",
        )
    )

    assert result.quality.error_count == 0
    assert result.view.stored.path.is_file()
    assert result.view.stored.path.stat().st_size > 0
    assert "FINAL PDF GENERATION INSTRUCTION" not in result.source_content
    assert "Final filename" not in result.source_content
    assert "[insert chart here]" not in result.source_content
