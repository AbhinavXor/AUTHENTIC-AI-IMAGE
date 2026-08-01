from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from artifacts.composer import compose_artifact_draft, compose_artifact_revision
from artifacts.large_source import plan_large_source
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.source_fidelity import (
    resolve_source_fidelity,
    source_fidelity_metrics,
)
from artifacts.storage import ArtifactStorage
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.artifacts import ArtifactSourceSnapshot
from schemas.chat import ChatResponse, TokenUsage


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "mathematics_authoritative_source.txt"
)


class UnexpectedModelRouter:
    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        raise AssertionError(
            "Lossless source-fidelity generation must not ask a model to summarize the source."
        )


class UnsafeRevisionRouter:
    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        return ChatResponse(
            answer="# Replacement\n\nA tiny unrelated answer.",
            provider="test",
            model="unsafe",
            request_id="unsafe-revision",
            usage=TokenUsage(
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
            ),
        )


def _service(tmp_path: Path, router: object) -> ArtifactLifecycleService:
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
        model_router=router,  # type: ignore[arg-type]
    )


def _source() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_authoritative_mathematics_source_enters_lossless_mode() -> None:
    source = _source()
    request = ArtifactComposeRequest(
        prompt=source,
        format="pdf",
        title="Mathematics Master Explanation",
    )
    plan = plan_large_source(request)
    fidelity = resolve_source_fidelity(request, plan.source_text)

    assert fidelity.preserve_all is True
    assert fidelity.body_character_count > 14_000
    assert len(fidelity.numbered_heading_titles) >= 35
    assert fidelity.minimum_expected_pages >= 11


@pytest.mark.asyncio
async def test_lossless_draft_preserves_all_numbered_chapters_and_examples() -> None:
    source = _source()
    request = ArtifactComposeRequest(
        prompt=source,
        format="pdf",
        title="Mathematics Master Explanation",
    )
    draft = await compose_artifact_draft(
        request,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )
    fidelity = resolve_source_fidelity(request, source)
    metrics = source_fidelity_metrics(
        fidelity.source_body,
        draft.content,
        fidelity.numbered_heading_titles,
    )

    assert draft.provider == "deterministic"
    assert draft.model == "professional-document-v5"
    assert metrics.passed
    assert "### 1. Mathematical Thinking" in draft.content
    assert "### 37. Final Verification Checklist" in draft.content
    assert "C(12) = 296" in draft.content
    assert "x = [-b ± √(b² - 4ac)] / 2a" in draft.content
    assert "P(A|B) = P(A ∩ B)/P(B)" in draft.content
    assert "## Executive Overview" in draft.content
    assert "## Glossary and Notation" in draft.content
    assert "## Conclusion" in draft.content
    assert "Document Production Requirements" not in draft.content
    assert "hidden in chat preview" not in draft.content
    assert draft.content.count("```authentic-chart") >= 10


@pytest.mark.asyncio
async def test_lossless_source_renders_to_substantial_pdf(tmp_path: Path) -> None:
    source = _source()
    result = await _service(
        tmp_path,
        UnexpectedModelRouter(),
    ).compose_and_create(
        ArtifactComposeRequest(
            prompt=source,
            format="pdf",
            title="Mathematics Master Explanation",
            filename="Mathematics-Master-Explanation.pdf",
            idempotency_key="source-fidelity-render-test-0001",
        )
    )

    assert result.view.version.format == "pdf"
    assert result.quality.error_count == 0
    assert result.quality.page_or_slide_count >= 11
    reader = PdfReader(str(result.view.stored.path))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Mathematical Thinking" in extracted
    assert "Final Verification Checklist" in extracted
    assert "Linear Cost Model" in result.source_content
    assert "Quadratic Function" in result.source_content
    assert "Regression Example: Observations and Fitted Line" in result.source_content
    assert result.quality.warning_count == 0


@pytest.mark.asyncio
async def test_recovered_snapshot_drives_full_professional_pdf(
    tmp_path: Path,
) -> None:
    source = _source()
    result = await _service(
        tmp_path,
        UnexpectedModelRouter(),
    ).compose_and_create(
        ArtifactComposeRequest(
            prompt=(
                "Create the requested artifact from "
                "the complete recovered source snapshot."
            ),
            format="pdf",
            title="Mathematics Master Explanation",
            filename="Recovered-Mathematics.pdf",
            source_snapshot=ArtifactSourceSnapshot(
                kind="artifact_version",
                summary=(
                    "Complete authoritative mathematics "
                    "source"
                ),
                content=source,
                confidence=1.0,
            ),
            idempotency_key=(
                "source-recovery-render-test-0001"
            ),
        )
    )

    reader = PdfReader(
        str(result.view.stored.path)
    )
    extracted = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    assert (
        result.view.version.page_or_slide_count
        >= 35
    )
    assert "Mathematical Thinking" in extracted
    assert "Integration by Substitution" in extracted
    assert "Statistical Inference" in extracted
    assert "Final Verification Checklist" in extracted
    assert result.quality.error_count == 0
    assert result.quality.warning_count == 0


@pytest.mark.asyncio
async def test_comparison_table_revision_is_additive_and_lossless() -> None:
    current = """# University Operations\n\n## Benefits\n\nAutomation reduces repetitive processing.\n\n## Risks\n\nGovernance and human oversight remain necessary.\n"""
    request = ArtifactComposeRequest(
        prompt="Add a comparison table and create a new version.",
        format="pdf",
        title="University Operations",
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )

    assert current.rstrip() in draft.content
    assert "## Comparative Concept Matrix" in draft.content
    assert "| Benefits |" in draft.content
    assert "| Risks |" in draft.content
    assert draft.provider == "deterministic"
    assert draft.model == "professional-revision-v5"


@pytest.mark.asyncio
async def test_unsafe_non_destructive_revision_is_rejected() -> None:
    current = "# Full Document\n\n## One\n\n" + ("Preserved factual content. " * 200)
    request = ArtifactComposeRequest(
        prompt="Improve the formatting and add a short introduction.",
        format="pdf",
        title="Full Document",
    )

    with pytest.raises(Exception, match="without losing existing content"):
        await compose_artifact_revision(
            request,
            current_content=current,
            instruction=request.prompt,
            model_router=UnsafeRevisionRouter(),  # type: ignore[arg-type]
        )
