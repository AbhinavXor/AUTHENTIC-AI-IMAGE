from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.artifact_sources as artifact_source_routes
from ai.provider_adapter import ProviderError
from artifacts.architecture_registry import architecture_registry
from artifacts.composer import (
    ArtifactCompositionError,
    compose_artifact_draft,
    compose_artifact_revision,
)
from artifacts.prompt_compiler import (
    compact_analysis_instruction,
    compile_composition_prompt,
    estimate_prompt_budget,
)
from artifacts.source_vault import ArtifactSourceVault
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.artifacts import ArtifactSourceReference
from schemas.chat import ChatResponse, TokenUsage


class SizeThenSuccessRouter:
    def __init__(self, *, leak_first: bool = False) -> None:
        self.messages: list[str] = []
        self.leak_first = leak_first

    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        del history
        self.messages.append(message)
        if len(self.messages) == 1 and not self.leak_first:
            raise ProviderError(
                "Provider context length exceeded.",
                provider="test",
                code="request",
                retryable=False,
                status_code=413,
            )
        if len(self.messages) == 1:
            answer = (
                "# Systems Report\n\n## OUTPUT CONTRACT\n\n"
                "Do not print these instructions."
            )
        else:
            answer = "# Systems Report\n\n## Overview\n\nValidated source content."
        return ChatResponse(
            answer=answer,
            provider="test",
            model="test-model",
            usage=TokenUsage(),
        )


class StaticDraftRouter:
    def __init__(self, answer: str) -> None:
        self.answer_text = answer

    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        del message, history
        return ChatResponse(
            answer=self.answer_text,
            provider="test",
            model="test-model",
            usage=TokenUsage(),
        )


def request_with_separate_source(
    *,
    prompt: str,
) -> ArtifactComposeRequest:
    return ArtifactComposeRequest(
        prompt=prompt,
        format="pdf",
        source_snapshot={
            "kind": "uploaded_file",
            "summary": "BTech systems project source",
            "content": (
                "# Systems Report\n\n## Overview\n\n"
                + "Validated engineering source. " * 120
            ),
            "attachment_names": ["source.pdf"],
        },
    )


def test_long_redesign_instruction_compiles_to_server_profile_budget() -> None:
    request = request_with_separate_source(
        prompt=(
            "Redesign this attached PDF as a BTech final-year project report.\n"
            + "Preserve content and improve equations, tables, graphs, and architecture.\n"
            + "Do not add branding, watermark, date, headers, or footers.\n"
        ) * 350,
    )
    compiled = compile_composition_prompt(
        request,
        source_text=request.source_snapshot.content or "",
        mode="standard",
    )
    assert compiled.profile_id == "redesign_existing"
    assert compiled.compacted is True
    assert compiled.estimate.within_budget is True
    assert len(compiled.text) < len(request.prompt)
    assert compiled.text.count("AUTHORITATIVE SOURCE") == 2


@pytest.mark.asyncio
async def test_provider_size_rejection_retries_once_in_compact_mode() -> None:
    router = SizeThenSuccessRouter()
    request = request_with_separate_source(
        prompt="Redesign this uploaded PDF professionally. " * 300,
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# Systems Report")
    assert len(router.messages) == 2
    assert len(router.messages[1]) <= len(router.messages[0])


@pytest.mark.asyncio
async def test_internal_instruction_leakage_retries_before_delivery() -> None:
    router = SizeThenSuccessRouter(leak_first=True)
    request = request_with_separate_source(
        prompt="Redesign the attached PDF.",
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert "OUTPUT CONTRACT" not in draft.content
    assert len(router.messages) == 2


@pytest.mark.asyncio
async def test_missing_provider_title_is_repaired_from_uploaded_source() -> None:
    request = request_with_separate_source(
        prompt="Redesign the attached PDF professionally.",
    )
    router = StaticDraftRouter(
        "## Executive Summary\n\nValidated engineering content."
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# source") is False
    assert draft.content.startswith("# Systems Report")
    assert "## Executive Summary" in draft.content


@pytest.mark.asyncio
async def test_invalid_user_title_is_replaced_and_extra_h1_is_demoted() -> None:
    request = request_with_separate_source(
        prompt="Redesign the attached PDF professionally.",
    )
    router = StaticDraftRouter(
        "# User\n\n## Overview\n\nUseful content.\n\n# Results\n\nMeasured result."
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# Systems Report")
    assert "# User" not in draft.content
    assert "\n## Results\n" in draft.content


@pytest.mark.asyncio
async def test_late_h1_section_is_not_mistaken_for_document_title() -> None:
    request = request_with_separate_source(
        prompt="Redesign the attached PDF professionally.",
    )
    router = StaticDraftRouter(
        "## Executive Summary\n\nUseful content.\n\n# Conclusion\n\nFinal result."
    )
    draft = await compose_artifact_draft(
        request,
        model_router=router,
    )
    assert draft.content.startswith("# Systems Report")
    assert "\n## Conclusion\n" in draft.content


@pytest.mark.asyncio
async def test_attached_pdf_redesign_without_uploaded_source_fails_clearly() -> None:
    request = ArtifactComposeRequest(
        prompt="Redesign the attached PDF professionally.",
        format="pdf",
        source_snapshot={
            "kind": "explicit_prompt",
            "summary": "Redesign instruction only",
            "content": "Redesign the attached PDF professionally.",
            "attachment_names": [],
        },
    )
    router = StaticDraftRouter("# Incorrect Fallback\n\nNo source content.")
    with pytest.raises(
        ArtifactCompositionError,
        match="Attach the PDF or document to this message",
    ):
        await compose_artifact_draft(
            request,
            model_router=router,
        )


@pytest.mark.asyncio
async def test_large_design_revision_preserves_content_without_provider_rewrite() -> None:
    router = SizeThenSuccessRouter()
    current = (
        "# Existing Project\n\n## Chapter\n\n"
        + "Canonical engineering content. " * 900
    )
    request = ArtifactComposeRequest(
        prompt="Redesign this PDF with a new professional BTech architecture.",
        source_snapshot={
            "kind": "artifact_version",
            "summary": "Existing Project",
            "content": current,
        },
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=router,
    )
    assert draft.model == "profile-redesign-v20"
    assert "Canonical engineering content" in draft.content
    assert router.messages == []


@pytest.mark.asyncio
async def test_short_design_only_revision_also_preserves_content_without_rewrite() -> None:
    router = SizeThenSuccessRouter()
    current = (
        "# BTech Project Report\n\n"
        "## Overview\n\nCanonical project content.\n\n"
        "## Conclusion\n\nVerified conclusion."
    )
    request = ArtifactComposeRequest(
        prompt="Isko best professional design me final kar do.",
        source_snapshot={
            "kind": "artifact_version",
            "summary": "BTech Project Report",
            "content": current,
        },
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=router,
    )
    assert draft.model == "profile-redesign-v20"
    assert draft.content == current
    assert router.messages == []


@pytest.mark.asyncio
async def test_design_plus_content_change_still_uses_revision_model() -> None:
    router = StaticDraftRouter(
        "# BTech Project Report\n\n## Overview\n\nCanonical project content.\n\n"
        "## New Risk Section\n\nA verified risk section.\n\n"
        "## Conclusion\n\nVerified conclusion."
    )
    current = (
        "# BTech Project Report\n\n## Overview\n\nCanonical project content.\n\n"
        "## Conclusion\n\nVerified conclusion."
    )
    request = ArtifactComposeRequest(
        prompt="Improve the design and add a new risk section.",
    )
    draft = await compose_artifact_revision(
        request,
        current_content=current,
        instruction=request.prompt,
        model_router=router,
    )
    assert draft.model == "test-model"
    assert "New Risk Section" in draft.content


def test_uploaded_pdf_is_stored_as_durable_source_without_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = ArtifactSourceVault(
        root_directory=tmp_path / "sources",
        retention_hours=1,
    )
    monkeypatch.setattr(
        artifact_source_routes,
        "get_artifact_source_vault",
        lambda: vault,
    )
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "AI-Enabled University Operations System\nBTech project source",
    )
    payload = document.tobytes()
    document.close()

    app = FastAPI()
    app.include_router(
        artifact_source_routes.router,
        prefix="/api/v1",
    )
    response = TestClient(app).post(
        "/api/v1/artifact-sources/upload",
        files={"file": ("project.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    reference = ArtifactSourceReference.model_validate(body["reference"])
    stored = vault.get(reference)
    assert stored.snapshot.kind == "uploaded_file"
    assert "AI-Enabled University Operations" in (stored.snapshot.content or "")


def test_legacy_document_prompt_is_compacted_instead_of_rejected() -> None:
    compacted = compact_analysis_instruction(
        "Redesign the attached PDF professionally. " * 500,
        maximum_characters=4_000,
    )
    assert 0 < len(compacted) <= 4_000


def test_v20_preserves_v19_registry_and_has_no_default_page_cap() -> None:
    assert len(architecture_registry()) == 500
    estimate = estimate_prompt_budget("small prompt", mode="standard")
    assert estimate.within_budget is True
    from core.artifact_settings import artifact_settings

    assert artifact_settings.enforce_single_pdf_page_limit is False
