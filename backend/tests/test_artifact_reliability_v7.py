from __future__ import annotations

from pathlib import Path

import pytest

from artifacts.composer import compose_artifact_draft
from artifacts.parser import parse_artifact_document
from artifacts.quality import normalize_markdown_source, validate_document_quality
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.source_fidelity import (
    is_canonical_artifact_markdown,
    normalize_recovered_artifact_markdown,
    organize_source_losslessly,
    resolve_source_fidelity,
)
from artifacts.storage import ArtifactStorage
from schemas.artifact_composer import ArtifactComposeRequest


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "mathematics_authoritative_source.txt"
)


class UnexpectedModelRouter:
    async def answer(self, *, message: str, history: list[object]):
        raise AssertionError(
            "Canonical artifact recovery must not call an external model."
        )


def _canonical_math_document() -> str:
    source = FIXTURE.read_text(encoding="utf-8")
    request = ArtifactComposeRequest(
        prompt=source,
        format="pdf",
        title="Add a Comparison Table and a New Version",
    )
    profile = resolve_source_fidelity(request, source)
    return organize_source_losslessly(
        profile,
        fallback_title=request.title or "Mathematics",
    )


def _service(tmp_path: Path) -> ArtifactLifecycleService:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=80 * 1024 * 1024,
    )
    repository = ArtifactRepository(
        storage,
        root_directory=tmp_path / "records",
    )
    return ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )


def test_canonical_artifact_recovery_is_idempotent() -> None:
    canonical = _canonical_math_document()
    assert is_canonical_artifact_markdown(canonical)

    recovered = normalize_recovered_artifact_markdown(
        canonical,
        fallback_title="Recovered Mathematics",
    )

    assert recovered.count("## Executive Overview") == 1
    assert recovered.count("## Learning Roadmap") == 1
    assert recovered.count("### 1. Mathematical Thinking") == 1
    assert recovered.count("### 37. Final Verification Checklist") == 1
    assert recovered.count("```authentic-chart") == canonical.count(
        "```authentic-chart"
    )
    assert "Document Production Requirements" not in recovered
    assert "hidden in chat preview" not in recovered

    artifact = parse_artifact_document(
        normalize_markdown_source(recovered),
        title=None,
        subtitle=None,
        author="Authentic AI",
    )
    quality = validate_document_quality(
        artifact,
        source_snapshot={
            "kind": "artifact_version",
            "summary": "Recovered mathematics artifact",
            "content": recovered,
        },
    )
    assert quality.error_count == 0, quality.to_dict()


@pytest.mark.asyncio
async def test_recovered_canonical_artifact_does_not_get_organised_twice() -> None:
    canonical = _canonical_math_document()
    request = ArtifactComposeRequest(
        prompt=(
            "Complete stored authoritative mathematics source ko recover "
            "karke polished professional PDF bana do. Preserve all chapters."
        ),
        format="pdf",
        source_snapshot={
            "kind": "artifact_version",
            "summary": "Recovered canonical mathematics artifact",
            "content": canonical,
            "message_ids": [],
            "attachment_names": [],
            "confidence": 0.92,
        },
    )

    draft = await compose_artifact_draft(
        request,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )

    assert draft.provider == "deterministic"
    assert draft.model == "canonical-artifact-recovery-v8"
    assert draft.content.count("## Executive Overview") == 1
    assert draft.content.count("### 1. Mathematical Thinking") == 1
    assert draft.content.count("### 37. Final Verification Checklist") == 1
    assert "Document Production Requirements" not in draft.content
    assert "hidden in chat preview" not in draft.content


@pytest.mark.asyncio
async def test_recovered_canonical_artifact_renders_successfully(
    tmp_path: Path,
) -> None:
    canonical = _canonical_math_document()
    result = await _service(tmp_path).compose_and_create(
        ArtifactComposeRequest(
            prompt=(
                "Recover the complete stored mathematics artifact and "
                "create a polished PDF without losing any chapter."
            ),
            format="pdf",
            filename="Recovered-Mathematics.pdf",
            source_snapshot={
                "kind": "artifact_version",
                "summary": "Recovered mathematics artifact",
                "content": canonical,
                "message_ids": [],
                "attachment_names": [],
                "confidence": 0.92,
            },
            idempotency_key="artifact-reliability-v7-render-0001",
        )
    )

    assert result.provider == "deterministic"
    assert result.model == "canonical-artifact-recovery-v8"
    assert result.quality.error_count == 0, result.quality.to_dict()
    assert result.quality.page_or_slide_count >= 20
    assert result.source_content.count("## Executive Overview") == 1
    assert result.source_content.count("### 37. Final Verification Checklist") == 1


def test_old_command_title_and_internal_section_are_repaired() -> None:
    old_artifact = """# Add a Comparison Table and a New Version

## Executive Overview

A professional mathematics reference.

## Part I — Mathematical Foundations

### 1. Mathematical Thinking

Mathematical thinking starts with assumptions and verification.

## Document Production Requirements

- Create a PDF.
- Do not remove anything.

## Conclusion

Mathematics requires clear reasoning.
"""
    repaired = normalize_recovered_artifact_markdown(
        old_artifact,
        fallback_title="Professional Mathematics",
    )

    assert repaired.startswith("# Professional Mathematics")
    assert "Add a Comparison Table and a New Version" not in repaired
    assert "Document Production Requirements" not in repaired
    assert repaired.count("## Executive Overview") == 1
    assert repaired.count("## Conclusion") == 1
