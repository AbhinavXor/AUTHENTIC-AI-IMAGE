from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from artifacts.architecture_registry import VISUAL_SYSTEMS, architecture_registry
from artifacts.models import ArtifactDocument

ArchitectureMode = Literal[
    "preset",
    "customized_preset",
    "hybrid",
    "synthesized",
    "safe_fallback",
]

PresentationTier = Literal[
    "auto",
    "standard",
    "professional",
    "premium",
]


@dataclass(frozen=True, slots=True)
class ArchitectureDecision:
    architecture_id: str
    mode: ArchitectureMode
    domain_overlay: str
    page_strategy: tuple[str, ...]
    confidence: float
    rationale: tuple[str, ...]


_FAMILY_RULES: tuple[tuple[str, str], ...] = (
    ("final_year_capstone_report", r"final[- ]?year|capstone|major project"),
    ("mini_project_report", r"mini project"),
    ("laboratory_report", r"lab(?:oratory)? report|experiment report"),
    ("laboratory_manual", r"lab(?:oratory)? manual"),
    ("technical_research_paper", r"research paper|methodology|abstract|experiment"),
    ("literature_review", r"literature review|related work"),
    ("internship_report", r"internship report|industrial training"),
    ("seminar_technical_report", r"seminar report|technical seminar"),
    ("software_project_documentation", r"software project|api|source code|implementation"),
    ("data_analysis_and_simulation_report", r"data analysis|simulation|dataset|benchmark|kpi"),
    ("engineering_design_document", r"system architecture|engineering design|technical design"),
    ("solved_problem_book", r"solved problems?|worked examples?|numericals"),
    ("formula_handbook", r"formula sheet|formula handbook"),
    ("exam_revision_notes", r"exam|revision|last minute|quick notes"),
    ("viva_preparation_guide", r"viva|interview questions?"),
    ("previous_year_question_solution", r"previous year|pyq|question paper"),
    ("practice_problem_set", r"practice problems?|exercise set"),
    ("tutorial_workbook", r"tutorial|workbook"),
    ("university_assignment", r"assignment|homework"),
    ("chapter_study_guide", r"chapter|complete notes|study guide"),
    ("lecture_notes", r"lecture notes?|class notes?"),
)

_DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    ("ai_machine_learning", r"machine learning|deep learning|neural|transformer|dataset|model training"),
    ("computer_science", r"computer science|programming|algorithm|database|dbms|operating system|network|software"),
    ("electronics_electrical", r"electronics|electrical|circuit|signal|control system|microprocessor|vlsi"),
    ("mechanical_engineering", r"mechanical|thermodynamic|fluid|machine design|stress|strain"),
    ("civil_engineering", r"civil|structure|survey|concrete|construction|geotechnical"),
    ("mathematics", r"mathematics|calculus|algebra|equation|theorem|proof|derivative|integral"),
    ("physics", r"physics|quantum|mechanics|optics|electromagnetic"),
    ("chemistry", r"chemistry|reaction|molecule|organic|inorganic"),
)


def _match(text: str, rules: tuple[tuple[str, str], ...], fallback: str) -> tuple[str, float]:
    for index, (value, pattern) in enumerate(rules):
        if re.search(pattern, text, re.IGNORECASE):
            return value, max(0.72, 0.96 - index * 0.012)
    return fallback, 0.55


def _visual_system(text: str, *, domain: str, has_code: bool, has_data: bool, has_math: bool) -> str:
    if has_code or domain in {"computer_science", "ai_machine_learning"}:
        return "code_first_technical"
    if has_data:
        return "data_rich_analytical"
    if has_math or re.search(r"study|notes|learn|explain", text, re.IGNORECASE):
        return "visual_learning"
    if re.search(r"research|formal|publication", text, re.IGNORECASE):
        return "formal_research"
    return "modern_engineering"


_PREMIUM_PRESENTATION = re.compile(
    r"\b(?:best\s+professional|highly\s+professional|most\s+professional|"
    r"premium|publication[- ]quality|submission[- ]ready|faculty[- ]ready|"
    r"final[- ]ready|portfolio[- ]ready|executive[- ]grade|world[- ]class|"
    r"polished|professionally\s+(?:final|redesign|design|ready))\b",
    re.IGNORECASE,
)

_PROFESSIONAL_PRESENTATION = re.compile(
    r"\b(?:professional|professionally|academic[- ]quality|college\s+submission)\b",
    re.IGNORECASE,
)


def _resolved_presentation_tier(
    request_text: str,
    configured: PresentationTier,
) -> Literal["standard", "professional", "premium"]:
    if configured != "auto":
        return configured
    if _PREMIUM_PRESENTATION.search(request_text):
        return "premium"
    if _PROFESSIONAL_PRESENTATION.search(request_text):
        return "professional"
    return "standard"


def _explicit_visual_system(request_text: str) -> str | None:
    rules = (
        ("print_optimized_monochrome", r"black.?and.?white|monochrome|print[- ]optimized"),
        ("minimal_academic", r"minimal(?:\s+academic)?"),
        ("classic_university", r"classic|university\s+style"),
        ("modern_engineering", r"modern\s+engineering"),
        ("technical_grid", r"technical\s+grid"),
        ("formal_research", r"formal\s+research"),
        ("data_rich_analytical", r"data[- ]rich"),
        ("visual_learning", r"visual\s+learning"),
        ("code_first_technical", r"code[- ]first"),
        ("accessible_reading", r"accessible(?:\s+reading)?"),
    )
    for visual_system, pattern in rules:
        if re.search(pattern, request_text, re.IGNORECASE):
            return visual_system
    return None


def _visual_for_tier(
    inferred_visual: str,
    tier: Literal["standard", "professional", "premium"],
) -> str:
    """Apply a visible quality tier without sacrificing explicit directions.

    Standard documents favor neutral readability. Professional documents use
    the content-aware visual system. Premium requests intentionally move to a
    higher-contrast publication system, ensuring that a user-requested visual
    upgrade cannot silently render the same architecture as a normal PDF.
    """

    if tier == "standard":
        return "accessible_reading"
    if tier == "professional":
        return inferred_visual
    premium_map = {
        "visual_learning": "classic_university",
        "formal_research": "classic_university",
        "print_optimized_monochrome": "classic_university",
    }
    return premium_map.get(inferred_visual, "technical_grid")


_EXPLICIT_VISUAL_DIRECTION = re.compile(
    r"\b(?:minimal|classic|university style|modern engineering|technical grid|"
    r"formal research|data[- ]rich|visual learning|code[- ]first|monochrome|"
    r"black.?and.?white|accessible)\b",
    re.IGNORECASE,
)


def _next_visual_system(current: str) -> str:
    """Return a deterministic, professional alternative to *current*.

    This is used only for generic design-only revisions. Explicit user style
    requests always win, while requests such as "best professional design"
    must produce a visibly distinct version instead of re-rendering the same
    architecture.
    """

    cycle = (
        "modern_engineering",
        "technical_grid",
        "classic_university",
        "minimal_academic",
        "formal_research",
        "data_rich_analytical",
        "visual_learning",
        "code_first_technical",
        "print_optimized_monochrome",
        "accessible_reading",
    )
    try:
        return cycle[(cycle.index(current) + 1) % len(cycle)]
    except ValueError:
        return "modern_engineering"


def _page_strategy(document: ArtifactDocument, *, domain: str) -> tuple[str, ...]:
    strategies: list[str] = ["cover", "contents"]
    block_names = {type(block).__name__ for section in document.sections for block in section.blocks}
    titles = " ".join(section.title for section in document.sections).casefold()
    if "EquationBlock" in block_names or domain in {"mathematics", "physics", "electronics_electrical"}:
        strategies.extend(["equation_derivation", "worked_example", "formula_summary"])
    if "CodeBlock" in block_names or domain in {"computer_science", "ai_machine_learning"}:
        strategies.extend(["algorithm", "code_explanation", "architecture_diagram"])
    if "TableBlock" in block_names:
        strategies.extend(["comparison_table", "wide_landscape_table"])
    if "ChartBlock" in block_names or any(word in titles for word in ("result", "performance", "analysis", "kpi")):
        strategies.append("chart_analysis")
    if "risk" in titles:
        strategies.append("risk_matrix")
    if any(word in titles for word in ("roadmap", "timeline", "implementation")):
        strategies.extend(["timeline", "roadmap"])
    strategies.extend(["normal_reading", "conclusion", "references", "appendix"])
    return tuple(dict.fromkeys(strategies))


def select_architecture(
    *,
    request_text: str,
    document: ArtifactDocument,
    requested_length: str = "standard",
    requested_visual_system: str = "auto",
    presentation_tier: PresentationTier = "auto",
    previous_architecture_id: str | None = None,
    force_distinct: bool = False,
) -> ArchitectureDecision:
    source_text = "\n".join(
        [request_text, document.title]
        + [section.title for section in document.sections]
        + [
            getattr(block, "text", "")
            for section in document.sections
            for block in section.blocks
        ]
    )[:80_000]
    family, family_confidence = _match(source_text, _FAMILY_RULES, "technical_proposal_and_portfolio")
    domain, domain_confidence = _match(source_text, _DOMAIN_RULES, "general_engineering")
    block_names = {type(block).__name__ for section in document.sections for block in section.blocks}
    has_code = "CodeBlock" in block_names
    has_data = "TableBlock" in block_names or "ChartBlock" in block_names
    has_math = "EquationBlock" in block_names or bool(re.search(r"\b(?:equation|formula|calculate|solve|roi|=)\b", source_text, re.IGNORECASE))
    inferred_visual = _visual_system(
        source_text,
        domain=domain,
        has_code=has_code,
        has_data=has_data,
        has_math=has_math,
    )
    resolved_tier = _resolved_presentation_tier(
        request_text,
        presentation_tier,
    )
    explicit_visual = _explicit_visual_system(request_text)
    visual = (
        requested_visual_system
        if requested_visual_system in VISUAL_SYSTEMS
        else (
            explicit_visual
            or _visual_for_tier(
                inferred_visual,
                resolved_tier,
            )
        )
    )
    explicit_family_request = any(
        re.search(pattern, request_text, re.IGNORECASE)
        for _, pattern in _FAMILY_RULES
    )
    previous_parts = (
        previous_architecture_id.split(".")
        if previous_architecture_id
        else []
    )
    if (
        force_distinct
        and len(previous_parts) == 3
        and not explicit_family_request
    ):
        # A generic restyle must preserve the semantic document family.
        # The revision changes presentation, not whether a capstone suddenly
        # becomes a proposal, lecture note, or another document type.
        family = previous_parts[0]

    detail = "concise" if requested_length == "brief" else "comprehensive"
    architecture_id = f"{family}.{visual}.{detail}"
    if (
        force_distinct
        and len(previous_parts) == 3
        and previous_parts[1] == visual
        and requested_visual_system == "auto"
        and _EXPLICIT_VISUAL_DIRECTION.search(request_text) is None
    ):
        visual = _next_visual_system(visual)
        architecture_id = f"{family}.{visual}.{detail}"
    registry = architecture_registry()
    confidence = round((family_confidence * 0.55) + (domain_confidence * 0.25) + 0.20, 3)

    if architecture_id in registry and confidence >= 0.82:
        mode: ArchitectureMode = "preset"
    elif architecture_id in registry and confidence >= 0.68:
        mode = "customized_preset"
    elif confidence >= 0.58:
        mode = "hybrid"
    else:
        mode = "synthesized"

    # The family/visual product space is complete, so synthesized decisions
    # still resolve to a safe registered base while retaining custom page logic.
    if architecture_id not in registry:
        architecture_id = "technical_proposal_and_portfolio.accessible_reading.comprehensive"
        mode = "safe_fallback"

    return ArchitectureDecision(
        architecture_id=architecture_id,
        mode=mode,
        domain_overlay=domain,
        page_strategy=_page_strategy(document, domain=domain),
        confidence=confidence,
        rationale=(
            f"Detected document family: {family.replace('_', ' ')}.",
            f"Detected domain overlay: {domain.replace('_', ' ')}.",
            f"Selected visual system: {visual.replace('_', ' ')}.",
            f"Applied presentation tier: {resolved_tier}.",
            *(
                ("Selected a distinct design system for this design revision.",)
                if force_distinct and previous_architecture_id != architecture_id
                else ()
            ),
            "No fixed page limit is applied; pagination follows content.",
        ),
    )
