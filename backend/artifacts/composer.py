from __future__ import annotations

from dataclasses import dataclass

from ai.model_router import ModelRouter
from core.artifact_settings import (
    artifact_settings,
)
from schemas.artifact_composer import (
    ArtifactComposeRequest,
)


class ArtifactCompositionError(
    RuntimeError
):
    """
    Raised when an AI-generated artifact
    draft is empty, invalid, or too large.
    """


@dataclass(frozen=True, slots=True)
class ComposedArtifactDraft:
    content: str
    provider: str
    model: str
    request_id: str | None


_LENGTH_GUIDANCE = {
    "brief": (
        "Create a concise artifact with "
        "approximately 700 to 1,200 words."
    ),
    "standard": (
        "Create a complete artifact with "
        "approximately 1,500 to 2,500 words."
    ),
    "detailed": (
        "Create a detailed artifact with "
        "approximately 3,000 to 4,500 words."
    ),
}


_TONE_GUIDANCE = {
    "professional": (
        "Use a polished, neutral, "
        "professional writing style."
    ),
    "executive": (
        "Use an executive-ready style with "
        "clear decisions, risks, priorities, "
        "and recommended actions."
    ),
    "technical": (
        "Use a precise technical style with "
        "clear architecture, implementation, "
        "constraints, and operational detail."
    ),
    "simple": (
        "Use simple, direct language that a "
        "non-technical reader can understand."
    ),
    "academic": (
        "Use a formal academic style with "
        "careful definitions, structured "
        "analysis, and qualified conclusions."
    ),
}


_FORMAT_GUIDANCE = {
    "pdf": (
        "Structure the content as a polished "
        "report suitable for a fixed-layout PDF."
    ),
    "docx": (
        "Structure the content as an editable "
        "professional document with clear "
        "headings and complete paragraphs."
    ),
    "pptx": (
        "Structure the content for a presentation. "
        "Use one major section per slide, concise "
        "bullets, short paragraphs, and clear "
        "slide-ready headings."
    ),
}


def _boolean_instruction(
    *,
    enabled: bool,
    enabled_text: str,
    disabled_text: str,
) -> str:
    if enabled:
        return enabled_text

    return disabled_text


def build_artifact_composition_prompt(
    request: ArtifactComposeRequest,
) -> str:
    """
    Build a controlled prompt that asks the
    model for Markdown-only artifact content.
    """

    title_instruction = (
        request.title
        if request.title is not None
        else (
            "Infer a concise professional title "
            "from the user's request."
        )
    )

    executive_summary_instruction = (
        _boolean_instruction(
            enabled=(
                request
                .include_executive_summary
            ),
            enabled_text=(
                "Include an Executive Summary "
                "near the beginning."
            ),
            disabled_text=(
                "Do not include an "
                "Executive Summary section."
            ),
        )
    )

    table_instruction = (
        _boolean_instruction(
            enabled=request.include_table,
            enabled_text=(
                "Include at least one useful "
                "Markdown table when the subject "
                "contains comparable information."
            ),
            disabled_text=(
                "Do not create a table unless it "
                "is essential for correctness."
            ),
        )
    )

    recommendations_instruction = (
        _boolean_instruction(
            enabled=(
                request
                .include_recommendations
            ),
            enabled_text=(
                "Include practical recommendations "
                "or next actions."
            ),
            disabled_text=(
                "Do not add a recommendations "
                "section."
            ),
        )
    )

    conclusion_instruction = (
        _boolean_instruction(
            enabled=request.include_conclusion,
            enabled_text=(
                "End with a clear conclusion."
            ),
            disabled_text=(
                "Do not add a separate conclusion."
            ),
        )
    )

    return "\n".join(
        [
            (
                "You are the professional artifact "
                "composition engine for Authentic AI."
            ),
            "",
            "USER REQUEST",
            request.prompt,
            "",
            "OUTPUT REQUIREMENTS",
            (
                "- Return only the finished "
                "Markdown document."
            ),
            (
                "- Do not include commentary about "
                "how you created it."
            ),
            (
                "- Do not wrap the full response "
                "inside a Markdown code fence."
            ),
            (
                "- Do not claim that a file was "
                "generated or downloaded."
            ),
            (
                "- Do not invent citations, sources, "
                "statistics, names, dates, or facts."
            ),
            (
                "- Clearly label assumptions when "
                "the user has not supplied enough "
                "information."
            ),
            (
                "- Use logical heading hierarchy "
                "starting with one level-one title."
            ),
            (
                "- Use complete, useful content. "
                "Do not leave placeholders."
            ),
            (
                "- Keep headings, tables, lists, "
                "and code blocks valid Markdown."
            ),
            "",
            "DOCUMENT SETTINGS",
            f"- Output format: {request.format}",
            f"- Required language: {request.language}",
            f"- Intended title: {title_instruction}",
            (
                "- "
                + _TONE_GUIDANCE[
                    request.tone
                ]
            ),
            (
                "- "
                + _LENGTH_GUIDANCE[
                    request.length
                ]
            ),
            (
                "- "
                + _FORMAT_GUIDANCE[
                    request.format
                ]
            ),
            (
                "- "
                + executive_summary_instruction
            ),
            "- " + table_instruction,
            (
                "- "
                + recommendations_instruction
            ),
            "- " + conclusion_instruction,
            "",
            (
                "Generate the complete Markdown "
                "document now."
            ),
        ]
    )


def _remove_outer_code_fence(
    content: str,
) -> str:
    """
    Remove one accidental outer Markdown fence
    while preserving internal code blocks.
    """

    stripped = content.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if len(lines) < 3:
        return stripped

    first_line = lines[0].strip()
    last_line = lines[-1].strip()

    allowed_opening_fences = {
        "```",
        "```md",
        "```markdown",
    }

    if (
        first_line.lower()
        not in allowed_opening_fences
        or last_line != "```"
    ):
        return stripped

    return "\n".join(
        lines[1:-1]
    ).strip()


def _validate_draft(
    content: str,
) -> str:
    normalized = (
        _remove_outer_code_fence(
            content
        )
    )

    if not normalized:
        raise ArtifactCompositionError(
            (
                "The AI provider returned an "
                "empty artifact draft."
            )
        )

    if len(normalized) > (
        artifact_settings
        .maximum_content_characters
    ):
        raise ArtifactCompositionError(
            (
                "The AI-generated artifact draft "
                "exceeds the configured content "
                "limit."
            )
        )

    return normalized


async def compose_artifact_draft(
    request: ArtifactComposeRequest,
    *,
    model_router: ModelRouter,
) -> ComposedArtifactDraft:
    """
    Compose a professional Markdown draft
    without generating or storing the file.
    """

    composition_prompt = (
        build_artifact_composition_prompt(
            request
        )
    )

    response = await model_router.answer(
        message=composition_prompt,
        history=[],
    )

    content = _validate_draft(
        response.answer
    )

    return ComposedArtifactDraft(
        content=content,
        provider=response.provider,
        model=response.model,
        request_id=response.request_id,
    )