from artifacts.architecture_autopilot import select_architecture
from artifacts.architecture_registry import architecture_registry
from artifacts.layout_brief import apply_layout_brief
from artifacts.parser import parse_artifact_document
from schemas.artifact_composer import ArtifactComposeRequest


def test_registry_contains_exactly_500_architectures() -> None:
    registry = architecture_registry()
    assert len(registry) == 500
    assert "final_year_capstone_report.code_first_technical.comprehensive" in registry
    assert "lecture_notes.visual_learning.concise" in registry


def test_autopilot_selects_btech_machine_learning_architecture() -> None:
    document = parse_artifact_document(
        "# Transformer Final-Year Project\n\n## Methodology\n\n```python\nprint('train')\n```\n\n## Results\n\n| Metric | Value |\n|---|---:|\n| Accuracy | 94.2 |"
    )
    decision = select_architecture(
        request_text="BTech final-year machine learning project report with code, dataset analysis and graphs",
        document=document,
        requested_length="detailed",
        presentation_tier="professional",
    )
    assert decision.architecture_id == "final_year_capstone_report.code_first_technical.comprehensive"
    assert decision.domain_overlay == "ai_machine_learning"
    assert "code_explanation" in decision.page_strategy
    assert "chart_analysis" in decision.page_strategy


def test_generic_design_revision_selects_a_distinct_visual_system() -> None:
    document = parse_artifact_document(
        "# Smart Campus Final-Year Project\n\n"
        "## Overview\n\nA faculty-ready BTech capstone report."
    )
    original = select_architecture(
        request_text="BTech final-year project report",
        document=document,
        requested_length="detailed",
        presentation_tier="professional",
    )
    revised = select_architecture(
        request_text="Isko best professional design me final kar do.",
        document=document,
        requested_length="detailed",
        previous_architecture_id=original.architecture_id,
        force_distinct=True,
    )

    assert original.architecture_id != revised.architecture_id
    assert original.architecture_id.split(".")[1] == "modern_engineering"
    assert revised.architecture_id.split(".")[1] == "technical_grid"


def test_fresh_normal_professional_and_premium_requests_are_distinct() -> None:
    document = parse_artifact_document(
        "# Smart Campus Project\n\n## Overview\n\nA BTech project report."
    )
    normal = select_architecture(
        request_text="Create a PDF from this project.",
        document=document,
        presentation_tier="standard",
    )
    professional = select_architecture(
        request_text="Create a professional PDF from this project.",
        document=document,
        presentation_tier="professional",
    )
    premium = select_architecture(
        request_text="Make this the best professional final-ready PDF.",
        document=document,
        presentation_tier="premium",
    )

    assert normal.architecture_id.split(".")[1] == "accessible_reading"
    assert professional.architecture_id.split(".")[1] == "modern_engineering"
    assert premium.architecture_id.split(".")[1] == "technical_grid"
    assert len({normal.architecture_id, professional.architecture_id, premium.architecture_id}) == 3


def test_explicit_creation_style_overrides_presentation_tier() -> None:
    document = parse_artifact_document(
        "# Project Report\n\n## Overview\n\nTechnical content."
    )
    decision = select_architecture(
        request_text="Create a premium black-and-white monochrome PDF.",
        document=document,
        presentation_tier="premium",
    )
    assert decision.architecture_id.split(".")[1] == "print_optimized_monochrome"


def test_explicit_revision_style_is_not_overridden_by_rotation() -> None:
    document = parse_artifact_document(
        "# Project Report\n\n## Overview\n\nTechnical content."
    )
    revised = select_architecture(
        request_text="Use a black-and-white monochrome print design.",
        document=document,
        previous_architecture_id=(
            "technical_proposal_and_portfolio."
            "print_optimized_monochrome.comprehensive"
        ),
        force_distinct=True,
    )
    assert (
        revised.architecture_id.split(".")[1]
        == "print_optimized_monochrome"
    )


def test_layout_brief_has_no_fixed_page_limit() -> None:
    request = ArtifactComposeRequest(
        prompt="Create complete calculus study notes with solved equations and graphs.",
        length="detailed",
        source_snapshot={
            "kind": "explicit_prompt",
            "summary": "Calculus notes",
            "content": "# Calculus Notes\n\n## Derivatives\n\n$$f'(x)=2x$$",
        },
    )
    document = parse_artifact_document("# Calculus Notes\n\n## Derivatives\n\n$$f'(x)=2x$$")
    resolved = apply_layout_brief(request, document)
    assert resolved.layout_brief.page_limit is None
    assert resolved.layout_brief.architecture_id
    assert resolved.layout_brief.domain_overlay == "mathematics"


def test_role_name_is_never_used_as_title() -> None:
    document = parse_artifact_document("# User\n\n# AI-Enabled University Operations\n\n## Overview\n\nContent")
    assert document.title == "AI-Enabled University Operations"


def test_exact_duplicate_sections_are_removed() -> None:
    document = parse_artifact_document(
        "# Report\n\n## Findings\n\nSame content.\n\n## Findings\n\nSame content."
    )
    assert [section.title for section in document.sections].count("Findings") == 1
