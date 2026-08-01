from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any

from artifacts.contracts import ArtifactAnswerRouter
from artifacts.large_source import (
    LargeSourcePlan,
    plan_large_source,
    split_large_source,
)
from artifacts.planner import ArtifactPlan
from artifacts.prompt_compiler import (
    CompiledArtifactPrompt,
    InternalInstructionLeakageError,
    PromptBudgetExceeded,
    compile_chunk_prompt,
    compile_composition_prompt,
    compile_revision_prompt,
    is_prompt_size_error,
    sanitize_and_validate_model_output,
)
from artifacts.retry import run_with_provider_retry
from artifacts.source_fidelity import (
    apply_deterministic_additive_revision,
    canonical_revision_title,
    infer_professional_title,
    is_canonical_artifact_markdown,
    is_destructive_or_condensing_revision,
    normalize_recovered_artifact_markdown,
    organize_source_losslessly,
    sanitize_recovered_source_payload,
    resolve_source_fidelity,
    source_fidelity_metrics,
)
from artifacts.visualization_blocks import preserve_authentic_chart_blocks
from core.artifact_settings import artifact_settings
from schemas.artifact_composer import ArtifactComposeRequest


class ArtifactCompositionError(RuntimeError):
    """Raised when an artifact draft is empty, invalid, or unsafe."""


@dataclass(frozen=True, slots=True)
class ComposedArtifactDraft:
    content: str
    provider: str
    model: str
    request_id: str | None


CompositionProgressCallback = Callable[
    [int, int, str],
    Awaitable[None] | None,
]


_LENGTH_GUIDANCE = {
    "brief": "Create a concise artifact while preserving all necessary source content.",
    "standard": "Create a complete artifact whose length follows the source and purpose.",
    "detailed": "Create a fully detailed artifact without imposing an artificial page or word limit.",
}

_TONE_GUIDANCE = {
    "professional": "Use a polished, neutral, professional writing style.",
    "executive": (
        "Use an executive-ready style with clear decisions, risks, "
        "priorities, and recommended actions."
    ),
    "technical": (
        "Use a precise technical style with architecture, implementation, "
        "constraints, and operational detail."
    ),
    "simple": "Use simple, direct language for a non-technical reader.",
    "academic": (
        "Use a formal academic style with careful definitions, structured "
        "analysis, and qualified conclusions."
    ),
}

_FORMAT_GUIDANCE = {
    "pdf": "Structure the content as a polished fixed-layout report.",
    "docx": (
        "Structure the content as an editable professional document with "
        "clear headings and complete paragraphs."
    ),
    "pptx": (
        "Structure the content for a presentation with one main idea per "
        "slide, concise bullets, and slide-ready headings."
    ),
    "zip": (
        "Structure the content as a long-form report that will be split into "
        "multiple numbered PDF volumes inside one ZIP bundle."
    ),
}

_GENERIC_CREATE_REQUEST = re.compile(
    r"^\s*(?:(?:please\s+)?(?:create|make|generate|prepare|produce|export|convert|bana\s*do|banado|banao)\s+)?(?:a\s+|an\s+)?(?:professional\s+)?(?:pdf|docx|pptx|document|presentation|file)(?:\s+(?:please|for\s+me))?\s*[.!?]*$",
    re.IGNORECASE,
)

_LEVEL_ONE_HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_ANY_LEVEL_ONE_HEADING = re.compile(r"^#\s+", re.MULTILINE)
_INVALID_DRAFT_TITLE = re.compile(
    r"^(?:user|assistant|serenya|source|attachment|untitled|file|document|"
    r"uploaded\s+(?:file|pdf|document)|pdf\s+document|professional\s+pdf|"
    r"generated\s+document|create(?:\s+a)?\s+pdf|redesign(?:\s+this)?\s+pdf|"
    r"final\s+(?:pdf|document|artifact)(?:\s+generation)?\s+instruction)s?$",
    re.IGNORECASE,
)
_TITLE_ACTION_COMMAND = re.compile(
    r"\b(?:create|make|generate|prepare|produce|redesign|revise|update|convert|"
    r"organise|organize)\b[\s\S]{0,120}\b(?:pdf|document|artifact|file)\b",
    re.IGNORECASE,
)
_ATTACHED_SOURCE_REFERENCE = re.compile(
    r"\b(?:attached|uploaded|enclosed)\s+(?:pdf|document|file)\b",
    re.IGNORECASE,
)
_LAYOUT_ONLY_REVISION = re.compile(
    r"\b(?:redesign|restyle|reformat|layout|architecture|typography|visual\s+design|"
    r"professional\s+design|change\s+(?:the\s+)?design)\b",
    re.IGNORECASE,
)
_CONTENT_MUTATION_REVISION = re.compile(
    r"\b(?:add|insert|include|remove|delete|exclude|rewrite|translate|summari[sz]e|"
    r"shorten|expand|replace|correct|fact[- ]?check|new\s+(?:section|chapter|"
    r"table|chart|graph|diagram|equation)|change\s+(?:the\s+)?(?:content|"
    r"conclusion|recommendations?|data|calculation))\b",
    re.IGNORECASE,
)


def _boolean_instruction(
    *,
    enabled: bool,
    enabled_text: str,
    disabled_text: str,
) -> str:
    return enabled_text if enabled else disabled_text


def _source_instructions(
    request: ArtifactComposeRequest,
) -> list[str]:
    snapshot = request.source_snapshot

    if snapshot is None:
        if _GENERIC_CREATE_REQUEST.match(request.prompt):
            raise ArtifactCompositionError(
                "The artifact request does not identify a topic or source."
            )

        return [
            "The user's explicit request is the authoritative source.",
            "Do not substitute a different company, product, or topic.",
        ]

    instructions = [
        "Use the supplied source snapshot as the primary authoritative source.",
        "Preserve its subject, scope, terminology, and factual boundaries.",
        "Do not replace it with generic Authentic AI company content unless "
        "the source itself is about Authentic AI.",
        "Do not invent missing facts; state limitations or assumptions clearly.",
        f"Source kind: {snapshot.kind}",
        f"Source summary: {snapshot.summary}",
    ]

    if snapshot.content:
        instructions.extend(
            [
                "",
                "AUTHORITATIVE SOURCE CONTENT",
                snapshot.content,
                "END AUTHORITATIVE SOURCE CONTENT",
            ]
        )

    return instructions


def build_artifact_composition_prompt(
    request: ArtifactComposeRequest,
    *,
    plan: ArtifactPlan | None = None,
) -> str:
    large_plan = plan_large_source(request)
    mode = "compact" if request.prompt_mode == "compact" else "standard"
    return compile_composition_prompt(
        request,
        source_text=large_plan.source_text,
        mode=mode,
        planned_sections=(plan.sections if plan is not None else ()),
    ).text


def build_large_chunk_prompt(
    request: ArtifactComposeRequest,
    *,
    large_plan: LargeSourcePlan,
    chunk: str,
    chunk_index: int,
    chunk_count: int,
) -> str:
    del large_plan
    mode = "compact" if request.prompt_mode == "compact" else "standard"
    return compile_chunk_prompt(
        request,
        chunk=chunk,
        chunk_index=chunk_index,
        chunk_count=chunk_count,
        mode=mode,
    ).text


def build_artifact_revision_prompt(
    request: ArtifactComposeRequest,
    *,
    current_content: str,
    instruction: str,
) -> str:
    mode = "compact" if request.prompt_mode == "compact" else "standard"
    return compile_revision_prompt(
        request,
        current_content=current_content,
        instruction=instruction,
        mode=mode,
    ).text


def _remove_outer_code_fence(content: str) -> str:
    stripped = content.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if len(lines) < 3:
        return stripped

    if (
        lines[0].strip().lower()
        not in {"```", "```md", "```markdown"}
        or lines[-1].strip() != "```"
    ):
        return stripped

    return "\n".join(lines[1:-1]).strip()


def _validate_fragment(content: str) -> str:
    normalized = _remove_outer_code_fence(content)
    if not normalized:
        raise ArtifactCompositionError(
            "The AI provider returned an empty large-document fragment."
        )
    return normalized


def _normalize_fragment(content: str, *, fallback_heading: str) -> str:
    normalized = _validate_fragment(content)
    normalized = _ANY_LEVEL_ONE_HEADING.sub("## ", normalized)
    if not re.search(r"^##\s+\S", normalized, re.MULTILINE):
        normalized = f"## {fallback_heading}\n\n{normalized}"
    return normalized.strip()


def _clean_draft_title_candidate(
    value: str | None,
) -> str | None:
    if not value:
        return None
    candidate = value.strip().lstrip("#").strip(" .,:;-_")
    candidate = re.sub(
        r"\.(?:pdf|docx|pptx|zip)$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"_+", " ", candidate)
    if "-" in candidate and not re.search(r"\s", candidate):
        candidate = re.sub(r"-+", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,:;-_")
    if (
        len(candidate) < 4
        or _INVALID_DRAFT_TITLE.fullmatch(candidate)
        or _TITLE_ACTION_COMMAND.search(candidate)
    ):
        return None
    return candidate[:180]


def _resolve_draft_title(
    request: ArtifactComposeRequest,
    *,
    large_plan: LargeSourcePlan | None = None,
    content: str = "",
    current_content: str | None = None,
) -> str:
    snapshot = request.source_snapshot
    attachment_title = None
    if snapshot is not None and snapshot.attachment_names:
        attachment_title = snapshot.attachment_names[0]

    inferred_source_title = None
    if large_plan is not None:
        inferred_source_title = infer_professional_title(
            large_plan.source_text,
            "",
        )

    candidates = (
        request.title,
        attachment_title,
        request.filename,
        large_plan.inferred_title if large_plan is not None else None,
        (
            canonical_revision_title(
                current_content,
                source_snapshot_content=(
                    snapshot.content
                    if snapshot is not None
                    else None
                ),
                fallback_title="",
            )
            if current_content
            else None
        ),
        inferred_source_title,
        infer_professional_title(content, "") if content else None,
    )
    for candidate in candidates:
        cleaned = _clean_draft_title_candidate(candidate)
        if cleaned:
            return cleaned
    return "Professional Document"


def _validate_draft(
    content: str,
    *,
    fallback_title: str = "Professional Document",
) -> str:
    normalized = _remove_outer_code_fence(content)

    if not normalized:
        raise ArtifactCompositionError(
            "The AI provider returned an empty artifact draft."
        )

    if len(normalized) > artifact_settings.maximum_content_characters:
        raise ArtifactCompositionError(
            "The AI-generated artifact draft exceeds the configured content limit."
        )

    title = _clean_draft_title_candidate(fallback_title)
    if title is None:
        title = "Professional Document"

    headings = list(
        _LEVEL_ONE_HEADING.finditer(normalized)
    )
    first_h1_is_document_title = bool(
        headings
        and not normalized[: headings[0].start()].strip()
    )
    if not first_h1_is_document_title:
        normalized = f"# {title}\n\n{normalized}"
    else:
        primary = headings[0]
        primary_title = _clean_draft_title_candidate(
            primary.group(1)
        )
        if primary_title is None:
            normalized = (
                normalized[:primary.start()]
                + f"# {title}"
                + normalized[primary.end():]
            )

    # A document has one canonical title. Provider-created additional H1
    # blocks are section headings and are safely demoted instead of causing a
    # recoverable draft to fail. This also handles a provider response that
    # begins with H2 content and introduces an H1 section later.
    first_seen = False
    repaired_lines: list[str] = []
    for line in normalized.splitlines():
        if re.match(r"^#\s+\S", line):
            if first_seen:
                repaired_lines.append("#" + line)
                continue
            first_seen = True
        repaired_lines.append(line)
    normalized = "\n".join(repaired_lines).strip()

    return normalized


async def _emit_progress(
    callback: CompositionProgressCallback | None,
    completed: int,
    total: int,
    stage: str,
) -> None:
    if callback is None:
        return
    result = callback(completed, total, stage)
    if inspect.isawaitable(result):
        await result


async def _run_profile_prompt(
    *,
    model_router: ArtifactAnswerRouter,
    standard_factory: Callable[[], CompiledArtifactPrompt],
    compact_factory: Callable[[], CompiledArtifactPrompt],
    force_compact: bool = False,
) -> tuple[Any, str, CompiledArtifactPrompt]:
    try:
        compiled = (
            compact_factory()
            if force_compact
            else standard_factory()
        )
    except PromptBudgetExceeded:
        compiled = compact_factory()

    async def invoke(
        selected: CompiledArtifactPrompt,
    ) -> tuple[Any, str]:
        response = await run_with_provider_retry(
            lambda: model_router.answer(
                message=selected.text,
                history=[],
            )
        )
        content = sanitize_and_validate_model_output(
            response.answer
        )
        return response, content

    try:
        response, content = await invoke(compiled)
    except Exception as error:
        retryable_compaction = (
            compiled.mode != "compact"
            and (
                is_prompt_size_error(error)
                or isinstance(
                    error,
                    InternalInstructionLeakageError,
                )
            )
        )
        if not retryable_compaction:
            if isinstance(error, InternalInstructionLeakageError):
                raise ArtifactCompositionError(str(error)) from error
            raise
        compiled = compact_factory()
        try:
            response, content = await invoke(compiled)
        except InternalInstructionLeakageError as compact_error:
            raise ArtifactCompositionError(
                str(compact_error)
            ) from compact_error

    return response, content, compiled


def _deterministic_large_source_document(
    request: ArtifactComposeRequest,
    large_plan: LargeSourcePlan,
) -> ComposedArtifactDraft:
    recovered_payload = bool(
        request.source_snapshot is not None
        and request.source_snapshot.kind == "artifact_version"
    )
    source_text = large_plan.source_text
    if recovered_payload:
        source_text = sanitize_recovered_source_payload(source_text)
        if not source_text:
            raise ArtifactCompositionError(
                "The stored artifact source contains no recoverable document content."
            )
        recovered_chunks = split_large_source(source_text)
        large_plan = replace(
            large_plan,
            source_text=source_text,
            chunks=recovered_chunks or (source_text,),
            source_character_count=len(source_text),
        )

    title = (
        request.title
        or large_plan.inferred_title
        or "Professional Document"
    ).strip()
    fidelity = resolve_source_fidelity(
        request,
        source_text,
    )
    if fidelity.source_truncated:
        raise ArtifactCompositionError(
            "The complete source is not available in this chat preview. Re-paste or upload the original source, or use an existing artifact card so Serenya can securely recover its stored source."
        )

    recovered_canonical = bool(
        recovered_payload
        and is_canonical_artifact_markdown(source_text)
    )

    if recovered_canonical:
        content = normalize_recovered_artifact_markdown(
            source_text,
            fallback_title=title,
        )
    else:
        content = organize_source_losslessly(
            fidelity,
            fallback_title=title,
            include_derived_visualizations=True,
        )

    minimum_sections = (
        request.bundle_volume_count
        or (2 if request.format == "zip" else 1)
    )
    section_count = len(
        re.findall(r"^##\s+\S", content, re.MULTILINE)
    )
    if request.format == "zip" and section_count < minimum_sections:
        parts: list[str] = [f"# {title}"]
        for index, chunk in enumerate(large_plan.chunks, start=1):
            normalized_chunk = _ANY_LEVEL_ONE_HEADING.sub(
                "### ",
                chunk,
            )
            normalized_chunk = re.sub(
                r"^##\s+",
                "### ",
                normalized_chunk,
                flags=re.MULTILINE,
            )
            parts.extend(
                [
                    "",
                    f"## Source Part {index}",
                    "",
                    normalized_chunk.strip(),
                ]
            )
        content = "\n".join(parts).strip() + "\n"

    content = preserve_authentic_chart_blocks(
        source_text,
        content,
    )
    metrics = source_fidelity_metrics(
        fidelity.source_body,
        content,
        fidelity.numbered_heading_titles,
    )
    if fidelity.preserve_all and not metrics.passed:
        raise ArtifactCompositionError(
            "The lossless document organizer could not preserve the complete source."
        )

    return ComposedArtifactDraft(
        content=_validate_draft(
            content,
            fallback_title=title,
        ),
        provider="deterministic",
        model=(
            "canonical-artifact-recovery-v8"
            if recovered_canonical
            else "professional-document-v5"
        ),
        request_id=None,
    )


async def _compose_large_artifact_draft(
    request: ArtifactComposeRequest,
    *,
    model_router: ArtifactAnswerRouter,
    large_plan: LargeSourcePlan,
    progress_callback: CompositionProgressCallback | None,
) -> ComposedArtifactDraft:
    fragments: list[str] = []
    provider = "unknown"
    model = "unknown"
    request_id: str | None = None
    total = len(large_plan.chunks)

    for index, chunk in enumerate(large_plan.chunks, start=1):
        await _emit_progress(
            progress_callback,
            index - 1,
            total,
            f"Organizing large source part {index} of {total}",
        )
        response, response_content, _ = await _run_profile_prompt(
            model_router=model_router,
            standard_factory=lambda chunk=chunk, index=index: compile_chunk_prompt(
                request,
                chunk=chunk,
                chunk_index=index,
                chunk_count=total,
                mode="standard",
            ),
            compact_factory=lambda chunk=chunk, index=index: compile_chunk_prompt(
                request,
                chunk=chunk,
                chunk_index=index,
                chunk_count=total,
                mode="compact",
            ),
            force_compact=(request.prompt_mode == "compact"),
        )
        provider = response.provider
        model = response.model
        request_id = response.request_id or request_id
        fragments.append(
            _normalize_fragment(
                response_content,
                fallback_heading=f"Part {index}",
            )
        )
        await _emit_progress(
            progress_callback,
            index,
            total,
            f"Organized large source part {index} of {total}",
        )

    title = (
        request.title
        or large_plan.inferred_title
        or "Professional Document"
    ).strip()
    content = "\n\n".join(
        [f"# {title}", *fragments]
    )
    content = preserve_authentic_chart_blocks(
        large_plan.source_text,
        content,
    )
    return ComposedArtifactDraft(
        content=_validate_draft(
            content,
            fallback_title=title,
        ),
        provider=provider,
        model=(
            f"{model} (multi-pass {total})"
            if total > 1
            else model
        ),
        request_id=request_id,
    )


async def compose_artifact_draft(
    request: ArtifactComposeRequest,
    *,
    model_router: ArtifactAnswerRouter,
    plan: ArtifactPlan | None = None,
    progress_callback: CompositionProgressCallback | None = None,
) -> ComposedArtifactDraft:
    snapshot = request.source_snapshot
    if (
        _ATTACHED_SOURCE_REFERENCE.search(request.prompt)
        and request.source_ref is None
        and (
            snapshot is None
            or snapshot.kind not in {"uploaded_file", "artifact_version"}
        )
    ):
        raise ArtifactCompositionError(
            "Attach the PDF or document to this message before requesting a redesign. The current request contains an attachment reference, but no uploaded source reached the document engine."
        )
    if (
        request.source_snapshot is None
        and request.source_ref is None
        and _GENERIC_CREATE_REQUEST.match(request.prompt)
    ):
        raise ArtifactCompositionError(
            "The artifact request does not identify a topic or source."
        )
    large_plan = plan_large_source(request)
    fidelity = resolve_source_fidelity(
        request,
        large_plan.source_text,
    )
    if (
        (
            request.source_snapshot is not None
            and request.source_snapshot.kind == "artifact_version"
        )
        or fidelity.preserve_all
        or request.format == "zip"
        or request.bundle_volume_count is not None
        or len(large_plan.chunks) > 32
    ):
        await _emit_progress(
            progress_callback,
            1,
            1,
            "Preserving and structuring very large source",
        )
        return _deterministic_large_source_document(
            request,
            large_plan,
        )

    if large_plan.use_multi_pass:
        return await _compose_large_artifact_draft(
            request,
            model_router=model_router,
            large_plan=large_plan,
            progress_callback=progress_callback,
        )

    planned_sections = plan.sections if plan is not None else ()
    response, response_content, _ = await _run_profile_prompt(
        model_router=model_router,
        standard_factory=lambda: compile_composition_prompt(
            request,
            source_text=large_plan.source_text,
            mode="standard",
            planned_sections=planned_sections,
        ),
        compact_factory=lambda: compile_composition_prompt(
            request,
            source_text=large_plan.source_text,
            mode="compact",
            planned_sections=planned_sections,
        ),
        force_compact=(request.prompt_mode == "compact"),
    )
    content = _validate_draft(
        response_content,
        fallback_title=_resolve_draft_title(
            request,
            large_plan=large_plan,
            content=response_content,
        ),
    )
    content = preserve_authentic_chart_blocks(
        large_plan.source_text,
        content,
    )
    return ComposedArtifactDraft(
        content=content,
        provider=response.provider,
        model=response.model,
        request_id=response.request_id,
    )


def is_design_only_revision(instruction: str) -> bool:
    """Return whether a revision changes presentation without changing content."""

    return bool(
        _LAYOUT_ONLY_REVISION.search(instruction)
        and not _CONTENT_MUTATION_REVISION.search(instruction)
    )


async def compose_artifact_revision(
    request: ArtifactComposeRequest,
    *,
    current_content: str,
    instruction: str,
    model_router: ArtifactAnswerRouter,
) -> ComposedArtifactDraft:
    deterministic_revision = apply_deterministic_additive_revision(
        current_content,
        instruction,
    )
    if deterministic_revision is not None:
        return ComposedArtifactDraft(
            content=_validate_draft(
                preserve_authentic_chart_blocks(
                    current_content,
                    deterministic_revision,
                ),
                fallback_title=_resolve_draft_title(
                    request,
                    content=deterministic_revision,
                    current_content=current_content,
                ),
            ),
            provider="deterministic",
            model="professional-revision-v5",
            request_id=None,
        )

    if is_design_only_revision(instruction):
        # A design-only revision does not need a model to rewrite the entire
        # source, regardless of document length. Keeping canonical content
        # intact lets the architecture autopilot recompose it safely and
        # avoids false content-loss rejection on short documents.
        return ComposedArtifactDraft(
            content=_validate_draft(
                sanitize_and_validate_model_output(
                    current_content
                ),
                fallback_title=_resolve_draft_title(
                    request,
                    current_content=current_content,
                ),
            ),
            provider="deterministic",
            model="profile-redesign-v20",
            request_id=None,
        )
    if (
        len(current_content)
        > artifact_settings.provider_prompt_budget_characters - 4_000
    ):
        chunks = split_large_source(
            current_content,
            target_characters=6_000,
        )
        fragments: list[str] = []
        provider = "unknown"
        model = "unknown"
        request_id: str | None = None
        revision_request = request.model_copy(
            update={"prompt": instruction}
        )
        for index, chunk in enumerate(chunks, start=1):
            response, response_content, _ = await _run_profile_prompt(
                model_router=model_router,
                standard_factory=lambda chunk=chunk, index=index: compile_chunk_prompt(
                    revision_request,
                    chunk=chunk,
                    chunk_index=index,
                    chunk_count=len(chunks),
                    mode="standard",
                ),
                compact_factory=lambda chunk=chunk, index=index: compile_chunk_prompt(
                    revision_request,
                    chunk=chunk,
                    chunk_index=index,
                    chunk_count=len(chunks),
                    mode="compact",
                ),
                force_compact=(request.prompt_mode == "compact"),
            )
            provider = response.provider
            model = response.model
            request_id = response.request_id or request_id
            fragments.append(
                _normalize_fragment(
                    response_content,
                    fallback_heading=f"Revised Part {index}",
                )
            )
        title_match = _LEVEL_ONE_HEADING.search(current_content)
        title = (
            request.title
            or (title_match.group(1).strip() if title_match else "Professional Document")
        )
        content = _validate_draft(
            f"# {title}\n\n" + "\n\n".join(fragments),
            fallback_title=title,
        )
        content = preserve_authentic_chart_blocks(
            current_content,
            content,
        )
        return ComposedArtifactDraft(
            content=content,
            provider=provider,
            model=f"{model} (compact revision {len(chunks)})",
            request_id=request_id,
        )

    response, response_content, _ = await _run_profile_prompt(
        model_router=model_router,
        standard_factory=lambda: compile_revision_prompt(
            request,
            current_content=current_content,
            instruction=instruction,
            mode="standard",
        ),
        compact_factory=lambda: compile_revision_prompt(
            request,
            current_content=current_content,
            instruction=instruction,
            mode="compact",
        ),
        force_compact=(request.prompt_mode == "compact"),
    )
    content = _validate_draft(
        response_content,
        fallback_title=_resolve_draft_title(
            request,
            content=response_content,
            current_content=current_content,
        ),
    )
    content = preserve_authentic_chart_blocks(
        current_content,
        content,
    )
    content = preserve_authentic_chart_blocks(
        request.source_snapshot.content
        if request.source_snapshot is not None
        else None,
        content,
    )

    if not is_destructive_or_condensing_revision(instruction):
        metrics = source_fidelity_metrics(
            current_content,
            content,
        )
        if (
            metrics.token_coverage_ratio < 0.90
            or metrics.character_retention_ratio < 0.72
        ):
            raise ArtifactCompositionError(
                "The requested revision could not be applied without losing existing content."
            )

    return ComposedArtifactDraft(
        content=content,
        provider=response.provider,
        model=response.model,
        request_id=response.request_id,
    )
