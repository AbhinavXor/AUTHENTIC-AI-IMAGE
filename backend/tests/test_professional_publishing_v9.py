from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from artifacts.equations import normalize_math_expression
from artifacts.large_source import estimate_pdf_pages, plan_large_source
from artifacts.models import (
    ArtifactDocument,
    ArtifactSection,
    PageBreakBlock,
    ParagraphBlock,
)
from artifacts.pdf_renderer import render_pdf
from artifacts.quality import inspect_rendered_file
from schemas.artifact_composer import ArtifactComposeRequest


def test_equation_normalization_handles_degrees_and_radians() -> None:
    normalized = normalize_math_expression(
        "180 degrees = π radians"
    )
    assert "180^{\\circ}" in normalized
    assert "\\pi" in normalized
    assert "\\mathrm{radians}" in normalized


def test_equation_normalization_preserves_indefinite_integrals() -> None:
    normalized = normalize_math_expression("∫(3x² - 4) dx")
    assert normalized.startswith("\\int")
    assert "3x^{2} - 4" in normalized
    assert "\\,dx" in normalized
    assert "_{3}" not in normalized
    assert "^{2}" in normalized


def test_equation_normalization_uses_professional_fractions() -> None:
    expected_value = normalize_math_expression(
        "E(X) = [1 + 2 + 3 + 4 + 5 + 6]/6"
    )
    conditional = normalize_math_expression(
        "P(A|B) = P(A∩B)/P(B)"
    )
    assert "\\frac{1 + 2 + 3 + 4 + 5 + 6}{6}" in expected_value
    assert "\\frac{P(A\\cap B)}{P(B)}" in conditional


def test_estimated_three_hundred_page_source_stays_single_pdf() -> None:
    source = " ".join(["mathematics"] * 83_000)
    estimated = estimate_pdf_pages(source)
    assert 285 <= estimated <= 320

    plan = plan_large_source(
        ArtifactComposeRequest(
            prompt=source,
            format="pdf",
            title="Three Hundred Page Reference",
        )
    )
    assert plan.estimated_page_count == estimated
    assert plan.bundle_volume_count is None


def test_source_above_legacy_page_budget_has_no_default_page_cap() -> None:
    source = " ".join(["mathematics"] * 96_000)
    plan = plan_large_source(
        ArtifactComposeRequest(
            prompt=source,
            format="pdf",
            title="Oversized Reference",
        )
    )
    assert plan.estimated_page_count > 320
    assert plan.bundle_volume_count is None


def test_renderer_supports_a_single_pdf_near_three_hundred_pages(
    tmp_path: Path,
) -> None:
    sections: list[ArtifactSection] = []
    for index in range(1, 291):
        blocks: list[object] = [
            ParagraphBlock(
                "This page validates stable long-document pagination, "
                "embedded typography, running headers, bookmarks, and "
                "source-faithful text rendering."
            )
        ]
        if index < 290:
            blocks.append(PageBreakBlock(reason="stress_test"))
        sections.append(
            ArtifactSection(
                title=f"{index}. Long Document Validation Chapter",
                level=2,
                blocks=tuple(blocks),
            )
        )

    output = tmp_path / "professional-300-page-validation.pdf"
    render_pdf(
        ArtifactDocument(
            title="Professional Publishing 300-Page Validation",
            subtitle="Long-document reliability and publication-quality rendering",
            author="Authentic AI",
            sections=tuple(sections),
        ),
        output,
    )

    reader = PdfReader(str(output))
    assert 300 <= len(reader.pages) <= 320
    assert reader.outline

    quality = inspect_rendered_file(output, format="pdf")
    assert quality.error_count == 0, quality.to_dict()
    assert not any(
        issue.code == "unembedded_pdf_fonts"
        for issue in quality.issues
    )
