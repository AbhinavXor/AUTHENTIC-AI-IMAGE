from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from ai.provider_adapter import ProviderError
from artifacts.document_profiles import (
    DocumentProfile,
    resolve_document_profile,
)
from artifacts.source_fidelity import sanitize_recovered_source_payload
from core.artifact_settings import artifact_settings
from schemas.artifact_composer import ArtifactComposeRequest


PromptMode = Literal["standard", "compact"]


class PromptBudgetExceeded(ValueError):
    pass


class InternalInstructionLeakageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PromptBudgetEstimate:
    characters: int
    estimated_tokens: int
    budget_characters: int
    within_budget: bool


@dataclass(frozen=True, slots=True)
class CompiledArtifactPrompt:
    text: str
    profile_id: str
    mode: PromptMode
    estimate: PromptBudgetEstimate
    compacted: bool


_SPACE = re.compile(r"[ \t]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_FINAL_FILENAME = re.compile(
    r"\bfinal\s+file(?:name)?\s*:\s*([^\n]{1,180})",
    re.IGNORECASE,
)
_HIGH_VALUE = re.compile(
    r"\b(?:redesign|preserve|retain|remove|omit|without|include|title|filename|"
    r"unbranded|watermark|equation|formula|math|chart|graph|table|diagram|"
    r"architecture|reference|appendix|landscape|page\s+number|header|footer|"
    r"author|date|language|audience|b\.?tech|project|research)\b",
    re.IGNORECASE,
)
_META_LEAKAGE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:"
    r"final\s+(?:pdf|document|artifact)\s+(?:generation\s+)?instructions?"
    r"|document\s+production\s+requirements?"
    r"|internal\s+(?:instructions?|prompt)"
    r"|prompt\s+instructions?"
    r"|hidden\s+instructions?"
    r"|output\s+contract"
    r")\s*:?[ \t]*$"
)
_META_DIRECTIVE = re.compile(
    r"(?im)^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:do\s+not\s+print\s+(?:these|the)\s+instructions|"
    r"do\s+not\s+expose\s+(?:the\s+)?(?:system|hidden)\s+prompt|"
    r"return\s+only\s+the\s+finished\s+markdown\s+document|"
    r"generate\s+the\s+complete\s+markdown\s+document\s+now)\s*[.!]?[ \t]*$"
)


def estimate_prompt_budget(
    text: str,
    *,
    mode: PromptMode,
) -> PromptBudgetEstimate:
    budget = (
        artifact_settings.compact_prompt_budget_characters
        if mode == "compact"
        else artifact_settings.provider_prompt_budget_characters
    )
    characters = len(text)
    return PromptBudgetEstimate(
        characters=characters,
        estimated_tokens=max(1, math.ceil(characters / 4)),
        budget_characters=budget,
        within_budget=characters <= budget,
    )


def compact_user_instruction(
    instruction: str,
    *,
    source_is_prompt: bool,
) -> str:
    normalized = "\n".join(
        line.strip()
        for line in instruction.replace("\r", "\n").splitlines()
        if line.strip()
    )
    if not normalized:
        return "Create the requested professional document."
    if source_is_prompt:
        return (
            "Create the requested professional document from the supplied "
            "authoritative source. Preserve its supported content and apply "
            "the server-selected document profile."
        )

    selected: list[str] = []
    seen: set[str] = set()
    for sentence in _SENTENCE.split(normalized):
        candidate = _SPACE.sub(" ", sentence).strip(" -\t")
        if not candidate:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        if not selected or _HIGH_VALUE.search(candidate):
            seen.add(key)
            selected.append(candidate)
        if len(" ".join(selected)) >= (
            artifact_settings.maximum_compiled_instruction_characters
        ):
            break

    filename_match = _FINAL_FILENAME.search(normalized)
    if filename_match is not None:
        filename_line = f"Final filename: {filename_match.group(1).strip()}"
        if filename_line.casefold() not in seen:
            selected.append(filename_line)

    result = " ".join(selected).strip()
    limit = artifact_settings.maximum_compiled_instruction_characters
    if len(result) > limit:
        result = result[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    return result or "Create the requested professional document."


def compact_analysis_instruction(
    instruction: str,
    *,
    maximum_characters: int,
) -> str:
    """Bound a legacy file-analysis prompt without returning a raw size error."""

    compacted = compact_user_instruction(
        instruction,
        source_is_prompt=False,
    )
    if len(compacted) <= maximum_characters:
        return compacted
    return compacted[:maximum_characters].rsplit(" ", 1)[0].rstrip(" ,;:") + "."


def _profile_lines(profile: DocumentProfile) -> list[str]:
    return [
        f"Profile: {profile.profile_id}",
        f"Goal: {profile.goal}",
        *(f"- {directive}" for directive in profile.directives),
    ]


def _compile(
    *,
    request: ArtifactComposeRequest,
    source_text: str,
    mode: PromptMode,
    fragment: bool,
    chunk_label: str | None = None,
    planned_sections: tuple[str, ...] = (),
) -> CompiledArtifactPrompt:
    profile = resolve_document_profile(request)
    source_is_prompt = (
        request.source_snapshot is None
        and request.source_ref is None
        and source_text.strip() == request.prompt.strip()
    )
    instruction = compact_user_instruction(
        request.prompt,
        source_is_prompt=source_is_prompt,
    )
    rules = [
        "Return only finished Markdown content; never print control instructions.",
        "Use valid heading hierarchy and no raw production metadata.",
        "Preserve source-supported facts; never invent data, citations, or missing values.",
        "Keep equations, units, tables, code, and authentic-chart blocks accurate.",
        "Document length follows the source; there is no fixed page target.",
    ]
    if fragment:
        rules.extend(
            [
                "Return a complete Markdown fragment beginning at heading level two.",
                "Do not add a level-one title or repeat content outside this source part.",
            ]
        )
    else:
        rules.append("Use exactly one level-one title.")

    lines = [
        "PROFESSIONAL DOCUMENT COMPILER",
        *_profile_lines(profile),
        "",
        "USER INTENT",
        instruction,
        "",
        "STRUCTURED SETTINGS",
        f"Format={request.format}; language={request.language}; tone={request.tone}; length={request.length}",
        f"DocumentType={request.document_type}; layout={request.layout_family}; branding={request.branding_mode}",
    ]
    if planned_sections:
        lines.append("SuggestedFlow=" + " > ".join(planned_sections[:16]))
    if chunk_label:
        lines.append(f"SourcePart={chunk_label}")
    lines.extend(
        [
            "",
            "NON-NEGOTIABLE RULES",
            *(f"- {rule}" for rule in rules),
            "",
            "AUTHORITATIVE SOURCE",
            source_text.strip(),
            "END AUTHORITATIVE SOURCE",
            "",
            "Compose the requested content now.",
        ]
    )
    text = "\n".join(lines)
    estimate = estimate_prompt_budget(text, mode=mode)
    if not estimate.within_budget:
        raise PromptBudgetExceeded(
            f"Compiled {mode} prompt requires {estimate.characters} characters "
            f"but the budget is {estimate.budget_characters}."
        )
    return CompiledArtifactPrompt(
        text=text,
        profile_id=profile.profile_id,
        mode=mode,
        estimate=estimate,
        compacted=(
            mode == "compact"
            or instruction.strip() != request.prompt.strip()
        ),
    )


def compile_composition_prompt(
    request: ArtifactComposeRequest,
    *,
    source_text: str,
    mode: PromptMode,
    planned_sections: tuple[str, ...] = (),
) -> CompiledArtifactPrompt:
    return _compile(
        request=request,
        source_text=source_text,
        mode=mode,
        fragment=False,
        planned_sections=planned_sections,
    )


def compile_chunk_prompt(
    request: ArtifactComposeRequest,
    *,
    chunk: str,
    chunk_index: int,
    chunk_count: int,
    mode: PromptMode,
) -> CompiledArtifactPrompt:
    return _compile(
        request=request,
        source_text=chunk,
        mode=mode,
        fragment=True,
        chunk_label=f"{chunk_index}/{chunk_count}",
    )


def compile_revision_prompt(
    request: ArtifactComposeRequest,
    *,
    current_content: str,
    instruction: str,
    mode: PromptMode,
) -> CompiledArtifactPrompt:
    revision_request = request.model_copy(
        update={"prompt": instruction}
    )
    return _compile(
        request=revision_request,
        source_text=current_content,
        mode=mode,
        fragment=False,
    )


def is_prompt_size_error(error: BaseException) -> bool:
    message = str(error).casefold()
    if isinstance(error, ProviderError):
        if error.status_code in {400, 413, 414, 422}:
            return True
        if error.code == "request" and any(
            signal in message
            for signal in (
                "too long",
                "context length",
                "token limit",
                "request size",
                "payload",
            )
        ):
            return True
    return any(
        signal in message
        for signal in (
            "prompt is too long",
            "context length exceeded",
            "maximum context",
            "request entity too large",
        )
    )


def sanitize_and_validate_model_output(content: str) -> str:
    if _META_LEAKAGE.search(content) or _META_DIRECTIVE.search(content):
        raise InternalInstructionLeakageError(
            "The model output exposed internal document instructions."
        )
    cleaned = sanitize_recovered_source_payload(content)
    if _META_LEAKAGE.search(cleaned) or _META_DIRECTIVE.search(cleaned):
        raise InternalInstructionLeakageError(
            "The model output exposed internal document instructions."
        )
    return cleaned
