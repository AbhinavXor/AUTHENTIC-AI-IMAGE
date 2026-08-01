from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from artifacts.layout_brief import apply_layout_brief
from artifacts.parser import parse_artifact_document
from artifacts.pdf_renderer import render_pdf
from schemas.artifact_composer import ArtifactComposeRequest


def _request(**updates):
    base = {
        "prompt": "Create a professional PDF.",
        "format": "pdf",
        "branding_mode": "none",
    }
    base.update(updates)
    return ArtifactComposeRequest(**base)


def test_default_layout_is_unbranded_and_metadata_free() -> None:
    request = _request()
    artifact = parse_artifact_document(
        "# Operational Report\n\n## Findings\n\nClear findings.",
    )
    resolved = apply_layout_brief(request, artifact)

    assert resolved.layout_brief.branding_mode == "none"
    assert resolved.layout_brief.footer_mode == "none"
    assert resolved.layout_brief.header_mode == "none"


def test_layout_family_is_inferred_from_document_intent() -> None:
    artifact = parse_artifact_document(
        "# Calculus Study Guide\n\n## Derivatives\n\nA worked example."
    )
    resolved = apply_layout_brief(
        _request(
            prompt=(
                "Create an academic textbook with chapters, worked examples, "
                "theorems and review questions."
            )
        ),
        artifact,
    )

    assert resolved.layout_brief.family == "academic_textbook"
    assert resolved.layout_brief.include_section_openers is True


def test_explicit_layout_override_wins() -> None:
    artifact = parse_artifact_document(
        "# Metrics\n\n## Results\n\nA concise result."
    )
    resolved = apply_layout_brief(
        _request(
            layout_family="case_study",
            visual_density="spacious",
            header_mode="running_section",
        ),
        artifact,
    )

    assert resolved.layout_brief.family == "case_study"
    assert resolved.layout_brief.visual_density == "spacious"
    assert resolved.layout_brief.header_mode == "running_section"


def test_unbranded_pdf_does_not_inject_authentic_ai(tmp_path: Path) -> None:
    request = _request(
        title="University Operations Report",
        author=None,
        layout_family="executive_report",
    )
    artifact = parse_artifact_document(
        """
# University Operations Report

## Executive Summary

The university can streamline routine administrative work.

## Recommendations

- Automate standard requests.
- Keep human review for exceptions.
""",
        title=request.title,
        author=request.author,
    )
    artifact = apply_layout_brief(request, artifact)
    output = tmp_path / "unbranded.pdf"
    render_pdf(artifact, output)

    text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)
    assert "Authentic AI" not in text
    assert "University Operations Report" in text


def test_wide_table_uses_landscape_page(tmp_path: Path) -> None:
    request = _request(
        title="Process Comparison",
        layout_family="data_report",
    )
    artifact = parse_artifact_document(
        """
# Process Comparison

## Comparative Analysis

| Workflow Area | Legacy Manual Process | AI Automated Process | Primary Technology Stack | Processing Time Reduction | Human Involvement Level |
|---|---|---|---|---|---|
| Admissions Triage | Manual transcript review and SIS entry | Document parsing and automated extraction | Vision OCR, NLP, Integration Bus | 94.8% reduction | Exception review and final decision |
| Financial Aid Verification | Cross-checking financial records | Rules engine and anomaly detection | Automated Decision Systems | 94.4% reduction | High-risk and appeal cases only |
""",
        title=request.title,
    )
    artifact = apply_layout_brief(request, artifact)
    output = tmp_path / "wide-table.pdf"
    render_pdf(artifact, output)

    pages = PdfReader(output).pages
    assert any(
        float(page.mediabox.width) > float(page.mediabox.height)
        for page in pages
    )
