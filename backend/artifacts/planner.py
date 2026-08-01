from __future__ import annotations

import re
from dataclasses import dataclass

from artifacts.parser import sanitize_filename
from schemas.artifact_composer import (
    ArtifactComposeRequest,
)

_GENERIC_WORDS = re.compile(
    r"\b(?:create|make|generate|prepare|produce|export|convert|draft|"
    r"professional|detailed|complete|pdf|docx|pptx|document|presentation|"
    r"file|report|please|for\s+me|bana\s*do|banado|banao|taiyar\s*karo|"
    r"unbranded|branded|premium|clean|polished|formal|executive)\b",
    re.IGNORECASE,
)
_DIRECTIVE_TAIL = re.compile(
    r"(?:\n+|[.!?]\s+)(?:include|add|use|format|layout|style|"
    r"make\s+sure|do\s+not|without|with\s+the\s+following)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_TOPIC_AFTER_ABOUT = re.compile(
    r"\b(?:about|regarding|covering|focused\s+on)\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)
_TOPIC_AFTER_FOR = re.compile(
    r"\b(?:specification|proposal|report|brief|document|pdf)\s+for\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)
_SPACE = re.compile(r"\s+")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ArtifactPlan:
    title: str
    filename: str
    document_type: str
    purpose: str
    audience: str | None
    sections: tuple[str, ...]


def _clean_topic(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(
        r"^(?:User|Serenya):\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )

    about_match = _TOPIC_AFTER_ABOUT.search(normalized)
    if about_match:
        normalized = about_match.group(1)
    else:
        for_match = _TOPIC_AFTER_FOR.search(normalized)
        if for_match:
            normalized = for_match.group(1)

    normalized = _DIRECTIVE_TAIL.sub("", normalized)
    normalized = re.split(
        r"\n\s*(?:[-*•]|\d+[.)])\s+",
        normalized,
        maxsplit=1,
    )[0]
    normalized = re.sub(
        r"\b(?:include|add|use|with)\s*:\s*.*$",
        "",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    normalized = re.sub(
        r"\b(?:about|on|regarding|covering|explaining)\s+",
        "",
        normalized,
        count=1,
        flags=re.IGNORECASE,
    )
    normalized = _GENERIC_WORDS.sub(" ", normalized)
    normalized = re.sub(r"[`*_#>|\[\](){}]", " ", normalized)
    normalized = _SPACE.sub(" ", normalized).strip(" .,:;-_")
    words = normalized.split()

    if len(words) > 12:
        normalized = " ".join(words[:12])

    return normalized


def _source_topic(
    request: ArtifactComposeRequest,
) -> str:
    snapshot = request.source_snapshot

    candidates: list[str] = []

    if snapshot is not None:
        if snapshot.content:
            headings = _HEADING.findall(
                snapshot.content
            )
            candidates.extend(headings[:2])

            user_lines = re.findall(
                r"(?:^|\n)User:\s*(.+)",
                snapshot.content,
                flags=re.IGNORECASE,
            )
            candidates.extend(user_lines[-2:])

            if re.search(
                r"\b(?:logo|brandmark|lettermark)\b",
                snapshot.content,
                flags=re.IGNORECASE,
            ):
                brand_match = re.search(
                    r"\b([A-Z][A-Za-z0-9-]{2,30})\s+(?:logo|brandmark|lettermark)\b",
                    snapshot.content,
                )
                if brand_match:
                    candidates.insert(
                        0,
                        f"{brand_match.group(1)} Logo Analysis",
                    )
                else:
                    candidates.insert(
                        0,
                        "Logo Analysis and Redesign Directions",
                    )

        candidates.append(snapshot.summary)

    candidates.append(request.prompt)

    for candidate in candidates:
        topic = _clean_topic(candidate)
        if len(topic) >= 4:
            return topic

    return "Professional Document"


def _title_case_topic(topic: str) -> str:
    small_words = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    result: list[str] = []

    for index, word in enumerate(topic.split()):
        if (
            index > 0
            and word.casefold() in small_words
        ):
            result.append(word.casefold())
        elif word.isupper() and len(word) <= 6:
            result.append(word)
        else:
            result.append(
                word[:1].upper()
                + word[1:]
            )

    return " ".join(result)[:240]


def _document_type(
    request: ArtifactComposeRequest,
) -> str:
    if request.format == "pptx":
        return "presentation"

    combined = " ".join(
        filter(
            None,
            [
                request.prompt,
                request.purpose,
                request.source_snapshot.summary
                if request.source_snapshot
                else None,
            ],
        )
    )

    explicit_patterns = (
        ("executive_brief", r"\b(?:executive report|executive brief|board report|leadership report)\b"),
        ("technical_specification", r"\b(?:technical specification|technical spec|engineering specification)\b"),
        ("research_report", r"\b(?:research paper|research report|literature review)\b"),
        ("proposal", r"\b(?:business proposal|project proposal|statement of work)\b"),
    )
    for document_type, pattern in explicit_patterns:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            return document_type

    patterns = (
        (
            "academic_textbook",
            r"\b(?:textbook|academic\s+notes?|lesson|chapter|theorem|proof|worked\s+examples?|mathematics|calculus|algebra|study\s+guide)\b",
        ),
        (
            "data_report",
            r"\b(?:data\s+report|analytics|dashboard|benchmark|metrics?|kpi|statistical|survey\s+results?)\b",
        ),
        (
            "case_study",
            r"\b(?:case\s+study|customer\s+story|challenge\s+solution|lessons?\s+learned)\b",
        ),
        (
            "research_report",
            r"\b(?:research|evidence|market\s+analysis|study|investigation)\b",
        ),
        (
            "technical_specification",
            r"\b(?:architecture|technical|engineering|api|implementation|specification)\b",
        ),
        (
            "proposal",
            r"\b(?:proposal|business\s+case|pitch|recommendation\s+memo)\b",
        ),
        (
            "policy_document",
            r"\b(?:policy|governance|standard|compliance|procedure)\b",
        ),
        (
            "executive_brief",
            r"\b(?:executive|leadership|board|brief|summary)\b",
        ),
    )

    for document_type, pattern in patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return document_type

    return request.document_type


def _section_blueprint(
    document_type: str,
    request: ArtifactComposeRequest,
) -> tuple[str, ...]:
    base: dict[str, tuple[str, ...]] = {
        "professional_report": (
            "Executive Summary",
            "Context and Objectives",
            "Analysis",
            "Key Findings",
        ),
        "executive_brief": (
            "Executive Summary",
            "Situation",
            "Key Insights",
            "Decisions and Priorities",
        ),
        "technical_specification": (
            "Executive Summary",
            "Scope and Requirements",
            "Architecture",
            "Implementation Considerations",
            "Risks and Controls",
        ),
        "research_report": (
            "Executive Summary",
            "Research Scope",
            "Evidence and Analysis",
            "Findings",
            "Limitations",
        ),
        "proposal": (
            "Executive Summary",
            "Problem and Opportunity",
            "Proposed Approach",
            "Implementation Plan",
            "Risks and Mitigations",
        ),
        "policy_document": (
            "Purpose",
            "Scope",
            "Policy Requirements",
            "Roles and Responsibilities",
            "Controls and Exceptions",
        ),
        "presentation": (
            "Title",
            "Context",
            "Key Insights",
            "Recommendations",
            "Next Steps",
        ),
        "general_document": (
            "Overview",
            "Main Content",
            "Key Points",
        ),
        "academic_textbook": (
            "Learning Overview",
            "Core Concepts",
            "Worked Examples",
            "Applications",
            "Review and Verification",
        ),
        "data_report": (
            "Executive Summary",
            "Data Scope and Method",
            "Key Metrics",
            "Comparative Analysis",
            "Insights and Actions",
        ),
        "case_study": (
            "Executive Summary",
            "Context and Challenge",
            "Approach",
            "Results",
            "Lessons and Recommendations",
        ),
        "modern_summary": (
            "Overview",
            "Key Insights",
            "Recommended Actions",
        ),
    }

    sections = list(
        base.get(
            document_type,
            base["professional_report"],
        )
    )

    if not request.include_executive_summary:
        sections = [
            section
            for section in sections
            if section != "Executive Summary"
        ]

    if (
        request.include_recommendations
        and "Recommendations" not in sections
    ):
        sections.append("Recommendations")

    if (
        request.include_conclusion
        and document_type != "presentation"
        and "Conclusion" not in sections
    ):
        sections.append("Conclusion")

    return tuple(sections)


def plan_artifact(
    request: ArtifactComposeRequest,
) -> tuple[ArtifactComposeRequest, ArtifactPlan]:
    topic = _source_topic(request)
    title = (
        request.title.strip()
        if request.title
        else _title_case_topic(topic)
    )
    document_type = _document_type(request)
    purpose = (
        request.purpose.strip()
        if request.purpose
        else f"Present a clear, accurate, and professionally structured {document_type.replace('_', ' ')} about {topic}."
    )
    filename = (
        request.filename.strip()
        if request.filename
        else f"{sanitize_filename(title)}.{request.format}"
    )
    sections = _section_blueprint(
        document_type,
        request,
    )
    planned_request = request.model_copy(
        update={
            "title": title,
            "filename": filename,
            "document_type": document_type,
            "purpose": purpose,
        }
    )

    return planned_request, ArtifactPlan(
        title=title,
        filename=filename,
        document_type=document_type,
        purpose=purpose,
        audience=request.audience,
        sections=sections,
    )
