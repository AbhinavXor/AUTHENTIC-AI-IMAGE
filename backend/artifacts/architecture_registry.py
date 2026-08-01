from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

ArchitectureDetailMode = Literal["concise", "comprehensive"]

DOCUMENT_FAMILIES: tuple[str, ...] = (
    "lecture_notes",
    "chapter_study_guide",
    "concept_explanation",
    "exam_revision_notes",
    "formula_handbook",
    "solved_problem_book",
    "practice_problem_set",
    "tutorial_workbook",
    "viva_preparation_guide",
    "previous_year_question_solution",
    "university_assignment",
    "laboratory_manual",
    "laboratory_report",
    "experiment_observation_report",
    "mini_project_report",
    "major_project_report",
    "final_year_capstone_report",
    "engineering_design_document",
    "software_project_documentation",
    "data_analysis_and_simulation_report",
    "technical_research_paper",
    "literature_review",
    "internship_report",
    "seminar_technical_report",
    "technical_proposal_and_portfolio",
)

VISUAL_SYSTEMS: tuple[str, ...] = (
    "minimal_academic",
    "classic_university",
    "modern_engineering",
    "technical_grid",
    "formal_research",
    "data_rich_analytical",
    "visual_learning",
    "code_first_technical",
    "print_optimized_monochrome",
    "accessible_reading",
)

DETAIL_MODES: tuple[ArchitectureDetailMode, ...] = (
    "concise",
    "comprehensive",
)

PAGE_COMPONENTS: tuple[str, ...] = (
    "cover",
    "contents",
    "chapter_opener",
    "executive_summary",
    "normal_reading",
    "two_column_analysis",
    "definition",
    "theorem",
    "proof",
    "formula_summary",
    "equation_derivation",
    "worked_example",
    "code_explanation",
    "algorithm",
    "comparison_table",
    "wide_landscape_table",
    "chart_analysis",
    "diagram",
    "architecture_diagram",
    "process_flow",
    "risk_matrix",
    "timeline",
    "roadmap",
    "kpi_dashboard",
    "recommendations",
    "conclusion",
    "glossary",
    "references",
    "appendix",
    "viva_questions",
)


@dataclass(frozen=True, slots=True)
class ArchitectureProfile:
    architecture_id: str
    family: str
    visual_system: str
    detail_mode: ArchitectureDetailMode
    supported_components: tuple[str, ...]


@lru_cache(maxsize=1)
def architecture_registry() -> dict[str, ArchitectureProfile]:
    """Return exactly 500 deterministic, validated architecture profiles.

    Profiles are generated from a controlled product space rather than 500
    copied templates. This keeps every profile testable and lets the renderer
    compose new layouts from the same safe component vocabulary.
    """

    registry: dict[str, ArchitectureProfile] = {}
    for family in DOCUMENT_FAMILIES:
        for visual_system in VISUAL_SYSTEMS:
            for detail_mode in DETAIL_MODES:
                architecture_id = f"{family}.{visual_system}.{detail_mode}"
                registry[architecture_id] = ArchitectureProfile(
                    architecture_id=architecture_id,
                    family=family,
                    visual_system=visual_system,
                    detail_mode=detail_mode,
                    supported_components=PAGE_COMPONENTS,
                )
    if len(registry) != 500:
        raise RuntimeError("Architecture registry must contain exactly 500 profiles.")
    return registry
