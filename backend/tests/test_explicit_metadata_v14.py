from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from artifacts.layout_brief import apply_layout_brief
from artifacts.parser import parse_artifact_document
from artifacts.pdf_renderer import render_pdf
from artifacts.planner import plan_artifact
from schemas.artifact_composer import ArtifactComposeRequest


def _request(**updates):
    base = {
        "prompt": "Create a professional PDF about university AI automation.",
        "format": "pdf",
        "branding_mode": "none",
    }
    base.update(updates)
    return ArtifactComposeRequest(**base)


def test_title_excludes_style_and_include_directives() -> None:
    request, plan = plan_artifact(
        _request(
            prompt=(
                "Create an unbranded professional executive report about "
                "university AI automation. Include: executive summary, "
                "operational workflow analysis, comparison table and risks."
            )
        )
    )

    assert plan.title == "University AI Automation"
    assert request.title == "University AI Automation"


def test_default_cover_metadata_is_explicit_only() -> None:
    request = _request(layout_family="executive_report")
    artifact = parse_artifact_document(
        "# University AI Automation\n\n## Findings\n\nClear findings.",
        title="University AI Automation",
    )
    resolved = apply_layout_brief(request, artifact)
    brief = resolved.layout_brief

    assert brief.cover_eyebrow is None
    assert brief.cover_show_profile is False
    assert brief.cover_show_subtitle is False
    assert brief.cover_show_date is False
    assert brief.header_mode == "none"
    assert brief.footer_mode == "none"


def test_explicit_date_subtitle_and_page_numbers_are_honoured() -> None:
    request = _request(
        prompt=(
            "Create a report about university AI automation with a subtitle, "
            "include the current date and page numbers."
        ),
        subtitle="Operational transformation plan",
        layout_family="executive_report",
    )
    artifact = parse_artifact_document(
        "# University AI Automation\n\n## Findings\n\nClear findings.",
        title="University AI Automation",
        subtitle=request.subtitle,
    )
    brief = apply_layout_brief(request, artifact).layout_brief

    assert brief.cover_show_subtitle is True
    assert brief.cover_show_date is True
    assert brief.footer_mode == "page_number"


def test_default_pdf_contains_no_auto_date_label_profile_or_header(tmp_path: Path) -> None:
    request = _request(
        title="University AI Automation",
        layout_family="executive_report",
    )
    artifact = parse_artifact_document(
        """
# University AI Automation

## Executive Summary

A concise operational overview.

## Operational Workflow Analysis

A requested analysis section.
""",
        title=request.title,
    )
    artifact = apply_layout_brief(request, artifact)
    output = tmp_path / "explicit-only.pdf"
    render_pdf(artifact, output)

    reader = PdfReader(output)
    pages = reader.pages
    text = "\n".join(page.extract_text() or "" for page in pages)
    cover = pages[0].extract_text() or ""

    assert "EXECUTIVE REPORT" not in cover
    assert "Operational analysis, evidence, risks" not in cover
    assert "SECTIONS" not in cover
    assert "Prepared by" not in cover
    assert "2026" not in cover
    assert "Include:" not in cover
    assert "University AI Automation" in cover
    assert "Operational Workflow Analysis" in text
    assert "/CreationDate" not in (reader.metadata or {})
    assert "/ModDate" not in (reader.metadata or {})
