from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.artifact_sources as artifact_source_routes
from ai.provider_adapter import ProviderError
from artifacts import pdf_source_extractor
from artifacts.architecture_registry import architecture_registry
from artifacts.composer import (
    ArtifactCompositionError,
    compose_artifact_draft,
    compose_artifact_revision,
)
from artifacts.document_profiles import resolve_document_profile
from artifacts.large_source import plan_large_source
from artifacts.models import (
    ArtifactDocument,
    ArtifactLayoutBrief,
    ArtifactSection,
    TableBlock,
)
from artifacts.pdf_renderer import render_pdf
from artifacts.prompt_compiler import (
    compact_analysis_instruction,
    compile_composition_prompt,
    estimate_prompt_budget,
)
from artifacts.parser import parse_artifact_document
from artifacts.quality import (
    normalize_document_structure,
    normalize_markdown_source,
    validate_document_quality,
)
from artifacts.source_fidelity import (
    is_canonical_artifact_markdown,
    organize_source_losslessly,
    resolve_source_fidelity,
)
from artifacts.source_vault import ArtifactSourceVault
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.artifacts import ArtifactSourceReference
from schemas.chat import ChatResponse, TokenUsage


class SizeThenSuccessRouter:
    def __init__(self, *, leak_first: bool = False) -> None:
        self.messages: list[str] = []
        self.leak_first = leak_first

    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        del history
        self.messages.append(message)
        if len(self.messages) == 1 and not self.leak_first:
            raise ProviderError(
                "Provider context length exceeded.",
                provider="test",
                code="request",
                retryable=False,
                status_code=413,
            )
        if len(self.messages) == 1:
            answer = (
                "# Systems Report\n\n## OUTPUT CONTRACT\n\n"
                "Do not print these instructions."
            )
        else:
            answer = "# Systems Report\n\n## Overview\n\nValidated source content."
        return ChatResponse(
            answer=answer,
            provider="test",
            model="test-model",
            usage=TokenUsage(),
        )


class StaticDraftRouter:
    def __init__(self, answer: str) -> None:
        self.answer_text = answer

    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        del message, history
        return ChatResponse(
            answer=self.answer_text,
            provider="test",
            model="test-model",
            usage=TokenUsage(),
        )


def request_with_separate_source(
    *,
    prompt: str,
) -> ArtifactComposeRequest:
    return ArtifactComposeRequest(
        prompt=prompt,
        format="pdf",
        source_snapshot={
            "kind": "uploaded_file",
            "summary": "BTech systems project source",
            "content": (
                "# Systems Report\n\n## Overview\n\n"
                + "Validated engineering source. " * 120
            ),
            "attachment_names": ["source.pdf"],
        },
    )


def test_long_redesign_instruction_compiles_to_server_profile_budget() -> None:
    request = request_with_separate_source(
        prompt=(
            "Redesign this attached PDF as a BTech final-year project report.\n"
            + "Preserve content and improve equations, tables, graphs, and architecture.\n"
            + "Do not add branding, watermark, date, headers, or footers.\n"
        ) * 350,
    )
    compiled = compile_composition_prompt(
        request,
        source_text=request.source_snapshot.content or "",
        mode="standard",
    )
    assert compiled.profile_id == "redesign_existing"
    assert compiled.compacted is True
    assert compiled.estimate.within_budget is True
    assert len(compiled.text) < len(request.prompt)
    assert compiled.text.count("AUTHORITATIVE SOURCE") == 2


@pytest.mark.asyncio
async def test_provider_size_rejection_retries_once_in_compact_mode() -> None:
    router = SizeThenSuccessRouter()
    request = request_with_separate_source(
        prompt="Redesign this uploaded PDF professionally. " * 300,
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# Systems Report")
    assert len(router.messages) == 2
    assert len(router.messages[1]) <= len(router.messages[0])


@pytest.mark.asyncio
async def test_internal_instruction_leakage_retries_before_delivery() -> None:
    router = SizeThenSuccessRouter(leak_first=True)
    request = request_with_separate_source(
        prompt="Redesign the attached PDF.",
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert "OUTPUT CONTRACT" not in draft.content
    assert len(router.messages) == 2


@pytest.mark.asyncio
async def test_missing_provider_title_is_repaired_from_uploaded_source() -> None:
    request = request_with_separate_source(
        prompt="Redesign the attached PDF professionally.",
    )
    router = StaticDraftRouter(
        "## Executive Summary\n\nValidated engineering content."
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# source") is False
    assert draft.content.startswith("# Systems Report")
    assert "## Executive Summary" in draft.content


@pytest.mark.asyncio
async def test_invalid_user_title_is_replaced_and_extra_h1_is_demoted() -> None:
    request = request_with_separate_source(
        prompt="Redesign the attached PDF professionally.",
    )
    router = StaticDraftRouter(
        "# User\n\n## Overview\n\nUseful content.\n\n# Results\n\nMeasured result."
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# Systems Report")
    assert "# User" not in draft.content
    assert "\n## Results\n" in draft.content


@pytest.mark.asyncio
async def test_late_h1_section_is_not_mistaken_for_document_title() -> None:
    request = request_with_separate_source(
        prompt="Redesign the attached PDF professionally.",
    )
    router = StaticDraftRouter(
        "## Executive Summary\n\nUseful content.\n\n# Conclusion\n\nFinal result."
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# Systems Report")
    assert "\n## Conclusion\n" in draft.content


@pytest.mark.asyncio
async def test_attached_pdf_redesign_without_uploaded_source_fails_clearly() -> None:
    request = ArtifactComposeRequest(
        prompt="Redesign the attached PDF professionally.",
        format="pdf",
        source_snapshot={
            "kind": "explicit_prompt",
            "summary": "Redesign instruction only",
            "content": "Redesign the attached PDF professionally.",
            "attachment_names": [],
        },
    )
    router = StaticDraftRouter("# Incorrect Fallback\n\nNo source content.")
    with pytest.raises(
        ArtifactCompositionError,
        match="Attach the PDF or document to this message",
    ):
        await compose_artifact_draft(
            request,
            model_router=router,
        )


@pytest.mark.asyncio
async def test_large_design_revision_preserves_content_without_provider_rewrite() -> None:
    router = SizeThenSuccessRouter()
    current = (
        "# Existing Project\n\n## Chapter\n\n"
        + "Canonical engineering content. " * 900
    )
    request = ArtifactComposeRequest(
        prompt="Redesign this PDF with a new professional BTech architecture.",
        source_snapshot={
            "kind": "artifact_version",
            "summary": "Existing Project",
            "content": current,
        },
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=router,
    )
    assert draft.model == "profile-redesign-v20"
    assert "Canonical engineering content" in draft.content
    assert router.messages == []


@pytest.mark.asyncio
async def test_short_design_only_revision_also_preserves_content_without_rewrite() -> None:
    router = SizeThenSuccessRouter()
    current = (
        "# BTech Project Report\n\n"
        "## Overview\n\nCanonical project content.\n\n"
        "## Conclusion\n\nVerified conclusion."
    )
    request = ArtifactComposeRequest(
        prompt="Isko best professional design me final kar do.",
        source_snapshot={
            "kind": "artifact_version",
            "summary": "BTech Project Report",
            "content": current,
        },
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=router,
    )
    assert draft.model == "profile-redesign-v20"
    assert draft.content == current
    assert router.messages == []


@pytest.mark.asyncio
async def test_design_plus_content_change_still_uses_revision_model() -> None:
    router = StaticDraftRouter(
        "# BTech Project Report\n\n## Overview\n\nCanonical project content.\n\n"
        "## New Risk Section\n\nA verified risk section.\n\n"
        "## Conclusion\n\nVerified conclusion."
    )
    current = (
        "# BTech Project Report\n\n## Overview\n\nCanonical project content.\n\n"
        "## Conclusion\n\nVerified conclusion."
    )
    request = ArtifactComposeRequest(
        prompt="Improve the design and add a new risk section.",
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=router,
    )
    assert draft.model == "test-model"
    assert "New Risk Section" in draft.content


def test_uploaded_pdf_is_stored_as_durable_source_without_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = ArtifactSourceVault(
        root_directory=tmp_path / "sources",
        retention_hours=1,
    )
    monkeypatch.setattr(
        artifact_source_routes,
        "get_artifact_source_vault",
        lambda: vault,
    )
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "AI-Enabled University Operations System\nBTech project source",
    )
    payload = document.tobytes()
    document.close()

    app = FastAPI()
    app.include_router(
        artifact_source_routes.router,
        prefix="/api/v1",
    )
    response = TestClient(app).post(
        "/api/v1/artifact-sources/upload",
        files={"file": ("project.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    reference = ArtifactSourceReference.model_validate(body["reference"])
    stored = vault.get(reference)
    assert stored.snapshot.kind == "uploaded_file"
    assert "AI-Enabled University Operations" in (stored.snapshot.content or "")


def _semantic_source_pdf() -> bytes:
    document = pymupdf.open()
    document.set_metadata({"title": "Semantic Systems Engineering Report"})

    cover = document.new_page(width=595, height=842)
    cover.insert_text((60, 75), "Executive Summary", fontsize=20)
    cover.insert_text(
        (60, 108),
        "This report preserves document hierarchy and structured evidence.",
        fontsize=9.2,
    )
    x_positions = (60, 245, 520)
    y_positions = (150, 180, 210, 240)
    for x in x_positions:
        cover.draw_line((x, y_positions[0]), (x, y_positions[-1]))
    for y in y_positions:
        cover.draw_line((x_positions[0], y), (x_positions[-1], y))
    cells = (
        ("Metric", "Verified Value"),
        ("Accuracy", "96%"),
        ("Latency", "2.4 seconds"),
    )
    for row_index, row in enumerate(cells):
        for column_index, value in enumerate(row):
            cover.insert_text(
                (x_positions[column_index] + 6, y_positions[row_index] + 20),
                value,
                fontsize=8.5,
            )

    contents = document.new_page(width=595, height=842)
    contents.insert_text((45, 22), "SEMANTIC SYSTEMS REPORT", fontsize=7.2)
    contents.insert_text((60, 75), "Table of Contents", fontsize=18)
    for index, value in enumerate(
        (
            "Executive Summary 1",
            "Results and Recommendations 3",
            "Appendix 4",
        )
    ):
        contents.insert_text((65, 115 + index * 24), value, fontsize=9.2)
    contents.insert_text((60, 818), "Internal Baseline | Page 2", fontsize=7.2)

    results = document.new_page(width=595, height=842)
    results.insert_text((45, 22), "SEMANTIC SYSTEMS REPORT", fontsize=7.2)
    results.insert_text((60, 75), "Results and Recommendations", fontsize=20)
    results.insert_text(
        (60, 108),
        "The measured result remains source-supported and professionally structured.",
        fontsize=9.2,
    )
    results.insert_text((60, 145), "Implementation controls", fontsize=12)
    results.insert_text(
        (60, 170),
        "Use staged verification, clear ownership, and auditable quality gates.",
        fontsize=9.2,
    )
    results.insert_text(
        (60, 205),
        "2. ILO — Sectoral employment statistics",
        fontsize=7.8,
    )
    results.insert_text((60, 818), "Internal Baseline | Page 3", fontsize=7.2)

    payload = document.tobytes()
    document.close()
    return payload


def test_uploaded_pdf_extraction_preserves_hierarchy_tables_and_clean_margins() -> None:
    extracted, title, page_count = artifact_source_routes.extract_pdf_source(
        _semantic_source_pdf(),
        fallback_title="Fallback Source",
    )

    assert title == "Semantic Systems Engineering Report"
    assert page_count == 3
    assert extracted.startswith("# Semantic Systems Engineering Report")
    assert "## Executive Summary" in extracted
    assert "## Results and Recommendations" in extracted
    assert "| Metric | Verified Value |" in extracted
    assert "| Accuracy | 96% |" in extracted
    assert "2. ILO" in extracted
    assert "Sectoral employment statistics" in extracted
    assert "## 2. ILO" not in extracted
    assert "Table of Contents" not in extracted
    assert "SEMANTIC SYSTEMS REPORT" not in extracted
    assert "Internal Baseline | Page" not in extracted


def _large_mixed_page_source_pdf(page_count: int = 96) -> bytes:
    document = pymupdf.open()
    document.set_metadata({"title": "Scalable Engineering Reference"})

    page_sizes = (
        (595, 842),
        (842, 595),
        (720, 720),
        (612, 792),
    )
    for page_index in range(page_count):
        width, height = page_sizes[page_index % len(page_sizes)]
        page = document.new_page(width=width, height=height)
        if page_index == 0:
            page.insert_text(
                (54, 86),
                "Scalable Engineering Reference",
                fontsize=24,
                fontname="hebo",
            )
        else:
            page.insert_text(
                (36, 20),
                "SCALABLE ENGINEERING REFERENCE",
                fontsize=7,
            )
            page.insert_text(
                (54, 78),
                f"Chapter {page_index}",
                fontsize=18,
                fontname="hebo",
            )
        page.insert_text(
            (54, 118),
            (
                "This page preserves its source hierarchy while arbitrary page "
                "dimensions and long document sequences are processed safely."
            ),
            fontsize=10,
        )
        page.insert_text(
            (54, height - 18),
            f"Engineering Reference | Page {page_index + 1}",
            fontsize=7,
        )

    payload = document.tobytes()
    document.close()
    return payload


def test_typography_sampling_is_bounded_and_spans_the_document() -> None:
    indexes = pdf_source_extractor._sample_page_indexes(10_000)

    assert len(indexes) <= pdf_source_extractor.MAX_TYPOGRAPHY_SAMPLE_PAGES
    assert indexes[0] == 1
    assert indexes[-1] == 9_999
    assert indexes == tuple(sorted(set(indexes)))


def test_large_mixed_page_pdf_is_processed_without_a_page_count_cap() -> None:
    extracted, title, page_count = artifact_source_routes.extract_pdf_source(
        _large_mixed_page_source_pdf(),
    )

    assert title == "Scalable Engineering Reference"
    assert page_count == 96
    assert "## Chapter 1" in extracted
    assert "## Chapter 95" in extracted
    assert "<!--AUTHENTIC_SOURCE_PAGE:0096-->" in extracted
    assert "SCALABLE ENGINEERING REFERENCE" not in extracted
    assert "Engineering Reference / Page" not in extracted
    assert "Engineering Reference | Page" not in extracted


def test_large_durable_source_reaches_multi_volume_planning() -> None:
    from core.artifact_settings import artifact_settings

    source_size = artifact_settings.pdf_bundle_source_characters + 1
    assert artifact_settings.maximum_source_characters > source_size
    request = ArtifactComposeRequest(
        prompt="Create a professional PDF from the durable source.",
        format="pdf",
        source_snapshot={
            "kind": "uploaded_file",
            "summary": "Long source",
            "content": "x" * source_size,
        },
    )

    plan = plan_large_source(request)

    assert plan.source_character_count == source_size
    assert plan.bundle_volume_count == 2


def test_structured_uploaded_pdf_bypasses_flat_editorial_overview() -> None:
    extracted, title, _ = artifact_source_routes.extract_pdf_source(
        _semantic_source_pdf(),
    )
    request = ArtifactComposeRequest(
        prompt="Create a professional PDF of this uploaded PDF.",
        format="pdf",
        title=title,
        source_snapshot={
            "kind": "uploaded_file",
            "summary": "Semantic engineering source",
            "content": extracted,
            "attachment_names": ["semantic-source.pdf"],
        },
    )
    profile = resolve_source_fidelity(request, extracted)
    organized = organize_source_losslessly(
        profile,
        fallback_title=title or "Professional Document",
    )
    artifact = normalize_document_structure(
        parse_artifact_document(
            normalize_markdown_source(organized),
            title=title,
        )
    )

    assert is_canonical_artifact_markdown(extracted) is True
    assert "## Editorial Overview" not in organized
    assert len(artifact.sections) >= 2
    assert any(
        isinstance(block, TableBlock)
        for section in artifact.sections
        for block in section.blocks
    )


def test_generic_professional_request_for_uploaded_pdf_uses_redesign_profile() -> None:
    request = request_with_separate_source(
        prompt="Create a professional PDF of this PDF.",
    )
    assert resolve_document_profile(request).profile_id == "redesign_existing"


def test_wide_table_stays_with_its_section_heading(
    tmp_path: Path,
) -> None:
    artifact = ArtifactDocument(
        title="Wide Table Layout Test",
        subtitle=None,
        author=None,
        sections=(
            ArtifactSection(
                title="Wide Results",
                level=1,
                blocks=(
                    TableBlock(
                        columns=("A", "B", "C", "D", "E", "F"),
                        rows=tuple(
                            tuple(f"Value {row}-{column}" for column in range(6))
                            for row in range(10)
                        ),
                    ),
                ),
            ),
        ),
        layout_brief=ArtifactLayoutBrief(
            family="data_report",
            include_table_of_contents=False,
            include_section_openers=False,
            use_landscape_for_wide_tables=True,
            footer_mode="none",
        ),
    )
    output = tmp_path / "wide-table.pdf"
    render_pdf(artifact, output)
    rendered = pymupdf.open(output)
    try:
        matching_pages = [
            page.get_text("text")
            for page in rendered
            if "Wide Results" in page.get_text("text")
        ]
    finally:
        rendered.close()

    assert len(matching_pages) == 1
    assert "TABLE 1" in matching_pages[0]


def test_uploaded_pdf_redesign_keeps_technology_as_prose() -> None:
    source_pdf = pymupdf.open()
    page = source_pdf.new_page()
    page.insert_text(
        (72, 72),
        (
            "Authentic AI Final Build Phases and Change Baseline\n"
            "Editorial Overview\n"
            "technology.\n"
            "The platform uses modern technology for a complete engineering "
            "implementation plan and faculty-ready professional submission.\n"
            "Conclusion\n"
            "The final report preserves the verified source meaning."
        ),
    )
    payload = source_pdf.tobytes()
    source_pdf.close()

    extracted, metadata_title, _ = (
        artifact_source_routes.extract_pdf_source(payload)
    )
    request = ArtifactComposeRequest(
        prompt="Create a professional PDF of this uploaded PDF.",
        format="pdf",
        title=(
            metadata_title
            or "Authentic AI Final Build Phases and Change Baseline"
        ),
        source_snapshot={
            "kind": "uploaded_file",
            "summary": "Uploaded BTech project source",
            "content": extracted,
            "attachment_names": ["source.pdf"],
        },
    )
    profile = resolve_source_fidelity(request, extracted)
    organized = organize_source_losslessly(
        profile,
        fallback_title=request.title or "Professional Document",
    )
    artifact = normalize_document_structure(
        parse_artifact_document(
            normalize_markdown_source(organized),
            title=request.title,
        )
    )
    quality = validate_document_quality(
        artifact,
        source_snapshot=request.source_snapshot.model_dump(),
    )

    assert "$$technology.$$" not in organized
    assert quality.error_count == 0, quality.to_dict()


def test_legacy_document_prompt_is_compacted_instead_of_rejected() -> None:
    compacted = compact_analysis_instruction(
        "Redesign the attached PDF professionally. " * 500,
        maximum_characters=4_000,
    )
    assert 0 < len(compacted) <= 4_000


def test_v20_preserves_v19_registry_and_has_no_default_page_cap() -> None:
    assert len(architecture_registry()) == 500
    estimate = estimate_prompt_budget("small prompt", mode="standard")
    assert estimate.within_budget is True
    from core.artifact_settings import artifact_settings

    assert artifact_settings.enforce_single_pdf_page_limit is False
