from __future__ import annotations

import re
from dataclasses import replace

from artifacts.architecture_autopilot import select_architecture
from artifacts.models import (
    ArtifactDocument,
    ArtifactLayoutBrief,
    BrandingMode,
    CalloutBlock,
    ChartBlock,
    EquationBlock,
    LayoutFamily,
    TableBlock,
)
from schemas.artifact_composer import ArtifactComposeRequest

_LAYOUT_PATTERNS: tuple[tuple[LayoutFamily, re.Pattern[str]], ...] = (
    (
        "academic_textbook",
        re.compile(
            r"\b(?:textbook|academic\s+notes?|lesson|chapter|theorem|proof|"
            r"worked\s+examples?|mathematics|physics|chemistry|calculus|algebra|"
            r"study\s+guide|learning\s+material)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "research_paper",
        re.compile(
            r"\b(?:research\s+paper|research\s+report|literature\s+review|"
            r"methodology|evidence\s+review|experiment|abstract)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "technical_spec",
        re.compile(
            r"\b(?:technical\s+spec(?:ification)?|architecture|engineering|"
            r"api|implementation|system\s+design|security\s+design|runbook|"
            r"deployment|data\s+model)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "proposal_document",
        re.compile(
            r"\b(?:proposal|business\s+case|statement\s+of\s+work|sow|"
            r"project\s+plan|implementation\s+plan|pitch|investment\s+case|"
            r"budget|timeline|milestone)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "case_study",
        re.compile(
            r"\b(?:case\s+study|customer\s+story|before\s+and\s+after|"
            r"challenge\s+solution|outcomes?|lessons?\s+learned)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "data_report",
        re.compile(
            r"\b(?:data\s+report|analytics|dashboard|benchmark|metrics?|kpi|"
            r"statistical|survey\s+results?|performance\s+report|comparison\s+table)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "executive_report",
        re.compile(
            r"\b(?:executive|board|leadership|management|strategy|strategic|"
            r"operational\s+analysis|risk\s+assessment|recommendations?|"
            r"decision\s+memo|business\s+report)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "modern_summary",
        re.compile(
            r"\b(?:minimal|modern|clean|summary|brief|one[-\s]?pager|"
            r"concise|simple\s+report)\b",
            re.IGNORECASE,
        ),
    ),
)

_DOCUMENT_TYPE_MAP: dict[str, LayoutFamily] = {
    "professional_report": "executive_report",
    "executive_brief": "executive_report",
    "technical_specification": "technical_spec",
    "research_report": "research_paper",
    "proposal": "proposal_document",
    "policy_document": "technical_spec",
    "presentation": "modern_summary",
    "general_document": "modern_summary",
    "academic_textbook": "academic_textbook",
    "data_report": "data_report",
    "case_study": "case_study",
    "modern_summary": "modern_summary",
}


def _source_text(request: ArtifactComposeRequest, artifact: ArtifactDocument) -> str:
    snapshot = request.source_snapshot
    return "\n".join(
        part
        for part in (
            request.prompt,
            request.purpose or "",
            request.audience or "",
            snapshot.summary if snapshot is not None else "",
            snapshot.content[:20_000]
            if snapshot is not None and snapshot.content
            else "",
            artifact.title,
            "\n".join(section.title for section in artifact.sections[:24]),
        )
        if part
    )


def _block_counts(artifact: ArtifactDocument) -> tuple[int, int, int, int]:
    tables = charts = equations = callouts = 0
    for section in artifact.sections:
        for block in section.blocks:
            tables += isinstance(block, TableBlock)
            charts += isinstance(block, ChartBlock)
            equations += isinstance(block, EquationBlock)
            callouts += isinstance(block, CalloutBlock)
    return tables, charts, equations, callouts


def _family(
    request: ArtifactComposeRequest,
    artifact: ArtifactDocument,
    text: str,
) -> tuple[LayoutFamily, list[str]]:
    requested = request.layout_family
    if requested != "auto":
        return requested, [f"Explicit layout family: {requested}."]

    prompt_text = "\n".join(
        part
        for part in (
            request.prompt,
            request.purpose or "",
            request.audience or "",
            request.source_snapshot.summary
            if request.source_snapshot is not None
            else "",
        )
        if part
    )
    explicit_family_patterns: tuple[tuple[LayoutFamily, re.Pattern[str]], ...] = (
        ("executive_report", re.compile(r"\b(?:executive report|executive brief|board report|leadership report)\b", re.IGNORECASE)),
        ("technical_spec", re.compile(r"\b(?:technical specification|technical spec|engineering specification)\b", re.IGNORECASE)),
        ("research_paper", re.compile(r"\b(?:research paper|research report|literature review)\b", re.IGNORECASE)),
        ("proposal_document", re.compile(r"\b(?:business proposal|project proposal|statement of work)\b", re.IGNORECASE)),
    )
    for family, pattern in explicit_family_patterns:
        if pattern.search(prompt_text):
            return family, [
                f"Explicit request selected the {family.replace('_', ' ')} family."
            ]

    for family, pattern in _LAYOUT_PATTERNS:
        if pattern.search(prompt_text):
            return family, [
                f"User request matched the {family.replace('_', ' ')} family."
            ]

    tables, charts, equations, _ = _block_counts(artifact)
    if equations >= 4:
        return "academic_textbook", [
            "Equation-rich source selected the academic textbook family."
        ]
    if charts >= 3 or tables >= 4:
        return "data_report", [
            "Visualization-heavy source selected the data report family."
        ]

    mapped = _DOCUMENT_TYPE_MAP.get(
        request.document_type,
        "modern_summary",
    )
    source_matches = [
        family
        for family, pattern in _LAYOUT_PATTERNS
        if pattern.search(text)
    ]
    if mapped in source_matches:
        return mapped, [
            f"Source signals confirmed the {mapped.replace('_', ' ')} document-type family."
        ]
    if source_matches:
        family = source_matches[0]
        return family, [
            f"Document language matched the {family.replace('_', ' ')} family."
        ]

    return mapped, [
        f"Document type mapped to the {mapped.replace('_', ' ')} family."
    ]

_NEGATIVE_DATE = re.compile(
    r"\b(?:no date|without (?:a )?date|remove (?:the )?date|date mat|date hata)\b",
    re.IGNORECASE,
)
_POSITIVE_DATE = re.compile(
    r"\b(?:include|show|add|display|print|with)\s+(?:the\s+)?(?:current\s+)?date\b|\bdated\s+document\b",
    re.IGNORECASE,
)
_POSITIVE_PROFILE = re.compile(
    r"\b(?:document statistics|cover metrics|section count|figure count|table count|equation count)\b",
    re.IGNORECASE,
)
_POSITIVE_LABEL = re.compile(
    r"\b(?:document type label|cover label|show (?:the )?(?:report|document) type)\b",
    re.IGNORECASE,
)
_POSITIVE_SUBTITLE = re.compile(
    r"\b(?:include|show|add|display|with)\s+(?:a\s+)?subtitle\b",
    re.IGNORECASE,
)
_POSITIVE_PAGE_NUMBERS = re.compile(
    r"\b(?:page numbers?|numbered pages?|paginate)\b",
    re.IGNORECASE,
)
_POSITIVE_RUNNING_HEADER = re.compile(
    r"\b(?:running header|section header|page header)\b",
    re.IGNORECASE,
)
_POSITIVE_TITLE_FOOTER = re.compile(
    r"\b(?:title in (?:the )?footer|footer with (?:the )?title)\b",
    re.IGNORECASE,
)


def _explicit_prompt(request: ArtifactComposeRequest) -> str:
    return "\n".join(
        part
        for part in (
            request.prompt,
            request.purpose or "",
        )
        if part
    )


def _header_mode(request: ArtifactComposeRequest, family: LayoutFamily) -> str:
    del family
    if request.header_mode != "auto":
        return request.header_mode
    if _POSITIVE_RUNNING_HEADER.search(_explicit_prompt(request)):
        return "running_section"
    return "none"


def _footer_mode(request: ArtifactComposeRequest) -> str:
    if request.footer_mode != "none":
        return request.footer_mode
    prompt = _explicit_prompt(request)
    if _POSITIVE_TITLE_FOOTER.search(prompt):
        return "page_number_and_title"
    if _POSITIVE_PAGE_NUMBERS.search(prompt):
        return "page_number"
    return "none"


def resolve_layout_brief(
    request: ArtifactComposeRequest,
    artifact: ArtifactDocument,
) -> ArtifactLayoutBrief:
    """Create a deterministic, source-aware layout brief.

    The composer may suggest a layout through request fields, but render-time
    policy remains deterministic: source content is never changed by this
    function, branding defaults to off, and unsupported combinations fall back
    to a readable professional layout.
    """

    text = _source_text(request, artifact)
    family, rationale = _family(request, artifact, text)
    tables, charts, equations, callouts = _block_counts(artifact)

    density = request.visual_density
    if density == "auto":
        if family in {"executive_report", "modern_summary"} and len(artifact.sections) <= 8:
            density = "spacious"
        elif tables >= 3 or equations >= 8:
            density = "compact"
        else:
            density = "balanced"

    branding: BrandingMode = request.branding_mode
    prompt = _explicit_prompt(request)
    cover_show_author = bool(request.author)
    cover_show_date = bool(request.include_cover_date)
    if _NEGATIVE_DATE.search(prompt):
        cover_show_date = False
    elif _POSITIVE_DATE.search(prompt):
        cover_show_date = True
    cover_profile = bool(request.include_cover_profile) or bool(
        _POSITIVE_PROFILE.search(prompt)
    )
    cover_show_subtitle = bool(request.subtitle) or bool(
        request.include_cover_subtitle
        or _POSITIVE_SUBTITLE.search(prompt)
    )
    show_document_label = bool(request.include_document_label) or bool(
        _POSITIVE_LABEL.search(prompt)
    )

    eyebrow_map: dict[LayoutFamily, str] = {
        "executive_report": "EXECUTIVE REPORT",
        "research_paper": "RESEARCH PUBLICATION",
        "academic_textbook": "ACADEMIC EDITION",
        "technical_spec": "TECHNICAL SPECIFICATION",
        "proposal_document": "PROPOSAL",
        "data_report": "DATA & ANALYTICS REPORT",
        "case_study": "CASE STUDY",
        "modern_summary": "PROFESSIONAL BRIEF",
    }

    if branding in {"title_only", "subtle", "full"}:
        cover_eyebrow = f"AUTHENTIC AI / {eyebrow_map[family]}"
    elif show_document_label:
        cover_eyebrow = eyebrow_map[family]
    else:
        cover_eyebrow = None

    include_section_openers = request.include_section_openers and family in {
        "academic_textbook",
        "technical_spec",
        "proposal_document",
        "case_study",
        "research_paper",
    }

    if callouts >= 3:
        rationale.append("Callout-rich content enabled section-aware emphasis blocks.")
    if tables >= 1:
        rationale.append("Table-aware pagination and width management enabled.")
    if charts >= 1:
        rationale.append("Chart-aware page composition enabled.")

    autopilot = select_architecture(
        # Use only the user's control text for presentation-tier and explicit
        # style detection. The parsed document still supplies content signals
        # inside select_architecture, while planner-authored words such as
        # "professional" cannot upgrade an otherwise normal request.
        request_text=request.prompt,
        document=artifact,
        requested_length=request.length,
        requested_visual_system=request.architecture_visual_system,
        presentation_tier=request.presentation_tier,
        previous_architecture_id=request.previous_architecture_id,
        force_distinct=request.design_revision,
    )
    rationale.extend(autopilot.rationale)

    return ArtifactLayoutBrief(
        family=family,
        branding_mode=branding,
        visual_density=density,
        header_mode=_header_mode(request, family),  # type: ignore[arg-type]
        footer_mode=_footer_mode(request),  # type: ignore[arg-type]
        include_table_of_contents=request.include_table_of_contents,
        include_section_openers=include_section_openers,
        use_landscape_for_wide_tables=True,
        cover_show_profile=cover_profile,
        cover_show_author=cover_show_author,
        cover_show_subtitle=cover_show_subtitle,
        cover_show_date=cover_show_date,
        cover_eyebrow=cover_eyebrow,
        rationale=tuple(rationale),
        architecture_id=autopilot.architecture_id,
        visual_system=autopilot.architecture_id.split(".")[1],
        architecture_mode=autopilot.mode,
        domain_overlay=autopilot.domain_overlay,
        page_strategy=autopilot.page_strategy,
        page_limit=None,
    )


def apply_layout_brief(
    request: ArtifactComposeRequest,
    artifact: ArtifactDocument,
) -> ArtifactDocument:
    return replace(
        artifact,
        layout_brief=resolve_layout_brief(request, artifact),
    )
