from __future__ import annotations

from pathlib import Path

from artifacts.source_fidelity import (
    looks_like_equation,
    organize_source_losslessly,
    resolve_source_fidelity,
)
from schemas.artifact_composer import ArtifactComposeRequest


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "mathematics_authoritative_source.txt"
)


def _source() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_equation_classifier_does_not_turn_prose_into_math_banner() -> None:
    assert looks_like_equation("x = 9") is True
    assert looks_like_equation("3x - 7 = 20") is True
    assert looks_like_equation("Therefore, x = 9 is correct.") is False
    assert looks_like_equation("The sign reverses whenever an inequality is divided by a negative number.") is False
    assert looks_like_equation("Important logarithm rules are:") is False
    assert looks_like_equation("technology.") is False
    assert looks_like_equation("The platform uses modern technology.") is False
    assert looks_like_equation("The catalog is ready for faculty review.") is False


def test_professional_textbook_structure_has_no_internal_leakage() -> None:
    source = _source()
    request = ArtifactComposeRequest(
        prompt=source,
        format="pdf",
        title="Add a Comparison Table and a New Version",
    )
    profile = resolve_source_fidelity(request, source)
    content = organize_source_losslessly(
        profile,
        fallback_title=request.title or "Document",
    )

    assert content.startswith("# Mathematics:")
    assert "Add a Comparison Table and a New Version" not in content
    assert "Document Production Requirements" not in content
    assert "hidden in chat preview" not in content
    assert "## Executive Overview" in content
    assert "## Learning Roadmap" in content
    assert "## Part IV" in content
    assert "## Glossary and Notation" in content
    assert "## Conclusion" in content
    assert "| Derivative | An instantaneous rate of change" in content
    assert "| For example |" not in content
    assert "#### Example" not in content
    assert "**Example:**" in content
